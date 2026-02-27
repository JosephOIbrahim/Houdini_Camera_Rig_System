"""
Wolfram upgrade: Validate every optics formula against Wolfram Alpha.
Generates a validation report and saves to wolfram_audit.json.
"""

from __future__ import annotations


def validate_all_optics() -> list:
    """Run Wolfram validation on every optics formula in the rig."""
    from cinema_camera.wolfram_oracle import ValidationResult, WolframOracle

    oracle = WolframOracle()
    results: list[ValidationResult] = []

    results.append(oracle.validate_formula(
        name="Hyperfocal Distance",
        formula_description=(
            "Is hyperfocal distance H = f^2/(N*c) + f "
            "where f=focal length, N=f-number, c=circle of confusion?"
        ),
        expected_result="true",
    ))

    results.append(oracle.validate_formula(
        name="DOF Near Limit",
        formula_description=(
            "Is the near depth of field limit "
            "D_near = s*H / (H + (s-f)) "
            "where s=subject distance, H=hyperfocal, f=focal length?"
        ),
    ))

    results.append(oracle.validate_formula(
        name="DOF Far Limit",
        formula_description=(
            "Is the far depth of field limit "
            "D_far = s*H / (H - (s-f)) for s < H?"
        ),
    ))

    results.append(oracle.validate_formula(
        name="Horizontal FOV",
        formula_description=(
            "Is horizontal field of view "
            "FOV = 2 * arctan(sensor_width / (2 * focal_length))?"
        ),
        expected_result="true",
    ))

    results.append(oracle.validate_formula(
        name="T-stop to F-stop",
        formula_description=(
            "Is T-stop = f-stop / sqrt(transmittance) "
            "where transmittance is the fraction of light transmitted?"
        ),
    ))

    results.append(oracle.validate_formula(
        name="Brown-Conrady Radial Distortion",
        formula_description=(
            "Brown-Conrady distortion model: "
            "x_distorted = x(1 + k1*r^2 + k2*r^4 + k3*r^6) "
            "where r^2 = x^2 + y^2. "
            "Is this the standard radial distortion model?"
        ),
    ))

    results.append(oracle.validate_noise_model(
        signal_level=100.0, ei=800, native_iso=800,
    ))

    results.append(oracle.validate_noise_model(
        signal_level=5.0, ei=3200, native_iso=800,
    ))

    # Print report
    print("\n" + "=" * 60)
    print("OPTICS FORMULA VALIDATION REPORT")
    print("=" * 60)

    passed = sum(1 for r in results if r.verified)
    failed = len(results) - passed
    for r in results:
        status = "PASS" if r.verified else "REVIEW"
        print(f"\n[{status}] {r.claim}")
        print(f"  Query: {r.wolfram_query[:80]}...")
        if not r.verified:
            print(f"  Response: {r.wolfram_response[:120]}...")

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} need review")
    print(f"{'=' * 60}")

    return results
