 """Shared workbook I/O for the Tableau Tools package.

  A `.twb` is raw XML; a `.twbx` is a ZIP containing one `.twb` plus assets
  (extracts, images, thumbnails). When loading a `.twbx` we hold every other
  zip member as raw bytes so they round-trip byte-for-byte on save.
  """

  from __future__ import annotations

  import shutil
  import sys
  import zipfile
  from dataclasses import dataclass, field
  from pathlib import Path

  from lxml import etree


  def _xml_parser() -> etree.XMLParser:
      """Strict parser settings required for Tableau workbook round-tripping.

      - strip_cdata=False: Tableau wraps calc formulas, custom SQL, and parameter
        defaults in CDATA when they contain <, >, &, or quotes. The default
        parser strips these and rewrites them as escaped text on save.
      - resolve_entities=False: workbooks are user-supplied; don't process DTDs.
      """
      return etree.XMLParser(strip_cdata=False, resolve_entities=False, remove_blank_text=False)


  @dataclass
  class Workbook:
      path: Path
      root: etree._Element
      is_twbx: bool
      twb_name: str | None = None
      other_files: dict[str, bytes] = field(default_factory=dict)


  def load_workbook(path: Path) -> Workbook:
      is_twbx = path.suffix.lower() == ".twbx"

      if is_twbx:
          with zipfile.ZipFile(path, "r") as zf:
              twb_names = [n for n in zf.namelist() if n.endswith(".twb")]
              if not twb_names:
                  sys.exit("  ERROR: No .twb found inside the .twbx archive.")
              twb_name = twb_names[0]
              twb_bytes = zf.read(twb_name)
              other_files = {n: zf.read(n) for n in zf.namelist() if n != twb_name}
      else:
          twb_bytes = path.read_bytes()
          twb_name = None
          other_files = {}

      try:
          root = etree.fromstring(twb_bytes, _xml_parser())
      except etree.XMLSyntaxError as exc:
          sys.exit(f"  ERROR: Could not parse XML — {exc}")

      return Workbook(
          path=path,
          root=root,
          is_twbx=is_twbx,
          twb_name=twb_name,
          other_files=other_files,
      )


  def save_workbook(wb: Workbook) -> None:
      new_bytes = etree.tostring(
          wb.root, xml_declaration=True, encoding="UTF-8", standalone=True, pretty_print=False
      )

      if wb.is_twbx:
          tmp = wb.path.with_suffix(".twbx.tmp")
          with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
              zf.writestr(wb.twb_name, new_bytes)
              for name, data in wb.other_files.items():
                  zf.writestr(name, data)
          tmp.replace(wb.path)
      else:
          wb.path.write_bytes(new_bytes)


  def backup(path: Path) -> Path:
      bak = path.with_suffix(path.suffix + ".bak")
      shutil.copy2(path, bak)
      print(f"  [backup] {bak}")
      return bak


  def validate_workbook_path(arg: str) -> Path:
      p = Path(arg)
      if not p.exists():
          sys.exit(f"  ERROR: File not found — {p}")
      if p.suffix.lower() not in (".twb", ".twbx"):
          sys.exit("  ERROR: File must be a .twb or .twbx.")
      return p
