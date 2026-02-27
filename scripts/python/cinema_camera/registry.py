"""
Cinema Camera Rig v4.0 — Lens and Body Registry

Extensible registry for lens and camera body providers.
New lenses/bodies register via register_lens() / register_body().
"""

from __future__ import annotations

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
