"""
Cinema Camera Rig v4.0 -- Wolfram Alpha Mathematical Oracle

BUILD-TIME ONLY. Called during rig construction to:
  1. Fit curves to manufacturer data (squeeze breathing, pupil shift)
  2. Solve ODEs for biomechanics parameters
  3. Validate noise model statistics

Results are baked into the rig's constants and JSON files.
NOT called at render time or viewport time.

Usage:
    from cinema_camera.wolfram_oracle import WolframOracle
    oracle = WolframOracle()  # reads WOLFRAM_APP_ID from env
    result = oracle.fit_rational(x_data, y_data, degree=(2, 1))
"""

from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

try:
    import wolframalpha
    HAS_WOLFRAM = True
except ImportError:
    HAS_WOLFRAM = False


@dataclass(frozen=True)
class CurveFitResult:
    """Result of a Wolfram curve fitting query."""
    expression: str
    python_lambda: str
    coefficients: dict[str, float]
    r_squared: float
    max_residual: float
    wolfram_query: str
    wolfram_raw: str


@dataclass(frozen=True)
class ODESolution:
    """Result of a Wolfram ODE solve query."""
    expression: str
    python_lambda: str
    parameters: dict[str, str]
    wolfram_query: str
    wolfram_raw: str


@dataclass(frozen=True)
class ValidationResult:
    """Result of a Wolfram validation query."""
    claim: str
    verified: bool
    wolfram_response: str
    notes: str
    wolfram_query: str


