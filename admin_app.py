from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
import sqlite3
import secrets
import uuid
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime

app = Flask(__name__)

# ============================================================
# APP CONFIG
# ============================================================
app.secret_key = "change_this_to_a_long_random_secret"
app.permanent_session_lifetime = timedelta(minutes=30)

GALLERY_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "static", "uploads", "gallery")
GALLERY_UPLOAD_DIR = os.path.abspath(GALLERY_UPLOAD_DIR)
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "m4v"}
MAX_IMAGE_SIZE = 15 * 1024 * 1024
MAX_VIDEO_SIZE = 100 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024
os.makedirs(GALLERY_UPLOAD_DIR, exist_ok=True)

# ============================================================
# DATABASE CONNECTION
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "orca_projects.db")
DB_PATH = os.path.abspath(DB_PATH)

print("Using DB:", DB_PATH)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================
# CREATE ADMIN USER
# ============================================================
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

    username = "admin"
    password = generate_password_hash("admin123")

    try:
        cursor.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            (username, password)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass

    conn.close()

# ============================================================
# ENSURE APPOINTMENTS TABLE + COLUMNS EXIST
# ============================================================
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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gallery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            media_type TEXT NOT NULL CHECK(media_type IN ('image', 'video')),
            title TEXT,
            description TEXT,
            is_latest INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
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
        print("Status column added to appointments table.")

    conn.commit()
    conn.close()

def ensure_bin_columns():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(appointments)")
    columns = [column[1] for column in cursor.fetchall()]

    if "is_deleted" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN is_deleted INTEGER DEFAULT 0")
        print("is_deleted column added.")

    if "deleted_at" not in columns:
        cursor.execute("ALTER TABLE appointments ADD COLUMN deleted_at TEXT")
        print("deleted_at column added.")

    conn.commit()
    conn.close()

ensure_appointments_table()
ensure_status_column()
ensure_bin_columns()

# ============================================================
# LOGIN CHECK
# ============================================================
@app.before_request
def require_login():
    allowed = {"login", "static"}
    if request.endpoint in allowed or request.endpoint is None:
        return

    if "user" not in session:
        return redirect(url_for("login"))

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def home():
    return redirect(url_for("login"))

# -------------------------
# LOGIN
# -------------------------
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
        else:
            error = "Invalid username or password."

    if request.method == "GET":
        session.clear()

    return render_template("login.html", error=error, message=message)

# -------------------------
# LOGOUT
# -------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------
# CHANGE PASSWORD
# -------------------------
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

        new_hashed = generate_password_hash(new_password)

        conn.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (new_hashed, session["user"])
        )
        conn.commit()
        conn.close()

        session.clear()
        return redirect(url_for("login", message="Password updated successfully. Please log in again."))

    return render_template("change_password.html", error=error, success=success)

# -------------------------
# DASHBOARD
# -------------------------
@app.route("/dashboard")
def dashboard():
    conn = get_db_connection()
    appointments = conn.execute("""
        SELECT * FROM appointments
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY appointment_date DESC, appointment_time DESC
    """).fetchall()
    gallery_items = conn.execute("""
        SELECT * FROM gallery_items
        ORDER BY created_at DESC, id DESC
    """).fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        appointments=appointments,
        gallery_items=gallery_items,
        gallery_success=request.args.get("gallery_success"),
        gallery_error=request.args.get("gallery_error")
    )

# -------------------------
# BIN VIEW
# -------------------------
@app.route("/bin")
def bin_view():
    conn = get_db_connection()
    deleted = conn.execute("""
        SELECT * FROM appointments
        WHERE COALESCE(is_deleted, 0) = 1
        ORDER BY deleted_at DESC
    """).fetchall()
    conn.close()

    return render_template("bin.html", appointments=deleted)

@app.route("/gallery-media/<path:filename>")
def gallery_media(filename):
    return send_from_directory(GALLERY_UPLOAD_DIR, filename)


# -------------------------
# GALLERY / LATEST WORK
# -------------------------
def _gallery_media_type(filename):
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    if extension in ALLOWED_VIDEO_EXTENSIONS:
        return "video"
    return None


