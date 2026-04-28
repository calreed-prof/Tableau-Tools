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

from .common import backup, load_env, load_workbook, save_workbook, validate_workbook_path


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


def collect_published_datasources(root: etree._Element) -> list:
    """Find datasources backed by a published Tableau datasource (sqlproxy connection)."""
    results = []
    for ds in root.iter("datasource"):
        for conn in ds.iter("connection"):
            if conn.get("class") != "sqlproxy":
                continue
            ds_caption = ds.get("caption") or ds.get("name") or "<unnamed>"
            dbname = conn.get("dbname", "").lstrip("/")
            results.append({
                "kind": "published_datasource",
                "ds_name": ds_caption,
                "published_name": ds_caption,
                "published_dbname": dbname,
                "server": conn.get("server", ""),
                "site": conn.get("site", ""),
                "display_sql": f"[Published on {conn.get('server', 'unknown server')}]",
                "nodes": [],
            })
            break  # one sqlproxy per datasource
    return results


_KIND_LABEL = {
    "initial_sql": "Initial SQL",
    "custom_sql": "Custom SQL",
    "published_datasource": "Published DS",
}


def print_entries(entries: list) -> None:
    print()
    print(f"  {'#':<4}  {'Type':<14}  {'Datasource':<35}  Preview")
    print("  " + "-" * 95)
    has_readonly = False
    for i, e in enumerate(entries, 1):
        label = _KIND_LABEL.get(e["kind"], e["kind"])
        if e.get("read_only"):
            label = f"{label}*"
            has_readonly = True
        ds = e["ds_name"][:34]
        preview = " ".join(e["display_sql"].split())[:58]
        suffix = "..." if e["kind"] != "published_datasource" else ""
        print(f"  {i:<4}  {label:<14}  {ds:<35}  {preview}{suffix}")
    if has_readonly:
        print("  * = read-only (from published datasource; edits not saved)")
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


def _expand_published_ds(ds_root: etree._Element, published_name: str) -> list:
    """Collect SQL entries from a downloaded published datasource and mark them read-only."""
    sub_entries = collect_sql_entries(ds_root)
    for sub in sub_entries:
        sub["read_only"] = True
        sub["ds_name"] = f"{published_name} / {sub['ds_name']}"
    return sub_entries


def _fetch_published_ds(entry: dict) -> etree._Element | None:
    """Sign in, download, and return the XML root for a published datasource."""
    from . import tableau_api

    env = load_env()
    pat_name = env.get("TABLEAU_PAT_NAME")
    pat_secret = env.get("TABLEAU_PAT")
    if not pat_name or not pat_secret:
        print("  ERROR: TABLEAU_PAT_NAME and TABLEAU_PAT must both be set in .env")
        return None

    server = env.get("TABLEAU_SERVER") or entry.get("server")
    if not server:
        print("  ERROR: TABLEAU_SERVER not set in .env and no server found in workbook.")
        return None

    site = entry.get("site") or env.get("TABLEAU_SITE", "")

    site_label = f"site '{site}'" if site else "default site"
    print(f"\n  Connecting to {server} ({site_label}) ...")
    try:
        token, site_id = tableau_api.sign_in(server, site, pat_name, pat_secret)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None

    candidates: list[str] = []
    for name in (entry.get("published_name"), entry.get("published_dbname")):
        if name and name not in candidates:
            candidates.append(name)

    try:
        ds_id = None
        tried: list[str] = []
        for name in candidates:
            print(f"  Signed in. Looking up '{name}' ...")
            ds_id = tableau_api.find_datasource_id(server, token, site_id, name)
            tried.append(name)
            if ds_id is not None:
                break
        if ds_id is None:
            print(f"  ERROR: Datasource not found on server. Tried: {', '.join(repr(n) for n in tried)}")
            return None
        print("  Downloading ...", end="", flush=True)
        last = [0]

        def _tick(done: int, total: int | None) -> None:
            if total and done - last[0] >= total // 20 or done == total:
                print(".", end="", flush=True)
                last[0] = done

        try:
            return tableau_api.download_datasource_xml(server, token, site_id, ds_id, progress_cb=_tick)
        finally:
            print()
    except RuntimeError as exc:
        print(f"  ERROR: {exc}")
        return None
    finally:
        tableau_api.sign_out(server, token)


def run(workbook_path: Path) -> None:
    wb = load_workbook(workbook_path)
    sql_entries = collect_sql_entries(wb.root)
    pub_entries = collect_published_datasources(wb.root)
    entries = sql_entries + pub_entries

    if not entries:
        print("\n  No Initial SQL, Custom SQL, or published datasources found in this workbook.\n")
        return

    print(f"\n  Found {len(entries)} SQL block(s) in '{workbook_path.name}':")
    print_entries(entries)

    modified = False
    prompt = "  Command (#=edit/view  show <#>=print full SQL  list  q): "

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
                    entry = entries[n - 1]
                    if entry["kind"] == "published_datasource":
                        print(f"  '{entry['ds_name']}' is a published datasource — select it by number to download and expand its SQL inline.")
                    else:
                        print_full_sql(n, entry)
                else:
                    print(f"  Number must be between 1 and {len(entries)}.")
            else:
                print("  Usage: show <#>   e.g. show 2")
            continue

        if raw.isdigit():
            n = int(raw)
            if 1 <= n <= len(entries):
                entry = entries[n - 1]
                if entry["kind"] == "published_datasource":
                    ds_root = _fetch_published_ds(entry)
                    if ds_root is not None:
                        sub_entries = _expand_published_ds(ds_root, entry["published_name"])
                        entries[n - 1 : n] = sub_entries
                        if sub_entries:
                            print(f"\n  Loaded {len(sub_entries)} SQL block(s) from '{entry['published_name']}'.")
                        else:
                            print(f"\n  No SQL found in '{entry['published_name']}'.")
                        print_entries(entries)
                elif entry.get("read_only"):
                    print(f"\n  Viewing #{n}: {entry['ds_name']} (read-only — edits will not be saved)\n")
                    open_in_editor(get_sql(entry))
                else:
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
