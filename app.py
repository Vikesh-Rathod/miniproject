from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import os

app = Flask(__name__)

# Development secret key
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "dev-only-change-this-secret-before-deployment"
)


# Connect to the database
def get_db_connection():
    conn = sqlite3.connect("complaints.db")
    conn.row_factory = sqlite3.Row
    return conn


# Create database tables if they do not exist
def initialize_database():
    conn = get_db_connection()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen'
        )
    """)

    # Create complaints table if it does not exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    conn.commit()
    conn.close()


# Require users to log in before accessing a page
def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access that page.")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


# Home page
@app.route("/")
def home():
    # Logged-in users go to the dashboard
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


# User registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill in all fields.")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()

        try:
            conn.execute(
                """
                INSERT INTO users (name, email, password)
                VALUES (?, ?, ?)
                """,
                (name, email, hashed_password)
            )
            conn.commit()

        except sqlite3.IntegrityError:
            flash("An account with this email already exists.")
            return render_template("register.html")

        finally:
            conn.close()

        flash("Registration successful! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


# User login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()

        try:
            user = conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()
        finally:
            conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]

            # After login, open the dashboard
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.")

    return render_template("login.html")


# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# Submit a complaint
@app.route("/complaint", methods=["GET", "POST"])
@login_required
def submit_complaint():

    if request.method == "POST":

        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()

        # Accepted complaint categories
        allowed_categories = {
            "Garbage",
            "Road",
            "Drainage",
            "Water",
            "Streetlight",
            "Other"
        }

        # Validate submitted information
        if (
            category not in allowed_categories
            or not description
            or len(description) > 2000
            or not location
            or len(location) > 250
        ):
            flash("Please enter valid complaint details.")
            return redirect(url_for("submit_complaint"))

        conn = get_db_connection()

        try:
            cursor = conn.execute(
                """
                INSERT INTO complaints
                (name, category, description, location, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_name"],
                    category,
                    description,
                    location,
                    "Pending"
                )
            )

            complaint_id = cursor.lastrowid
            conn.commit()

        finally:
            conn.close()

        # Show the complaint ID after successful submission
        return render_template(
            "complaint_success.html",
            complaint_id=complaint_id
        )

    return render_template("complaint.html")


# Complaint tracking
@app.route("/track", methods=["GET", "POST"])
@login_required
def track_complaint():

    complaint = None
    error = None

    if request.method == "POST":

        complaint_id = request.form.get(
            "complaint_id", ""
        ).strip()

        if complaint_id.isdigit():

            conn = get_db_connection()

            try:
                complaint = conn.execute(
                    """
                    SELECT * FROM complaints
                    WHERE id = ?
                    """,
                    (int(complaint_id),)
                ).fetchone()

            finally:
                conn.close()

        if complaint is None:
            error = "Complaint not found. Please check your ID."

    return render_template(
        "track.html",
        complaint=complaint,
        error=error
    )


# Run the application
if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)