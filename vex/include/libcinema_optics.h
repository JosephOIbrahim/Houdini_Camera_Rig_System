// ═══════════════════════════════════════════════════════════
// libcinema_optics.h — Cinema Camera Rig v4.0
//
// Optical math library for Houdini VEX/CVEX shaders.
// Used by: karma_cinema_lens.vfl, COP STMap generator,
//          COP anamorphic flare, COP bokeh effects.
//
// v3.0: CO_DistortionCoeffs, co_apply_distortion, co_undistort,
//       co_generate_bokeh_kernel
// v4.0: co_evaluate_squeeze_curve, co_apply_anamorphic_distortion
// ═══════════════════════════════════════════════════════════

#ifndef __LIBCINEMA_OPTICS_H__
#define __LIBCINEMA_OPTICS_H__


// ════════════════════════════════════════════════════════════
// DISTORTION COEFFICIENTS (Brown-Conrady + Anamorphic)
// ════════════════════════════════════════════════════════════

struct CO_DistortionCoeffs {
    float k1;                   // Radial (barrel/pincushion)
    float k2;                   // Higher-order radial
    float k3;                   // Highest-order radial
    float p1;                   // Tangential
    float p2;                   // Tangential
    float squeeze_uniformity;   // 1.0 = perfect, <1.0 = varies across frame
};


// ════════════════════════════════════════════════════════════
// v3.0 SPHERICAL DISTORTION
// ════════════════════════════════════════════════════════════

// PERF: O(1) per pixel | ~10ms @ 4K | Memory: negligible
vector2
co_apply_distortion(
    vector2 uv_centered;
    CO_DistortionCoeffs coeffs
) {
    float x = uv_centered.x;
    float y = uv_centered.y;

    float r2 = x*x + y*y;
    float r4 = r2 * r2;
    float r6 = r4 * r2;

    // Radial distortion (Brown-Conrady)
    float radial = 1.0 + coeffs.k1*r2 + coeffs.k2*r4 + coeffs.k3*r6;

    // Tangential distortion
    float dx = 2.0*coeffs.p1*x*y + coeffs.p2*(r2 + 2.0*x*x);
    float dy = coeffs.p1*(r2 + 2.0*y*y) + 2.0*coeffs.p2*x*y;

    float distorted_x = x * radial + dx;
    float distorted_y = y * radial + dy;

    return set(distorted_x, distorted_y);
}


// ── Iterative Inverse (Newton-Raphson) ────────────────────
// Maps distorted coordinates back to undistorted coordinates.
// Used by STMap "redistort" mode and comp round-trip validation.

// PERF: O(iterations) per pixel, typically 5-10 | ~30ms @ 4K
vector2
co_undistort(
    vector2 uv_distorted;
    CO_DistortionCoeffs coeffs
) {
    // Newton-Raphson: iteratively refine undistorted position
    // Start with the distorted position as initial guess
    vector2 uv = uv_distorted;
    int max_iter = 10;
    float tolerance = 1e-6;

    for (int iter = 0; iter < max_iter; iter++) {
        // Forward: apply distortion to current guess
        vector2 distorted = co_apply_distortion(uv, coeffs);

        // Error between our distorted guess and the target
        vector2 err = distorted - uv_distorted;

        // Check convergence
        if (length(err) < tolerance) break;

        // Update guess by subtracting error
        // (first-order approximation of the Jacobian inverse)
        uv -= err;
    }

    return uv;
}


// ════════════════════════════════════════════════════════════
// BOKEH KERNEL GENERATOR
// ════════════════════════════════════════════════════════════

// Generates a polygonal iris shape value for a given pixel position.
// Used by COP anamorphic flare builder for FFT convolution kernel.
//
// Returns intensity (0-1) where 1 = inside iris, 0 = outside.

// PERF: O(1) per pixel | <5ms for 512x512 kernel
float
co_generate_bokeh_kernel(
    float cx;               // Centered X coordinate (-1 to 1)
    float cy;               // Centered Y coordinate (-1 to 1)
    int blades;             // Number of iris blades (e.g. 11 for Cooke)
    float squeeze;          // Anamorphic squeeze (1.0 = spherical, 2.0 = 2x)
    float rotation_deg      // Iris blade rotation offset
) {
    // Apply anamorphic squeeze to X axis
    float sx = cx / max(squeeze, 0.01);
    float sy = cy;

    float r = sqrt(sx*sx + sy*sy);
    float theta = atan2(sy, sx) + radians(rotation_deg);

    // Polygonal iris shape
    float blade_angle = M_TWO_PI / (float)blades;
    float sector = theta - blade_angle * floor(theta / blade_angle + 0.5);
    float edge = cos(M_PI / (float)blades) / cos(sector);

    // Smooth edge with anti-aliasing
    float kernel_val = 1.0 - smooth(edge - 0.02, edge + 0.02, r);

    return kernel_val;
}


// ════════════════════════════════════════════════════════════
// v4.0 DYNAMIC SQUEEZE (Mumps)
// ════════════════════════════════════════════════════════════

// Front-anamorphic lenses only achieve nominal squeeze at infinity.
// As focus decreases toward MOD, effective squeeze drops.
// This function interpolates the squeeze curve at a given focus distance.

// PERF: O(n) where n = curve points | <0.001ms | Memory: negligible
float
co_evaluate_squeeze_curve(
    float focus_m;
    float curve_focus[];       // Sorted focus distances (m)
    float curve_squeeze[];     // Corresponding squeeze values
    float nominal_squeeze      // Fallback if arrays empty
) {
    int n = len(curve_focus);
    if (n == 0) return nominal_squeeze;
    if (n != len(curve_squeeze)) return nominal_squeeze;  // guard

    if (focus_m <= curve_focus[0]) return curve_squeeze[0];
    if (focus_m >= curve_focus[n-1]) return curve_squeeze[n-1];

    for (int i = 0; i < n - 1; i++) {
        if (curve_focus[i] <= focus_m && focus_m <= curve_focus[i+1]) {
            float t = (focus_m - curve_focus[i]) /
                      (curve_focus[i+1] - curve_focus[i]);
            return lerp(curve_squeeze[i], curve_squeeze[i+1], t);
        }
    }
    return nominal_squeeze;
}


// ── Anamorphic Distortion with Dynamic Squeeze ─────────────

// PERF: O(1) per pixel | ~15ms @ 4K | Memory: negligible
vector2
co_apply_anamorphic_distortion(
    vector2 uv_centered;
    CO_DistortionCoeffs coeffs;
    float effective_squeeze     // Dynamic squeeze at current focus distance
) {
    float x = uv_centered.x;
    float y = uv_centered.y;

    float r2 = x*x + y*y;
    float r4 = r2 * r2;
    float r6 = r4 * r2;

    // Radial distortion (Brown-Conrady)
    float radial = 1.0 + coeffs.k1*r2 + coeffs.k2*r4 + coeffs.k3*r6;

    // Tangential
    float dx = 2.0*coeffs.p1*x*y + coeffs.p2*(r2 + 2.0*x*x);
    float dy = coeffs.p1*(r2 + 2.0*y*y) + 2.0*coeffs.p2*x*y;

    // Anamorphic squeeze non-uniformity (across frame)
    float sq_var = lerp(1.0, coeffs.squeeze_uniformity, r2);

    // Dynamic squeeze applied to X axis
    // Nominal 2.0x -> effective 1.85x at MOD for front-anamorphic
    float distorted_x = (x * radial + dx) * effective_squeeze;
    float distorted_y = (y * radial + dy) * sq_var;

    return set(distorted_x, distorted_y);
}


#endif // __LIBCINEMA_OPTICS_H__
