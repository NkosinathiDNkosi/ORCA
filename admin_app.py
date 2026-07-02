from flask import Flask, render_template, request, redirect, url_for, session
import os
import sqlite3
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta, datetime

app = Flask(__name__)

app.secret_key = "change_this_to_a_long_random_secret"
app.permanent_session_lifetime = timedelta(minutes=30)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "orca_projects.db"))

print("Using DB:", DB_PATH)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_admin():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123"))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass

    conn.close()

def ensure_appointments_table():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            service TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',
            is_deleted INTEGER DEFAULT 0,
            deleted_at TEXT
        )
    """)

    conn.commit()
    conn.close()

def ensure_status_column():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "status" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN status TEXT DEFAULT 'Pending'")

    conn.commit()
    conn.close()

def ensure_bin_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_deleted" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN is_deleted INTEGER DEFAULT 0")

    if "deleted_at" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN deleted_at TEXT")

    conn.commit()
    conn.close()

@app.before_request
def require_login():
    allowed = {"login", "static"}

    if request.endpoint in allowed or request.endpoint is None:
        return

    if "user" not in session:
        return redirect(url_for("login"))

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    message = request.args.get("message")

    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session.permanent = True
            session["user"] = username

            token = secrets.token_urlsafe(24)
            session["tab_token"] = token

            return f"""
            <!doctype html>
            <html>
            <head><meta charset="utf-8"></head>
            <body>
              <script>
                sessionStorage.setItem("orca_admin_tab_token", "{token}");
                window.location.replace("{url_for('dashboard')}");
              </script>
            </body>
            </html>
            """

        error = "Invalid username or password."

    if request.method == "GET":
        session.clear()

    return render_template("login.html", error=error, message=message)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    error = None
    success = None

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]

        if len(new_password) < 6:
            return render_template(
                "change_password.html",
                error="New password must be at least 6 characters long."
            )

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?",
            (session["user"],)
        ).fetchone()

        if not user or not check_password_hash(user["password"], current_password):
            conn.close()
            return render_template(
                "change_password.html",
                error="Current password is incorrect."
            )

        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (generate_password_hash(new_password), session["user"])
        )
        conn.commit()
        conn.close()

        session.clear()
        return redirect(url_for(
            "login",
            message="Password updated successfully. Please log in again."
        ))

    return render_template("change_password.html", error=error, success=success)

@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT * FROM appointments
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY appointment_date DESC, appointment_time DESC
    """).fetchall()
    conn.close()

    return render_template("dashboard.html", appointments=appointments)

@app.route("/admin/trash")
def bin_page():
    conn = get_db_connection()
    deleted = conn.execute("""
        SELECT * FROM appointments
        WHERE COALESCE(is_deleted, 0) = 1
        ORDER BY deleted_at DESC
    """).fetchall()
    conn.close()

    return render_template("bin.html", appointments=deleted)

@app.route("/bin")
def old_bin_redirect():
    return redirect(url_for("bin_page"))

@app.route("/confirm/<int:appointment_id>")
def confirm_appointment(appointment_id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE appointments SET status = 'Confirmed' WHERE id = ?",
        (appointment_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/status/<int:appointment_id>", methods=["POST"])
def update_status(appointment_id):
    status = request.form.get("status", "Pending")
    allowed_statuses = {"Pending", "Confirmed", "Completed", "Cancelled"}

    if status not in allowed_statuses:
        status = "Pending"

    conn = get_db_connection()
    conn.execute(
        "UPDATE appointments SET status = ? WHERE id = ?",
        (status, appointment_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/delete/<int:appointment_id>", methods=["GET", "POST"])
def delete_appointment(appointment_id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 1,
            deleted_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(timespec="seconds"), appointment_id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/restore/<int:appointment_id>", methods=["GET", "POST"])
def restore_appointment(appointment_id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 0,
            deleted_at = NULL
        WHERE id = ?
    """, (appointment_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("bin_page"))

@app.route("/purge/<int:appointment_id>", methods=["GET", "POST"])
def purge_appointment(appointment_id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM appointments WHERE id = ? AND COALESCE(is_deleted, 0) = 1",
        (appointment_id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("bin_page"))

create_admin()
ensure_appointments_table()
ensure_status_column()
ensure_bin_columns()

if __name__ == "__main__":
    app.run(debug=True)
