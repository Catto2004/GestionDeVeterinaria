import os
import re
import smtplib
import sqlite3
import ssl
from contextlib import closing
from datetime import date, datetime
from email.message import EmailMessage
from functools import wraps
from io import BytesIO
from math import isfinite
from pathlib import Path
from xml.sax.saxutils import escape

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    session,
    url_for,
)
from markupsafe import Markup
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-before-deploy")
DATABASE = Path(__file__).resolve().parent / "veterinaria.db"
TIME_BLOCKS = (
    "09:00-10:00",
    "10:00-11:00",
    "11:00-12:00",
    "14:00-15:00",
    "15:00-16:00",
    "16:00-17:00",
)

LAYOUT = """
<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }} - Gestión de Veterinaria</title>
</head>
<body>
    <header>
        <h1>Gestión de Veterinaria</h1>
        <nav>
            <a href="{{ url_for('index') }}">Inicio</a> |
            <a href="{{ url_for('owners') }}">Dueños</a> |
            <a href="{{ url_for('pets') }}">Mascotas</a> |
            <a href="{{ url_for('new_appointment') }}">Agendar cita</a> |
            <a href="{{ url_for('schedule') }}">Agenda</a> |
            <a href="{{ url_for('appointments') }}">Consultar citas</a> |
            <a href="{{ url_for('veterinarians') }}">Veterinarios</a> |
            <a href="{{ url_for('prescriptions') }}">Recetas</a> |
            {% if session.get('veterinarian_id') %}
                <a href="{{ url_for('logout') }}">Cerrar sesión ({{ session.get('veterinarian_name') }})</a>
            {% else %}
                <a href="{{ url_for('login') }}">Acceso veterinario</a> |
                <a href="{{ url_for('register_veterinarian_account') }}">Crear cuenta veterinaria</a>
            {% endif %}
        </nav>
    </header>
    <main>
        <h2>{{ title }}</h2>
        {{ content }}
    </main>
</body>
</html>
"""


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with closing(get_db()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS owners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                species TEXT NOT NULL,
                breed TEXT NOT NULL,
                age INTEGER NOT NULL,
                weight REAL NOT NULL,
                description TEXT,
                allergies TEXT NOT NULL DEFAULT '',
                conditions TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (owner_id) REFERENCES owners (id)
            );

            CREATE TABLE IF NOT EXISTS veterinarians (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                specialty TEXT
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                pet_id INTEGER NOT NULL,
                veterinarian_id INTEGER NOT NULL,
                appointment_date TEXT NOT NULL,
                time_block TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Programada',
                FOREIGN KEY (owner_id) REFERENCES owners (id),
                FOREIGN KEY (pet_id) REFERENCES pets (id),
                FOREIGN KEY (veterinarian_id) REFERENCES veterinarians (id)
            );

            CREATE TABLE IF NOT EXISTS veterinarian_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                veterinarian_id INTEGER UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                FOREIGN KEY (veterinarian_id) REFERENCES veterinarians (id)
            );

            CREATE TABLE IF NOT EXISTS medical_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                veterinarian_id INTEGER NOT NULL,
                visit_date TEXT NOT NULL,
                diagnosis TEXT NOT NULL,
                anamnesis TEXT NOT NULL,
                observations TEXT NOT NULL,
                FOREIGN KEY (pet_id) REFERENCES pets (id),
                FOREIGN KEY (veterinarian_id) REFERENCES veterinarians (id)
            );

            CREATE TABLE IF NOT EXISTS prescriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pet_id INTEGER NOT NULL,
                veterinarian_id INTEGER NOT NULL,
                issue_date TEXT NOT NULL,
                medication TEXT NOT NULL,
                dosage TEXT NOT NULL,
                duration TEXT NOT NULL,
                instructions TEXT NOT NULL DEFAULT '',
                FOREIGN KEY (pet_id) REFERENCES pets (id),
                FOREIGN KEY (veterinarian_id) REFERENCES veterinarians (id)
            );
            """
        )
        pet_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(pets)")
        }
        for column in ("allergies", "conditions"):
            if column not in pet_columns:
                connection.execute(
                    f"ALTER TABLE pets ADD COLUMN {column} TEXT NOT NULL DEFAULT ''"
                )
        _migrate_appointment_slots(connection)
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_active_slot
            ON appointments (veterinarian_id, appointment_date, time_block)
            WHERE status = 'Programada'
            """
        )
        connection.commit()


def _migrate_appointment_slots(connection):
    table = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'appointments'"
    ).fetchone()
    if not table or "UNIQUE" not in (table["sql"] or "").upper():
        return

    connection.commit()
    connection.executescript(
        """
        PRAGMA foreign_keys = OFF;
        BEGIN;
        CREATE TABLE appointments_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            pet_id INTEGER NOT NULL,
            veterinarian_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            time_block TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Programada',
            FOREIGN KEY (owner_id) REFERENCES owners (id),
            FOREIGN KEY (pet_id) REFERENCES pets (id),
            FOREIGN KEY (veterinarian_id) REFERENCES veterinarians (id)
        );
        INSERT INTO appointments_new
            (id, owner_id, pet_id, veterinarian_id, appointment_date, time_block, status)
        SELECT id, owner_id, pet_id, veterinarian_id, appointment_date, time_block, status
        FROM appointments;
        DROP TABLE appointments;
        ALTER TABLE appointments_new RENAME TO appointments;
        COMMIT;
        PRAGMA foreign_keys = ON;
        """
    )


def render_page(title, template, **context):
    content = render_template_string(template, **context)
    return render_template_string(LAYOUT, title=title, content=Markup(content))


