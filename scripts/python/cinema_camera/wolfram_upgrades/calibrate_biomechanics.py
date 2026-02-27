"""
Wolfram upgrade: Derive exact spring/damping from second-order ODE.
Replaces hand-tuned linear approximations in biomechanics.py.
"""

from __future__ import annotations

import json
import os

# Physical targets from real camera operator experience
CALIBRATION_RIGS = [
    {"weight_kg": 5.0,  "arm_cm": 15.0, "settle_s": 0.3, "overshoot_pct": 15.0},
    {"weight_kg": 7.5,  "arm_cm": 18.0, "settle_s": 0.5, "overshoot_pct": 10.0},
    {"weight_kg": 10.0, "arm_cm": 20.0, "settle_s": 0.8, "overshoot_pct": 5.0},
    {"weight_kg": 13.3, "arm_cm": 22.0, "settle_s": 1.2, "overshoot_pct": 2.0},
    {"weight_kg": 20.0, "arm_cm": 25.0, "settle_s": 1.8, "overshoot_pct": 1.0},
]


def calibrate_biomechanics() -> None:
    """
    Solve exact spring/damping for calibration rigs, then fit
    the relationship so derive_biomechanics() uses exact curves.
    """
    from cinema_camera.wolfram_oracle import WolframOracle

    oracle = WolframOracle()

    results = []
    for rig in CALIBRATION_RIGS:
        r = oracle.solve_biomechanics_exact(
            combined_weight_kg=rig["weight_kg"],
            moment_arm_cm=rig["arm_cm"],
            settling_time_s=rig["settle_s"],
            overshoot_pct=rig["overshoot_pct"],
        )
        results.append(r)
        print(f"\nRig {rig['weight_kg']}kg:")
        print(f"  spring_k = {r['spring_k']:.4f}")
        print(f"  damping_ratio = {r['damping_ratio']:.4f}")
        print(f"  natural_freq = {r['natural_freq_hz']:.4f} Hz")

    inertias = [r["moment_of_inertia"] for r in results]
    spring_ks = [r["spring_k"] for r in results]
    dampings = [r["damping_ratio"] for r in results]

    spring_fit = oracle.fit_polynomial(inertias, spring_ks, degree=2, variable="I")
    print(f"\nspring_k(I) = {spring_fit.expression}")
    print(f"  R-squared = {spring_fit.r_squared:.6f}")

    damp_fit = oracle.fit_polynomial(inertias, dampings, degree=2, variable="I")
    print(f"\ndamping_ratio(I) = {damp_fit.expression}")
    print(f"  R-squared = {damp_fit.r_squared:.6f}")

    cinema_path = os.environ["CINEMA_CAMERA_PATH"]
    cal_path = os.path.join(cinema_path, "biomechanics_calibration.json")

    calibration = {
        "method": "wolfram_ode_exact",
        "spring_k_fit": {
            "expression": spring_fit.expression,
            "python_lambda": spring_fit.python_lambda,
            "coefficients": spring_fit.coefficients,
            "r_squared": spring_fit.r_squared,
        },
        "damping_ratio_fit": {
            "expression": damp_fit.expression,
            "python_lambda": damp_fit.python_lambda,
            "coefficients": damp_fit.coefficients,
            "r_squared": damp_fit.r_squared,
        },
        "calibration_points": [
            {
                **rig,
                "spring_k": r["spring_k"],
                "damping_ratio": r["damping_ratio"],
                "damping_c": r["damping_c"],
                "natural_freq_hz": r["natural_freq_hz"],
                "moment_of_inertia": r["moment_of_inertia"],
            }
            for rig, r in zip(CALIBRATION_RIGS, results)
        ],
    }

    with open(cal_path, "w", encoding="utf-8") as f:
        json.dump(calibration, f, indent=2)

    print(f"\nCalibration written to: {cal_path}")
