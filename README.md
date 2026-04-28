# Tableau Tools

> A small toolkit for working with Tableau workbooks (`.twb` / `.twbx`) without ever opening Tableau Desktop.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

---

## Tools

| Tool                  | What it does                                                                          |
|-----------------------|---------------------------------------------------------------------------------------|
| **SQL editor**        | List and edit every Initial SQL / Custom SQL block; browse SQL inside published datasources via the REST API |
| **Calculated fields** | Browse and edit every calculated field's formula in the TUI (writes back with a `.bak`); export to stdout or CSV; internal IDs resolved to readable names |

---

## Installation

```bash
git clone https://github.com/calreed-prof/Tableau-Tools.git
cd Tableau-Tools
pip install -r requirements.txt
```

Requires **Python 3.10+**. Dependencies: `lxml`, `textual[syntax]` (the latter pulls tree-sitter grammars for in-app SQL highlighting). No native dialogs — the workbook picker is a Textual screen, so it works over SSH/WSL.

### Environment variables (optional)

Create a `.env` file at the repo root for Tableau Server integration (see `.env.example`):

```ini
TABLEAU_SERVER   = 'your-tableau-server.com'
TABLEAU_SITE     = ''                        # leave empty for the default site
TABLEAU_PAT_NAME = 'your-token-name'
TABLEAU_PAT      = 'your-token-secret'
```

These are only needed when a workbook connects to a **published datasource** on Tableau Server and you want to browse its SQL.

---

## Usage

### Interactive launcher (recommended)

```bash
python -m tableau_tools                       # full TUI
python -m tableau_tools path/to/Dashboard.twbx # TUI pre-loaded with this workbook
```

