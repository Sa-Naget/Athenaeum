#!/usr/bin/env python3

import os
import sqlite3

from flask import Flask, g, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library.db")
COVERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "covers")
ALLOWED_COVER_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS authors (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS books (
    id            INTEGER PRIMARY KEY,
    title         TEXT NOT NULL,
    author_id     INTEGER REFERENCES authors(id),
    isbn          TEXT,
    cover_filename TEXT,
    status        TEXT NOT NULL DEFAULT 'want-to-read'
                  CHECK(status IN ('want-to-read', 'reading', 'read')),
    rating        INTEGER CHECK(rating BETWEEN 1 AND 5),
    added_date    TEXT DEFAULT (datetime('now')),
    finished_date TEXT
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS book_tags (
    book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
    tag_id  INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_books_author ON books(author_id);
CREATE INDEX IF NOT EXISTS idx_books_status ON books(status);

CREATE VIRTUAL TABLE IF NOT EXISTS books_fts USING fts5(title, author_name);

CREATE TRIGGER IF NOT EXISTS books_ai AFTER INSERT ON books BEGIN
    INSERT INTO books_fts(rowid, title, author_name)
    VALUES (new.id, new.title, (SELECT name FROM authors WHERE id = new.author_id));
END;

CREATE TRIGGER IF NOT EXISTS books_au AFTER UPDATE ON books BEGIN
    UPDATE books_fts
    SET title = new.title,
        author_name = (SELECT name FROM authors WHERE id = new.author_id)
    WHERE rowid = new.id;
END;

CREATE TRIGGER IF NOT EXISTS books_ad AFTER DELETE ON books BEGIN
    DELETE FROM books_fts WHERE rowid = old.id;
END;
"""

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5MB cap on uploads

SPINE_COLORS = ["spine-gold", "spine-maroon", "spine-teal"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_FILE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.executescript(SCHEMA)
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(books)")}
    if "cover_filename" not in existing_columns:
        conn.execute("ALTER TABLE books ADD COLUMN cover_filename TEXT")
    conn.commit()
    conn.close()
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
        query = """
            SELECT b.id, b.title, b.isbn, b.cover_filename, a.name AS author, b.status, b.rating,
                   GROUP_CONCAT(DISTINCT t.name) AS tags
            FROM books_fts
            JOIN books b ON books_fts.rowid = b.id
            LEFT JOIN authors a ON b.author_id = a.id
            LEFT JOIN book_tags bt ON b.id = bt.book_id
            LEFT JOIN tags t ON bt.tag_id = t.id
            WHERE books_fts MATCH ?
            GROUP BY b.id
            ORDER BY b.id DESC
        """
        rows = db.execute(query, (search,)).fetchall()
    else:
        query = """
            SELECT b.id, b.title, b.isbn, b.cover_filename, a.name AS author, b.status, b.rating,
                   GROUP_CONCAT(DISTINCT t.name) AS tags
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            LEFT JOIN book_tags bt ON b.id = bt.book_id
            LEFT JOIN tags t ON bt.tag_id = t.id
            WHERE 1=1
        """
        params = []
        if status:
            query += " AND b.status = ?"
            params.append(status)
        if tag:
            query += """ AND b.id IN (
                SELECT bt2.book_id FROM book_tags bt2
                JOIN tags t2 ON bt2.tag_id = t2.id WHERE t2.name = ?
            )"""
            params.append(tag)
        query += " GROUP BY b.id ORDER BY b.id DESC"
        rows = db.execute(query, params).fetchall()

    books = []
    for i, r in enumerate(rows):
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
    app.run(debug=True)