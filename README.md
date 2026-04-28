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
| **Calculated fields** | Extract every calculated field (name + formula) to stdout or CSV; internal IDs resolved to readable names |

---

## Installation

```bash
git clone https://github.com/calreed-prof/Tableau-Tools.git
cd Tableau-Tools
pip install -r requirements.txt
```

Requires **Python 3.10+**. Dependencies: `lxml`, `rich`, `questionary`. The launcher also uses **tkinter** (stdlib) for the file picker — bundled with Windows/macOS Python; on Linux install `python3-tk` if needed.

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
python -m tableau_tools
```

```text
╭─ Tableau Tools ──────────────────────────────────────────────╮
│ Edit and inspect Tableau workbooks — press Ctrl+C to exit    │
╰──────────────────────────────────────────────────────────────╯

? Choose a tool: (Use arrow keys)
 ❯ Edit SQL           — Initial / Custom SQL
   List calc fields   — name + formula
```

Arrow keys to pick a tool, then a native file picker opens filtered to `.twb` / `.twbx`. After the tool finishes you return to the menu. Press **Ctrl+C** to exit.

### Direct invocation

```bash
python -m tableau_tools.sql_editor path/to/Dashboard.twbx
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx --format csv
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx --format csv --output calcs.csv
```

---

## SQL editor

Lists every Initial SQL and Custom SQL block in the workbook and lets you edit each one in your editor of choice (`$EDITOR` / `$VISUAL`, falling back to Notepad on Windows or nano elsewhere).

When a datasource is backed by a **published datasource on Tableau Server** (rather than a direct database connection), it shows up in the list as a **Published DS** entry. Selecting it downloads the datasource via the REST API and opens a view-only SQL browser for its contents.

### Sample session

```text
  Found 4 SQL block(s) in 'Sales_Dashboard.twbx':

  #     Type            Datasource                           Preview
  -----------------------------------------------------------------------------------------------
  1     Initial SQL     Snowflake - Prod                     SET QUERY_TAG = 'tableau_dashboar...
  2     Custom SQL      Snowflake - Prod                     SELECT region, SUM(amount) AS rev...
  3     Custom SQL      Snowflake - Sandbox                  SELECT * FROM staging.daily_orders...
  4     Published DS    Sales Core                           [Published on tableau.company.com]

  Command (#=edit/view  show <#>=print full SQL  list  q): 4

  Connecting to tableau.company.com ...
  Signed in. Looking up 'Sales Core' ...
  Downloading ...

  SQL in 'Sales Core' (view-only — changes are not saved back to Tableau Server):

  #     Type            Datasource                           Preview
  -----------------------------------------------------------------------------------------------
  1     Custom SQL      Sales Core                           SELECT order_id, region, amount F...

  Command (#=open in editor  show <#>=print  list  q): show 1
  ...
```

### Commands (SQL editor)

| Command      | What it does                                               |
|--------------|------------------------------------------------------------|
| `<#>`        | Open entry `#` in `$EDITOR` (or download + browse if Published DS) |
| `show <#>`   | Print the full SQL for entry `#` in the terminal           |
| `list`       | Re-print the index of SQL blocks                           |
| `q`          | Quit (saves only if anything was edited)                   |

### Choosing your editor

Set `$EDITOR` (or `$VISUAL`) to whatever you prefer:

```bash
export EDITOR="code --wait"   # VS Code
export EDITOR="vim"
export EDITOR="subl -w"       # Sublime Text
```

On Windows without `$EDITOR` set, the script falls back to Notepad.

---

## Calculated fields

Read-only. Walks every `<datasource>` and emits one row per calculated field — display name, datasource, and formula. Internal Tableau IDs (e.g. `[Calculation_1234567890]`) in formulas are automatically resolved to their human-readable caption names so cross-field references are easy to follow. Parameters are included but flagged.

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
├── __main__.py            # interactive launcher (loops until Ctrl+C)
├── common.py              # workbook load/save/backup, .env loader
├── sql_editor.py          # Initial SQL / Custom SQL / Published DS browser
├── calculated_fields.py   # formula extractor with ID humanization
└── tableau_api.py         # Tableau REST API client (sign-in, download)
```

Each tool exposes both a `run(...)` function (used by the launcher) and a `main()` (argv parsing for `python -m tableau_tools.<tool>`).

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
