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
    float k1;                   // Radial (barrel/pincushion)  | dn 3DE: c2
    float k2;                   // Higher-order radial          | dn 3DE: c4
    float k3;                   // Highest-order radial         | dn 3DE: c6
    float p1;                   // Tangential                   | dn 3DE: v2
    float p2;                   // Tangential                   | dn 3DE: u2
    float squeeze_uniformity;   // 1.0 = perfect, <1.0 = varies across frame
    float cx;                   // Lens-center offset X (dn units; default 0)
    float cy;                   // Lens-center offset Y (dn units; default 0)
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


// ════════════════════════════════════════════════════════════
// v5.0 dn-NORMALIZED 3DE RADIAL-STANDARD (matchmove-portable)
// ════════════════════════════════════════════════════════════
//
// Mirrors scripts/python/cinema_camera/distortion.py, which is verified
// headless: g<->inverse round-trip to 1e-7 dn and analytic-Jacobian ==
// finite-difference (cinema_camera/tests/test_distortion.py). Operates in
// diagonally-normalized (dn) coords -- origin at the lens center, radius = 1
// at the frame corner. The CALLER (lens shader / STMap COP) does NDC<->dn
// normalization: dn = (ndc_xy_aspect_corrected) / (0.5 * image_diagonal).
//
// Brown-Conrady bridge from the existing coeff storage: c2=k1, c4=k2, c6=k3,
// u2=p2, v2=p1 (deg-4 decentering u4=v4=0). Direction: co_undistort_g maps
// DISTORTED -> UNDISTORTED (LDPK g) -- the lens shader applies it directly to
// Karma's distorted raster sample to shoot the ideal rectilinear ray.
// co_redistort_gi is its Newton inverse (undistorted -> distorted), used to
// bake the ST-map "redistort" layer.
//
// ADDITIVE: the v3.0 co_apply_distortion / co_undistort and v4.0 anamorphic
// paths are unchanged; wiring the shader/COP over to these is a deliberate,
// render-verified step (empirical NDC->dn constant must be confirmed on the
// target Karma build first).

// g(distorted) -> undistorted, at a dn point. PERF: O(1) per pixel.
vector2
co_undistort_g(
    vector2 uv_dn;
    CO_DistortionCoeffs c
) {
    float x = uv_dn.x - c.cx;
    float y = uv_dn.y - c.cy;
    float s = x*x + y*y;
    float radial = 1.0 + c.k1*s + c.k2*s*s + c.k3*s*s*s;   // c2, c4, c6
    float a = c.p2;   // u2 (deg-2 decentering; u4 = 0)
    float b = c.p1;   // v2 (v4 = 0)
    float gx = x*radial + (s + 2.0*x*x)*a + 2.0*x*y*b;
    float gy = y*radial + (s + 2.0*y*y)*b + 2.0*x*y*a;
    return set(gx + c.cx, gy + c.cy);
}

// gi(undistorted) -> distorted: Newton with the analytic Jacobian (inlined).
// Quadratic, edge-robust; seed p = q. PERF: O(iters), ~5-10 typical.
vector2
co_redistort_gi(
    vector2 q_dn;
    CO_DistortionCoeffs c;
    int max_iter
) {
    vector2 p = q_dn;
    for (int i = 0; i < max_iter; i++) {
        float x = p.x - c.cx;
        float y = p.y - c.cy;
        float s = x*x + y*y;
        float radial  = 1.0 + c.k1*s + c.k2*s*s + c.k3*s*s*s;
        float dradial = c.k1 + 2.0*c.k2*s + 3.0*c.k3*s*s;   // d(radial)/ds
        float a = c.p2;   // u2
        float b = c.p1;   // v2
        // g(p) - q  (error)
        float gx = x*radial + (s + 2.0*x*x)*a + 2.0*x*y*b;
        float gy = y*radial + (s + 2.0*y*y)*b + 2.0*x*y*a;
        float ex = (gx + c.cx) - q_dn.x;
        float ey = (gy + c.cy) - q_dn.y;
        if (ex*ex + ey*ey < 1e-20) break;
        // analytic Jacobian of g at p (u4=v4=0)
        float j00 = radial + 2.0*x*x*dradial + 6.0*x*a + 2.0*y*b;
        float j01 = 2.0*x*y*dradial + 2.0*y*a + 2.0*x*b;
        float j11 = radial + 2.0*y*y*dradial + 6.0*y*b + 2.0*x*a;
        float j10 = 2.0*x*y*dradial + 2.0*x*b + 2.0*y*a;
        float det = j00*j11 - j01*j10;
        if (abs(det) < 1e-12) break;
        p.x -= ( j11*ex - j01*ey) / det;
        p.y -= (-j10*ex + j00*ey) / det;
    }
    return p;
}


// ════════════════════════════════════════════════════════════
// v5.0 ANAMORPHIC: 3DE "Anamorphic - Standard, Degree 4" (dn)
// ════════════════════════════════════════════════════════════
//
// Mirrors scripts/python/cinema_camera/distortion.py (AnamorphicCoeffs /
// g_anamorphic), verified headless (round-trip, analytic Jacobian == finite
// difference, reduces-to-radial). Per-axis even polynomial in dn coords with
// cos2phi/cos4phi terms -- reproduces the horizontal/vertical asymmetry an
// isotropic radial polynomial cannot. The ~2x SQUEEZE is NOT here: it is the
// separate filmback rescale (rpa) applied in the lens shader's projection.
//
//   s = x^2+y^2;  d = x^2-y^2 (= r^2 cos2phi);  c4 = 2 d^2 - s^2 (= r^4 cos4phi)
//   gx = x (1 + cx02 s + cx22 d + cx04 s^2 + cx24 s d + cx44 c4)
//   gy = y (1 + cy02 s + cy22 d + cy04 s^2 + cy24 s d + cy44 c4)

