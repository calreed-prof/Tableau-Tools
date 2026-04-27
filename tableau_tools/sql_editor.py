"""Edit Initial SQL and Custom SQL in a Tableau workbook (.twb / .twbx).

Usage:
    python -m tableau_tools.sql_editor <path/to/workbook.twb|.twbx>

Commands inside the tool:
    list          Re-print the SQL index table
    show <#>      Print the FULL SQL for entry # directly in the terminal
    <#>           Open entry # in your editor ($EDITOR / Notepad / nano)
    q             Quit (saves if any edits were made)
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

from lxml import etree

from .common import backup, load_workbook, save_workbook, validate_workbook_path


def open_in_editor(sql: str) -> str:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        editor = "notepad" if platform.system() == "Windows" else "nano"

    with tempfile.NamedTemporaryFile(
        suffix=".sql", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(sql)
        tmp = f.name

    print(f"\n  Opening {tmp} in '{editor}' — save and close to continue.\n")
    try:
        subprocess.run(editor.split() + [tmp], check=True)
    except FileNotFoundError:
        print(f"  Editor '{editor}' not found. Falling back to inline paste.")
        print("  Paste new SQL below. Type END on its own line when done:")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        os.unlink(tmp)
        return "\n".join(lines)

    with open(tmp, "r", encoding="utf-8") as f:
        result = f.read()
    os.unlink(tmp)
    return result


def get_sql(entry: dict) -> str:
    node, attr = entry["nodes"][0]
    if attr:
        return node.get(attr, "")
    return node.text or ""


def set_sql(entry: dict, new_sql: str) -> None:
    for node, attr in entry["nodes"]:
        if attr:
            node.set(attr, new_sql)
        else:
            node.text = new_sql


def collect_sql_entries(root: etree._Element) -> list:
    """Walk every <datasource>; group SQL by (kind, datasource, sql_text).

    Tableau workbooks frequently repeat the same SQL across multiple
    connection nodes. We surface one entry per unique SQL but track every
    matching node so a single edit propagates to all of them.
    """
    groups: dict = {}

    def add(node, attr, kind, ds_name, **kwargs):
        sql = (node.get(attr, "") if attr else (node.text or "")).strip()
        if not sql:
            return
        key = (kind, ds_name, sql)
        if key in groups:
            groups[key]["nodes"].append((node, attr))
            return
        groups[key] = dict(
            kind=kind,
            ds_name=ds_name,
            nodes=[(node, attr)],
            display_sql=sql[:120],
            **kwargs,
        )

    for ds in root.iter("datasource"):
        ds_name = ds.get("caption") or ds.get("name") or "<unnamed>"

        for conn in ds.iter("connection"):
            for attr_key in ("initial_sql", "initialsql", "one-time-sql"):
                if attr_key in conn.attrib:
                    add(conn, attr_key, "initial_sql", ds_name)

        for node in ds.iter("initial_sql"):
            add(node, None, "initial_sql", ds_name)

        for rel in ds.iter("relation"):
            if rel.get("type") == "text":
                rel_name = rel.get("name") or rel.get("table") or "<unnamed>"
                add(rel, None, "custom_sql", ds_name, rel_name=rel_name)

    return list(groups.values())


def print_entries(entries: list) -> None:
    print()
    print(f"  {'#':<4}  {'Type':<14}  {'Datasource':<35}  Preview")
    print("  " + "-" * 95)
    for i, e in enumerate(entries, 1):
        label = "Initial SQL" if e["kind"] == "initial_sql" else "Custom SQL"
        ds = e["ds_name"][:34]
        preview = e["display_sql"].replace("\n", " ")[:58]
        print(f"  {i:<4}  {label:<14}  {ds:<35}  {preview}...")
    print()


def print_full_sql(n: int, entry: dict) -> None:
    label = "Initial SQL" if entry["kind"] == "initial_sql" else "Custom SQL"
    sql = get_sql(entry)
    bar = "-" * 60
    print(f"\n  {bar}")
    print(f"  #{n}  {label}  |  {entry['ds_name']}")
    print(f"  {bar}")
    print(sql)
    print(f"  {bar}\n")


def run(workbook_path: Path) -> None:
    wb = load_workbook(workbook_path)
    entries = collect_sql_entries(wb.root)

    if not entries:
        print("\n  No Initial SQL or Custom SQL found in this workbook.\n")
        return

    print(f"\n  Found {len(entries)} SQL block(s) in '{workbook_path.name}':")
    print_entries(entries)

    modified = False
    prompt = "  Command (#=edit  show <#>=view full SQL  list  q): "

    while True:
        raw = input(prompt).strip()
        if not raw:
            continue
        low = raw.lower()

        if low in ("q", "quit", "exit"):
            break

        if low == "list":
            print_entries(entries)
            continue

        if low.startswith("show"):
            parts = low.split()
            if len(parts) == 2 and parts[1].isdigit():
                n = int(parts[1])
                if 1 <= n <= len(entries):
                    print_full_sql(n, entries[n - 1])
                else:
                    print(f"  Number must be between 1 and {len(entries)}.")
            else:
                print("  Usage: show <#>   e.g. show 2")
            continue

        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(entries):
                entry = entries[n - 1]
                current_sql = get_sql(entry)
                print(f"\n  Editing #{n}: {entry['kind']} — {entry['ds_name']}")
                new_sql = open_in_editor(current_sql)
                if new_sql.strip() == current_sql.strip():
                    print("  No changes detected.")
                else:
                    set_sql(entry, new_sql)
                    modified = True
                    print("  Updated in memory.")
            else:
                print(f"  Number must be between 1 and {len(entries)}.")
            continue

        print("  Unknown command. Try a number, 'show <#>', 'list', or 'q'.")

    if not modified:
        print("\n  Nothing changed — workbook not written.\n")
        return

    backup(workbook_path)
    save_workbook(wb)
    print(f"\n  Saved to '{workbook_path}'\n")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    run(validate_workbook_path(sys.argv[1]))


if __name__ == "__main__":
    main()
