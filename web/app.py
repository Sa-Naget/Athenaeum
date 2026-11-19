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

def parse_tags(raw):
    return [t.strip() for t in raw.split(",") if t.strip()]


@app.route("/")
def index():
    db = get_db()
    status = request.args.get("status") or None
    tag = request.args.get("tag") or None
    search = request.args.get("q") or None
    books = fetch_books(db, status=status, tag=tag, search=search)
    all_tags = core_db.all_tags(db)
    counts = core_db.status_counts(db)
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
        book_id = core_db.add_book(
            db,
            request.form["title"].strip(),
            request.form.get("author", "").strip(),
            request.form.get("isbn", "").strip() or None,
            request.form.get("status", "reading"),
            parse_tags(request.form.get("tags", "")),
        )
        cover_filename = save_cover_file(request.files.get("cover"), book_id)
        if cover_filename:
            core_db.set_cover(db, book_id, cover_filename)
        return redirect(url_for("index"))

    return render_template("add-book.html")


@app.route("/books/<int:book_id>/edit", methods=["GET", "POST"])
def edit_book(book_id):
    db = get_db()

    if request.method == "POST":
        rating = request.form.get("rating") or None
        core_db.update_book(
            db,
            book_id,
            request.form["title"].strip(),
            request.form.get("author", "").strip(),
            request.form.get("isbn", "").strip() or None,
            request.form.get("status", "reading"),
            int(rating) if rating else None,
            parse_tags(request.form.get("tags", "")),
        )

        if request.form.get("remove_cover"):
            remove_existing_cover_files(book_id)
            core_db.set_cover(db, book_id, None)
        else:
            cover_filename = save_cover_file(request.files.get("cover"), book_id)
            if cover_filename:
                core_db.set_cover(db, book_id, cover_filename)
        return redirect(url_for("index"))

    book = core_db.get_book(db, book_id)
    if book is None:
        return redirect(url_for("index"))
    tags = ", ".join(core_db.get_book_tags(db, book_id))
    return render_template("edit-book.html", book=book, tags=tags)


@app.route("/books/<int:book_id>/status", methods=["POST"])
def update_status(book_id):
    core_db.update_status(get_db(), book_id, request.form["status"])
    return redirect(request.referrer or url_for("index"))


@app.route("/books/<int:book_id>/rate", methods=["POST"])
def rate_book(book_id):
    core_db.rate_book(get_db(), book_id, int(request.form["rating"]))
    return redirect(request.referrer or url_for("index"))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id):
    core_db.delete_book(get_db(), book_id)
    return redirect(request.referrer or url_for("index"))


@app.route("/stats")
def stats():
    data = core_db.get_stats(get_db())
    return render_template(
        "status.html",
        **data
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=False)