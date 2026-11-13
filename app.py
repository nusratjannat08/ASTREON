"""
ASTREON - Mars Mission Site Intelligence Platform
Application Backend Server
Integrates:
- NASA APIs (api.nasa.gov, data.nasa.gov, code.nasa.gov)
- Evidence-based Scientific Water Resource Potential Engine
- Continuous Solar Illumination, Seasonal Variation & Dust Storm Risk Monitor
- Dynamic Life Support Crisis & Food Rationing Optimizer
- Multi-Criteria Decision Analysis (MCDA) Site Ranking
"""

import os
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify

from scientific_engine import ScientificEngine, DEFAULT_HABITAT, merge_habitat
from nasa_client import NASAClient, DEFAULT_NASA_API_KEY

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "astreon.db"
DATA_PATH = BASE_DIR / "data" / "candidate_sites.json"

app = Flask(__name__, static_folder="static", template_folder="templates")
nasa_client = NASAClient(DEFAULT_NASA_API_KEY)


def init_db():
    """Initializes SQLite database for mission reservations and logs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mission_id TEXT UNIQUE,
            site_id TEXT,
            site_name TEXT,
            crew INTEGER,
            duration INTEGER,
            food_kg REAL,
            ration_kcal REAL,
            status TEXT,
            created_at TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            site_id TEXT,
            sol_hour REAL,
            ls_deg REAL,
            dust_scenario TEXT,
            solar_flux REAL,
            battery_soc REAL
        )
    """)
    conn.commit()
    conn.close()

# Automatically ensure DB tables exist on module load
init_db()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def habitat_from(data: dict) -> dict:
    """Shared habitat config sent by the UI (falls back to engine defaults)."""
    h = data.get("habitat") if isinstance(data, dict) else None
    if isinstance(h, str):
        try:
            h = json.loads(h)
        except ValueError:
            h = None
    return merge_habitat(h if isinstance(h, dict) else None)


def load_sites_raw() -> list:
    """Loads raw candidate site definitions from JSON data file."""
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ==========================================
# FLASK WEB & API ROUTES
# ==========================================

@app.route("/")
def index():
    """Renders main ASTREON application dashboard."""
    return render_template("index.html")


@app.route("/api/habitat/defaults", methods=["GET"])
def api_habitat_defaults():
    """The single shared habitat definition used by every module."""
    return jsonify(DEFAULT_HABITAT)