The launcher is a [Textual](https://textual.textualize.io/) TUI: arrow keys to pick a tool, Enter to open it. The workbook picker is a built-in screen (no native dialogs), so it works fine over SSH or in WSL. Each tool screen exposes its own key bindings in the footer. Press **q** on the launcher to quit.

### Direct invocation

```bash
python -m tableau_tools.sql_editor path/to/Dashboard.twbx
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx --format csv
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx --format csv --output calcs.csv
```

---

## SQL editor

Lists every Initial SQL and Custom SQL block in the workbook in a `DataTable`, with the selected entry's SQL shown in a syntax-highlighted `TextArea` below. Edit in place, press `s` to stage your changes, then `w` to write the workbook (a `.bak` copy is made automatically).

When a datasource is backed by a **published datasource on Tableau Server**, it appears as a **Published DS** row. Press `d` to download it via the REST API and expand its SQL inline as additional read-only rows.

The legacy CLI (`python -m tableau_tools.sql_editor <file>`) still works headlessly and uses your `$EDITOR` / `$VISUAL` (Notepad on Windows, nano elsewhere) — useful for scripts.

### Key bindings (SQL editor screen)

| Key          | Action                                                                  |
|--------------|-------------------------------------------------------------------------|
| `↑` / `↓`    | Move between SQL entries — the TextArea below updates instantly         |
| `e`          | Focus the TextArea to start editing                                     |
| `s`          | Stage the current TextArea contents into the in-memory workbook         |
| `w`          | Write the workbook to disk (creates `<file>.bak` first)                 |
| `d`          | Download the selected Published DS row and expand its SQL inline        |
| `r`          | Reload the workbook from disk (only when nothing is staged)             |
| `Esc`        | Back to the launcher (warns if you have unsaved staged edits)           |

---

## Calculated fields

Walks every `<datasource>` and lists one row per calculated field — display name, datasource, and formula. Internal Tableau IDs (e.g. `[Calculation_1234567890]`) in formulas are automatically resolved to their human-readable caption names so cross-field references are easy to follow. Parameters are included but flagged read-only.

In the TUI, edit the formula in the syntax-highlighted `TextArea`, press `s` to stage, then `w` to write the workbook (a `.bak` is made first). On save, captions you typed (e.g. `[Profit Ratio]`) are mapped back to the workbook's internal calc ids so Tableau Desktop sees the same convention it produced. Captions that aren't unique across the workbook are left as-is.

The headless CLI (`python -m tableau_tools.calculated_fields <file>`) remains read-only export — interactive editing is the TUI's job.

### Key bindings (Calculated fields screen)

| Key       | Action                                                      |
|-----------|-------------------------------------------------------------|
| `↑` / `↓` | Move between calc fields — the TextArea below updates       |
| `e`       | Focus the TextArea to start editing                         |
| `s`       | Stage the current formula into the in-memory workbook       |
| `w`       | Write the workbook to disk (creates `<file>.bak` first)     |
| `r`       | Reload from disk (only when nothing is staged)              |
| `x`       | Export all calc fields to `<workbook>.calcs.csv`            |
| `Esc`     | Back to the launcher (warns if you have unsaved staged edits) |

### Stdout

```bash
python -m tableau_tools.calculated_fields Sales_Dashboard.twbx
```

```text
  Found 12 calculated field(s):

  ------------------------------------------------------------
  #1  Profit Ratio  |  Snowflake - Prod
  ------------------------------------------------------------
  SUM([Profit]) / SUM([Sales])

  ------------------------------------------------------------
  #2  High Value Order  |  Snowflake - Prod
  ------------------------------------------------------------
  [Profit Ratio] > 0.3 AND [Sales] > 10000
```

### CSV

```bash
python -m tableau_tools.calculated_fields Sales_Dashboard.twbx --format csv
# → Sales_Dashboard.twbx.calcs.csv
```

Columns: `name, internal_name, datasource, is_parameter, formula`.

---

## How it works

- `.twbx` files are unzipped in memory; the inner `.twb` is parsed with `lxml`.
- Mutating tools hold every other zip member as raw bytes and repack the archive intact on save — extracts, images, and thumbnails are never touched.
- The SQL editor deduplicates entries by `(kind, datasource, sql_text)` so SQL repeated across multiple connection nodes shows up once in the index but is written to every location on save.
- Published datasources are detected by `<connection class="sqlproxy">` in the workbook XML. The REST API client (`tableau_api.py`) uses stdlib `urllib` — no extra dependencies.
- Calculated field formulas are humanized after collection: every `[Calculation_xyz]` internal token is replaced with the field's display name in a single pass. Cross-datasource qualifiers (tokens followed by `.`) are left alone.
- Mutating tools always write a `.bak` copy before modifying the workbook.

---

## Project layout

```
tableau_tools/
├── __init__.py
├── __main__.py                    # boots the Textual TUI
├── common.py                      # workbook load/save/backup, .env loader
├── sql_editor.py                  # SQL pure-logic + legacy CLI REPL
├── calculated_fields.py           # formula extractor with ID humanization
├── tableau_api.py                 # Tableau REST API client (sign-in, download)
└── tui/
    ├── app.py                     # TableauToolsApp + LauncherScreen
    ├── tools.py                   # TOOLS registry
    └── screens/
        ├── workbook_picker.py     # ModalScreen[Path | None]
        ├── sql_editor_screen.py   # SQL editor screen
        └── calculated_fields_screen.py
docs/
└── adding_tools.md                # SOP for adding a new tool
```

Each tool module exposes both a `run(...)` function and a `main()` (argv parsing for `python -m tableau_tools.<tool>`). The TUI screen for the same tool imports the module's pure-logic functions — no duplication. See [docs/adding_tools.md](docs/adding_tools.md) to add a new tool.

---

## Roadmap

- [ ] Bulk find / replace across all SQL blocks
- [ ] Diff preview before write
- [ ] Optional formatter (`sqlfluff` / `sqlparse`) on save
- [ ] Read-only "audit" mode that exports all SQL to a folder

PRs and issues welcome.

---

## License

[MIT](LICENSE) © Caleb Reed