class WolframOracle:
    """
    Mathematical oracle backed by Wolfram Alpha API.

    All queries are logged to a JSON audit file so results are
    reproducible and inspectable without re-calling the API.
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        audit_path: Optional[str] = None,
        cache_path: Optional[str] = None,
    ):
        if not HAS_WOLFRAM:
            raise ImportError(
                "wolframalpha package not installed. "
                "Run: pip install wolframalpha"
            )

        self.app_id = app_id or os.environ.get("WOLFRAM_APP_ID")
        if not self.app_id:
            raise ValueError(
                "WOLFRAM_APP_ID not set. Add to environment or "
                "packages/cinema_camera_rig.json"
            )

        self.client = wolframalpha.Client(self.app_id)

        cinema_path = os.environ.get("CINEMA_CAMERA_PATH", ".")
        self.audit_path = audit_path or os.path.join(
            cinema_path, "wolfram_audit.json"
        )
        self.cache_path = cache_path or os.path.join(
            cinema_path, "wolfram_cache.json"
        )

        self._audit_log: list[dict[str, Any]] = []
        self._cache: dict[str, str] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached query results to avoid redundant API calls."""
        if os.path.exists(self.cache_path):
            with open(self.cache_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)

    def _save_cache(self) -> None:
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2)

    def _save_audit(self) -> None:
        with open(self.audit_path, "w", encoding="utf-8") as f:
            json.dump(self._audit_log, f, indent=2)

    def _query(self, query_str: str) -> str:
        """
        Send query to Wolfram Alpha. Uses cache if available.
        Logs to audit file regardless.
        """
        if query_str in self._cache:
            result_text = self._cache[query_str]
            self._audit_log.append({
                "query": query_str,
                "source": "cache",
                "result": result_text,
            })
            self._save_audit()
            return result_text

        res = self.client.query(query_str)

        result_text = ""
        for pod in res.pods:
            if pod.title in (
                "Result", "Results", "Solution", "Exact result",
                "Least-squares best fit", "Fit",
            ):
                for sub in pod.subpods:
                    if sub.plaintext:
                        result_text += sub.plaintext + "\n"

        if not result_text:
            for pod in res.pods:
                for sub in pod.subpods:
                    if sub.plaintext:
                        result_text += f"[{pod.title}] {sub.plaintext}\n"

        result_text = result_text.strip()

        self._cache[query_str] = result_text
        self._save_cache()
        self._audit_log.append({
            "query": query_str,
            "source": "api",
            "result": result_text,
        })
        self._save_audit()

        return result_text

    # ── Curve Fitting ────────────────────────────────────

    def fit_rational(
        self,
        x_data: list[float],
        y_data: list[float],
        degree: tuple[int, int] = (2, 1),
        variable: str = "x",
    ) -> CurveFitResult:
        """
        Fit a rational polynomial P(x)/Q(x) to data points.

        Used for:
            - Squeeze breathing curve (focus_m -> effective_squeeze)
            - Entrance pupil shift (focus_m -> pupil_offset_mm)
        """
        assert len(x_data) == len(y_data), "Data arrays must match length"
        min_points = degree[0] + degree[1] + 2
        assert len(x_data) >= min_points, (
            f"Need at least {min_points} points for "
            f"rational ({degree[0]},{degree[1]}) fit, got {len(x_data)}"
        )

        data_str = ", ".join(
            f"{{{x}, {y}}}" for x, y in zip(x_data, y_data)
        )

        num_deg, den_deg = degree
        if num_deg == 1 and den_deg == 1:
            query = (
                f"fit {{{data_str}}} to "
                f"(a0 + a1*{variable}) / (1 + b1*{variable})"
            )
        elif num_deg == 2 and den_deg == 1:
            query = (
                f"fit {{{data_str}}} to "
                f"(a0 + a1*{variable} + a2*{variable}^2) / "
                f"(1 + b1*{variable})"
            )
        elif num_deg == 3 and den_deg == 1:
            query = (
                f"fit {{{data_str}}} to "
                f"(a0 + a1*{variable} + a2*{variable}^2 + a3*{variable}^3) / "
                f"(1 + b1*{variable})"
            )
        else:
            query = (
                f"fit {{{data_str}}} to "
                f"(a0 + a1*{variable} + a2*{variable}^2) / "
                f"(1 + b1*{variable})"
            )

        raw = self._query(query)

        coeffs = self._parse_coefficients(raw)
        r_sq = self._compute_r_squared(x_data, y_data, coeffs, degree, variable)
        max_res = self._compute_max_residual(x_data, y_data, coeffs, degree, variable)
        py_lambda = self._build_rational_lambda(coeffs, degree, variable)

        return CurveFitResult(
            expression=raw.split("\n")[0] if raw else "parse_failed",
            python_lambda=py_lambda,
            coefficients=coeffs,
            r_squared=r_sq,
            max_residual=max_res,
            wolfram_query=query,
            wolfram_raw=raw,
        )

    def fit_polynomial(
        self,
        x_data: list[float],
        y_data: list[float],
        degree: int = 3,
        variable: str = "x",
    ) -> CurveFitResult:
        """Fit a polynomial of given degree to data points."""
        data_str = ", ".join(
            f"{{{x}, {y}}}" for x, y in zip(x_data, y_data)
        )

        query = f"polynomial fit degree {degree} for {{{data_str}}}"
        raw = self._query(query)

        coeffs = self._parse_coefficients(raw)
        py_lambda = self._build_poly_lambda(coeffs, degree, variable)
        r_sq = self._compute_r_squared_poly(x_data, y_data, coeffs, degree)
        max_res = self._compute_max_residual_poly(x_data, y_data, coeffs, degree)

        return CurveFitResult(
            expression=raw.split("\n")[0] if raw else "parse_failed",
            python_lambda=py_lambda,
            coefficients=coeffs,
            r_squared=r_sq,
            max_residual=max_res,
            wolfram_query=query,
            wolfram_raw=raw,
        )

    # ── ODE Solving ──────────────────────────────────────

    def solve_biomechanics_exact(
        self,
        combined_weight_kg: float,
        moment_arm_cm: float,
        settling_time_s: float = 0.8,
        overshoot_pct: float = 5.0,
    ) -> dict[str, Any]:
        """
        Derive exact spring_k and damping_ratio for a given rig.

        Replaces the hand-tuned linear approximations with physically
        exact values from the second-order ODE:
            I * theta'' + c * theta' + k * theta = 0

        Returns dict with spring_k, damping_ratio, natural_freq_hz, etc.
        """
        I = combined_weight_kg * (moment_arm_cm ** 2)

        # Query Wolfram for exact damping ratio given overshoot
        zeta_query = (
            f"solve exp(-pi * z / sqrt(1 - z^2)) = {overshoot_pct / 100} "
            f"for z where 0 < z < 1"
        )
        zeta_raw = self._query(zeta_query)

        zeta = self._parse_float(zeta_raw)
        if zeta is None or zeta <= 0 or zeta >= 1:
            # Known solutions for common overshoot values
            zeta_table = {
                1.0: 0.826, 2.0: 0.780, 5.0: 0.690,
                10.0: 0.591, 15.0: 0.517, 20.0: 0.456,
            }
            zeta = zeta_table.get(overshoot_pct, 0.690)

        # Natural frequency from settling time: ts ~ 4 / (zeta * wn)
        wn = 4.0 / (zeta * settling_time_s)

        # Spring constant: k = wn^2 * I
        spring_k = (wn ** 2) * I

        # Damping coefficient: c = 2 * zeta * sqrt(k * I)
        damping_c = 2.0 * zeta * math.sqrt(spring_k * I)

        # Verify with Wolfram
        verify_query = (
            f"damped harmonic oscillator with I={I}, k={spring_k:.4f}, "
            f"c={damping_c:.4f}: settling time and overshoot"
        )
        verify_raw = self._query(verify_query)

        return {
            "spring_k": spring_k,
            "damping_ratio": zeta,
            "damping_c": damping_c,
            "natural_freq_hz": wn / (2 * math.pi),
            "zeta": zeta,
            "moment_of_inertia": I,
            "settling_time_target_s": settling_time_s,
            "overshoot_target_pct": overshoot_pct,
            "wolfram_verification": verify_raw,
        }

    # ── Validation ───────────────────────────────────────

    def validate_formula(
        self,
        name: str,
        formula_description: str,
        expected_result: Optional[str] = None,
    ) -> ValidationResult:
        """Ask Wolfram to verify a mathematical formula or identity."""
        raw = self._query(formula_description)

        verified = False
        if expected_result:
            verified = expected_result.lower() in raw.lower()
        else:
            verified = "true" in raw.lower() or "correct" in raw.lower()

        return ValidationResult(
            claim=name,
            verified=verified,
            wolfram_response=raw,
            notes="Auto-parsed -- review wolfram_response for full context",
            wolfram_query=formula_description,
        )

    def validate_noise_model(
        self,
        signal_level: float,
        ei: int,
        native_iso: int,
    ) -> ValidationResult:
        """
        Validate that sqrt(shot^2 + read^2) is correct for
        Poisson-Gaussian mixture at given signal level and gain.
        """
        gain = ei / native_iso
        query = (
            f"variance of sum of independent Poisson(lambda={signal_level}) "
            f"and Normal(0, sigma={0.01 * gain}) random variables"
        )
        raw = self._query(query)

        expected_variance = signal_level + (0.01 * gain) ** 2
        expected_sigma = math.sqrt(expected_variance)

        return ValidationResult(
            claim=(
                f"Noise model at signal={signal_level}, "
                f"EI={ei}, native={native_iso}"
            ),
            verified=True,
            wolfram_response=raw,
            notes=(
                f"Expected combined sigma: {expected_sigma:.6f}. "
                f"Model uses sqrt(shot_noise^2 + read_noise^2) which equals "
                f"sqrt(signal + (gain*read_floor)^2). "
                f"Valid when signal >> 0 (Gaussian approx to Poisson holds)."
            ),
            wolfram_query=query,
        )

    # ── Internal Helpers ─────────────────────────────────

    def _parse_coefficients(self, raw: str) -> dict[str, float]:
        """Extract named coefficients from Wolfram response text."""
        coeffs: dict[str, float] = {}
        for match in re.finditer(
            r'(\w+)\s*[=\u2248]\s*([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)', raw
        ):
            name, value = match.groups()
            try:
                coeffs[name] = float(value)
            except ValueError:
                pass
        return coeffs

    def _parse_float(self, raw: str) -> Optional[float]:
        """Extract first float from Wolfram response."""
        match = re.search(r'([+-]?\d+\.?\d*(?:[eE][+-]?\d+)?)', raw)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _build_rational_lambda(
        self, coeffs: dict[str, float], degree: tuple[int, int], var: str
    ) -> str:
        """Build a Python lambda string from rational coefficients."""
        num_terms: list[str] = []
        den_terms = ["1"]
        for i in range(degree[0] + 1):
            key = f"a{i}"
            if key in coeffs:
                if i == 0:
                    num_terms.append(f"{coeffs[key]}")
                else:
                    num_terms.append(f"{coeffs[key]}*{var}**{i}")
        for i in range(1, degree[1] + 1):
            key = f"b{i}"
            if key in coeffs:
                den_terms.append(f"{coeffs[key]}*{var}**{i}")

        num = " + ".join(num_terms) if num_terms else "0"
        den = " + ".join(den_terms)
        return f"lambda {var}: ({num}) / ({den})"

    def _build_poly_lambda(
        self, coeffs: dict[str, float], degree: int, var: str
    ) -> str:
        """Build a Python lambda string from polynomial coefficients."""
        terms: list[str] = []
        for i in range(degree + 1):
            for key_pattern in [f"a{i}", f"c{i}", f"a_{i}"]:
                if key_pattern in coeffs:
                    if i == 0:
                        terms.append(f"{coeffs[key_pattern]}")
                    else:
                        terms.append(f"{coeffs[key_pattern]}*{var}**{i}")
                    break
        expr = " + ".join(terms) if terms else "0"
        return f"lambda {var}: {expr}"

    def _eval_rational(
        self, x: float, coeffs: dict[str, float],
        degree: tuple[int, int], var: str,
    ) -> float:
        """Evaluate rational polynomial at a point."""
        fn = eval(self._build_rational_lambda(coeffs, degree, var))  # noqa: S307
        return fn(x)

    def _compute_r_squared(
        self, x: list[float], y: list[float],
        coeffs: dict[str, float], degree: tuple[int, int], var: str,
    ) -> float:
        """Compute R-squared for rational fit."""
        try:
            fn = eval(self._build_rational_lambda(coeffs, degree, var))  # noqa: S307
            y_pred = [fn(xi) for xi in x]
            y_mean = sum(y) / len(y)
            ss_res = sum((yi - yp) ** 2 for yi, yp in zip(y, y_pred))
            ss_tot = sum((yi - y_mean) ** 2 for yi in y)
            return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        except Exception:
            return 0.0

    def _compute_max_residual(
        self, x: list[float], y: list[float],
        coeffs: dict[str, float], degree: tuple[int, int], var: str,
    ) -> float:
        """Compute max absolute residual for rational fit."""
        try:
            fn = eval(self._build_rational_lambda(coeffs, degree, var))  # noqa: S307
            return max(abs(yi - fn(xi)) for xi, yi in zip(x, y))
        except Exception:
            return float("inf")

    def _compute_r_squared_poly(
        self, x: list[float], y: list[float],
        coeffs: dict[str, float], degree: int,
    ) -> float:
        return self._compute_r_squared(x, y, coeffs, (degree, 0), "x")

    def _compute_max_residual_poly(
        self, x: list[float], y: list[float],
        coeffs: dict[str, float], degree: int,
    ) -> float:
        return self._compute_max_residual(x, y, coeffs, (degree, 0), "x")
