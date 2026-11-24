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
    return "Gestion de Veterinaria"


init_db()


if __name__ == "__main__":
    app.run(debug=True)
