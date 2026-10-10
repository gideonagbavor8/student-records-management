import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATABASE = Path(os.environ.get("STUDENT_RECORDS_DATABASE", BASE_DIR / "instance" / "students.db"))


@contextmanager
def get_db():
    """Yield a foreign-key-enabled SQLite connection and manage its transaction."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        # Commit only after the caller's complete unit of work succeeds.
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """Create the relational schema and insert the initial catalogue and sample records."""
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with get_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_number TEXT NOT NULL UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                region TEXT NOT NULL DEFAULT 'Volta Region',
                program TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS enrollments (
                student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                PRIMARY KEY (student_id, course_id)
            );
            """
        )
        if connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 0:
            connection.executemany(
                "INSERT INTO courses (code, name) VALUES (?, ?)",
                [
                    ("CSE310", "Applied Programming"),
                    ("DB210", "Relational Databases"),
                    ("WEB220", "Web Application Development"),
                ],
            )
        if connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
            students = [
                ("VR-1001", "Esi", "Amegashie", "esi.amegashie@example.test", "Volta Region", "Computer Science"),
                ("VR-1002", "Kofi", "Adzaho", "kofi.adzaho@example.test", "Volta Region", "Information Technology"),
                ("VR-1003", "Ama", "Kpodo", "ama.kpodo@example.test", "Volta Region", "Software Engineering"),
            ]
            connection.executemany(
                """
                INSERT INTO students (student_number, first_name, last_name, email, region, program)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                students,
            )
            # Seed registrations by matching selected students with selected courses.
            connection.execute(
                """
                INSERT INTO enrollments (student_id, course_id)
                SELECT students.id, courses.id
                FROM students CROSS JOIN courses
                WHERE students.student_number IN ('VR-1001', 'VR-1002')
                  AND courses.code IN ('CSE310', 'DB210')
                """
            )


def create_app():
    """Create the Flask application, initialize its database, and register routes."""
    app = Flask(__name__)
    initialize_database()

    @app.get("/")
    def index():
        """Render the student directory page."""
        return render_template("index.html")

    @app.get("/api/courses")
    def list_courses():
        """Return the course catalogue as JSON for the registration form."""
        with get_db() as connection:
            rows = connection.execute("SELECT id, code, name FROM courses ORDER BY code").fetchall()
        return jsonify([dict(row) for row in rows])

    @app.get("/api/students")
    def list_students():
        """Return student records with their registered course IDs and names."""
        with get_db() as connection:
            # LEFT JOINs retain students who do not yet have course registrations.
            rows = connection.execute(
                """
                SELECT s.id, s.student_number, s.first_name, s.last_name, s.email, s.region, s.program,
                       COALESCE(GROUP_CONCAT(c.id), '') AS course_ids,
                       COALESCE(GROUP_CONCAT(c.code || ' - ' || c.name, '||'), '') AS courses
                FROM students AS s
                LEFT JOIN enrollments AS e ON e.student_id = s.id
                LEFT JOIN courses AS c ON c.id = e.course_id
                GROUP BY s.id
                ORDER BY s.last_name COLLATE NOCASE, s.first_name COLLATE NOCASE
                """
            ).fetchall()
        results = []
        for row in rows:
            student = dict(row)
            student["course_ids"] = [int(value) for value in student["course_ids"].split(",") if value]
            student["courses"] = student["courses"].split("||") if student["courses"] else []
            results.append(student)
        return jsonify(results)

    @app.post("/api/students")
    def create_student():
        """Validate and create a student and the selected course registrations."""
        data, error = validate_student(request.get_json(silent=True))
        if error:
            return jsonify(error), 400
        try:
            with get_db() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO students (student_number, first_name, last_name, email, region, program)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["student_number"],
                        data["first_name"],
                        data["last_name"],
                        data["email"],
                        data["region"],
                        data["program"],
                    ),
                )
                save_enrollments(connection, cursor.lastrowid, data["course_ids"])
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": duplicate_error(exc)}), 409
        return jsonify({"id": cursor.lastrowid}), 201

    @app.put("/api/students/<int:student_id>")
    def update_student(student_id):
        """Update a student and replace their course registrations atomically."""
        data, error = validate_student(request.get_json(silent=True))
        if error:
            return jsonify(error), 400
        try:
            with get_db() as connection:
                cursor = connection.execute(
                    """
                    UPDATE students
                    SET student_number = ?, first_name = ?, last_name = ?, email = ?, region = ?, program = ?
                    WHERE id = ?
                    """,
                    (
                        data["student_number"],
                        data["first_name"],
                        data["last_name"],
                        data["email"],
                        data["region"],
                        data["program"],
                        student_id,
                    ),
                )
                if cursor.rowcount == 0:
                    return jsonify({"error": "Student record not found."}), 404
                connection.execute("DELETE FROM enrollments WHERE student_id = ?", (student_id,))
                save_enrollments(connection, student_id, data["course_ids"])
        except sqlite3.IntegrityError as exc:
            return jsonify({"error": duplicate_error(exc)}), 409
        return jsonify({"message": "Student record updated."})

    @app.delete("/api/students/<int:student_id>")
    def delete_student(student_id):
        """Delete a student; the database cascades deletion to their enrollments."""
        with get_db() as connection:
            cursor = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Student record not found."}), 404
        return jsonify({"message": "Student record deleted."})

    return app


def validate_student(data):
    """Validate a submitted student payload and normalize its fields and course IDs."""
    if not isinstance(data, dict):
        return None, {"error": "A student record is required."}

    fields = ("student_number", "first_name", "last_name", "email", "program")
    values = {field: data.get(field, "").strip() if isinstance(data.get(field, ""), str) else "" for field in fields}
    if any(not value for value in values.values()):
        return None, {"error": "Student number, name, email, and program are required."}
    if "@" not in values["email"] or "." not in values["email"].rsplit("@", 1)[-1]:
        return None, {"error": "Enter a valid email address."}

    region = data.get("region", "Volta Region")
    if not isinstance(region, str) or not region.strip():
        return None, {"error": "Region is required."}
    course_ids = data.get("course_ids", [])
    if not isinstance(course_ids, list) or any(type(course_id) is not int for course_id in course_ids):
        return None, {"error": "Course selections are invalid."}
    values.update(region=region.strip(), course_ids=list(dict.fromkeys(course_ids)))
    return values, None


def save_enrollments(connection, student_id, course_ids):
    """Verify selected courses exist, then insert the student's enrollment links."""
    if not course_ids:
        return
    placeholders = ",".join("?" for _ in course_ids)
    existing = {
        row["id"]
        for row in connection.execute(
            f"SELECT id FROM courses WHERE id IN ({placeholders})", course_ids
        ).fetchall()
    }
    if existing != set(course_ids):
        raise sqlite3.IntegrityError("Selected course does not exist.")
    connection.executemany(
        "INSERT INTO enrollments (student_id, course_id) VALUES (?, ?)",
        [(student_id, course_id) for course_id in course_ids],
    )


def duplicate_error(exc):
    """Translate known uniqueness violations into user-facing conflict messages."""
    message = str(exc)
    if "students.email" in message:
        return "That email address is already in use."
    if "students.student_number" in message:
        return "That student number is already in use."
    return "The record conflicts with existing data."


app = None


def get_app():
    """Lazy factory that returns the Flask application, creating it on first access."""
    global app
    if app is None:
        app = create_app()
    return app


if __name__ == "__main__":
    app = get_app()
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
