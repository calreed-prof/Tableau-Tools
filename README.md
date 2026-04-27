# Tableau Tools

> Edit Tableau workbook SQL without ever opening Tableau Desktop.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)](#)

A small toolkit for power users who'd rather work in their terminal than wait for Tableau Desktop to load. Operates directly on `.twb` / `.twbx` files — no Tableau Server, no Tableau Desktop license required for the script itself.

---

## Why?

Updating Initial SQL or Custom SQL in a Tableau workbook normally means:

1. Open Tableau Desktop (slow).
2. Find the data source.
3. Drill into the connection.
4. Edit SQL in a tiny modal with no syntax highlighting.
5. Save and pray.

For a workbook with a dozen data sources, this gets old fast — especially when you're refactoring schema names or doing find-and-replace style edits across an entire dashboard.

**Tableau Tools** lets you list every SQL block in a workbook and edit each one in your editor of choice (VS Code, vim, Sublime, Notepad — whatever `$EDITOR` points at). Changes are written back to the `.twb` / `.twbx`, with a `.bak` safety copy created automatically.

---

## Features

- Lists every **Initial SQL** and **Custom SQL** block across all datasources in a workbook
- Opens each block in your `$EDITOR` (falls back to Notepad on Windows, nano on \*nix)
- Works on both `.twb` (raw XML) and `.twbx` (zipped) workbooks — non-XML assets pass through untouched
- Deduplicates SQL repeated across multiple connection nodes (common in extracts) and updates all instances on save
- Always writes a `.bak` backup before modifying the workbook
- Pure Python — no Tableau Server / Tableau Desktop runtime dependency

---

## Installation

```bash
git clone https://github.com/calreed-prof/Tableau-Tools.git
cd Tableau-Tools
pip install -r requirements.txt
```

Requires **Python 3.10+**.

---

## Usage

```bash
python tableau_sql_editor.py path/to/Dashboard.twb
# or a packaged workbook
python tableau_sql_editor.py path/to/Dashboard.twbx
```

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

## How it works

- `.twbx` files are unzipped in memory; the inner `.twb` is parsed with `lxml`.
- Each `<datasource>` is walked for `<connection>` initial-SQL attributes, `<initial_sql>` elements, and `<relation type="text">` nodes (Custom SQL).
- Entries are deduplicated using a stable XPath-style tree-path key — so SQL that appears in multiple connection nodes shows up once in the index but is updated in every location on save.
- On save, the `.twbx` is repacked with the modified `.twb` plus every original asset (extracts, images, thumbnails) byte-for-byte intact.

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
