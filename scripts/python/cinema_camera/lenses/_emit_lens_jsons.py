"""
Emit cinema_camera/lenses/cooke_ana_i_s35_*.json from cooke_anamorphic_i_s35.py.

Run from repo root:
    python scripts/python/cinema_camera/lenses/_emit_lens_jsons.py

Or with explicit output dir:
    python ... _emit_lens_jsons.py --out cinema_camera/lenses
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _repo_root_from_this_file() -> Path:
    # this file: scripts/python/cinema_camera/lenses/_emit_lens_jsons.py
    return Path(__file__).resolve().parents[4]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output dir (default: <repo>/cinema_camera/lenses)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching disk",
    )
    args = parser.parse_args(argv)

    # Make sibling import work when run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from cooke_anamorphic_i_s35 import (
        COOKE_ANA_I_S35_LENSES,
        COOKE_ANA_I_S35_PDF_VERSION,
    )

    out_dir = args.out or (_repo_root_from_this_file() / "cinema_camera" / "lenses")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Cooke Anamorphic/i S35 datasheet version: {COOKE_ANA_I_S35_PDF_VERSION}")
    print(f"Output dir: {out_dir}")
    print(f"Lenses to emit: {len(COOKE_ANA_I_S35_LENSES)}")
    print()

    for lens in COOKE_ANA_I_S35_LENSES:
        out_path = out_dir / f"{lens['lens_id']}.json"
        text = json.dumps(lens, indent=2, ensure_ascii=False) + "\n"
        if args.dry_run:
            print(f"  [dry-run] {out_path.name}  ({len(text)} bytes)")
        else:
            out_path.write_text(text, encoding="utf-8", newline="\n")
            print(f"  wrote   {out_path.name}  ({len(text)} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