def veterinarian_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("veterinarian_id"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/")
def index():
    return render_page(
        "Inicio",
        """
        <p>Selecciona una opción para administrar la veterinaria:</p>
        <ul>
            <li><a href="{{ url_for('owners') }}">Registrar dueño</a></li>
            <li><a href="{{ url_for('pets') }}">Registrar mascota</a></li>
            <li><a href="{{ url_for('new_appointment') }}">Agendar cita</a></li>
            <li><a href="{{ url_for('schedule') }}">Ver agenda de veterinarios</a></li>
            <li><a href="{{ url_for('appointments') }}">Consultar citas</a></li>
            <li><a href="{{ url_for('veterinarians') }}">Registrar veterinario</a></li>
            <li><a href="{{ url_for('prescriptions') }}">Consultar recetas</a></li>
            <li><a href="{{ url_for('register_veterinarian_account') }}">Crear cuenta veterinaria</a></li>
        </ul>
        """,
    )


@app.route("/owners", methods=["GET", "POST"])
def owners():
    error = None
    if request.method == "POST":
        document = request.form.get("document", "").strip()
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        email = request.form.get("email", "").strip()
        if not all((document, name, phone, address, email)):
            error = "Todos los campos son obligatorios."
        elif not re.fullmatch(r"[0-9]+", phone):
            error = "El teléfono debe contener solo números."
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            error = "Ingresa un correo electrónico válido."
        else:
            try:
                with closing(get_db()) as connection:
                    connection.execute(
                        """
                        INSERT INTO owners (document, name, phone, address, email)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (document, name, phone, address, email),
                    )
                    connection.commit()
                return redirect(url_for("owners", message="Dueño registrado correctamente."))
            except sqlite3.IntegrityError:
                error = "El documento o correo ya está registrado."

    with closing(get_db()) as connection:
        owner_list = connection.execute(
            "SELECT document, name, phone, address, email FROM owners ORDER BY name"
        ).fetchall()
    return render_page(
        "Registro de dueños",
        """
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <form method="post">
            <label>Documento: <input name="document" required value="{{ request.form.get('document', '') }}"></label><br>
            <label>Nombre completo: <input name="name" required value="{{ request.form.get('name', '') }}"></label><br>
            <label>Teléfono: <input name="phone" inputmode="numeric" required value="{{ request.form.get('phone', '') }}"></label><br>
            <label>Dirección: <input name="address" required value="{{ request.form.get('address', '') }}"></label><br>
            <label>Correo electrónico: <input name="email" type="email" required value="{{ request.form.get('email', '') }}"></label><br>
            <button type="submit">Guardar dueño</button>
        </form>
        <h3>Dueños registrados</h3>
        {% if owners %}
            <ul>{% for owner in owners %}<li>{{ owner.name }} — documento {{ owner.document }}</li>{% endfor %}</ul>
        {% else %}<p>No hay dueños registrados.</p>{% endif %}
        """,
        error=error,
        message=request.args.get("message"),
        owners=owner_list,
        request=request,
    )


@app.route("/pets", methods=["GET", "POST"])
def pets():
    error = None
    search = request.values.get("search", "").strip()
    if request.method == "POST":
        owner_id = request.form.get("owner_id", "")
        name = request.form.get("name", "").strip()
        species = request.form.get("species", "").strip()
        breed = request.form.get("breed", "").strip()
        age_value = request.form.get("age", "").strip()
        weight_value = request.form.get("weight", "").strip()
        description = request.form.get("description", "").strip()
        allergies = request.form.get("allergies", "").strip()
        conditions = request.form.get("conditions", "").strip()
        try:
            age = int(age_value)
            weight = float(weight_value)
        except ValueError:
            age = -1
            weight = -1
        with closing(get_db()) as connection:
            owner = connection.execute(
                "SELECT id FROM owners WHERE id = ?", (owner_id,)
            ).fetchone()
            if not owner:
                error = "Selecciona un dueño registrado."
            elif not all((name, species, breed, age_value, weight_value)):
                error = "Completa todos los campos obligatorios."
            elif age < 0:
                error = "La edad debe ser un número entero igual o mayor que cero."
            elif not isfinite(weight) or weight <= 0:
                error = "El peso debe ser un número válido mayor que cero."
            else:
                connection.execute(
                    """
                    INSERT INTO pets
                        (owner_id, name, species, breed, age, weight, description, allergies, conditions)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        owner["id"],
                        name,
                        species,
                        breed,
                        age,
                        weight,
                        description,
                        allergies,
                        conditions,
                    ),
                )
                connection.commit()
                return redirect(url_for("pets", message="Mascota registrada correctamente."))

    with closing(get_db()) as connection:
        if search:
            owners_list = connection.execute(
                """
                SELECT id, document, name FROM owners
                WHERE document LIKE ? OR name LIKE ? ORDER BY name
                """,
                (f"%{search}%", f"%{search}%"),
            ).fetchall()
        else:
            owners_list = connection.execute(
                "SELECT id, document, name FROM owners ORDER BY name"
            ).fetchall()
        pet_list = connection.execute(
            """
            SELECT pets.id, pets.name, pets.species, pets.breed, owners.name AS owner_name
            FROM pets JOIN owners ON owners.id = pets.owner_id
            ORDER BY pets.name
            """
        ).fetchall()
    return render_page(
        "Ficha de mascotas",
        """
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <form method="get">
            <label>Buscar dueño por documento o nombre:
                <input name="search" value="{{ search }}">
            </label>
            <button type="submit">Buscar</button>
        </form>
        <form method="post">
            <input type="hidden" name="search" value="{{ search }}">
            <label>Dueño:
                <select name="owner_id" required>
                    <option value="">Selecciona un dueño</option>
                    {% for owner in owners %}
                    <option value="{{ owner.id }}" {% if request.form.get('owner_id') == owner.id|string %}selected{% endif %}>
                        {{ owner.name }} — {{ owner.document }}
                    </option>
                    {% endfor %}
                </select>
            </label><br>
            <label>Nombre: <input name="name" required value="{{ request.form.get('name', '') }}"></label><br>
            <label>Especie: <input name="species" required value="{{ request.form.get('species', '') }}"></label><br>
            <label>Raza: <input name="breed" required value="{{ request.form.get('breed', '') }}"></label><br>
            <label>Edad: <input name="age" type="number" min="0" required value="{{ request.form.get('age', '') }}"></label><br>
            <label>Peso (kg): <input name="weight" type="number" min="0.01" step="0.01" required value="{{ request.form.get('weight', '') }}"></label><br>
            <label>Descripción (opcional): <textarea name="description">{{ request.form.get('description', '') }}</textarea></label><br>
            <label>Alergias (opcional): <textarea name="allergies">{{ request.form.get('allergies', '') }}</textarea></label><br>
            <label>Condiciones médicas (opcional): <textarea name="conditions">{{ request.form.get('conditions', '') }}</textarea></label><br>
            <button type="submit">Guardar mascota</button>
        </form>
        {% if not owners %}<p>No hay dueños que coincidan. Registra un dueño o cambia la búsqueda.</p>{% endif %}
        <h3>Mascotas registradas</h3>
        {% if pets %}
            <ul>{% for pet in pets %}<li>{{ pet.name }} ({{ pet.species }}, {{ pet.breed }}) — dueño: {{ pet.owner_name }}{% if session.get('veterinarian_id') %} — <a href="{{ url_for('medical_records', pet_id=pet.id) }}">Historia clínica</a> — <a href="{{ url_for('new_prescription') }}">Nueva receta</a>{% endif %}</li>{% endfor %}</ul>
        {% else %}<p>No hay mascotas registradas.</p>{% endif %}
        """,
        error=error,
        message=request.args.get("message"),
        owners=owners_list,
        pets=pet_list,
        request=request,
        search=search,
    )


