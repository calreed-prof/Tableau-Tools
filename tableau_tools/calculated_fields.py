"""Extract every calculated field (name + formula) from a Tableau workbook.

Usage:
    python -m tableau_tools.calculated_fields <workbook.twb|.twbx>
    python -m tableau_tools.calculated_fields <workbook.twb|.twbx> --format csv [--output out.csv]

Calculated fields live as:
    <datasource>
      <column caption="My Calc" name="[Calculation_xyz]" ...>
        <calculation class="tableau" formula="SUM([Sales])" />
      </column>
    </datasource>
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from lxml import etree

from .common import load_workbook, validate_workbook_path


def _strip_brackets(name: str) -> str:
    if name.startswith("[") and name.endswith("]"):
        return name[1:-1]
    return name


def collect_calculated_fields(root: etree._Element) -> list[dict]:
    """Return one entry per <column> with a tableau-class <calculation> child.

    Skips columns whose calculation has no formula (parameters fall here for
    some workbook versions — they carry a literal value, not a formula).
    """
    results: list[dict] = []

    for ds in root.iter("datasource"):
        ds_caption = ds.get("caption") or ds.get("name") or "<unnamed>"
        ds_internal = ds.get("name") or ""
        is_parameters = ds_internal == "Parameters"

        for col in ds.iter("column"):
            calc = col.find("calculation")
            if calc is None:
                continue
            if calc.get("class") != "tableau":
                continue
            formula = calc.get("formula")
            if not formula:
                continue

            results.append(
                {
                    "name": col.get("caption") or _strip_brackets(col.get("name", "")),
                    "internal_name": col.get("name", ""),
                    "datasource": ds_caption,
                    "is_parameter": is_parameters,
                    "formula": formula,
                }
            )

    return results


def print_stdout(entries: list[dict]) -> None:
    if not entries:
        print("\n  No calculated fields found in this workbook.\n")
        return

    print(f"\n  Found {len(entries)} calculated field(s):\n")
    for i, e in enumerate(entries, 1):
        tag = " [parameter]" if e["is_parameter"] else ""
        bar = "-" * 60
        print(f"  {bar}")
        print(f"  #{i}  {e['name']}{tag}  |  {e['datasource']}")
        print(f"  {bar}")
        print(e["formula"])
        print()


def write_csv(entries: list[dict], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["name", "internal_name", "datasource", "is_parameter", "formula"],
        )
        writer.writeheader()
        writer.writerows(entries)
    print(f"  Wrote {len(entries)} calculated field(s) to {out_path}")


def run(workbook_path: Path, fmt: str = "stdout", output: Path | None = None) -> None:
    wb = load_workbook(workbook_path)
    entries = collect_calculated_fields(wb.root)

    if fmt == "csv":
        out = output or workbook_path.with_suffix(workbook_path.suffix + ".calcs.csv")
        write_csv(entries, out)
    else:
        print_stdout(entries)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m tableau_tools.calculated_fields",
        description="Extract calculated fields from a Tableau workbook.",
    )
    parser.add_argument("workbook", help="Path to a .twb or .twbx file")
    parser.add_argument(
        "--format",
        choices=("stdout", "csv"),
        default="stdout",
        help="Output format (default: stdout)",
    )
    parser.add_argument(
        "--output",
        help="CSV output path (default: <workbook>.calcs.csv). Only used with --format csv.",
    )
    args = parser.parse_args()

    run(
        validate_workbook_path(args.workbook),
        fmt=args.format,
        output=Path(args.output) if args.output else None,
    )


if __name__ == "__main__":
    main()