@app.route("/api/sites", methods=["GET"])
def api_sites():
    """Returns all candidate sites with evidence-based scientific water scores."""
    sites = load_sites_raw()
    processed = []
    for site in sites:
        water_analysis = ScientificEngine.calculate_water_potential(
            site.get("scientific_water_evidence", {})
        )
        site_copy = dict(site)
        site_copy["water_score"] = water_analysis["score"]
        site_copy["water_scientific"] = water_analysis
        processed.append(site_copy)
    return jsonify(processed)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Executes Multi-Criteria Decision Analysis (MCDA) for candidate landing zones
    based on mission profile, user criteria weighting, and constraints.
    """
    data = request.get_json() or {}

    try:
        crew = int(data.get("crew", 6))
        days = int(data.get("days", 30))
    except (TypeError, ValueError):
        return jsonify({"error": "Crew size and mission duration must be valid integers."}), 400

    if crew < 1 or days < 1:
        return jsonify({"error": "Crew and duration must be at least 1."}), 400

    weights = data.get("weights") or None
    habitat = habitat_from(data)

    filters = data.get("filters", {})
    max_slope = float(filters.get("max_slope", 10.0))
    min_water_score = float(filters.get("min_water_score", 0.0))

    raw_sites = load_sites_raw()
    evaluated = []

    for site in raw_sites:
        if site.get("slope_deg", 0.0) > max_slope:
            continue
        eval_result = ScientificEngine.evaluate_settlement_site(site, crew, days, weights, habitat)
        if eval_result["calculated_scores"]["water"] < min_water_score:
            continue
        evaluated.append(eval_result)

    # Sort descending by composite score
    evaluated.sort(key=lambda s: s["calculated_scores"]["final_composite_score"], reverse=True)

    if not evaluated:
        return jsonify({"error": "No candidate sites match the specified filter constraints."}), 404

    return jsonify({
        "crew": crew,
        "duration_sols": days,
        "weights_applied": weights,
        "total_sites_evaluated": len(evaluated),
        "best_site": evaluated[0],
        "ranked_sites": evaluated
    })


@app.route("/api/site/<site_id>/monitor", methods=["GET"])
def api_site_monitor(site_id):
    """
    Continuous Solar Energy & Environmental Risk Analysis for the selected site:
    - Diurnal solar insolation curve
    - Seasonal variation curve (Ls 0° - 360°)
    - Dust storm scenario simulation (clear, regional, global PEDE, winter haze)
    - Battery reserve state-of-charge (SoC) & power balance
    """
    sites = load_sites_raw()
    site = next((s for s in sites if s["id"] == site_id), None)
    if not site:
        return jsonify({"error": f"Site {site_id} not found."}), 404

    try:
        ls_deg = float(request.args.get("ls", 180.0))
        sol_hour = float(request.args.get("hour", 12.0))
    except ValueError:
        return jsonify({"error": "ls and hour must be numbers."}), 400
    scenario = request.args.get("scenario", "clear")
    habitat = habitat_from({"habitat": request.args.get("habitat")})
    pv_area = habitat["pv_area_m2"]

    lat = site["lat"]

    # 1. Instant solar irradiance
    tau = {"clear": 0.4, "regional": 1.6, "global_pede": 4.5, "winter_haze": 1.1}.get(scenario, 0.4)
    instant_irradiance = ScientificEngine.calculate_solar_irradiance(lat, ls_deg, sol_hour, tau)

    # 2. 24-hr Diurnal profile
    diurnal_curve = ScientificEngine.generate_diurnal_profile(lat, ls_deg, tau)

    # 3. Seasonal variations (12 milestones)
    seasonal_curve = ScientificEngine.generate_seasonal_variation(lat, tau)

    # 4. Same habitat + same load model as the cascade, so the two views agree.
    extraction = float(site.get("scientific_water_evidence", {}).get("extraction_energy_kwh_kg", 0.35))
    loads = ScientificEngine.habitat_daily_loads(lat, ls_deg, tau, habitat["crew"], extraction,
                                                 habitat["greenhouse"], habitat["water_recycling_eff"])
    hab_load = loads["total"] / 24.65
    storm_simulation = ScientificEngine.simulate_dust_storm_scenario(
        latitude_deg=lat,
        ls_deg=ls_deg,
        scenario=scenario,
        array_area_m2=pv_area,
        battery_capacity_kwh=habitat["battery_kwh"],
        habitat_base_load_kw=hab_load
    )
    if habitat["nuclear_kw"] > 0:
        storm_simulation["note"] = "Single-sol view excludes the fission unit; see Stress Test for the full model."

    return jsonify({
        "site_id": site["id"],
        "site_name": site["name"],
        "latitude": lat,
        "longitude": site["lon"],
        "query_state": {
            "ls_deg": ls_deg,
            "sol_hour": sol_hour,
            "scenario": scenario,
            "pv_area_m2": pv_area,
            "battery_kwh": habitat["battery_kwh"],
            "hab_load_kw": round(hab_load, 2),
            "loads_kwh_per_sol": {k: round(v, 1) for k, v in loads.items() if k not in ("t_mean_c", "net_water_l", "o2_need_kg")}
        },
        "instant_irradiance": instant_irradiance,
        "diurnal_curve": diurnal_curve,
        "seasonal_curve": seasonal_curve,
        "dust_storm_simulation": storm_simulation
    })


@app.route("/api/site/<site_id>/water_evidence", methods=["GET"])
def api_site_water_evidence(site_id):
    """
    Returns deep scientific evidence for water potential at the selected site,
    citing SHARAD, GRS, CRISM, and extraction physics.
    """
    sites = load_sites_raw()
    site = next((s for s in sites if s["id"] == site_id), None)
    if not site:
        return jsonify({"error": f"Site {site_id} not found."}), 404

    evidence = site.get("scientific_water_evidence", {})
    analysis = ScientificEngine.calculate_water_potential(evidence)

    return jsonify({
        "site_id": site["id"],
        "site_name": site["name"],
        "water_analysis": analysis,
        "geological_context": site.get("geological_context", ""),
        "evidence_raw": evidence
    })


@app.route("/api/food_rationing/calculate", methods=["POST"])
def api_food_rationing():
    """
    Calculates life support food contingency and rationing guidelines when
    food supply is reduced or mission duration is extended.
    """
    data = request.get_json() or {}

    try:
        h = habitat_from(data)
        crew = int(data.get("crew_size", h["crew"]))
        nom_days = int(data.get("nominal_days", 30))
        ext_days = int(data.get("extended_days", 45))
        food_kg = float(data.get("food_stockpile_kg", 500.0))
        gh_yield = float(data.get("greenhouse_daily_yield_kg", 0.0))
        weight_kg = float(data.get("crew_avg_weight_kg", 75.0))
    except (TypeError, ValueError) as err:
        return jsonify({"error": f"Invalid parameter format: {str(err)}"}), 400

    # Reject physically meaningless inputs instead of computing a plan from them.
    limits = [
        (1 <= crew <= 50, "Crew size must be 1-50."),
        (1 <= ext_days <= 2000, "Extended duration must be 1-2000 sols."),
        (1 <= nom_days <= 2000, "Nominal duration must be 1-2000 sols."),
        (0 <= food_kg <= 100000, "Food stockpile must be 0-100,000 kg."),
        (0 <= gh_yield <= 100, "Greenhouse yield must be 0-100 kg/day."),
        (35 <= weight_kg <= 150, "Average crew weight must be 35-150 kg."),
    ]
    for ok, msg in limits:
        if not ok:
            return jsonify({"error": msg}), 400

    plan = ScientificEngine.calculate_food_rationing_plan(
        crew_size=crew,
        nominal_days=nom_days,
        extended_days=ext_days,
        food_stockpile_kg=food_kg,
        greenhouse_daily_yield_kg=gh_yield,
        crew_avg_weight_kg=weight_kg
    )

    return jsonify(plan)


@app.route("/api/cascade/simulate", methods=["POST"])
def api_cascade_simulate():
    """
    Executes The Domino Engine: Multi-Sol Dynamic Compound Crisis Cascader.
    Simulates coupled physical subsystems (power, thermal, water, O2, food, radiation)
    across an interactive forward multi-sol timeline with 4-tier emergency load shedding.
    """
    data = request.get_json() or {}

    sites = load_sites_raw()
    site_id = data.get("site_id", "MSA-001")
    site = next((s for s in sites if s["id"] == site_id), None)
    if not site:
        site = sites[0] if sites else {}

    h = habitat_from(data)
    try:
        crew_size = int(data.get("crew_size", h["crew"]))
        timeline_sols = int(data.get("timeline_sols", h["mission_sols"]))
        storm_scenario = data.get("storm_scenario", "global_pede")
        storm_start_sol = int(data.get("storm_start_sol", 5))
        storm_duration_sols = int(data.get("storm_duration_sols", 35))
        pv_area_m2 = float(data.get("pv_area_m2", h["pv_area_m2"]))
        battery_capacity_kwh = float(data.get("battery_capacity_kwh", h["battery_kwh"]))
        initial_battery_pct = float(data.get("initial_battery_pct", 100.0))
        nuclear_backup_kw = float(data.get("nuclear_backup_kw", h["nuclear_kw"]))
        dust_cleaners_active = bool(data.get("dust_cleaners_active", False))
        initial_water_l = float(data.get("initial_water_l", h["water_l"]))
        water_recycling_eff = float(data.get("water_recycling_eff", h["water_recycling_eff"]))
        initial_o2_kg = float(data.get("initial_o2_kg", h["o2_kg"]))
        initial_food_kg = float(data.get("initial_food_kg", h["food_kg"]))
        greenhouse_enabled = bool(data.get("greenhouse_enabled", h["greenhouse"]))
        rationing_strategy = data.get("rationing_strategy", "auto_adaptive")
        start_ls_deg = float(data.get("start_ls_deg", h["start_ls"]))
        spe_event_sol = int(data.get("spe_event_sol", 14))
        storm_shelter_active = bool(data.get("storm_shelter_active", True))
    except (TypeError, ValueError) as err:
        return jsonify({"error": f"Invalid simulation parameter: {str(err)}"}), 400

    cascade_result = ScientificEngine.simulate_compound_crisis_cascade(
        site_data=site,
        crew_size=crew_size,
        timeline_sols=timeline_sols,
        storm_scenario=storm_scenario,
        storm_start_sol=storm_start_sol,
        storm_duration_sols=storm_duration_sols,
        pv_area_m2=pv_area_m2,
        battery_capacity_kwh=battery_capacity_kwh,
        initial_battery_pct=initial_battery_pct,
        nuclear_backup_kw=nuclear_backup_kw,
        dust_cleaners_active=dust_cleaners_active,
        initial_water_l=initial_water_l,
        water_recycling_eff=water_recycling_eff,
        initial_o2_kg=initial_o2_kg,
        initial_food_kg=initial_food_kg,
        greenhouse_enabled=greenhouse_enabled,
        rationing_strategy=rationing_strategy,
        start_ls_deg=start_ls_deg,
        spe_event_sol=spe_event_sol,
        storm_shelter_active=storm_shelter_active
    )

    # Countermeasure impacts are measured by re-running the simulation, not hardcoded.
    h_run = dict(h, crew=crew_size, mission_sols=timeline_sols, pv_area_m2=pv_area_m2,
                 battery_kwh=battery_capacity_kwh, nuclear_kw=nuclear_backup_kw, water_l=initial_water_l,
                 o2_kg=initial_o2_kg, food_kg=initial_food_kg, greenhouse=greenhouse_enabled, start_ls=start_ls_deg)
    cms = ScientificEngine.evaluate_countermeasures(site, h_run, storm_scenario, storm_start_sol, storm_duration_sols)
    cascade_result["countermeasures"] = cms["options"]
    cascade_result["countermeasure_baseline"] = cms["baseline"]
    return jsonify(cascade_result)


@app.route("/api/crisis/assess", methods=["POST"])
def api_crisis_assess():
    """
    Crisis Mode: survival runway, ordered actions, relocation ranking and Earth-link outlook,
    computed entirely on the local machine (no Earth link needed).
    """
    data = request.get_json() or {}
    sites = load_sites_raw()
    site = next((s for s in sites if s["id"] == data.get("site_id")), None) or (sites[0] if sites else None)
    if not site:
        return jsonify({"error": "No sites available."}), 404
    scenario = data.get("storm_scenario", "regional")
    if scenario not in ("none", "regional", "global_pede", "extreme_pede"):
        return jsonify({"error": "Unknown storm scenario."}), 400
    try:
        start = max(1, int(data.get("storm_start_sol", 5)))
        dur = max(5, min(150, int(data.get("storm_duration_sols", 35))))
    except (TypeError, ValueError):
        return jsonify({"error": "Storm start and duration must be integers."}), 400
    h = habitat_from(data)
    return jsonify(ScientificEngine.crisis_assessment(site, sites, h, scenario, start, dur, _utcnow()))


# ==========================================
# NASA INTEGRATION ENDPOINTS
# ==========================================

@app.route("/api/nasa/status", methods=["GET"])
def api_nasa_status():
    """Honest data-link state for the top bar: LIVE / CACHED / OFFLINE MODEL."""
    force = request.args.get("force") == "1"
    return jsonify(nasa_client.link_status(force=force))


@app.route("/api/nasa/weather", methods=["GET"])
def api_nasa_weather():
    """Fetches Mars surface weather telemetry from api.nasa.gov InSight REMS."""
    return jsonify(nasa_client.get_mars_weather())


@app.route("/api/nasa/rover_photos", methods=["GET"])
def api_nasa_rover_photos():
    """Fetches rover surface photography from api.nasa.gov."""
    rover = request.args.get("rover", "perseverance")
    if rover not in ("perseverance", "curiosity"):
        return jsonify({"error": "Unknown rover."}), 400
    try:
        sol = int(request.args.get("sol", 1000))
    except ValueError:
        return jsonify({"error": "sol must be an integer."}), 400
    return jsonify(nasa_client.get_mars_rover_photos(rover, sol))


@app.route("/api/nasa/datasets", methods=["GET"])
def api_nasa_datasets():
    """Returns curated data.nasa.gov Open Data and PDS catalogs."""
    return jsonify({
        "portal": "https://data.nasa.gov/",
        "datasets": nasa_client.get_nasa_open_datasets()
    })


@app.route("/api/nasa/code_tools", methods=["GET"])
def api_nasa_code_tools():
    """Returns curated code.nasa.gov open-source software catalog."""
    return jsonify({
        "portal": "https://code.nasa.gov/",
        "tools": nasa_client.get_nasa_code_catalog()
    })


@app.route("/api/nasa/config_key", methods=["POST"])
def api_nasa_config_key():
    """Allows user to set their NASA API key and verify connection."""
    data = request.get_json() or {}
    key = data.get("api_key", DEFAULT_NASA_API_KEY).strip()
    nasa_client.set_api_key(key)
    res = nasa_client.test_connection()
    res["link"] = nasa_client.link_status(force=True)
    return jsonify(res)


# ==========================================
# RESERVATION & COMMUNICATIONS
# ==========================================

@app.route("/api/reserve", methods=["POST"])
def api_reserve():
    """Registers a formal settlement reservation in local SQLite DB."""
    data = request.get_json() or {}
    site_id = data.get("site_id")
    crew = int(data.get("crew", 6))
    duration = int(data.get("duration", 30))
    food_kg = float(data.get("food_kg", 500.0))
    ration_kcal = float(data.get("ration_kcal", 2800.0))

    sites = load_sites_raw()
    site = next((s for s in sites if s["id"] == site_id), None)
    if not site:
        return jsonify({"error": f"Site {site_id} not found."}), 404

    mission_id = f"ASTREON-{_utcnow().strftime('%Y%m%d%H%M%S')}"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reservations 
        (mission_id, site_id, site_name, crew, duration, food_kg, ration_kcal, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        mission_id, site["id"], site["name"], crew, duration, food_kg, ration_kcal,
        "AUTHORIZED", _utcnow().isoformat(timespec="seconds")
    ))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "mission_id": mission_id,
        "site_id": site["id"],
        "site_name": site["name"],
        "crew": crew,
        "duration": duration,
        "status": "AUTHORIZED"
    })


@app.route("/api/reservations", methods=["GET"])
def api_reservations():
    """Lists all saved settlement reservations."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT mission_id, site_id, site_name, crew, duration, food_kg, ration_kcal, status, created_at
        FROM reservations ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "mission_id": r[0],
            "site_id": r[1],
            "site_name": r[2],
            "crew": r[3],
            "duration": r[4],
            "food_kg": r[5],
            "ration_kcal": r[6],
            "status": r[7],
            "created_at": r[8]
        }
        for r in rows
    ])