@app.route("/veterinarians", methods=["GET", "POST"])
def veterinarians():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        specialty = request.form.get("specialty", "").strip()
        if not name:
            error = "El nombre del veterinario es obligatorio."
        else:
            with closing(get_db()) as connection:
                connection.execute(
                    "INSERT INTO veterinarians (name, specialty) VALUES (?, ?)",
                    (name, specialty),
                )
                connection.commit()
            return redirect(
                url_for("veterinarians", message="Veterinario registrado correctamente.")
            )
    with closing(get_db()) as connection:
        vet_list = connection.execute(
            "SELECT name, specialty FROM veterinarians ORDER BY name"
        ).fetchall()
    return render_page(
        "Registro de veterinarios",
        """
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <form method="post">
            <label>Nombre: <input name="name" required value="{{ request.form.get('name', '') }}"></label><br>
            <label>Especialidad (opcional): <input name="specialty" value="{{ request.form.get('specialty', '') }}"></label><br>
            <button type="submit">Guardar veterinario</button>
        </form>
        <h3>Veterinarios registrados</h3>
        {% if veterinarians %}
            <ul>{% for vet in veterinarians %}<li>{{ vet.name }}{% if vet.specialty %} — {{ vet.specialty }}{% endif %}</li>{% endfor %}</ul>
        {% else %}<p>No hay veterinarios registrados.</p>{% endif %}
        """,
        error=error,
        message=request.args.get("message"),
        veterinarians=vet_list,
        request=request,
    )


@app.route("/vet/register", methods=["GET", "POST"])
def register_veterinarian_account():
    error = None
    with closing(get_db()) as connection:
        available_vets = connection.execute(
            """
            SELECT veterinarians.id, veterinarians.name
            FROM veterinarians
            LEFT JOIN veterinarian_accounts
                ON veterinarian_accounts.veterinarian_id = veterinarians.id
            WHERE veterinarian_accounts.id IS NULL
            ORDER BY veterinarians.name
            """
        ).fetchall()
        if request.method == "POST":
            veterinarian_id = request.form.get("veterinarian_id", "")
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            veterinarian = connection.execute(
                "SELECT id, name FROM veterinarians WHERE id = ?", (veterinarian_id,)
            ).fetchone()
            if not veterinarian or not any(
                str(vet["id"]) == veterinarian_id for vet in available_vets
            ):
                error = "Selecciona un veterinario disponible."
            elif not username or len(password) < 8:
                error = "El usuario es obligatorio y la contraseña debe tener 8 caracteres o más."
            else:
                try:
                    connection.execute(
                        """
                        INSERT INTO veterinarian_accounts
                            (veterinarian_id, username, password_hash)
                        VALUES (?, ?, ?)
                        """,
                        (
                            veterinarian["id"],
                            username,
                            generate_password_hash(password),
                        ),
                    )
                    connection.commit()
                    return redirect(
                        url_for("login", message="Cuenta creada. Ya puedes iniciar sesión.")
                    )
                except sqlite3.IntegrityError:
                    error = "Ese nombre de usuario ya está registrado."

    return render_page(
        "Crear cuenta veterinaria",
        """
        <p>Selecciona un veterinario registrado para crear su acceso.</p>
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <form method="post">
            <label>Veterinario:
                <select name="veterinarian_id" required>
                    <option value="">Selecciona un veterinario</option>
                    {% for vet in veterinarians %}<option value="{{ vet.id }}">{{ vet.name }}</option>{% endfor %}
                </select>
            </label><br>
            <label>Usuario: <input name="username" required></label><br>
            <label>Contraseña (mínimo 8 caracteres): <input name="password" type="password" minlength="8" required></label><br>
            <button type="submit" {% if not veterinarians %}disabled{% endif %}>Crear cuenta</button>
        </form>
        {% if not veterinarians %}<p>No hay veterinarios disponibles. Registra primero un veterinario o revisa si ya tiene cuenta.</p>{% endif %}
        """,
        error=error,
        veterinarians=available_vets,
    )