@app.route("/upload-gallery", methods=["POST"])
def upload_gallery():
    files = request.files.getlist("gallery_files")
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    mark_latest = request.form.get("is_latest") == "1"

    valid_files = [f for f in files if f and f.filename]
    if not valid_files:
        return redirect(url_for("dashboard", gallery_error="Please select at least one image or video."))

    uploaded = []
    errors = []
    for file in valid_files:
        media_type = _gallery_media_type(file.filename)
        if not media_type:
            errors.append(f"{file.filename}: unsupported file type.")
            continue
        safe_name = secure_filename(file.filename)
        if not safe_name:
            errors.append("One file has an invalid filename.")
            continue
        extension = safe_name.rsplit(".", 1)[-1].lower()
        stored_name = f"{uuid.uuid4().hex}.{extension}"
        destination = os.path.join(GALLERY_UPLOAD_DIR, stored_name)
        try:
            file.save(destination)
            size = os.path.getsize(destination)
            max_size = MAX_IMAGE_SIZE if media_type == "image" else MAX_VIDEO_SIZE
            if size > max_size:
                os.remove(destination)
                errors.append(f"{file.filename}: file is larger than {max_size // (1024 * 1024)} MB.")
                continue
            uploaded.append((stored_name, media_type))
        except OSError:
            if os.path.exists(destination):
                os.remove(destination)
            errors.append(f"{file.filename}: upload failed.")

    if not uploaded:
        return redirect(url_for("dashboard", gallery_error="Upload failed. " + " ".join(errors)))

    conn = get_db_connection()
    if mark_latest:
        conn.execute("UPDATE gallery_items SET is_latest = 0")
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for stored_name, media_type in uploaded:
        conn.execute("""
            INSERT INTO gallery_items
            (filename, media_type, title, description, is_latest, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (stored_name, media_type, title or None, description or None, 1 if mark_latest else 0, created_at))
    conn.commit()
    conn.close()

    success_message = f"{len(uploaded)} item{'s' if len(uploaded) != 1 else ''} published to Latest Work."
    if errors:
        success_message += " Some files were skipped: " + " ".join(errors)
    return redirect(url_for("dashboard", gallery_success=success_message))


@app.route("/delete-gallery/<int:gallery_id>", methods=["POST"])
def delete_gallery(gallery_id):
    conn = get_db_connection()
    item = conn.execute("SELECT filename FROM gallery_items WHERE id = ?", (gallery_id,)).fetchone()
    if item:
        conn.execute("DELETE FROM gallery_items WHERE id = ?", (gallery_id,))
        conn.commit()
    conn.close()
    if item:
        filepath = os.path.join(GALLERY_UPLOAD_DIR, os.path.basename(item["filename"]))
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass
    return redirect(url_for("dashboard", gallery_success="Gallery item deleted."))


# -------------------------
# CONFIRM APPOINTMENT
# -------------------------
@app.route("/confirm/<int:id>")
def confirm_appointment(id):
    conn = get_db_connection()
    conn.execute(
        "UPDATE appointments SET status = 'Confirmed' WHERE id = ?",
        (id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))


# -------------------------
# UPDATE STATUS
# -------------------------
@app.route("/status/<int:id>", methods=["POST"])
def update_status(id):
    status = request.form.get("status", "Pending")
    allowed_statuses = {"Pending", "Confirmed", "Completed", "Cancelled"}
    if status not in allowed_statuses:
        status = "Pending"

    conn = get_db_connection()
    conn.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# -------------------------
# DELETE -> MOVE TO BIN
# -------------------------
@app.route("/delete/<int:id>", methods=["GET", "POST"])
def delete_appointment(id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 1,
            deleted_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(timespec="seconds"), id))
    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

# -------------------------
# RESTORE FROM BIN
# -------------------------
@app.route("/restore/<int:id>", methods=["GET", "POST"])
def restore_appointment(id):
    conn = get_db_connection()
    conn.execute("""
        UPDATE appointments
        SET is_deleted = 0,
            deleted_at = NULL
        WHERE id = ?
    """, (id,))
    conn.commit()
    conn.close()

    return redirect(url_for("bin_view"))

# -------------------------
# PERMANENT DELETE
# -------------------------
@app.route("/purge/<int:id>", methods=["GET", "POST"])
def purge_appointment(id):
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM appointments WHERE id = ? AND COALESCE(is_deleted, 0) = 1",
        (id,)
    )
    conn.commit()
    conn.close()

    return redirect(url_for("bin_view"))

# ============================================================
# RUN APP
# ============================================================
if __name__ == "__main__":
    create_admin()
    ensure_appointments_table()
    ensure_status_column()
    ensure_bin_columns()
    app.run(debug=True)