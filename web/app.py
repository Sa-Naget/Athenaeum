#!/usr/bin/env python3

import os
import sys

from flask import Flask, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import db as core_db

COVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "covers")
ALLOWED_COVER_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB cap on uploads

SPINE_COLORS = ["spine-gold", "spine-maroon", "spine-teal"]


def get_db():
    if "db" not in g:
        g.db = core_db.get_connection()
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    core_db.init_db()
    os.makedirs(COVERS_DIR, exist_ok=True)


def allowed_cover_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_COVER_EXTENSIONS


def save_cover_file(file_storage, book_id):
    """Saves an uploaded cover as covers/<book_id>.<ext>, replacing any prior cover
    for this book. Returns the new filename, or None if no valid file was given."""
    if not file_storage or not file_storage.filename:
        return None
    if not allowed_cover_file(file_storage.filename):
        return None

    ext = secure_filename(file_storage.filename).rsplit(".", 1)[1].lower()
    remove_existing_cover_files(book_id)
    filename = f"{book_id}.{ext}"
    file_storage.save(os.path.join(COVERS_DIR, filename))
    return filename


def remove_existing_cover_files(book_id):
    for ext in ALLOWED_COVER_EXTENSIONS:
        path = os.path.join(COVERS_DIR, f"{book_id}.{ext}")
        if os.path.exists(path):
            os.remove(path)


def get_or_create_author(db, name):
    name = name.strip()
    if not name:
        return None
    row = db.execute("SELECT id FROM authors WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO authors (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_tag(db, name):
    name = name.strip()
    row = db.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = db.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid


def fetch_books(db, status=None, tag=None, search=None):
    if search:
        rows = core_db.search_books(db, search)
    else:
        rows = core_db.list_books(db, status=status, tag=tag, newest_first=True)

    books = []
    for r in rows:
        d = dict(r)
        d["tags"] = d["tags"].split(",") if d["tags"] else []
        d["spine"] = SPINE_COLORS[r["id"] % len(SPINE_COLORS)]
        books.append(d)
    return books


@app.route("/")
def index():
    db = get_db()
    status = request.args.get("status") or None
    tag = request.args.get("tag") or None
    search = request.args.get("q") or None
    books = fetch_books(db, status=status, tag=tag, search=search)
    all_tags = [r["name"] for r in db.execute("SELECT name FROM tags ORDER BY name")]
    counts = {
        row["status"]: row["c"]
        for row in db.execute("SELECT status, COUNT(*) AS c FROM books GROUP BY status")
    }
    return render_template(
        "Index.html",
        books=books,
        active_status=status,
        active_tag=tag,
        search=search or "",
        all_tags=all_tags,
        counts=counts,
        total=sum(counts.values()),
    )


@app.route("/add", methods=["GET", "POST"])
def add_book():
    db = get_db()
    if request.method == "POST":
        title = request.form["title"].strip()
        author_name = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip() or None
        status = request.form.get("status", "want-to-read")
        tags_raw = request.form.get("tags", "")

        author_id = get_or_create_author(db, author_name) if author_name else None
        cur = db.execute(
            "INSERT INTO books (title, author_id, isbn, status) VALUES (?, ?, ?, ?)",
            (title, author_id, isbn, status),
        )
        book_id = cur.lastrowid

        for tag_name in [t.strip() for t in tags_raw.split(",") if t.strip()]:
            tag_id = get_or_create_tag(db, tag_name)
            db.execute(
                "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
                (book_id, tag_id),
            )

        cover_filename = save_cover_file(request.files.get("cover"), book_id)
        if cover_filename:
            db.execute("UPDATE books SET cover_filename = ? WHERE id = ?", (cover_filename, book_id))

        db.commit()
        return redirect(url_for("index"))

    return render_template("add-book.html")


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    db = get_db()

    if request.method == "POST":
        title = request.form["title"].strip()
        author_name = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip() or None
        status = request.form.get("status", "want-to-read")
        rating = request.form.get("rating") or None
        tags_raw = request.form.get("tags", "")

        author_id = get_or_create_author(db, author_name) if author_name else None
        finished_clause = ", finished_date = datetime('now')" if status == "read" else ""
        db.execute(
            f"UPDATE books SET title = ?, author_id = ?, isbn = ?, status = ?, rating = ?{finished_clause} WHERE id = ?",
            (title, author_id, isbn, status, int(rating) if rating else None, book_id),
        )

        db.execute("DELETE FROM book_tags WHERE book_id = ?", (book_id,))
        for tag_name in [t.strip() for t in tags_raw.split(",") if t.strip()]:
            tag_id = get_or_create_tag(db, tag_name)
            db.execute(
                "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
                (book_id, tag_id),
            )

        if request.form.get("remove_cover"):
            remove_existing_cover_files(book_id)
            db.execute("UPDATE books SET cover_filename = NULL WHERE id = ?", (book_id,))
        else:
            cover_filename = save_cover_file(request.files.get("cover"), book_id)
            if cover_filename:
                db.execute("UPDATE books SET cover_filename = ? WHERE id = ?", (cover_filename, book_id))

        db.commit()
        return redirect(url_for("index"))

    row = db.execute(
        """
        SELECT b.id, b.title, b.isbn, b.cover_filename, b.status, b.rating, a.name AS author
        FROM books b LEFT JOIN authors a ON b.author_id = a.id
        WHERE b.id = ?
        """,
        (book_id,),
    ).fetchone()
    if row is None:
        return redirect(url_for("index"))

    tag_names = [
        r["name"] for r in db.execute(
            "SELECT t.name FROM tags t JOIN book_tags bt ON t.id = bt.tag_id WHERE bt.book_id = ?",
            (book_id,),
        )
    ]
    return render_template("edit-book.html", book=row, tags=", ".join(tag_names))


@app.route("/books/<int:book_id>/status", methods=["POST"])
def update_status(book_id):
    db = get_db()
    new_status = request.form["status"]
    finished_clause = ", finished_date = datetime('now')" if new_status == "read" else ""
    db.execute(f"UPDATE books SET status = ?{finished_clause} WHERE id = ?", (new_status, book_id))
    db.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/books/<int:book_id>/rate", methods=["POST"])
def rate_book(book_id):
    db = get_db()
    rating = int(request.form["rating"])
    db.execute("UPDATE books SET rating = ? WHERE id = ?", (rating, book_id))
    db.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    db = get_db()
    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()
    return redirect(request.referrer or url_for("index"))


@app.route("/stats")
def stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) AS c FROM books").fetchone()["c"]
    by_status = db.execute("SELECT status, COUNT(*) AS c FROM books GROUP BY status").fetchall()
    top_authors = db.execute(
        """
        SELECT a.name, COUNT(*) AS c
        FROM books b JOIN authors a ON b.author_id = a.id
        GROUP BY a.id ORDER BY c DESC LIMIT 5
        """
    ).fetchall()
    avg_rating = db.execute(
        "SELECT AVG(rating) AS avg_rating FROM books WHERE rating IS NOT NULL"
    ).fetchone()["avg_rating"]
    return render_template(
        "status.html",
        total=total,
        by_status=by_status,
        top_authors=top_authors,
        avg_rating=avg_rating,
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=False)