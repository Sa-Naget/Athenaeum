# 📖 Athenaeum

A little book tracker that comes in two flavors: a terminal CLI and a local website, both talking to the exact same SQLite database. No cloud, no accounts, just files on your own machine (｡•ᴗ•｡)

## Structure ⋆｡°✩

```
athenaeum/
├── core/
│   └── db.py           ← schema + all query logic, shared by both interfaces
├── cli/
│   └── athe-cli.py     ← terminal version
├── web/
│   ├── app.py          ← website version (Flask)
│   ├── templates/
│   └── static/
└── library.db          ← created automatically, shared by both ♪
```

Only one place knows the schema: `core/db.py`. Both `athenaeum_cli.py` and `app.py` are thin wrappers around it, so fixing a bug or adding a column happens once and both interfaces pick it up. Add a book from the terminal, see it on the website (and vice versa) since they're reading/writing the same `library.db`.

## Usage (｡- ｡)

**Terminal:**
```
python cli/athe-cli.py init
python cli/athe-cli.py add-book "Piranesi" --author "Susanna Clarke"
python cli/athe-cli.py list
python cli/athe-cli.py search "darkness"
python cli/athe-cli.py stats
```

**Website:**
```
pip install -r requirements.txt
python web/app.py
```
then open **http://127.0.0.1:5000** (づ ◕‿◕ )づ

## How it works ('-')♡

- `core/db.py` owns the schema, the FTS5 full-text search setup, and every query (add/list/search/tag/rate/status/stats)
- The CLI just parses args and prints text
- The website just handles routes and renders templates
- Both filter by status/tag/author, support tags as a many-to-many relationship, and share the same stats

## A lil note 𐔌•ﻌ•𐦯

The website runs on Flask's dev server (`debug=True`), which is perfect for "just me, just my laptop" use but isn't meant to be exposed to the internet. Since Athenaeum only lives on your machine, which exactly the point ┐(￣ヮ￣)┌

## Ideas to extend it ⊹₊⟡⋆

- Cover images pulled from Open Library's API by ISBN
- A `reading_log` table + a little progress chart on the stats page
- A `sync` command that's not needed, because there's nothing to sync (it's already the same file!)
- Export your shelf to CSV or Markdown

## All in all

Make it yours! Add a shelf, rename a tab, repaint the spines whatever colors you like ᶻ 𝗓 𐰁