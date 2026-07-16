#!/usr/bin/env python3

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db


def cmd_init(args):
    db.init_db()
    print(f"\nDatabase ready at {db.DEFAULT_DB_PATH}\n")


def cmd_add_author(args):
    created = db.add_author(db.get_connection(), args.name)
    if created:
        print(f"\nAdded author: {args.name}\n")
    else:
        print(f"\nAuthor '{args.name}' already exists.\n")


def cmd_add_book(args):
    conn = db.get_connection()
    book_id = db.add_book(conn, args.title, args.author, args.isbn, args.status)
    print(f"\nAdded book #{book_id}: {args.title}\n")


def cmd_add_tag(args):
    created = db.add_tag(db.get_connection(), args.name)
    if created:
        print(f"\nAdded tag: {args.name}\n")
    else:
        print(f"\nTag '{args.name}' already exists.\n")


def cmd_tag(args):
    applied = db.tag_book(db.get_connection(), args.book_id, args.tag)
    if applied:
        print(f"\nTagged book #{args.book_id} with '{args.tag}'\n")
    else:
        print(f"\nBook #{args.book_id} already has tag '{args.tag}'.\n")


def cmd_list(args):
    rows = db.list_books(db.get_connection(), status=args.status, author=args.author, tag=args.tag)
    print_book_rows(rows)


def cmd_search(args):
    rows = db.search_books(db.get_connection(), args.query)
    print_book_rows(rows)


def print_book_rows(rows):
    if not rows:
        print("\nNo books found.\n")
        return
    print()
    for r in rows:
        rating = "*" * r["rating"] if r["rating"] else "unrated"
        author = r["author"] or "unknown author"
        tags = f" [{r['tags']}]" if r["tags"] else ""
        print(f"  #{r['id']:<3} {r['title']}  —  {author}  ({r['status']}, {rating}){tags}")
    print()


def cmd_status(args):
    db.update_status(db.get_connection(), args.book_id, args.status)
    print(f"\nBook #{args.book_id} marked as '{args.status}'\n")


def cmd_rate(args):
    db.rate_book(db.get_connection(), args.book_id, args.rating)
    print(f"\nBook #{args.book_id} rated {args.rating}/5\n")


def cmd_stats(args):
    stats = db.get_stats(db.get_connection())
    print("\n📚 Library stats\n")
    print(f"  Total books: {stats['total']}")
    print("\n  By status:")
    for row in stats["by_status"]:
        print(f"    {row['status']}: {row['c']}")
    print("\n  Top authors:")
    for row in stats["top_authors"]:
        print(f"    {row['name']}: {row['c']}")
    if stats["avg_rating"]:
        print(f"\n  Average rating: {stats['avg_rating']:.2f}/5")
    print()


def main():
    parser = argparse.ArgumentParser(description="Athenaeum — terminal edition")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the database and tables").set_defaults(func=cmd_init)

    p = sub.add_parser("add-author", help="Add an author")
    p.add_argument("name")
    p.set_defaults(func=cmd_add_author)

    p = sub.add_parser("add-book", help="Add a book")
    p.add_argument("title")
    p.add_argument("--author", default=None)
    p.add_argument("--isbn", default=None)
    p.add_argument("--status", default="want-to-read", choices=["want-to-read", "reading", "read"])
    p.set_defaults(func=cmd_add_book)

    p = sub.add_parser("add-tag", help="Add a tag")
    p.add_argument("name")
    p.set_defaults(func=cmd_add_tag)

    p = sub.add_parser("tag", help="Tag a book")
    p.add_argument("book_id", type=int)
    p.add_argument("tag")
    p.set_defaults(func=cmd_tag)

    p = sub.add_parser("list", help="List books")
    p.add_argument("--status", default=None, choices=["want-to-read", "reading", "read"])
    p.add_argument("--author", default=None)
    p.add_argument("--tag", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("search", help="Full-text search books")
    p.add_argument("query")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("status", help="Update a book's status")
    p.add_argument("book_id", type=int)
    p.add_argument("status", choices=["want-to-read", "reading", "read"])
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("rate", help="Rate a book 1-5")
    p.add_argument("book_id", type=int)
    p.add_argument("rating", type=int, choices=[1, 2, 3, 4, 5])
    p.set_defaults(func=cmd_rate)

    sub.add_parser("stats", help="Show library stats").set_defaults(func=cmd_stats)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()