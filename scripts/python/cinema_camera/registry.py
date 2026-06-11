"""
Cinema Camera Rig v4.0 — Lens and Body Registry

Extensible registry for lens and camera body providers.
New lenses/bodies register via register_lens() / register_body().
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Optional

from .protocols import CameraState, LensSpec, SensorSpec, FormatSpec


# Type aliases for provider factories
LensProvider = Callable[[Path], LensSpec]
BodyProvider = Callable[[], CameraState]

# Internal registries
_lens_registry: dict[str, LensProvider] = {}
_body_registry: dict[str, BodyProvider] = {}


def register_lens(lens_id: str, provider: LensProvider) -> None:
    """Register a lens provider factory."""
    _lens_registry[lens_id] = provider


def register_body(body_id: str, provider: BodyProvider) -> None:
    """Register a camera body provider factory."""
    _body_registry[body_id] = provider


def get_lens(lens_id: str, json_path: Optional[Path] = None) -> LensSpec:
    """Retrieve a lens spec by ID. Raises KeyError if not registered."""
    if lens_id not in _lens_registry:
        raise KeyError(
            f"Lens '{lens_id}' not registered. "
            f"Available: {list(_lens_registry.keys())}"
        )
    provider = _lens_registry[lens_id]
    if json_path is not None:
        return provider(json_path)
    return provider(Path())


def _repo_root() -> Path:
    """Repo root: $CINEMA_CAMERA_REPO if set, else derived from this file
    (<repo>/scripts/python/cinema_camera/registry.py)."""
    env = os.environ.get("CINEMA_CAMERA_REPO")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3]


def lens_json_dir() -> Path:
    """Directory holding the emitted per-lens JSON specs."""
    return _repo_root() / "cinema_camera" / "lenses"


def resolve_lens(lens_id: str) -> LensSpec:
    """
    Resolve a per-lens id (e.g. 'cooke_ana_i_s35_50mm') to a LensSpec.

    The HDA-facing lens_id is per-lens, while providers register per-family
    ('cooke_ana_i_s35'). The family is the longest registered key that
    prefixes lens_id; the JSON is <repo>/cinema_camera/lenses/<lens_id>.json.

    Raises KeyError with a actionable message on any miss.
    """
    lens_id = (lens_id or "").strip()
    if not lens_id:
        raise KeyError("resolve_lens: empty lens_id")

    family = None
    for key in sorted(_lens_registry, key=len, reverse=True):
        if lens_id == key or lens_id.startswith(key + "_"):
            family = key
            break
    if family is None:
        raise KeyError(
            f"resolve_lens: no registered lens family matches '{lens_id}'. "
            f"Families: {sorted(_lens_registry)}"
        )

    json_path = lens_json_dir() / f"{lens_id}.json"
    if not json_path.exists():
        raise KeyError(
            f"resolve_lens: lens JSON not found: {json_path} "
            f"(re-emit with lenses/_emit_lens_jsons.py?)"
        )
    return _lens_registry[family](json_path)


def list_lens_ids() -> list[str]:
    """All per-lens ids resolvable via resolve_lens() (JSON stems on disk
    that match a registered family)."""
    out = []
    d = lens_json_dir()
    if d.is_dir():
        for p in sorted(d.glob("*.json")):
            stem = p.stem
            if stem.startswith("_"):
                continue
            for key in _lens_registry:
                if stem == key or stem.startswith(key + "_"):
                    out.append(stem)
                    break
    return out


def get_body(body_id: str) -> CameraState:
    """Retrieve a camera body state by ID. Raises KeyError if not registered."""
    if body_id not in _body_registry:
        raise KeyError(
            f"Body '{body_id}' not registered. "
            f"Available: {list(_body_registry.keys())}"
        )
    return _body_registry[body_id]()


def list_lenses() -> list[str]:
    """Return all registered lens IDs."""
    return sorted(_lens_registry.keys())


def list_bodies() -> list[str]:
    """Return all registered body IDs."""
    return sorted(_body_registry.keys())
