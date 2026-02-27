"""
Wolfram upgrade: Fit entrance pupil position as function of focus distance.
Replaces static offset with focus-dependent rational curve.
"""

from __future__ import annotations

import json
import os


def fit_pupil_shift_curves() -> None:
    """Fit rational (1,1) to entrance pupil shift data in lens JSONs."""
    from cinema_camera.wolfram_oracle import WolframOracle

    oracle = WolframOracle()
    cinema_path = os.environ["CINEMA_CAMERA_PATH"]
    lens_dir = os.path.join(cinema_path, "lenses")

    for filename in os.listdir(lens_dir):
        if not filename.endswith(".json") or filename.startswith("_"):
            continue

        filepath = os.path.join(lens_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        mechanics = data.get("mechanics", {})
        shift_data = mechanics.get("entrance_pupil_shift")
        if not shift_data or len(shift_data) < 3:
            continue

        x_data = [p[0] for p in shift_data]
        y_data = [p[1] for p in shift_data]

        result = oracle.fit_rational(x_data, y_data, degree=(1, 1), variable="f")

        print(f"\n{filename} pupil shift:")
        print(f"  Expression: {result.expression}")
        print(f"  R-squared: {result.r_squared:.8f}")
        print(f"  Max residual: {result.max_residual:.4f} mm")

        mechanics["entrance_pupil_shift_fit"] = {
            "type": "rational_1_1",
            "coefficients": result.coefficients,
            "python_lambda": result.python_lambda,
            "r_squared": result.r_squared,
            "max_residual_mm": result.max_residual,
        }
        data["mechanics"] = mechanics

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    print("\nPupil shift curves fitted.")