@app.route("/vet/login", methods=["GET", "POST"])
def login():
    error = None
    next_path = request.args.get("next", "")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        with closing(get_db()) as connection:
            account = connection.execute(
                """
                SELECT veterinarian_accounts.username,
                       veterinarian_accounts.password_hash,
                       veterinarians.id AS veterinarian_id,
                       veterinarians.name AS veterinarian_name
                FROM veterinarian_accounts
                JOIN veterinarians
                    ON veterinarians.id = veterinarian_accounts.veterinarian_id
                WHERE veterinarian_accounts.username = ?
                """,
                (username,),
            ).fetchone()
        if account and check_password_hash(account["password_hash"], password):
            session.clear()
            session["veterinarian_id"] = account["veterinarian_id"]
            session["veterinarian_name"] = account["veterinarian_name"]
            session["username"] = account["username"]
            next_path = request.form.get("next", "")
            if not next_path.startswith("/") or next_path.startswith("//"):
                next_path = url_for("schedule")
            return redirect(next_path)
        error = "Usuario o contraseña incorrectos."
    return render_page(
        "Acceso veterinario",
        """
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <form method="post">
            <input type="hidden" name="next" value="{{ next_path }}">
            <label>Usuario: <input name="username" required></label><br>
            <label>Contraseña: <input name="password" type="password" required></label><br>
            <button type="submit">Iniciar sesión</button>
        </form>
        <p><a href="{{ url_for('register_veterinarian_account') }}">Crear cuenta veterinaria</a></p>
        """,
        error=error,
        message=request.args.get("message"),
        next_path=next_path,
    )


@app.route("/vet/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


def slot_is_in_the_past(appointment_date, time_block, now=None):
    now = now or datetime.now()
    if appointment_date < now.date():
        return True
    if appointment_date > now.date():
        return False
    try:
        start_time = datetime.strptime(time_block.split("-", 1)[0], "%H:%M").time()
    except ValueError:
        return True
    return start_time <= now.time()


def send_appointment_email(details):
    host = os.environ.get("SMTP_HOST", "").strip()
    sender = os.environ.get("SMTP_FROM", "").strip()
    if not host or not sender:
        return False, "Correo no configurado: define SMTP_HOST y SMTP_FROM."
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
        message = EmailMessage()
        message["Subject"] = "Confirmación de cita veterinaria"
        message["From"] = sender
        message["To"] = details["email"]
        message.set_content(
            f"""Hola {details['owner_name']},

Tu cita veterinaria ha sido programada.

Mascota: {details['pet_name']}
Fecha: {details['appointment_date']}
Hora: {details['time_block']}
Veterinario: {details['veterinarian_name']}

Recuerda llegar 10 minutos antes de la cita.
"""
        )
        smtp_ssl = os.environ.get("SMTP_USE_SSL", "").lower() == "true"
        smtp_class = smtplib.SMTP_SSL if smtp_ssl else smtplib.SMTP
        with smtp_class(host, port, timeout=10) as server:
            if not smtp_ssl and os.environ.get("SMTP_USE_TLS", "true").lower() == "true":
                server.starttls(context=ssl.create_default_context())
            username = os.environ.get("SMTP_USER", "")
            password = os.environ.get("SMTP_PASSWORD", "")
            if username:
                server.login(username, password)
            server.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError):
        app.logger.exception("No se pudo enviar la notificación de cita.")
        return False, "No se pudo enviar el correo de confirmación."
    return True, "Correo de confirmación enviado."


