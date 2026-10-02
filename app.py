
from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = "library_project_secret"

DATABASE = "library.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            category TEXT,
            quantity INTEGER NOT NULL DEFAULT 1,
            available INTEGER NOT NULL DEFAULT 1
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            return_date TEXT,
            fine INTEGER DEFAULT 0,
            FOREIGN KEY(book_id) REFERENCES books(id),
            FOREIGN KEY(student_id) REFERENCES students(id)
        )
    """)

    conn.commit()
    conn.close()


# Database tables will be created when the app starts
create_tables()


@app.route("/")
def index():
    conn = get_db()

    books = conn.execute(
        "SELECT * FROM books ORDER BY id DESC"
    ).fetchall()

    students = conn.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    issued = conn.execute("""
        SELECT issues.*, books.title, students.name
        FROM issues
        JOIN books ON issues.book_id = books.id
        JOIN students ON issues.student_id = students.id
        ORDER BY issues.id DESC
    """).fetchall()

    total_books = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM books"
    ).fetchone()[0]

    available_books = conn.execute(
        "SELECT COALESCE(SUM(available), 0) FROM books"
    ).fetchone()[0]

    total_students = conn.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    active_issues = conn.execute(
        "SELECT COUNT(*) FROM issues WHERE return_date IS NULL"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "index.html",
        books=books,
        students=students,
        issued=issued,
        total_books=total_books,
        available_books=available_books,
        total_students=total_students,
        active_issues=active_issues
    )


@app.route("/add_book", methods=["POST"])
def add_book():
    title = request.form["title"].strip()
    author = request.form["author"].strip()
    category = request.form["category"].strip()
    quantity = int(request.form["quantity"])

    if not title or not author or quantity < 1:
        flash("Please enter valid book details.")
        return redirect(url_for("index"))

    conn = get_db()

    conn.execute(
        """
        INSERT INTO books
        (title, author, category, quantity, available)
        VALUES (?, ?, ?, ?, ?)
        """,
        (title, author, category, quantity, quantity)
    )

    conn.commit()
    conn.close()

    flash("Book added successfully.")
    return redirect(url_for("index"))


@app.route("/delete_book/<int:book_id>")
def delete_book(book_id):
    conn = get_db()

    active = conn.execute(
        """
        SELECT COUNT(*)
        FROM issues
        WHERE book_id=? AND return_date IS NULL
        """,
        (book_id,)
    ).fetchone()[0]

    if active:
        flash("This book is currently issued, so it cannot be deleted.")
    else:
        conn.execute(
            "DELETE FROM issues WHERE book_id=?",
            (book_id,)
        )

        conn.execute(
            "DELETE FROM books WHERE id=?",
            (book_id,)
        )

        conn.commit()
        flash("Book deleted.")

    conn.close()
    return redirect(url_for("index"))


@app.route("/add_student", methods=["POST"])
def add_student():
    name = request.form["name"].strip()
    email = request.form["email"].strip()
    phone = request.form["phone"].strip()

    if not name:
        flash("Student name is required.")
        return redirect(url_for("index"))

    conn = get_db()

    conn.execute(
        """
        INSERT INTO students (name, email, phone)
        VALUES (?, ?, ?)
        """,
        (name, email, phone)
    )

    conn.commit()
    conn.close()

    flash("Student added successfully.")
    return redirect(url_for("index"))


@app.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    conn = get_db()

    active = conn.execute(
        """
        SELECT COUNT(*)
        FROM issues
        WHERE student_id=? AND return_date IS NULL
        """,
        (student_id,)
    ).fetchone()[0]

    if active:
        flash("This student has an issued book and cannot be deleted.")
    else:
        conn.execute(
            "DELETE FROM issues WHERE student_id=?",
            (student_id,)
        )

        conn.execute(
            "DELETE FROM students WHERE id=?",
            (student_id,)
        )

        conn.commit()
        flash("Student deleted.")

    conn.close()
    return redirect(url_for("index"))


@app.route("/issue_book", methods=["POST"])
def issue_book():
    book_id = request.form["book_id"]
    student_id = request.form["student_id"]

    conn = get_db()

    book = conn.execute(
        "SELECT * FROM books WHERE id=?",
        (book_id,)
    ).fetchone()

    if not book or book["available"] <= 0:
        flash("Book is not available.")
        conn.close()
        return redirect(url_for("index"))

    conn.execute(
        """
        INSERT INTO issues (book_id, student_id, issue_date)
        VALUES (?, ?, ?)
        """,
        (book_id, student_id, date.today().isoformat())
    )

    conn.execute(
        """
        UPDATE books
        SET available = available - 1
        WHERE id=?
        """,
        (book_id,)
    )

    conn.commit()
    conn.close()

    flash("Book issued successfully.")
    return redirect(url_for("index"))


@app.route("/return_book/<int:issue_id>")
def return_book(issue_id):
    conn = get_db()

    issue = conn.execute(
        "SELECT * FROM issues WHERE id=?",
        (issue_id,)
    ).fetchone()

    if not issue or issue["return_date"]:
        flash("Invalid return request.")
        conn.close()
        return redirect(url_for("index"))

    issue_date = datetime.strptime(
        issue["issue_date"],
        "%Y-%m-%d"
    ).date()

    return_date = date.today()

    days = (return_date - issue_date).days

    # 14 days allowed.
    # Fine is Rs. 2 for each extra day.
    extra_days = max(0, days - 14)
    fine = extra_days * 2

    conn.execute(
        """
        UPDATE issues
        SET return_date=?, fine=?
        WHERE id=?
        """,
        (
            return_date.isoformat(),
            fine,
            issue_id
        )
    )

    conn.execute(
        """
        UPDATE books
        SET available = available + 1
        WHERE id=?
        """,
        (issue["book_id"],)
    )

    conn.commit()
    conn.close()

    flash(f"Book returned. Fine: Rs. {fine}")
    return redirect(url_for("index"))


@app.route("/search")
def search():
    keyword = request.args.get("q", "").strip()

    conn = get_db()

    books = conn.execute(
        """
        SELECT * FROM books
        WHERE title LIKE ?
        OR author LIKE ?
        OR category LIKE ?
        ORDER BY title
        """,
        (
            f"%{keyword}%",
            f"%{keyword}%",
            f"%{keyword}%"
        )
    ).fetchall()

    conn.close()

    return render_template(
        "search.html",
        books=books,
        keyword=keyword
    )


if __name__ == "__main__":
    app.run(debug=True)
