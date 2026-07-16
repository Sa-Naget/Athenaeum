"""
core/db.py — all schema and query logic for Athenaeum, shared between the
CLI and the web app. Neither interface talks to sqlite3 directly; they both
call into this module, so there's exactly one place that knows the schema.
"""

import os
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(PROJECT_ROOT, "library.db")

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


def get_connection(db_path=None):
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path=None):
    conn = get_connection(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def get_or_create_author(conn, name):
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    row = conn.execute("SELECT id FROM authors WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO authors (name) VALUES (?)", (name,))
    return cur.lastrowid


def get_or_create_tag(conn, name):
    name = name.strip()
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid


def add_author(conn, name):
    """Returns True if created, False if it already existed."""
    try:
        conn.execute("INSERT INTO authors (name) VALUES (?)", (name,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def add_tag(conn, name):
    """Returns True if created, False if it already existed."""
    try:
        conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def add_book(conn, title, author_name=None, isbn=None, status="want-to-read", tags=None):
    """Creates a book (auto-creating its author/tags as needed). Returns the new book id."""
    author_id = get_or_create_author(conn, author_name) if author_name else None
    cur = conn.execute(
        "INSERT INTO books (title, author_id, isbn, status) VALUES (?, ?, ?, ?)",
        (title, author_id, isbn, status),
    )
    book_id = cur.lastrowid

    for tag_name in tags or []:
        tag_id = get_or_create_tag(conn, tag_name)
        conn.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )

    conn.commit()
    return book_id


def tag_book(conn, book_id, tag_name):
    """Returns True if the tag was newly applied, False if it was already there."""
    tag_id = get_or_create_tag(conn, tag_name)
    try:
        conn.execute(
            "INSERT INTO book_tags (book_id, tag_id) VALUES (?, ?)",
            (book_id, tag_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def list_books(conn, status=None, author=None, tag=None):
    query = """
        SELECT b.id, b.title, a.name AS author, b.status, b.rating,
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
    if author:
        query += " AND a.name LIKE ?"
        params.append(f"%{author}%")
    if tag:
        query += """ AND b.id IN (
            SELECT bt2.book_id FROM book_tags bt2
            JOIN tags t2 ON bt2.tag_id = t2.id WHERE t2.name = ?
        )"""
        params.append(tag)
    query += " GROUP BY b.id ORDER BY b.id"
    return conn.execute(query, params).fetchall()


def search_books(conn, search_query):
    query = """
        SELECT b.id, b.title, a.name AS author, b.status, b.rating,
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
    return conn.execute(query, (search_query,)).fetchall()


def all_tags(conn):
    return [r["name"] for r in conn.execute("SELECT name FROM tags ORDER BY name")]


def update_status(conn, book_id, status):
    finished_clause = ", finished_date = datetime('now')" if status == "read" else ""
    conn.execute(f"UPDATE books SET status = ?{finished_clause} WHERE id = ?", (status, book_id))
    conn.commit()


def rate_book(conn, book_id, rating):
    conn.execute("UPDATE books SET rating = ? WHERE id = ?", (rating, book_id))
    conn.commit()


def delete_book(conn, book_id):
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()


def get_stats(conn):
    total = conn.execute("SELECT COUNT(*) AS c FROM books").fetchone()["c"]
    by_status = conn.execute("SELECT status, COUNT(*) AS c FROM books GROUP BY status").fetchall()
    top_authors = conn.execute(
        """
        SELECT a.name, COUNT(*) AS c
        FROM books b JOIN authors a ON b.author_id = a.id
        GROUP BY a.id ORDER BY c DESC LIMIT 5
        """
    ).fetchall()
    avg_rating = conn.execute(
        "SELECT AVG(rating) AS avg_rating FROM books WHERE rating IS NOT NULL"
    ).fetchone()["avg_rating"]
    return {
        "total": total,
        "by_status": by_status,
        "top_authors": top_authors,
        "avg_rating": avg_rating,
    }