# Overview

The Student Records Management System is a small web application for keeping
student profiles and their course registrations together. It provides a
searchable directory backed by a relational SQLite database, so student and
course information can be stored once and connected through enrollment records.

The application is built with Python and Flask. On first startup it creates the
SQLite database at `instance/students.db`, creates its tables, and inserts
fictional sample students from Ghana's Volta Region along with a small course
catalogue. To run it on Windows from the project root:

```powershell
# Skip this step if .venv already exists.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Then open <http://127.0.0.1:5000> in a browser. In the directory, use the
search box to filter records by student name, student number, or program. Use
**Add student** to create a record and choose registered courses. The edit and
delete controls on each row update or remove that student's record. The
database location can be changed with the `STUDENT_RECORDS_DATABASE`
environment variable.

**Software Demo Video:** [Student Records Management System demonstration](https://vimeo.com/1234715208)

# Relational Database

The application uses SQLite, a relational database stored in the project at
`instance/students.db`. Python's built-in `sqlite3` module creates the database
and tables, executes parameterized SQL statements, and returns query results
to the Flask routes.

The schema contains three tables:

- **`students`** stores student number, name, email, region, program, and
  creation timestamp. Student numbers and email addresses must be unique.
- **`courses`** stores a unique course code and course name.
- **`enrollments`** connects students and courses. Its `student_id` and
  `course_id` foreign keys reference the corresponding rows in `students` and
  `courses`. The pair is the table's composite primary key, so a student
  cannot be enrolled in the same course twice. Deleting a student or course
  cascades to its related enrollment rows.

Each student can enroll in multiple courses, and each course can have multiple
students; `enrollments` represents that many-to-many relationship. The
student-directory query uses SQL `LEFT JOIN`s from `students` through
`enrollments` to `courses`, grouping registered course details with each
student. The Flask route returns those query results as JSON, and the browser
displays the student and course information in the directory.

# Development Environment

- **Operating system and editor:** Windows, developed in Visual Studio Code.
- **Python:** 3.13.11.
- **Web framework:** Flask 3.1.3, declared in `requirements.txt` as
  `Flask>=3.1,<4.0`.
- **Database:** SQLite 3.50.4 through Python's standard-library `sqlite3`
  module; it is not a separate Python package dependency.
- **Frontend:** HTML templates, CSS, and browser-native JavaScript. No
  JavaScript package manager or frontend build step is required.
- **Python dependencies:** Flask is the only directly declared third-party
  Python dependency; its required packages are installed by
  `pip install -r requirements.txt`.
- **Fonts:** The stylesheet imports DM Sans and Manrope from Google Fonts, with
  sans-serif fallbacks.

# Useful Websites

- [CSE 310 SQL Relational Database module](https://byui-cse.github.io/cse310-ww-course/modules/sql_database/README.md)
- [Python documentation](https://docs.python.org/3/)
- [Flask documentation](https://flask.palletsprojects.com/)
- [SQLite documentation](https://www.sqlite.org/docs.html)

# Future Work

- Add a dedicated interface for managing the course catalogue.
- Add pagination and server-side filtering for larger student directories.
- Add database backup and restore guidance for administrators.
