#!/usr/bin/env python3

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import db


def cmd_init(args):
    db.init_db()
    print(f"\nAthenaeum ready, our raw library is located at {db.DEFAULT_DB_PATH}\n")


def cmd_add_author(args):
    created = db.add_author(db.get_connection(), args.name)
    if created:
        print(f"\n    ᯓ★ Added {args.name} to lists of authors\n")
    else:
        print(f"\n    ⭑.ᐟ Hmm.. '{args.name}' already here\n")


def cmd_add_book(args):
    conn = db.get_connection()
    book_id = db.add_book(conn, args.title, args.author, args.isbn, args.status)
    print(f"\n    .✦ ݁˖ Added book #{book_id}, {args.title}\n")


def cmd_add_tag(args):
    created = db.add_tag(db.get_connection(), args.name)
    if created:
        print(f"\n    ᯓ★ Added {args.name} as a tag\n")
    else:
        print(f"\n    ⭑.ᐟ Huh, the '{args.name}' tag has already exists.\n")


def cmd_tag(args):
    applied = db.tag_book(db.get_connection(), args.book_id, args.tag)
    if applied:
        print(f"\n    𑣲⋆ Book #{args.book_id} has been tagged with '{args.tag}'\n")
    else:
        print(f"\n    ⭑.ᐟ that tag is available for book #{args.book_id}\n")


def cmd_list(args):
    rows = db.list_books(db.get_connection(), status=args.status, author=args.author, tag=args.tag)
    print_book_rows(rows)


def cmd_search(args):
    rows = db.search_books(db.get_connection(), args.query)
    print_book_rows(rows)


def print_book_rows(rows):
    if not rows:
        print("\n    Uh oh! Looks like you haven't add any books (˶˃𐃷˂˶) add a new book then come here again!\n")
        return
    print()
    for r in rows:
        rating = "★" * r["rating"] if r["rating"] else "☆"
        author = r["author"] or "... (｡· v ·｡) ?"
        tags = f" [{r['tags']}]" if r["tags"] else ""
        print(f"  #{r['id']:<3} {r['title']}  by  {author}  ({r['status']}, {rating}){tags}")
    print()


def cmd_status(args):
    db.update_status(db.get_connection(), args.book_id, args.status)
    print(f"\n    𑣲⋆ Book #{args.book_id} is marked as '{args.status}'\n")


def cmd_rate(args):
    db.rate_book(db.get_connection(), args.book_id, args.rating)
    print(f"\n    𑣲⋆ Book #{args.book_id} got {args.rating}/5 rating!\n")


def cmd_stats(args):
    stats = db.get_stats(db.get_connection())
    print("\nWelcome to ⋅˚₊‧ ୨🕮୧ ‧₊˚ ⋅ Athenaeum Library\n")
    print(f"  We have {stats['total']} total of books")
    print("\n  Which categorized by status,")
    for row in stats["by_status"]:
        print(f"    🕮{row['status']}: {row['c']}")
    print("\n  Or categorized by the top authors,")
    for row in stats["top_authors"]:
        print(f"    ✎ᝰ.{row['name']}: {row['c']}")
    if stats["avg_rating"]:
        print(f"\n  Our books have the average rating of {stats['avg_rating']:.2f}/5")
    print()


BANNER = r"""
   ___ _   _                                            
  / _ \ |_| |__   ___ _ __   __ _  ___ _   _ _ __ ___    
 / /_)/ __| '_ \ / _ \ '_ \ / _` |/ _ \ | | | '_ ` _ \   
/ ___/\ /| | | |  __/ | | | (_| |  __/ |_| | | | | | |  
\/     \__|_| |_|\___|_| |_|\__,_|\___|\__,_|_| |_| |_|
"""
 
QUICKSTART = """\
First time here? Get going with three commands:
 
    python athe-cli.py init
    python athe-cli.py add-book "book title" --author "book author"
    python athe-cli.py list
 
Run `python athe-cli.py <command> -h` for detailed help and examples
on any individual command (e.g. `python athe-cli.py add-book -h`) ദ്ദി(˵ •̀ ᴗ - ˵ ) ✧
"""
 
