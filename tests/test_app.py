import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as student_app


class StudentRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_directory.name) / "test-students.db"
        # Patch DATABASE before creating the app to ensure the app uses the test database.
        self.database_patch = patch.object(student_app, "DATABASE", self.database_path)
        self.database_patch.start()
        # Reset the lazy app singleton so the next get_app() call uses the patched DATABASE.
        student_app.app = None
        student_app.initialize_database()
        self.client = student_app.get_app().test_client()

    def tearDown(self):
        self.database_patch.stop()
        self.temp_directory.cleanup()
        # Reset the app singleton after each test to ensure test isolation.
        student_app.app = None

    def test_homepage_and_seed_data_load(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student directory", response.data)
        records = self.client.get("/api/students").get_json()
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["region"], "Volta Region")
        self.assertTrue(records[0]["courses"])

    def test_create_update_and_delete_student_with_enrollments(self):
        course_id = self.client.get("/api/courses").get_json()[0]["id"]
        record = {
            "student_number": "VR-1010",
            "first_name": "Akosua",
            "last_name": "Dzigbordi",
            "email": "akosua.dzigbordi@example.test",
            "region": "Volta Region",
            "program": "Computer Science",
            "course_ids": [course_id],
        }
        created = self.client.post("/api/students", json=record)
        self.assertEqual(created.status_code, 201)
        student_id = created.get_json()["id"]
        saved = next(
            item for item in self.client.get("/api/students").get_json() if item["id"] == student_id
        )
        self.assertEqual(saved["course_ids"], [course_id])

        record["program"] = "Software Engineering"
        updated = self.client.put(f"/api/students/{student_id}", json=record)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(
            next(item for item in self.client.get("/api/students").get_json() if item["id"] == student_id)[
                "program"
            ],
            "Software Engineering",
        )
        self.assertEqual(self.client.delete(f"/api/students/{student_id}").status_code, 200)

    def test_duplicate_student_number_is_reported(self):
        existing = self.client.get("/api/students").get_json()[0]
        response = self.client.post(
            "/api/students",
            json={
                "student_number": existing["student_number"],
                "first_name": "Kwame",
                "last_name": "Amedome",
                "email": "kwame.amedome@example.test",
                "program": "Computer Science",
                "course_ids": [],
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("already in use", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()
