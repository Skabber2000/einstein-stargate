import math
import os

from flask import Flask, jsonify, render_template, request

G = 6.67430e-11
C = 2.99792458e8
HBAR = 1.054571817e-34
M_SUN = 1.98892e30
M_EARTH = 5.9722e24
PLANCK_LENGTH = math.sqrt(HBAR * G / C**3)
PLANCK_MASS = math.sqrt(HBAR * C / G)
PLANCK_ENERGY = PLANCK_MASS * C**2

app = Flask(__name__)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def _no_cache(resp):
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    return resp


@app.route("/")
def index() -> str:
    return render_template(
        "index.html",
        constants={
            "G": G,
            "c": C,
            "hbar": HBAR,
            "M_sun": M_SUN,
            "M_earth": M_EARTH,
            "l_planck": PLANCK_LENGTH,
            "m_planck": PLANCK_MASS,
            "E_planck": PLANCK_ENERGY,
        },
    )


def _finite_float(raw, default: float, lo: float, hi: float) -> float:
    if raw is None:
        return default
    if str(raw).strip().lower() in {"nan", "inf", "-inf", "+inf", "infinity"}:
        raise ValueError("non-finite input")
    v = float(raw)
    if not math.isfinite(v) or v < lo or v > hi:
        raise ValueError("out of range")
    return v


@app.route("/api/compute")
def compute():
    try:
        M = _finite_float(request.args.get("M"), M_EARTH, 0.0, 1e60)
        b0 = _finite_float(request.args.get("b0"), 1.0, 1e-40, 1e30)
        body_radius = _finite_float(request.args.get("R"), 0.0, 0.0, 1e30)
    except ValueError:
        return jsonify(error="bad input"), 400

    r_s = 2 * G * M / C**2

    # Kretschmann scalar at three sample radii outside horizon
    samples = {}
    if r_s > 0:
        for label, factor in (("rs", 1.0), ("2rs", 2.0), ("10rs", 10.0)):
            r = factor * r_s
            samples[label] = 48 * G**2 * M**2 / (C**4 * r**6)

    # Interior (uniform density) — G^0_0 = 8πGρ/c² in 1/m² (curvature units)
    interior = None
    if body_radius > 0:
        rho = 3 * M / (4 * math.pi * body_radius**3)
        G00 = 8 * math.pi * G * rho / C**2
        interior = {
            "rho_kg_m3": rho,
            "G00_per_m2": G00,
            "compactness": r_s / body_radius,
        }

    # Morris–Thorne style space-gate energy at throat b0
    E_classical = C**4 * b0 / G                 # |∫T_kk| ~ c⁴ b0 / G
    E_qi = HBAR * C / b0                        # Ford–Roman quantum bound
    M_classical = E_classical / C**2

    return jsonify(
        inputs={"M_kg": M, "b0_m": b0, "R_body_m": body_radius},
        schwarzschild={
            "r_s_m": r_s,
            "kretschmann": samples,
        },
        interior=interior,
        space_gate={
            "E_classical_J": E_classical,
            "E_classical_kg": M_classical,
            "E_classical_Msun": M_classical / M_SUN,
            "E_qi_J": E_qi,
            "E_qi_kg": E_qi / C**2,
            "ratio_classical_over_qi": E_classical / E_qi,
            "b0_in_planck_lengths": b0 / PLANCK_LENGTH,
            "E_classical_in_planck_E": E_classical / PLANCK_ENERGY,
        },
        constants={
            "G": G,
            "c": C,
            "hbar": HBAR,
            "M_sun": M_SUN,
            "M_earth": M_EARTH,
            "l_planck": PLANCK_LENGTH,
            "m_planck": PLANCK_MASS,
            "E_planck": PLANCK_ENERGY,
        },
    )


if __name__ == "__main__":
    run_kwargs = {"host": "127.0.0.1", "port": 5000}
    if os.environ.get("FLASK_DEBUG") == "1":
        run_kwargs["debug"] = True
    app.run(**run_kwargs)
