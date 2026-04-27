#!/usr/bin/env python3
"""
tableau_sql_editor.py
---------------------
Edit Initial SQL and Custom SQL in a Tableau workbook (.twb / .twbx)
WITHOUT loading it in Tableau.

Author: Caleb

Usage:
    python tableau_sql_editor.py <path/to/workbook.twb>
    python tableau_sql_editor.py <path/to/workbook.twbx>

Commands inside the tool:
    list          Re-print the SQL index table
    show <#>      Print the FULL SQL for entry # directly in the terminal
    <#>           Open entry # in your editor ($EDITOR / Notepad / nano)
    q             Quit (saves if any edits were made)

Features:
  - Deduplicates by stable tree-path key (not Python object id)
  - Works on both .twb (XML) and .twbx (ZIP containing .twb)
  - Opens selected SQL in $EDITOR (set EDITOR=code --wait for VS Code)
  - Writes changes back; always creates a .bak backup first

Testing
"""

import os
import sys
import shutil
import zipfile
import tempfile
import platform
import subprocess
from pathlib import Path
from lxml import etree


# ---------------------------------------------------------------------------
# Stable node key — XPath-style ancestor path
# ---------------------------------------------------------------------------

def node_key(node: etree._Element, attr: str | None) -> str:
    """
    Build a stable string key from the node's position in the tree.
    Uses the tag and sibling-index of every ancestor so it never changes
    between iterations (unlike id() which depends on Python object identity).
    """
    parts = []
    el = node
    while el is not None:
        parent = el.getparent()
        if parent is not None:
            siblings = [c for c in parent if c.tag == el.tag]
            idx = siblings.index(el)
            parts.append(f"{el.tag}[{idx}]")
        else:
            parts.append(el.tag)
        el = parent
    key = "/".join(reversed(parts))
    return f"{key}@{attr}" if attr else key


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup(path: Path) -> Path:
    bak = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, bak)
    print(f"  [backup] {bak}")
    return bak


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def get_sql(entry: dict) -> str:
    node, attr = entry["nodes"][0]
    if attr:
        return node.get(attr, "")
    return node.text or ""


def set_sql(entry: dict, new_sql: str):
    for node, attr in entry["nodes"]:
        if attr:
            node.set(attr, new_sql)
        else:
            node.text = new_sql

# ---------------------------------------------------------------------------
# Collect SQL entries — deduplicated by stable tree-path key
# ---------------------------------------------------------------------------

def collect_sql_entries(root: etree._Element) -> list:
    groups: dict = {}  # key -> entry dict with list of (node, attr)

    def add(node, attr, kind, ds_name, **kwargs):
        sql = (node.get(attr, "") if attr else (node.text or "")).strip()
        if not sql:
            return
        # Dedupe key: kind + datasource caption + SQL content
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


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_entries(entries: list):
    print()
    print(f"  {'#':<4}  {'Type':<14}  {'Datasource':<35}  Preview")
    print("  " + "-" * 95)
    for i, e in enumerate(entries, 1):
        label   = "Initial SQL" if e["kind"] == "initial_sql" else "Custom SQL"
        ds      = e["ds_name"][:34]
        preview = e["display_sql"].replace("\n", " ")[:58]
        print(f"  {i:<4}  {label:<14}  {ds:<35}  {preview}...")
    print()


def print_full_sql(n: int, entry: dict):
    label = "Initial SQL" if entry["kind"] == "initial_sql" else "Custom SQL"
    sql   = get_sql(entry)
    bar   = "-" * 60
    print(f"\n  {bar}")
    print(f"  #{n}  {label}  |  {entry['ds_name']}")
    print(f"  {bar}")
    print(sql)
    print(f"  {bar}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(workbook_path: Path):
    is_twbx = workbook_path.suffix.lower() == ".twbx"

    if is_twbx:
        with zipfile.ZipFile(workbook_path, "r") as zf:
            twb_names = [n for n in zf.namelist() if n.endswith(".twb")]
            if not twb_names:
                sys.exit("  ERROR: No .twb found inside the .twbx archive.")
            twb_name    = twb_names[0]
            twb_bytes   = zf.read(twb_name)
            other_files = {n: zf.read(n) for n in zf.namelist() if n != twb_name}
    else:
        twb_bytes   = workbook_path.read_bytes()
        twb_name    = None
        other_files = {}

    try:
        root = etree.fromstring(twb_bytes)
    except etree.XMLSyntaxError as exc:
        sys.exit(f"  ERROR: Could not parse XML — {exc}")

    entries = collect_sql_entries(root)

    if not entries:
        print("\n  No Initial SQL or Custom SQL found in this workbook.\n")
        return

    print(f"\n  Found {len(entries)} SQL block(s) in '{workbook_path.name}':")
    print_entries(entries)

    modified = False
    prompt   = "  Command (#=edit  show <#>=view full SQL  list  q): "

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
                entry       = entries[n - 1]
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
    new_bytes = etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=False)

    if is_twbx:
        tmp = workbook_path.with_suffix(".twbx.tmp")
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(twb_name, new_bytes)
            for name, data in other_files.items():
                zf.writestr(name, data)
        tmp.replace(workbook_path)
    else:
        workbook_path.write_bytes(new_bytes)

    print(f"\n  Saved to '{workbook_path}'\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    p = Path(sys.argv[1])
    if not p.exists():
        sys.exit(f"  ERROR: File not found — {p}")
    if p.suffix.lower() not in (".twb", ".twbx"):
        sys.exit("  ERROR: File must be a .twb or .twbx.")

    run(p)