@app.route("/api/network/telemetry", methods=["POST"])
def api_network_telemetry():
    """
    Simulates NASA Delay/Disruption Tolerant Networking (DTN) link between
    Mars settlement and Earth Deep Space Network (DSN):
    Calculates orbital speed-of-light propagation latency (4.3 to 21.0 minutes).
    """
    data = request.get_json() or {}
    message = str(data.get("message", "Telemetry ping")).strip()
    connected = bool(data.get("connected", True))
    try:
        day_offset = float(data.get("day_offset", 0.0))
    except (TypeError, ValueError):
        day_offset = 0.0

    # Real Earth-Mars geometry for (today + day_offset), from Keplerian orbital elements.
    geo = ScientificEngine.earth_mars_geometry(_utcnow(), day_offset)
    dist_au = geo["distance_au"]
    latency_minutes = geo["one_way_light_min"]
    # Solar conjunction: Mars within ~3° of the Sun as seen from Earth -> radio link unusable.
    is_conjunction = geo["sun_earth_mars_angle_deg"] < 3.0

    if not connected:
        return jsonify({
            "status": "QUEUED_STORE_AND_FORWARD",
            "connected": False,
            "latency_minutes": latency_minutes,
            "distance_au": dist_au,
            "message": message,
            "bundle_id": f"DTN-BUNDLE-{_utcnow().strftime('%H%M%S')}",
            "detail": "Interplanetary link severed. Message cached locally in DTN non-volatile custody storage."
        })

    if is_conjunction:
        return jsonify({
            "status": "SOLAR_CONJUNCTION_BLACKOUT",
            "connected": False,
            "latency_minutes": latency_minutes,
            "distance_au": dist_au,
            "sun_angle_deg": geo["sun_earth_mars_angle_deg"],
            "message": message,
            "bundle_id": f"DTN-BUNDLE-{_utcnow().strftime('%H%M%S')}",
            "detail": "Mars-Earth Solar Conjunction: Direct RF line-of-sight occluded by solar corona. Commencing autonomous hold."
        })

    return jsonify({
        "status": "DELIVERED_DSN",
        "connected": True,
        "latency_minutes": latency_minutes,
        "distance_au": dist_au,
        "sun_angle_deg": geo["sun_earth_mars_angle_deg"],
        "round_trip_min": round(2 * latency_minutes, 1),
        "message": message,
        "timestamp": _utcnow().isoformat(timespec="seconds"),
        "detail": f"Telemetry verified by NASA Deep Space Network (Goldstone/Canberra/Madrid). One-way latency: {latency_minutes} min."
    })


if __name__ == "__main__":
    init_db()
    print("=" * 60)
    print(" ASTREON - Mars Mission Site Intelligence Platform")
    print(" Initialized database and scientific simulation engines.")
    print(" Serving at: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)
