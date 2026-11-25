import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime as RealDateTime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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

    def add_pet(self, owner_id, **extra):
        data = {
            "owner_id": str(owner_id),
            "name": "Luna",
            "species": "Perro",
            "breed": "Criolla",
            "age": "4",
            "weight": "12.5",
            "description": "",
            "allergies": "",
            "conditions": "",
        }
        data.update(extra)
        return self.client.post("/pets", data=data, follow_redirects=True)

    def add_veterinarian(self):
        return self.client.post(
            "/veterinarians",
            data={"name": "Dra. López", "specialty": "General"},
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

    def test_schedule_cancellation_releases_the_time_block(self):
        self.add_owner()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            owner_id = connection.execute(
                "SELECT id FROM owners WHERE document = '12345'"
            ).fetchone()[0]
        self.add_pet(owner_id)
        self.add_veterinarian()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            pet_id = connection.execute("SELECT id FROM pets").fetchone()[0]
            veterinarian_id = connection.execute(
                "SELECT id FROM veterinarians"
            ).fetchone()[0]
        booking = {
            "pet_id": str(pet_id),
            "veterinarian_id": str(veterinarian_id),
            "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
            "time_block": "09:00-10:00",
        }

        booked = self.client.post("/appointments/new", data=booking)
        self.assertEqual(booked.status_code, 302)
        status_url = f"/schedule/status?date={booking['appointment_date']}"
        slots = self.client.get(status_url).get_json()["slots"]
        booked_slot = next(slot for slot in slots if slot["time_block"] == "09:00-10:00")
        self.assertEqual(booked_slot["status"], "occupied")

        cancelled = self.client.post(
            f"/appointments/{booked_slot['appointment_id']}/cancel",
            data={"date": booking["appointment_date"]},
        )
        self.assertEqual(cancelled.status_code, 302)
        slots = self.client.get(status_url).get_json()["slots"]
        available_slot = next(
            slot for slot in slots if slot["time_block"] == "09:00-10:00"
        )
        self.assertEqual(available_slot["status"], "free")

        replacement = self.client.post("/appointments/new", data=booking)
        self.assertEqual(replacement.status_code, 302)
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            statuses = connection.execute(
                "SELECT status, COUNT(*) FROM appointments GROUP BY status"
            ).fetchall()
        self.assertEqual(dict(statuses), {"Cancelada": 1, "Programada": 1})

    def test_past_time_block_is_rejected_by_server(self):
        self.add_owner()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            owner_id = connection.execute(
                "SELECT id FROM owners WHERE document = '12345'"
            ).fetchone()[0]
        self.add_pet(owner_id)
        self.add_veterinarian()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            pet_id = connection.execute("SELECT id FROM pets").fetchone()[0]
            veterinarian_id = connection.execute(
                "SELECT id FROM veterinarians"
            ).fetchone()[0]

        class FixedDateTime(RealDateTime):
            @classmethod
            def now(cls, tz=None):
                current = RealDateTime.now(tz)
                return current.replace(hour=15, minute=30, second=0, microsecond=0)

        with patch.object(veterinary_app, "datetime", FixedDateTime):
            response = self.client.post(
                "/appointments/new",
                data={
                    "pet_id": str(pet_id),
                    "veterinarian_id": str(veterinarian_id),
                    "appointment_date": date.today().isoformat(),
                    "time_block": "09:00-10:00",
                },
            )
        self.assertIn("ya pasó", response.get_data(as_text=True))
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        self.assertEqual(count, 0)

    def test_veterinarian_login_history_and_prescription_pdf(self):
        self.add_owner()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            owner_id = connection.execute(
                "SELECT id FROM owners WHERE document = '12345'"
            ).fetchone()[0]
        self.add_pet(owner_id, allergies="Penicilina", conditions="Asma")
        self.add_veterinarian()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            pet_id = connection.execute("SELECT id FROM pets").fetchone()[0]
            veterinarian_id = connection.execute(
                "SELECT id FROM veterinarians"
            ).fetchone()[0]

        denied = self.client.get(f"/pets/{pet_id}/medical-records")
        self.assertEqual(denied.status_code, 302)
        self.assertIn("/vet/login", denied.headers["Location"])
        account = self.client.post(
            "/vet/register",
            data={
                "veterinarian_id": str(veterinarian_id),
                "username": "doctora",
                "password": "secure-pass-123",
            },
        )
        self.assertEqual(account.status_code, 302)
        login = self.client.post(
            "/vet/login",
            data={"username": "doctora", "password": "secure-pass-123"},
        )
        self.assertEqual(login.status_code, 302)

        history = self.client.get(f"/pets/{pet_id}/medical-records")
        history_html = history.get_data(as_text=True)
        self.assertIn("ALERTA MÉDICA", history_html)
        self.assertIn("Penicilina", history_html)
        self.assertIn("Asma", history_html)
        saved = self.client.post(
            f"/pets/{pet_id}/medical-records",
            data={
                "visit_date": date.today().isoformat(),
                "diagnosis": "Infección",
                "anamnesis": "Tos",
                "observations": "Revisar en una semana",
            },
            follow_redirects=True,
        )
        self.assertIn("Infección", saved.get_data(as_text=True))
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            record_id = connection.execute(
                "SELECT id FROM medical_records"
            ).fetchone()[0]
        edited = self.client.post(
            f"/pets/{pet_id}/medical-records/{record_id}/edit",
            data={
                "visit_date": date.today().isoformat(),
                "diagnosis": "Diagnóstico actualizado",
                "anamnesis": "Tos",
                "observations": "Control",
            },
        )
        self.assertEqual(edited.status_code, 302)
        self.assertIn(
            "Diagnóstico actualizado",
            self.client.get(f"/pets/{pet_id}/medical-records").get_data(as_text=True),
        )

        prescription = self.client.post(
            "/prescriptions/new",
            data={
                "pet_id": str(pet_id),
                "medication": "Medicamento A",
                "dosage": "1 tableta",
                "duration": "5 días",
                "instructions": "Después de comer",
            },
        )
        self.assertEqual(prescription.status_code, 302)
        prescriptions_page = self.client.get("/prescriptions")
        self.assertIn("Medicamento A", prescriptions_page.get_data(as_text=True))
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            prescription_id = connection.execute(
                "SELECT id FROM prescriptions"
            ).fetchone()[0]
        pdf = self.client.get(f"/prescriptions/{prescription_id}/pdf")
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf.mimetype, "application/pdf")
        self.assertTrue(pdf.data.startswith(b"%PDF"))

    def test_failed_email_does_not_prevent_saving_appointment(self):
        self.add_owner()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            owner_id = connection.execute(
                "SELECT id FROM owners WHERE document = '12345'"
            ).fetchone()[0]
        self.add_pet(owner_id)
        self.add_veterinarian()
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            pet_id = connection.execute("SELECT id FROM pets").fetchone()[0]
            veterinarian_id = connection.execute(
                "SELECT id FROM veterinarians"
            ).fetchone()[0]

        with (
            patch.dict(
                "os.environ",
                {
                    "SMTP_HOST": "smtp.example.test",
                    "SMTP_FROM": "clinic@example.test",
                    "SMTP_USE_TLS": "false",
                },
                clear=True,
            ),
            patch.object(veterinary_app.smtplib, "SMTP", side_effect=OSError("offline")),
        ):
            response = self.client.post(
                "/appointments/new",
                data={
                    "pet_id": str(pet_id),
                    "veterinarian_id": str(veterinarian_id),
                    "appointment_date": (date.today() + timedelta(days=1)).isoformat(),
                    "time_block": "09:00-10:00",
                },
                follow_redirects=True,
            )

        self.assertIn("La cita quedó guardada", response.get_data(as_text=True))
        with closing(sqlite3.connect(veterinary_app.DATABASE)) as connection:
            count = connection.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        self.assertEqual(count, 1)

    def test_confirmation_email_contains_appointment_details(self):
        smtp = MagicMock()
        smtp.__enter__.return_value = smtp
        details = {
            "owner_name": "Ana Pérez",
            "email": "ana@example.com",
            "pet_name": "Luna",
            "appointment_date": "2026-12-01",
            "time_block": "09:00-10:00",
            "veterinarian_name": "Dra. López",
        }
        with (
            patch.dict(
                "os.environ",
                {
                    "SMTP_HOST": "smtp.example.test",
                    "SMTP_FROM": "clinic@example.test",
                    "SMTP_USE_TLS": "false",
                },
                clear=True,
            ),
            patch.object(veterinary_app.smtplib, "SMTP", return_value=smtp),
        ):
            sent, _ = veterinary_app.send_appointment_email(details)

        self.assertTrue(sent)
        message = smtp.send_message.call_args.args[0]
        body = message.get_content()
        for expected in (
            "Ana Pérez",
            "Luna",
            "2026-12-01",
            "09:00-10:00",
            "Dra. López",
            "10 minutos antes",
        ):
            self.assertIn(expected, body)


if __name__ == "__main__":
    unittest.main()