@app.route("/appointments/new", methods=["GET", "POST"])
def new_appointment():
    error = None
    if request.method == "POST":
        pet_id = request.form.get("pet_id", "")
        veterinarian_id = request.form.get("veterinarian_id", "")
        appointment_date = request.form.get("appointment_date", "")
        time_block = request.form.get("time_block", "")
        try:
            selected_date = date.fromisoformat(appointment_date)
        except ValueError:
            selected_date = None
        with closing(get_db()) as connection:
            pet = connection.execute(
                "SELECT id, owner_id FROM pets WHERE id = ?", (pet_id,)
            ).fetchone()
            vet = connection.execute(
                "SELECT id FROM veterinarians WHERE id = ?", (veterinarian_id,)
            ).fetchone()
            if not pet:
                error = "Selecciona una mascota registrada."
            elif not vet:
                error = "Selecciona un veterinario registrado."
            elif selected_date is None:
                error = "Selecciona una fecha válida."
            elif time_block not in TIME_BLOCKS:
                error = "Selecciona un bloque de horario válido."
            elif slot_is_in_the_past(selected_date, time_block):
                error = "No se puede agendar una fecha u hora que ya pasó."
            else:
                duplicate = connection.execute(
                    """
                    SELECT 1 FROM appointments
                    WHERE veterinarian_id = ? AND appointment_date = ? AND time_block = ?
                        AND status = 'Programada'
                    """,
                    (vet["id"], appointment_date, time_block),
                ).fetchone()
                if duplicate:
                    error = "Ese veterinario ya tiene una cita en ese horario."
                else:
                    try:
                        cursor = connection.execute(
                            """
                            INSERT INTO appointments
                                (owner_id, pet_id, veterinarian_id, appointment_date, time_block)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (pet["owner_id"], pet["id"], vet["id"], appointment_date, time_block),
                        )
                        details = connection.execute(
                            """
                            SELECT owners.name AS owner_name, owners.email, pets.name AS pet_name,
                                   veterinarians.name AS veterinarian_name,
                                   appointments.appointment_date, appointments.time_block
                            FROM appointments
                            JOIN owners ON owners.id = appointments.owner_id
                            JOIN pets ON pets.id = appointments.pet_id
                            JOIN veterinarians ON veterinarians.id = appointments.veterinarian_id
                            WHERE appointments.id = ?
                            """,
                            (cursor.lastrowid,),
                        ).fetchone()
                        connection.commit()
                        email_sent, email_message = send_appointment_email(details)
                        return redirect(
                            url_for(
                                "schedule",
                                date=appointment_date,
                                message="Cita programada correctamente.",
                                email_status="sent" if email_sent else "failed",
                                email_message=email_message,
                            )
                        )
                    except sqlite3.IntegrityError:
                        error = "Ese veterinario ya tiene una cita en ese horario."

    with closing(get_db()) as connection:
        pet_list = connection.execute(
            """
            SELECT pets.id, pets.name, owners.name AS owner_name
            FROM pets JOIN owners ON owners.id = pets.owner_id ORDER BY owners.name, pets.name
            """
        ).fetchall()
        vet_list = connection.execute(
            "SELECT id, name, specialty FROM veterinarians ORDER BY name"
        ).fetchall()
    return render_page(
        "Agendar cita",
        """
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        {% if not pets %}<p>Primero registra un dueño y una mascota.</p>{% endif %}
        {% if not veterinarians %}<p>Primero registra un veterinario.</p>{% endif %}
        <form method="post">
            <label>Dueño / Mascota:
                <select name="pet_id" required>
                    <option value="">Selecciona una mascota</option>
                    {% for pet in pets %}
                    <option value="{{ pet.id }}" {% if request.form.get('pet_id') == pet.id|string %}selected{% endif %}>
                        {{ pet.owner_name }} — {{ pet.name }}
                    </option>
                    {% endfor %}
                </select>
            </label><br>
            <label>Veterinario:
                <select name="veterinarian_id" required>
                    <option value="">Selecciona un veterinario</option>
                    {% for vet in veterinarians %}
                    <option value="{{ vet.id }}" {% if request.form.get('veterinarian_id') == vet.id|string %}selected{% endif %}>
                        {{ vet.name }}{% if vet.specialty %} — {{ vet.specialty }}{% endif %}
                    </option>
                    {% endfor %}
                </select>
            </label><br>
            <label>Fecha: <input type="date" name="appointment_date" min="{{ today }}" required value="{{ request.form.get('appointment_date', '') }}"></label><br>
            <label>Bloque:
                <select name="time_block" required>
                    <option value="">Selecciona un horario</option>
                    {% for block in blocks %}
                    <option value="{{ block }}" data-start="{{ block[:5] }}" {% if request.form.get('time_block') == block %}selected{% endif %}>{{ block }}</option>
                    {% endfor %}
                </select>
            </label><br>
            <button type="submit" {% if not pets or not veterinarians %}disabled{% endif %}>Guardar cita</button>
        </form>
        <p><a href="{{ url_for('schedule') }}">Ver la agenda completa</a></p>
        <script>
        const appointmentDate = document.querySelector('[name="appointment_date"]');
        const timeOptions = document.querySelector('[name="time_block"]').options;
        function disablePastBlocks() {
            const now = new Date();
            const selectedDate = appointmentDate.value;
            const today = [
                now.getFullYear(),
                String(now.getMonth() + 1).padStart(2, '0'),
                String(now.getDate()).padStart(2, '0')
            ].join('-');
            for (const option of timeOptions) {
                if (!option.dataset.start) continue;
                option.disabled = selectedDate < today ||
                    (selectedDate === today && option.dataset.start <=
                        `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`);
            }
        }
        appointmentDate.addEventListener('change', disablePastBlocks);
        disablePastBlocks();
        </script>
        """,
        error=error,
        message=request.args.get("message"),
        pets=pet_list,
        veterinarians=vet_list,
        today=date.today().isoformat(),
        blocks=TIME_BLOCKS,
        request=request,
    )


def get_schedule_slots(selected_date):
    with closing(get_db()) as connection:
        veterinarians = connection.execute(
            "SELECT id, name FROM veterinarians ORDER BY name"
        ).fetchall()
        occupied = connection.execute(
            """
            SELECT id, veterinarian_id, time_block
            FROM appointments
            WHERE appointment_date = ? AND status = 'Programada'
            """,
            (selected_date.isoformat(),),
        ).fetchall()

    appointments_by_slot = {
        (appointment["veterinarian_id"], appointment["time_block"]): appointment["id"]
        for appointment in occupied
    }
    now = datetime.now()
    slots = []
    for veterinarian in veterinarians:
        for block in TIME_BLOCKS:
            appointment_id = appointments_by_slot.get((veterinarian["id"], block))
            if appointment_id:
                status = "occupied"
            elif slot_is_in_the_past(selected_date, block, now):
                status = "past"
            else:
                status = "free"
            slots.append(
                {
                    "veterinarian_id": veterinarian["id"],
                    "veterinarian_name": veterinarian["name"],
                    "time_block": block,
                    "status": status,
                    "appointment_id": appointment_id,
                }
            )
    return slots


@app.route("/schedule")
def schedule():
    selected_date_value = request.args.get("date", date.today().isoformat())
    try:
        selected_date = date.fromisoformat(selected_date_value)
    except ValueError:
        abort(400, description="La fecha de agenda no es válida.")
    slots = get_schedule_slots(selected_date)
    return render_page(
        "Agenda de veterinarios",
        """
        <style>
            table { border-collapse: collapse; }
            th, td { border: 1px solid #555; padding: 8px; text-align: center; }
            .free { background: #b7e4c7; }
            .occupied { background: #f4a6a6; }
            .past { background: #ddd; color: #555; }
        </style>
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if email_status == 'failed' %}<p role="alert">{{ email_message }} La cita quedó guardada.</p>{% elif email_status == 'sent' %}<p>{{ email_message }}</p>{% endif %}
        <form method="get">
            <label>Fecha: <input type="date" name="date" min="{{ today }}" value="{{ selected_date }}" required></label>
            <button type="submit">Ver agenda</button>
        </form>
        <p>Verde = libre; rojo = ocupado; gris = horario pasado.</p>
        <table id="schedule-grid" data-date="{{ selected_date }}">
            <thead>
                <tr><th>Veterinario</th>{% for block in blocks %}<th>{{ block }}</th>{% endfor %}</tr>
            </thead>
            <tbody>
                {% for vet in veterinarians %}
                <tr>
                    <th>{{ vet.name }}</th>
                    {% for block in blocks %}
                    {% set slot = slots_by_key[(vet.id, block)] %}
                    <td id="slot-{{ vet.id }}-{{ loop.index0 }}" class="{{ slot.status }}"
                        data-vet-id="{{ vet.id }}" data-block="{{ block }}">
                        <span class="slot-status">{% if slot.status == 'free' %}Libre{% elif slot.status == 'occupied' %}Ocupado{% else %}Pasado{% endif %}</span>
                        <form class="cancel-form" method="post"
                              action="{% if slot.appointment_id %}{{ url_for('cancel_appointment', appointment_id=slot.appointment_id) }}{% else %}#{% endif %}"
                              {% if slot.status != 'occupied' %}hidden{% endif %}>
                            <input type="hidden" name="date" value="{{ selected_date }}">
                            <button type="submit">Cancelar</button>
                        </form>
                    </td>
                    {% endfor %}
                </tr>
                {% endfor %}
                {% if not veterinarians %}<tr><td colspan="{{ blocks|length + 1 }}">No hay veterinarios registrados.</td></tr>{% endif %}
            </tbody>
        </table>
        <p><a href="{{ url_for('new_appointment') }}">Agendar una cita</a></p>
        <script>
        const grid = document.getElementById('schedule-grid');
        async function refreshSchedule() {
            const response = await fetch('{{ url_for("schedule_status") }}?date=' +
                encodeURIComponent(grid.dataset.date));
            if (!response.ok) return;
            const data = await response.json();
            for (const slot of data.slots) {
                const cell = [...grid.querySelectorAll('td[data-vet-id]')].find(
                    item => item.dataset.vetId === String(slot.veterinarian_id) &&
                        item.dataset.block === slot.time_block
                );
                if (!cell) continue;
                cell.classList.remove('free', 'occupied', 'past');
                cell.classList.add(slot.status);
                cell.querySelector('.slot-status').textContent =
                    slot.status === 'free' ? 'Libre' :
                    slot.status === 'occupied' ? 'Ocupado' : 'Pasado';
                const form = cell.querySelector('.cancel-form');
                form.hidden = slot.status !== 'occupied';
                if (slot.appointment_id) {
                    form.action = `/appointments/${slot.appointment_id}/cancel`;
                }
            }
        }
        setInterval(refreshSchedule, 5000);
        </script>
        """,
        message=request.args.get("message"),
        email_status=request.args.get("email_status"),
        email_message=request.args.get("email_message"),
        today=date.today().isoformat(),
        selected_date=selected_date.isoformat(),
        blocks=TIME_BLOCKS,
        veterinarians=_get_veterinarians(),
        slots_by_key={
            (slot["veterinarian_id"], slot["time_block"]): slot for slot in slots
        },
    )


def _get_veterinarians():
    with closing(get_db()) as connection:
        return connection.execute(
            "SELECT id, name FROM veterinarians ORDER BY name"
        ).fetchall()


@app.route("/schedule/status")
def schedule_status():
    try:
        selected_date = date.fromisoformat(request.args.get("date", ""))
    except ValueError:
        abort(400, description="La fecha de agenda no es válida.")
    return jsonify({"slots": get_schedule_slots(selected_date)})


@app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
def cancel_appointment(appointment_id):
    selected_date = request.form.get("date", date.today().isoformat())
    with closing(get_db()) as connection:
        cursor = connection.execute(
            "UPDATE appointments SET status = 'Cancelada' WHERE id = ? AND status = 'Programada'",
            (appointment_id,),
        )
        connection.commit()
    message = (
        "Cita cancelada."
        if cursor.rowcount
        else "La cita no existe o ya fue cancelada."
    )
    return redirect(url_for("schedule", date=selected_date, message=message))


@app.route("/appointments", methods=["GET"])
def appointments():
    document = request.args.get("document", "").strip()
    owner = None
    appointment_list = []
    error = None
    if document:
        with closing(get_db()) as connection:
            owner = connection.execute(
                "SELECT id, name FROM owners WHERE document = ?", (document,)
            ).fetchone()
            if owner:
                appointment_list = connection.execute(
                    """
                    SELECT appointments.appointment_date, appointments.time_block,
                           pets.name AS pet_name, veterinarians.name AS veterinarian_name
                    FROM appointments
                    JOIN pets ON pets.id = appointments.pet_id
                    JOIN veterinarians ON veterinarians.id = appointments.veterinarian_id
                    WHERE appointments.owner_id = ? AND appointments.status = 'Programada'
                    ORDER BY appointments.appointment_date, appointments.time_block
                    """,
                    (owner["id"],),
                ).fetchall()
            else:
                error = "No se encontró un dueño con ese documento."
    return render_page(
        "Consultar citas",
        """
        <form method="get">
            <label>Documento del dueño:
                <input name="document" required value="{{ document }}">
            </label>
            <button type="submit">Consultar</button>
        </form>
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        {% if owner %}
            <h3>Citas de {{ owner.name }}</h3>
            {% if appointments %}
                <ul>
                    {% for appointment in appointments %}
                    <li>Fecha: {{ appointment.appointment_date }} | Hora: {{ appointment.time_block }} |
                        Mascota: {{ appointment.pet_name }} | Veterinario: {{ appointment.veterinarian_name }}</li>
                    {% endfor %}
                </ul>
            {% else %}<p>No registra citas programadas</p>{% endif %}
        {% endif %}
        """,
        document=document,
        error=error,
        owner=owner,
        appointments=appointment_list,
    )


@app.route("/pets/<int:pet_id>/medical-records", methods=["GET", "POST"])
@veterinarian_required
def medical_records(pet_id):
    error = None
    with closing(get_db()) as connection:
        pet = connection.execute(
            "SELECT id, name, allergies, conditions FROM pets WHERE id = ?",
            (pet_id,),
        ).fetchone()
        if not pet:
            abort(404)
        if request.method == "POST":
            visit_date = request.form.get("visit_date", "")
            diagnosis = request.form.get("diagnosis", "").strip()
            anamnesis = request.form.get("anamnesis", "").strip()
            observations = request.form.get("observations", "").strip()
            try:
                date.fromisoformat(visit_date)
            except ValueError:
                error = "Ingresa una fecha de atención válida."
            if not all((diagnosis, anamnesis, observations)):
                error = "Completa diagnóstico, anamnesis y observaciones."
            if not error:
                connection.execute(
                    """
                    INSERT INTO medical_records
                        (pet_id, veterinarian_id, visit_date, diagnosis, anamnesis, observations)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pet_id,
                        session["veterinarian_id"],
                        visit_date,
                        diagnosis,
                        anamnesis,
                        observations,
                    ),
                )
                connection.commit()
                return redirect(
                    url_for(
                        "medical_records",
                        pet_id=pet_id,
                        message="Nota clínica registrada.",
                    )
                )
        records = connection.execute(
            """
            SELECT medical_records.*, veterinarians.name AS veterinarian_name
            FROM medical_records
            JOIN veterinarians ON veterinarians.id = medical_records.veterinarian_id
            WHERE medical_records.pet_id = ?
            ORDER BY medical_records.visit_date DESC, medical_records.id DESC
            """,
            (pet_id,),
        ).fetchall()
    return render_page(
        f"Historia clínica de {pet['name']}",
        """
        {% if pet.allergies or pet.conditions %}
        <aside role="alert" style="border: 2px solid red; color: red; padding: 10px;">
            <strong>ALERTA MÉDICA</strong>
            {% if pet.allergies %}<p>Alergias: {{ pet.allergies }}</p>{% endif %}
            {% if pet.conditions %}<p>Condiciones: {{ pet.conditions }}</p>{% endif %}
        </aside>
        {% endif %}
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <h3>Agregar nota clínica</h3>
        <form method="post">
            <label>Fecha de atención: <input type="date" name="visit_date" required value="{{ request.form.get('visit_date', today) }}"></label><br>
            <label>Diagnóstico: <textarea name="diagnosis" required>{{ request.form.get('diagnosis', '') }}</textarea></label><br>
            <label>Anamnesis: <textarea name="anamnesis" required>{{ request.form.get('anamnesis', '') }}</textarea></label><br>
            <label>Observaciones: <textarea name="observations" required>{{ request.form.get('observations', '') }}</textarea></label><br>
            <button type="submit">Guardar nota</button>
        </form>
        <h3>Notas anteriores</h3>
        {% if records %}
            <ul>
            {% for record in records %}
                <li>
                    {{ record.visit_date }} — {{ record.veterinarian_name }}:
                    Diagnóstico: {{ record.diagnosis }};
                    Anamnesis: {{ record.anamnesis }};
                    Observaciones: {{ record.observations }}.
                    <a href="{{ url_for('edit_medical_record', pet_id=pet.id, record_id=record.id) }}">Editar</a>
                </li>
            {% endfor %}
            </ul>
        {% else %}<p>La mascota aún no tiene notas clínicas.</p>{% endif %}
        """,
        pet=pet,
        records=records,
        error=error,
        message=request.args.get("message"),
        today=date.today().isoformat(),
        request=request,
    )


@app.route(
    "/pets/<int:pet_id>/medical-records/<int:record_id>/edit",
    methods=["GET", "POST"],
)
@veterinarian_required
def edit_medical_record(pet_id, record_id):
    with closing(get_db()) as connection:
        record = connection.execute(
            """
            SELECT * FROM medical_records
            WHERE id = ? AND pet_id = ?
            """,
            (record_id, pet_id),
        ).fetchone()
        if not record:
            abort(404)
        if request.method == "POST":
            visit_date = request.form.get("visit_date", "")
            diagnosis = request.form.get("diagnosis", "").strip()
            anamnesis = request.form.get("anamnesis", "").strip()
            observations = request.form.get("observations", "").strip()
            try:
                date.fromisoformat(visit_date)
            except ValueError:
                abort(400, description="La fecha de atención no es válida.")
            if not all((diagnosis, anamnesis, observations)):
                abort(400, description="Completa todos los campos clínicos.")
            connection.execute(
                """
                UPDATE medical_records
                SET visit_date = ?, diagnosis = ?, anamnesis = ?, observations = ?
                WHERE id = ? AND pet_id = ?
                """,
                (visit_date, diagnosis, anamnesis, observations, record_id, pet_id),
            )
            connection.commit()
            return redirect(url_for("medical_records", pet_id=pet_id))
        pet = connection.execute(
            "SELECT id, name FROM pets WHERE id = ?", (pet_id,)
        ).fetchone()
    return render_page(
        f"Editar historia clínica de {pet['name']}",
        """
        <form method="post">
            <label>Fecha de atención: <input type="date" name="visit_date" required value="{{ record.visit_date }}"></label><br>
            <label>Diagnóstico: <textarea name="diagnosis" required>{{ record.diagnosis }}</textarea></label><br>
            <label>Anamnesis: <textarea name="anamnesis" required>{{ record.anamnesis }}</textarea></label><br>
            <label>Observaciones: <textarea name="observations" required>{{ record.observations }}</textarea></label><br>
            <button type="submit">Guardar cambios</button>
        </form>
        """,
        pet=pet,
        record=record,
    )


@app.route("/prescriptions/new", methods=["GET", "POST"])
@veterinarian_required
def new_prescription():
    error = None
    if request.method == "POST":
        pet_id = request.form.get("pet_id", "")
        medication = request.form.get("medication", "").strip()
        dosage = request.form.get("dosage", "").strip()
        duration = request.form.get("duration", "").strip()
        instructions = request.form.get("instructions", "").strip()
        with closing(get_db()) as connection:
            pet = connection.execute(
                "SELECT id FROM pets WHERE id = ?", (pet_id,)
            ).fetchone()
            if not pet:
                error = "Selecciona una mascota registrada."
            elif not all((medication, dosage, duration)):
                error = "Medicamento, dosis y duración son obligatorios."
            else:
                connection.execute(
                    """
                    INSERT INTO prescriptions
                        (pet_id, veterinarian_id, issue_date, medication, dosage, duration, instructions)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        pet["id"],
                        session["veterinarian_id"],
                        date.today().isoformat(),
                        medication,
                        dosage,
                        duration,
                        instructions,
                    ),
                )
                connection.commit()
                return redirect(
                    url_for("prescriptions", message="Receta emitida correctamente.")
                )

    with closing(get_db()) as connection:
        pet_list = connection.execute(
            """
            SELECT pets.id, pets.name, owners.name AS owner_name
            FROM pets JOIN owners ON owners.id = pets.owner_id
            ORDER BY owners.name, pets.name
            """
        ).fetchall()
    return render_page(
        "Emitir receta médica",
        """
        {% if error %}<p role="alert">{{ error }}</p>{% endif %}
        <form method="post">
            <label>Mascota:
                <select name="pet_id" required>
                    <option value="">Selecciona una mascota</option>
                    {% for pet in pets %}<option value="{{ pet.id }}">{{ pet.owner_name }} — {{ pet.name }}</option>{% endfor %}
                </select>
            </label><br>
            <label>Medicamento: <input name="medication" required></label><br>
            <label>Dosis: <input name="dosage" required></label><br>
            <label>Duración: <input name="duration" required></label><br>
            <label>Instrucciones adicionales: <textarea name="instructions"></textarea></label><br>
            <button type="submit" {% if not pets %}disabled{% endif %}>Emitir receta</button>
        </form>
        {% if not pets %}<p>No hay mascotas registradas.</p>{% endif %}
        """,
        error=error,
        pets=pet_list,
    )


@app.route("/prescriptions")
def prescriptions():
    with closing(get_db()) as connection:
        prescription_list = connection.execute(
            """
            SELECT prescriptions.id, prescriptions.issue_date, prescriptions.medication,
                   prescriptions.dosage, prescriptions.duration, pets.name AS pet_name,
                   owners.name AS owner_name, veterinarians.name AS veterinarian_name
            FROM prescriptions
            JOIN pets ON pets.id = prescriptions.pet_id
            JOIN owners ON owners.id = pets.owner_id
            JOIN veterinarians ON veterinarians.id = prescriptions.veterinarian_id
            ORDER BY prescriptions.issue_date DESC, prescriptions.id DESC
            """
        ).fetchall()
    return render_page(
        "Recetas para recepción",
        """
        {% if message %}<p>{{ message }}</p>{% endif %}
        {% if session.get('veterinarian_id') %}<p><a href="{{ url_for('new_prescription') }}">Emitir una receta</a></p>{% endif %}
        {% if prescriptions %}
            <ul>
            {% for prescription in prescriptions %}
                <li>
                    {{ prescription.issue_date }} — Mascota: {{ prescription.pet_name }},
                    dueño: {{ prescription.owner_name }}, medicamento:
                    {{ prescription.medication }}, dosis: {{ prescription.dosage }},
                    duración: {{ prescription.duration }}, veterinario:
                    {{ prescription.veterinarian_name }}.
                    <a href="{{ url_for('prescription_pdf', prescription_id=prescription.id) }}">Descargar PDF</a>
                </li>
            {% endfor %}
            </ul>
        {% else %}<p>No hay recetas emitidas.</p>{% endif %}
        """,
        message=request.args.get("message"),
        prescriptions=prescription_list,
    )


@app.route("/prescriptions/<int:prescription_id>/pdf")
def prescription_pdf(prescription_id):
    with closing(get_db()) as connection:
        prescription = connection.execute(
            """
            SELECT prescriptions.*, pets.name AS pet_name, owners.name AS owner_name,
                   veterinarians.name AS veterinarian_name
            FROM prescriptions
            JOIN pets ON pets.id = prescriptions.pet_id
            JOIN owners ON owners.id = pets.owner_id
            JOIN veterinarians ON veterinarians.id = prescriptions.veterinarian_id
            WHERE prescriptions.id = ?
            """,
            (prescription_id,),
        ).fetchone()
    if not prescription:
        abort(404)

    def pdf_text(value):
        return escape(str(value)).replace("\n", "<br/>")

    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=letter, title="Receta veterinaria")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("VETERINARIA", styles["Title"]),
        Paragraph("Receta médica", styles["Heading2"]),
        Spacer(1, 16),
        Paragraph(f"Fecha: {pdf_text(prescription['issue_date'])}", styles["Normal"]),
        Paragraph(f"Cliente: {pdf_text(prescription['owner_name'])}", styles["Normal"]),
        Paragraph(f"Mascota: {pdf_text(prescription['pet_name'])}", styles["Normal"]),
        Paragraph(f"Medicamento: {pdf_text(prescription['medication'])}", styles["Normal"]),
        Paragraph(f"Dosis: {pdf_text(prescription['dosage'])}", styles["Normal"]),
        Paragraph(f"Duración: {pdf_text(prescription['duration'])}", styles["Normal"]),
        Paragraph(
            f"Instrucciones: {pdf_text(prescription['instructions'] or 'Ninguna')}",
            styles["Normal"],
        ),
        Spacer(1, 48),
        Paragraph("Firma del veterinario:", styles["Normal"]),
        Spacer(1, 28),
        Paragraph("________________________________________", styles["Normal"]),
        Paragraph(pdf_text(prescription["veterinarian_name"]), styles["Normal"]),
    ]
    document.build(story)
    output.seek(0)
    return send_file(
        output,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"receta-{prescription_id}.pdf",
    )


init_db()


if __name__ == "__main__":
    app.run(debug=True)
