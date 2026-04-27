# Tableau Tools

> A small toolkit for working with Tableau workbooks (`.twb` / `.twbx`) without ever opening Tableau Desktop.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

Operates directly on `.twb` / `.twbx` files — no Tableau Server, no Tableau Desktop license required for the scripts themselves.

---

## Tools

| Tool                  | What it does                                                       |
|-----------------------|--------------------------------------------------------------------|
| **SQL editor**        | List and edit every Initial SQL / Custom SQL block in a workbook   |
| **Calculated fields** | Extract every calculated field (name + formula) to stdout or CSV   |

---

## Installation

```bash
git clone https://github.com/calreed-prof/Tableau-Tools.git
cd Tableau-Tools
pip install -r requirements.txt
```

Requires **Python 3.10+**. Dependencies: `lxml`, `rich`, `questionary`. The launcher also uses **tkinter** (stdlib) for the file picker — bundled with Windows/macOS Python; on Linux install `python3-tk` if you don't already have it.

---

## Usage

### Interactive launcher (recommended)

```bash
python -m tableau_tools
```

```text
╭─ Tableau Tools ─────────────────────────╮
│ Edit and inspect Tableau workbooks      │
╰─────────────────────────────────────────╯

? Choose a tool: (Use arrow keys)
 ❯ Edit SQL           — Initial / Custom SQL
   List calc fields   — name + formula
   Quit
```

Arrow keys to pick a tool, then a native file picker opens to select the workbook (filtered to `.twb` / `.twbx`).

### Direct invocation

Each tool can also be run directly:

```bash
python -m tableau_tools.sql_editor path/to/Dashboard.twbx
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx --format csv
python -m tableau_tools.calculated_fields path/to/Dashboard.twbx --format csv --output calcs.csv
```

---

## SQL editor

Lists every Initial SQL and Custom SQL block in the workbook and lets you edit each one in your editor of choice (`$EDITOR` / `$VISUAL`, falling back to Notepad on Windows or nano elsewhere).

### Sample session

```text
  Found 3 SQL block(s) in 'Sales_Dashboard.twbx':

  #     Type            Datasource                           Preview
  -----------------------------------------------------------------------------------------------
  1     Initial SQL     Snowflake - Prod                     SET QUERY_TAG = 'tableau_dashboar...
  2     Custom SQL      Snowflake - Prod                     SELECT region, SUM(amount) AS rev...
  3     Custom SQL      Snowflake - Sandbox                  SELECT * FROM staging.daily_orders...

  Command (#=edit  show <#>=view full SQL  list  q): show 2

  ------------------------------------------------------------
  #2  Custom SQL  |  Snowflake - Prod
  ------------------------------------------------------------
  SELECT region, SUM(amount) AS revenue
  FROM   sales.fact_orders
  WHERE  order_date >= DATEADD(month, -12, CURRENT_DATE)
  GROUP  BY region
  ------------------------------------------------------------

  Command (#=edit  show <#>=view full SQL  list  q): 2

  Editing #2: custom_sql — Snowflake - Prod

    Opening /tmp/tmpXa9b2c.sql in 'code --wait' — save and close to continue.

  Updated in memory.

  Command (#=edit  show <#>=view full SQL  list  q): q

  [backup] Sales_Dashboard.twbx.bak

  Saved to 'Sales_Dashboard.twbx'
```

### Commands

| Command      | What it does                                          |
|--------------|-------------------------------------------------------|
| `<#>`        | Open entry `#` in `$EDITOR`                           |
| `show <#>`   | Print the full SQL for entry `#` in the terminal      |
| `list`       | Re-print the index of SQL blocks                      |
| `q`          | Quit (saves only if anything was edited)              |

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

Read-only. Walks every `<datasource>` and emits one row per calculated field — display name, datasource, and formula. Parameters (which also use the `<calculation>` element) are included but flagged.

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
  #2  Region Bucket  |  Snowflake - Prod
  ------------------------------------------------------------
  IF [Sales] > 100000 THEN "High" ELSE "Low" END
  ...
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
- Mutating tools (SQL editor) hold every other zip member as raw bytes and repack the archive byte-for-byte intact on save (extracts, images, thumbnails are never touched).
- Each `<datasource>` is walked for the relevant XML structures — `<connection>` initial-SQL attributes / `<initial_sql>` / `<relation type="text">` for the SQL editor; `<column> / <calculation class="tableau">` for calculated fields.
- The SQL editor deduplicates entries by `(kind, datasource, sql_text)` so SQL repeated across multiple connection nodes shows up once in the index but is updated in every location on save.
- Mutating tools always write a `.bak` copy before modifying the workbook.

---

## Project layout

```
tableau_tools/
├── __init__.py
├── __main__.py            # interactive launcher
├── common.py              # workbook load/save/backup
├── sql_editor.py
└── calculated_fields.py
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
