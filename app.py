import re
import sqlite3
from contextlib import closing
from datetime import date
from math import isfinite
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for
from markupsafe import Markup


app = Flask(__name__)
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
            <a href="{{ url_for('appointments') }}">Consultar citas</a> |
            <a href="{{ url_for('veterinarians') }}">Veterinarios</a>
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
                FOREIGN KEY (veterinarian_id) REFERENCES veterinarians (id),
                UNIQUE (veterinarian_id, appointment_date, time_block)
            );
            """
        )
        connection.commit()


def render_page(title, template, **context):
    content = render_template_string(template, **context)
    return render_template_string(LAYOUT, title=title, content=Markup(content))


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
            <li><a href="{{ url_for('appointments') }}">Consultar citas</a></li>
            <li><a href="{{ url_for('veterinarians') }}">Registrar veterinario</a></li>
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
                    INSERT INTO pets (owner_id, name, species, breed, age, weight, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (owner["id"], name, species, breed, age, weight, description),
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
            SELECT pets.name, pets.species, pets.breed, owners.name AS owner_name
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
            <button type="submit">Guardar mascota</button>
        </form>
        {% if not owners %}<p>No hay dueños que coincidan. Registra un dueño o cambia la búsqueda.</p>{% endif %}
        <h3>Mascotas registradas</h3>
        {% if pets %}
            <ul>{% for pet in pets %}<li>{{ pet.name }} ({{ pet.species }}, {{ pet.breed }}) — dueño: {{ pet.owner_name }}</li>{% endfor %}</ul>
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
            elif selected_date is None or selected_date < date.today():
                error = "Selecciona una fecha válida a partir de hoy."
            elif time_block not in TIME_BLOCKS:
                error = "Selecciona un bloque de horario válido."
            else:
                duplicate = connection.execute(
                    """
                    SELECT 1 FROM appointments
                    WHERE veterinarian_id = ? AND appointment_date = ? AND time_block = ?
                    """,
                    (vet["id"], appointment_date, time_block),
                ).fetchone()
                if duplicate:
                    error = "Ese veterinario ya tiene una cita en ese horario."
                else:
                    try:
                        connection.execute(
                            """
                            INSERT INTO appointments
                                (owner_id, pet_id, veterinarian_id, appointment_date, time_block)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (pet["owner_id"], pet["id"], vet["id"], appointment_date, time_block),
                        )
                        connection.commit()
                        return redirect(
                            url_for("new_appointment", message="Cita programada correctamente.")
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
                    <option value="{{ block }}" {% if request.form.get('time_block') == block %}selected{% endif %}>{{ block }}</option>
                    {% endfor %}
                </select>
            </label><br>
            <button type="submit" {% if not pets or not veterinarians %}disabled{% endif %}>Guardar cita</button>
        </form>
        """,
        error=error,
        message=request.args.get("message"),
        pets=pet_list,
        veterinarians=vet_list,
        today=date.today().isoformat(),
        blocks=TIME_BLOCKS,
        request=request,
    )


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


init_db()


if __name__ == "__main__":
    app.run(debug=True)