struct CO_AnamorphicCoeffs {
    float cx02; float cx22; float cx04; float cx24; float cx44;
    float cy02; float cy22; float cy04; float cy24; float cy44;
    float cx; float cy;     // lens-center offset (dn units)
};

// g(distorted) -> undistorted, at a dn point.
vector2
co_anamorphic_undistort_g(
    vector2 uv_dn;
    CO_AnamorphicCoeffs c
) {
    float x = uv_dn.x - c.cx;
    float y = uv_dn.y - c.cy;
    float s = x*x + y*y;
    float d = x*x - y*y;
    float c4 = 2.0*d*d - s*s;
    float rx = 1.0 + c.cx02*s + c.cx22*d + c.cx04*s*s + c.cx24*s*d + c.cx44*c4;
    float ry = 1.0 + c.cy02*s + c.cy22*d + c.cy04*s*s + c.cy24*s*d + c.cy44*c4;
    return set(x*rx + c.cx, y*ry + c.cy);
}

// gi(undistorted) -> distorted: Newton with the analytic Jacobian (inlined).
vector2
co_anamorphic_redistort_gi(
    vector2 q_dn;
    CO_AnamorphicCoeffs c;
    int max_iter
) {
    vector2 p = q_dn;
    for (int i = 0; i < max_iter; i++) {
        float x = p.x - c.cx;
        float y = p.y - c.cy;
        float s = x*x + y*y;
        float d = x*x - y*y;
        float c4 = 2.0*d*d - s*s;
        float rx = 1.0 + c.cx02*s + c.cx22*d + c.cx04*s*s + c.cx24*s*d + c.cx44*c4;
        float ry = 1.0 + c.cy02*s + c.cy22*d + c.cy04*s*s + c.cy24*s*d + c.cy44*c4;
        float ex = (x*rx + c.cx) - q_dn.x;
        float ey = (y*ry + c.cy) - q_dn.y;
        if (ex*ex + ey*ey < 1e-20) break;
        float drx_dx = 2.0*x*(c.cx02 + c.cx22 + 2.0*s*c.cx04 + c.cx24*(d+s) + 2.0*c.cx44*(2.0*d-s));
        float drx_dy = 2.0*y*(c.cx02 - c.cx22 + 2.0*s*c.cx04 + c.cx24*(d-s) - 2.0*c.cx44*(2.0*d+s));
        float dry_dx = 2.0*x*(c.cy02 + c.cy22 + 2.0*s*c.cy04 + c.cy24*(d+s) + 2.0*c.cy44*(2.0*d-s));
        float dry_dy = 2.0*y*(c.cy02 - c.cy22 + 2.0*s*c.cy04 + c.cy24*(d-s) - 2.0*c.cy44*(2.0*d+s));
        float j00 = rx + x*drx_dx;
        float j01 = x*drx_dy;
        float j10 = y*dry_dx;
        float j11 = ry + y*dry_dy;
        float det = j00*j11 - j01*j10;
        if (abs(det) < 1e-12) break;
        p.x -= ( j11*ex - j01*ey) / det;
        p.y -= (-j10*ex + j00*ey) / det;
    }
    return p;
}


// ════════════════════════════════════════════════════════════
// ST-MAP SAMPLING (shared by the render inverse + the COP bake)
// ════════════════════════════════════════════════════════════
//
// The single source of truth for the Nuke/Flame ST-map. Uses the SAME
// square-NDC -> dn normalization as karma_cinema_lens.vfl, so the ST-map bake
// and the rendered distortion are byte-identical (no render-vs-bake drift).
//
//   pixel UV in [0,1]  ->  square NDC [-1,1]  ->  dn  ->  g / gi  ->  UV [0,1]
//   aspect = image aspect (xres/yres). mode 0 = g (co_undistort_g / forward),
//   mode 1 = gi (co_redistort_gi / inverse). g . gi == identity, so a forward
//   bake fed through a backward bake returns to the source pixel (round-trip).

vector2
co_stmap_pixel(vector2 uv01; float aspect; CO_DistortionCoeffs c; int mode)
{
    float e = sqrt(aspect*aspect + 1.0);
    vector2 dn = set((uv01.x*2.0 - 1.0) * aspect / e, (uv01.y*2.0 - 1.0) / e);
    dn = (mode == 0) ? co_undistort_g(dn, c) : co_redistort_gi(dn, c, 10);
    float nx = dn.x * e / aspect;
    float ny = dn.y * e;
    return set(nx*0.5 + 0.5, ny*0.5 + 0.5);
}

vector2
co_stmap_pixel_anamorphic(vector2 uv01; float aspect; CO_AnamorphicCoeffs c; int mode)
{
    float e = sqrt(aspect*aspect + 1.0);
    vector2 dn = set((uv01.x*2.0 - 1.0) * aspect / e, (uv01.y*2.0 - 1.0) / e);
    dn = (mode == 0) ? co_anamorphic_undistort_g(dn, c) : co_anamorphic_redistort_gi(dn, c, 12);
    float nx = dn.x * e / aspect;
    float ny = dn.y * e;
    return set(nx*0.5 + 0.5, ny*0.5 + 0.5);
}


#endif // __LIBCINEMA_OPTICS_H__
