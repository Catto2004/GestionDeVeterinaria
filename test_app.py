import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import app as veterinary_app


class VeterinaryAppTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_database = veterinary_app.DATABASE
        veterinary_app.DATABASE = Path(self.temporary_directory.name) / "test.db"
        veterinary_app.init_db()
        veterinary_app.app.config["TESTING"] = True
        self.client = veterinary_app.app.test_client()

    def tearDown(self):
        veterinary_app.DATABASE = self.original_database
        self.temporary_directory.cleanup()

    def add_owner(self, document="12345", name="Ana Pérez"):
        return self.client.post(
            "/owners",
            data={
                "document": document,
                "name": name,
                "phone": "3001234567",
                "address": "Calle 1",
                "email": f"{document}@example.com",
            },
            follow_redirects=True,
        )

    def test_homepage_shows_all_main_sections(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        for label in (
            "Registrar dueño",
            "Registrar mascota",
            "Agendar cita",
            "Consultar citas",
            "Registrar veterinario",
        ):
            self.assertIn(label, response.get_data(as_text=True))

    def test_owner_rejects_non_numeric_phone_and_invalid_email(self):
        data = {
            "document": "12345",
            "name": "Ana Pérez",
            "phone": "30012ABC",
            "address": "Calle 1",
            "email": "ana@example.com",
        }
        response = self.client.post("/owners", data=data)
        self.assertIn("solo números", response.get_data(as_text=True))

        data["phone"] = "3001234567"
        data["email"] = "correo-invalido"
        response = self.client.post("/owners", data=data)
        self.assertIn("correo electrónico válido", response.get_data(as_text=True))

    def test_pet_rejects_non_finite_weight(self):
        self.add_owner()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            owner_id = connection.execute(
                "SELECT id FROM owners WHERE document = '12345'"
            ).fetchone()[0]

        response = self.client.post(
            "/pets",
            data={
                "owner_id": str(owner_id),
                "name": "Luna",
                "species": "Perro",
                "breed": "Criolla",
                "age": "4",
                "weight": "nan",
                "description": "",
            },
        )
        self.assertIn(
            "número válido mayor que cero", response.get_data(as_text=True)
        )
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM pets").fetchone()[0]
        self.assertEqual(count, 0)

    def test_pet_booking_collision_and_customer_appointment_lookup(self):
        self.add_owner()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            owner_id = connection.execute(
                "SELECT id FROM owners WHERE document = '12345'"
            ).fetchone()[0]

        pet_response = self.client.post(
            "/pets",
            data={
                "owner_id": str(owner_id),
                "name": "Luna",
                "species": "Perro",
                "breed": "Criolla",
                "age": "4",
                "weight": "12.5",
                "description": "Amigable",
            },
            follow_redirects=True,
        )
        self.assertIn("Mascota registrada correctamente", pet_response.get_data(as_text=True))

        vet_response = self.client.post(
            "/veterinarians",
            data={"name": "Dr. López", "specialty": "General"},
            follow_redirects=True,
        )
        self.assertIn(
            "Veterinario registrado correctamente", vet_response.get_data(as_text=True)
        )

        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            pet_id = connection.execute("SELECT id FROM pets").fetchone()[0]
            vet_id = connection.execute("SELECT id FROM veterinarians").fetchone()[0]
        booking = {
            "pet_id": str(pet_id),
            "veterinarian_id": str(vet_id),
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "time_block": "09:00-10:00",
        }
        booked = self.client.post(
            "/appointments/new", data=booking, follow_redirects=True
        )
        self.assertIn("Cita programada correctamente", booked.get_data(as_text=True))

        duplicate = self.client.post("/appointments/new", data=booking)
        self.assertIn("ya tiene una cita", duplicate.get_data(as_text=True))

        appointments = self.client.get("/appointments?document=12345")
        appointment_html = appointments.get_data(as_text=True)
        self.assertIn("Luna", appointment_html)
        self.assertIn("Dr. López", appointment_html)
        self.assertIn("09:00-10:00", appointment_html)

        self.add_owner(document="67890", name="Luis Gómez")
        no_appointments = self.client.get("/appointments?document=67890")
        self.assertIn(
            "No registra citas programadas",
            no_appointments.get_data(as_text=True),
        )

        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
