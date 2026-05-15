"""
Emit cinema_camera/lenses/*.json from the Cooke Python source files.

Emits both:
  - cooke_ana_i_s35_*.json     (10 primes, datasheet 030623)
  - cooke_ana_i_ff_plus_*.json (7  primes, datasheet pending -- skeleton)

Run from repo root:
    python scripts/python/cinema_camera/lenses/_emit_lens_jsons.py

Flags:
    --out <dir>     output dir (default: <repo>/cinema_camera/lenses)
    --family s35|ff_plus|all   emit a single family or both (default: all)
    --dry-run       print what would be written without touching disk
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root_from_this_file() -> Path:
    # this file: scripts/python/cinema_camera/lenses/_emit_lens_jsons.py
    return Path(__file__).resolve().parents[4]


def _emit_family(out_dir: Path, lenses: list[dict], label: str, dry_run: bool) -> None:
    print(f"\n=== {label} ===")
    print(f"  output dir: {out_dir}")
    print(f"  lenses:     {len(lenses)}")
    for lens in lenses:
        out_path = out_dir / f"{lens['lens_id']}.json"
        text = json.dumps(lens, indent=2, ensure_ascii=False) + "\n"
        if dry_run:
            print(f"  [dry-run] {out_path.name}  ({len(text)} bytes)")
        else:
            out_path.write_text(text, encoding="utf-8", newline="\n")
            print(f"  wrote     {out_path.name}  ({len(text)} bytes)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output dir (default: <repo>/cinema_camera/lenses)",
    )
    parser.add_argument(
        "--family",
        choices=("s35", "ff_plus", "all"),
        default="all",
        help="Which lens family to emit (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching disk",
    )
    args = parser.parse_args(argv)

    # Make sibling import work when run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))

    out_dir = args.out or (_repo_root_from_this_file() / "cinema_camera" / "lenses")
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.family in ("s35", "all"):
        from cooke_anamorphic_i_s35 import (
            COOKE_ANA_I_S35_LENSES,
            COOKE_ANA_I_S35_PDF_VERSION,
        )
        _emit_family(
            out_dir,
            COOKE_ANA_I_S35_LENSES,
            f"Cooke Anamorphic/i S35 (datasheet {COOKE_ANA_I_S35_PDF_VERSION})",
            args.dry_run,
        )

    if args.family in ("ff_plus", "all"):
        from cooke_anamorphic_i_ff_plus import (
            COOKE_ANA_I_FF_PLUS_LENSES,
            PDF_VERSION as FF_PLUS_PDF_VERSION,
        )
        _emit_family(
            out_dir,
            COOKE_ANA_I_FF_PLUS_LENSES,
            f"Cooke Anamorphic/i Full Frame Plus (datasheet {FF_PLUS_PDF_VERSION})",
            args.dry_run,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
