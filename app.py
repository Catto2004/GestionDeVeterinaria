import sqlite3
from pathlib import Path

from flask import Flask


app = Flask(__name__)
DATABASE = Path(__file__).resolve().parent / "veterinaria.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
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
                age INTEGER,
                weight REAL,
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


@app.route("/")
def index():
    return """
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Gestión de Veterinaria</title>
    </head>
    <body>
        <h1>Gestión de Veterinaria</h1>
        <p>Selecciona una opción:</p>
        <ul>
            <li><a href="/owners">Registrar dueño</a></li>
            <li><a href="/pets">Registrar mascota</a></li>
            <li><a href="/appointments/new">Agendar cita</a></li>
            <li><a href="/appointments">Consultar citas</a></li>
        </ul>
    </body>
    </html>
    """


@app.route("/owners")
@app.route("/pets")
@app.route("/appointments/new")
@app.route("/appointments")
def feature_in_progress():
    return """
    <!doctype html>
    <html lang="es">
    <head><meta charset="utf-8"><title>Módulo en desarrollo</title></head>
    <body>
        <h1>Módulo en desarrollo</h1>
        <p>Esta función todavía no está implementada.</p>
        <a href="/">Volver al inicio</a>
    </body>
    </html>
    """


init_db()


if __name__ == "__main__":
    app.run(debug=True)