EPILOG = """\
(๑>◡<๑) examples to try out:
  python athe-cli.py init
  python athe-cli.py add-book "Piranesi" --author "Susanna Clarke" --status reading
  python athe-cli.py tag 1 fantasy
  python athe-cli.py list --status reading
  python athe-cli.py list --tag fantasy
  python athe-cli.py search "piranesi"
  python athe-cli.py status 1 read
  python athe-cli.py rate 1 5
  python athe-cli.py stats
 
Run `python athe-cli.py <command> -h` for help on a specific command. ദ്ദി(˵ •̀ ᴗ - ˵ ) ✧
"""
 
 
def build_parser():
    parser = argparse.ArgumentParser(
        prog="athe-cli.py",
        description=BANNER + "\nWelcome to Athenaeum, a terminal book tracker backed by SQLite.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")
 
    sub.add_parser(
        "init",
        help="Create the database and tables (run this first)",
        description="Creates library.db and all tables. Don't worry, you csn run it again. It won't wipe the existing data.",
        epilog="example:\n  python athe-cli.py init\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    ).set_defaults(func=cmd_init)
 
    p = sub.add_parser(
        "add-author",
        help="Add an author (usually not needed — add-book creates authors automatically)",
        description="Adds an author by name. You typically don't need this directly, since "
                     "add-book will create the author for you if they don't already exist.",
        epilog='example:\n  python athe-cli.py add-author "Susanna Clarke"\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("name", help="Author's full name, or pen name")
    p.set_defaults(func=cmd_add_author)
 
    p = sub.add_parser(
        "add-book",
        help="Add a book to your library, silly",
        description="Adds a book. If --author doesn't exist yet, it'll be created automatically.",
        epilog='examples:\n'
               '  python athe-cli.py add-book "Piranesi"\n'
               '  python athe-cli.py add-book "Piranesi" --author "Susanna Clarke"\n'
               '  python athe-cli.py add-book "Piranesi" --author "Susanna Clarke" --status reading\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("title", help="Book title")
    p.add_argument("--author", default=None, help="Author's name (created automatically if new)")
    p.add_argument("--isbn", default=None, help="ISBN (optional)")
    p.add_argument("--status", default="want-to-read", choices=["want-to-read", "reading", "read"],
                    help="Reading status (default: want-to-read)")
    p.set_defaults(func=cmd_add_book)
 
    p = sub.add_parser(
        "add-tag",
        help="Add a tag (usually not needed — the tag command creates tags automatically)",
        description="Adds a tag by name. You typically don't need this directly, since "
                     "the tag command will create the tag for you if it doesn't already exist.",
        epilog='example:\n  python athe-cli.py add-tag "fantasy"\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("name", help="Tag name")
    p.set_defaults(func=cmd_add_tag)
 
    p = sub.add_parser(
        "tag",
        help="Attach a tag to a book (creates the tag if it's new)",
        description="Attaches a tag to a book by its numeric id. Use `list` or `search` "
                     "first to find a book's id.",
        epilog='example:\n  python athe-cli.py tag 1 fantasy\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("book_id", type=int, help="Book id (see it via `list` or `search`)")
    p.add_argument("tag", help="Tag name")
    p.set_defaults(func=cmd_tag)
 
    p = sub.add_parser(
        "list",
        help="List books, optionally filtered by status/author/tag",
        description="Lists books. With no flags, shows everything. Combine flags to narrow the results.",
        epilog='examples:\n'
               '  python athe-cli.py list\n'
               '  python athe-cli.py list --status reading\n'
               '  python athe-cli.py list --author "Le Guin"\n'
               '  python athe-cli.py list --tag fantasy\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--status", default=None, choices=["want-to-read", "reading", "read"], help="Filter by status")
    p.add_argument("--author", default=None, help="Filter by author name (partial match)")
    p.add_argument("--tag", default=None, help="Filter by exact tag name")
    p.set_defaults(func=cmd_list)
 
    p = sub.add_parser(
        "search",
        help="Full-text search across titles and authors",
        description="Searches titles and authors using SQLite's full-text search (FTS5).",
        epilog='example:\n  python athe-cli.py search "piranesi"\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("query", help="Search text")
    p.set_defaults(func=cmd_search)
 
    p = sub.add_parser(
        "status",
        help="Update a book's reading status",
        description="Updates a book's status. Setting it to 'read' also records today's finished date.",
        epilog='example:\n  python athe-cli.py status 1 read\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("book_id", type=int, help="Book id (see it via `list` or `search`)")
    p.add_argument("status", choices=["want-to-read", "reading", "read"], help="New status")
    p.set_defaults(func=cmd_status)
 
    p = sub.add_parser(
        "rate",
        help="Rate a book from 1 to 5",
        description="Sets a book's rating, from 1 (worst) to 5 (best).",
        epilog='example:\n  python athe-cli.py rate 1 5\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("book_id", type=int, help="Book id (see it via `list` or `search`)")
    p.add_argument("rating", type=int, choices=[1, 2, 3, 4, 5], help="Rating, 1-5")
    p.set_defaults(func=cmd_rate)
 
    sub.add_parser(
        "stats",
        help="Show totals, status breakdown, and top authors",
        description="Shows summary stats: total books, breakdown by status, top authors, average rating.",
        epilog='example:\n  python athe-cli.py stats\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    ).set_defaults(func=cmd_stats)
 
    return parser
 
 
def main():
    parser = build_parser()
    args = parser.parse_args()
 
    if not args.command:
        print(BANNER)
        print(QUICKSTART)
        return
 
    if args.command != "init" and not os.path.exists(db.DEFAULT_DB_PATH):
        print("\n    (ᵕ—ᴗ—) We apologize but it seems like the library haven't been built yet,\n")
        print("    please run python athe-cli.py init to help us build Athenaeum\n")
        return
 
    args.func(args)
 
 
if __name__ == "__main__":
    main()