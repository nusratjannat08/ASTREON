"""
ASTREON Scientific Engine
Core physical and mathematical models for:
1. Multi-Sensor Evidence-Based Water Resource Potential
2. Solar Illumination, Diurnal Irradiance, and Dust Storm Power Models
3. Life Support Contingency & Emergency Food Rationing Optimizer
4. Multi-Criteria Settlement Decision Analysis (MCDA)
"""

import math
from datetime import timezone
from typing import Dict, List, Any, Tuple

# Martian Physical & Orbital Constants
SOL_IN_SECONDS = 88775.244  # 1 Sol = 24h 39m 35.244s
MARS_SOLAR_CONSTANT = 589.0  # W/m^2 at mean distance (1.5237 AU)
AU_METERS = 149597870700
MARS_SEMI_MAJOR_AXIS = 1.523662  # AU
MARS_ECCENTRICITY = 0.09341233
MARS_OBLIQUITY = 25.19  # degrees axial tilt
LS_PERIHELION = 250.87  # degrees (closest to sun, max dust activity)
LS_APHELION = 70.87     # degrees (furthest from sun, cold northern summer)

# NASA Standard ECLSS Baselines (per person per sol)
NASA_BASELINE_CALORIES = 2800.0  # kcal/person/sol (active astronaut nominal)
NASA_BASELINE_WATER = 3.5        # L/person/sol (drinking + food rehydration)
NASA_BASELINE_OXYGEN = 0.84      # kg/person/sol
NASA_BASELINE_POWER = 5.0        # kWh/person/sol (habitat + ECLSS life support share)
KCAL_PER_KG_RATION = 4200.0       # Dense freeze-dried space foods
NASA_GCR_SURFACE_BASELINE_MSV = 0.67  # mSv/sol GCR surface dose at zero-elevation datum (Curiosity RAD)
NASA_RADIATION_30DAY_LIMIT_MSV = 250.0  # NASA career/short-term exposure limit
NASA_RADIATION_CAREER_LIMIT_MSV = 600.0 # NASA Astronaut lifetime limit
MARS_RADIUS_KM = 3389.5
PV_EFFICIENCY = 0.28

# ONE habitat definition shared by every module (ranking, solar monitor, cascade, food, crisis).
# Previously each tab used its own numbers (e.g. 350 vs 250 kWh battery, 12 kW flat load vs a
# thermal model), so the tabs contradicted each other. All values are editable in the UI.
DEFAULT_HABITAT: Dict[str, Any] = {
    "crew": 6,
    "pv_area_m2": 450.0,          # deployable PV array
    "battery_kwh": 300.0,         # Li-ion storage
    "nuclear_kw": 0.0,            # fission backup (Kilopower-class); 0 = none installed
    "food_kg": 800.0,             # stored rations (4,200 kcal/kg)
    "water_l": 3500.0,            # stored potable water
    "o2_kg": 150.0,               # high-pressure O2 reserve
    "water_recycling_eff": 0.90,  # ECLSS water recovery
    "greenhouse": True,
    "mission_sols": 60,           # simulation horizon
    "start_ls": 240.0,            # season at sol 1 (Ls 180-330 = dust-storm season)
    "rover_km_per_sol": 80.0,     # pressurized-rover traverse speed for relocation
    "rover_endurance_sols": 21,   # rover life-support endurance
}


def merge_habitat(h: Dict[str, Any] = None) -> Dict[str, Any]:
    """Defaults overlaid with any user-supplied values, clamped to sane ranges."""
    out = dict(DEFAULT_HABITAT)
    for k, v in (h or {}).items():
        if k in out and v is not None:
            out[k] = type(out[k])(v) if not isinstance(out[k], bool) else bool(v)
    clamp = {"crew": (1, 24), "pv_area_m2": (20, 5000), "battery_kwh": (20, 5000), "nuclear_kw": (0, 100),
             "food_kg": (0, 50000), "water_l": (0, 100000), "o2_kg": (0, 10000), "water_recycling_eff": (0, 0.99),
             "mission_sols": (10, 180), "start_ls": (0, 360), "rover_km_per_sol": (5, 500), "rover_endurance_sols": (1, 120)}
    for k, (lo, hi) in clamp.items():
        out[k] = type(out[k])(min(hi, max(lo, out[k])))
    return out


class ScientificEngine:
    """
    Implements scientifically validated algorithms for Mars mission evaluation.
    """

    # ==========================================
    # 1. SCIENTIFIC WATER RESOURCE POTENTIAL
    # ==========================================
    @staticmethod
    def calculate_water_potential(evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Replaces arbitrary water scores with an empirical multi-sensor model based on:
        - SHARAD radar dielectric constant & subsurface ice detection
        - Mars Odyssey Gamma Ray Spectrometer (GRS) Water Equivalent Hydrogen (WEH wt%)
        - CRISM visible-infrared spectral hydrated mineral signatures
        - Depth to ice table (overburden regolith thickness)
        - Specific extraction energy (kWh per kg of H2O recovered)
        """
        # 1. Radar Ice Confidence (SHARAD)
        # Dielectric constant: pure water ice epsilon' ~ 3.15, dry basalt ~ 6-9
        dielectric = evidence.get("dielectric_permittivity", 6.0)
        purity_pct = evidence.get("radar_ice_purity_pct", 0.0)
        has_slab_ice = evidence.get("has_massive_slab_ice", False)

        if has_slab_ice:
            radar_score = min(100.0, 50.0 + (purity_pct * 0.5))
        elif dielectric < 4.0:
            radar_score = 65.0 + (4.0 - dielectric) * 20.0
        else:
            radar_score = max(5.0, 35.0 - (dielectric - 4.0) * 8.0)

        # 2. GRS Hydrogen Score (0 to 12+ wt% WEH in upper meter)
        grs_weh = evidence.get("grs_weh_wt_pct", 2.0)
        # 8-10% is considered very high for non-polar regions
        grs_score = min(100.0, (grs_weh / 10.0) * 100.0)

        # 3. CRISM Mineral Hydration Score
        crism_hydration = evidence.get("crism_hydration_index", 0.2)  # 0.0 to 1.0
        crism_score = min(100.0, crism_hydration * 100.0)

        # 4. Overburden Accessibility Penalty / Depth Score
        depth_m = evidence.get("overburden_depth_m", 10.0)
        if depth_m <= 1.0:
            depth_score = 100.0
        elif depth_m <= 3.0:
            depth_score = 90.0 - (depth_m - 1.0) * 15.0
        elif depth_m <= 10.0:
            depth_score = 60.0 - (depth_m - 3.0) * 6.0
        else:
            depth_score = max(5.0, 20.0 - (depth_m - 10.0) * 1.5)

        # 5. Extraction Energy Penalty
        # Pure ice sublimation ~ 0.18-0.3 kWh/kg; Clay/Sulfate thermal dehydration ~ 0.7-1.4 kWh/kg
        energy_kwh_per_kg = evidence.get("extraction_energy_kwh_kg", 0.8)
        if energy_kwh_per_kg <= 0.25:
            energy_score = 100.0
        elif energy_kwh_per_kg <= 0.6:
            energy_score = 80.0 - (energy_kwh_per_kg - 0.25) * 60.0
        else:
            energy_score = max(10.0, 60.0 - (energy_kwh_per_kg - 0.6) * 50.0)

        # Weighted Composite Water Resource Potential Index (0 - 100)
        composite_score = round(
            (radar_score * 0.35) +
            (grs_score * 0.25) +
            (crism_score * 0.15) +
            (depth_score * 0.15) +
            (energy_score * 0.10),
            1
        )

        # Determine Primary Extraction Method & Classification
        if has_slab_ice and depth_m <= 3.0:
            resource_type = "Massive Subsurface Glacial Ice (Direct Sublimation Well)"
            feasibility = "HIGH - Drill & Rodriguez Well"
        elif has_slab_ice and depth_m > 3.0:
            resource_type = "Deep Glacial/Slab Ice (Requires Thermal Casing Drill)"
            feasibility = "MODERATE - Deep Subsurface Extraction"
        elif grs_weh >= 7.0:
            resource_type = "Pervasive Ground Ice / Permafrost Matrix"
            feasibility = "MODERATE - Regolith Excavation & Batch Distillation"
        elif crism_hydration >= 0.5:
            resource_type = "Hydrated Phyllosilicates & Polyhydrated Sulfates"
            feasibility = "CHALLENGING - High-Temp Thermal Desorption (>350°C)"
        else:
            resource_type = "Dry Basaltic Regolith (Trace Bound Moisture Only)"
            feasibility = "VERY LOW - High Energy Penalty"

        return {
            "score": composite_score,
            "radar_score": round(radar_score, 1),
            "grs_score": round(grs_score, 1),
            "crism_score": round(crism_score, 1),
            "depth_score": round(depth_score, 1),
            "energy_score": round(energy_score, 1),
            "resource_type": resource_type,
            "feasibility": feasibility,
            "dielectric_permittivity": dielectric,
            "ice_purity_pct": purity_pct,
            "grs_weh_wt_pct": grs_weh,
            "crism_hydration_index": crism_hydration,
            "overburden_depth_m": depth_m,
            "extraction_energy_kwh_kg": energy_kwh_per_kg,
            "instruments_cited": [
                "Mars Reconnaissance Orbiter (MRO) SHARAD Shallow Radar",
                "2001 Mars Odyssey Gamma Ray Spectrometer (GRS) HEND",
                "MRO Compact Reconnaissance Imaging Spectrometer for Mars (CRISM)",
                "High Resolution Imaging Science Experiment (HiRISE) Scarp Imaging"
            ]
        }

    # ==========================================
    # 2. SOLAR ILLUMINATION & DUST STORM ENGINE
    # ==========================================
    @staticmethod
    def get_mars_heliocentric_distance(ls_deg: float) -> float:
        """
        Calculate distance from Mars to Sun in AU for a given Solar Longitude (Ls in deg).
        """
        # True anomaly approx related to Ls: nu ~ Ls - omega
        nu_rad = math.radians((ls_deg - LS_PERIHELION) % 360)
        e = MARS_ECCENTRICITY
        a = MARS_SEMI_MAJOR_AXIS
        r = (a * (1 - e ** 2)) / (1 + e * math.cos(nu_rad))
        return r

    @staticmethod
    def earth_mars_geometry(when_utc, day_offset: float = 0.0) -> Dict[str, float]:
        """
        Earth-Mars distance and Sun-Earth-Mars angle from J2000 mean Keplerian elements
        (Standish, JPL "Approximate Positions of the Planets", valid 1800-2050; error << 0.01 AU,
        plenty for light-time). Returns one-way light time in minutes.
        """
        if when_utc.tzinfo is None:  # naive datetimes are UTC here (avoid local-time offset)
            when_utc = when_utc.replace(tzinfo=timezone.utc)
        jd = 2440587.5 + when_utc.timestamp() / 86400.0 + day_offset
        T = (jd - 2451545.0) / 36525.0
        elements = {  # a, e, I, L, long.peri, long.node  (+ rates per century)
            "earth": ((1.00000261, 0.00000562), (0.01671123, -0.00004392), (-0.00001531, -0.01294668),
                      (100.46457166, 35999.37244981), (102.93768193, 0.32327364), (0.0, 0.0)),
            "mars": ((1.52371034, 0.00001847), (0.09339410, 0.00007882), (1.84969142, -0.00813131),
                     (-4.55343205, 19140.30268499), (-23.94362959, 0.44441088), (49.55953891, -0.29257343)),
        }

        def helio(name):
            (a0, ad), (e0, ed), (i0, idd), (L0, Ld), (w0, wd), (O0, Od) = elements[name]
            a, e = a0 + ad * T, e0 + ed * T
            I, L, wbar, Om = [math.radians(x0 + xd * T) for x0, xd in ((i0, idd), (L0, Ld), (w0, wd), (O0, Od))]
            M = (L - wbar + math.pi) % (2 * math.pi) - math.pi
            E = M
            for _ in range(8):
                E = E - (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
            xp, yp = a * (math.cos(E) - e), a * math.sqrt(1 - e * e) * math.sin(E)
            w = wbar - Om
            cw, sw, cO, sO, cI, sI = math.cos(w), math.sin(w), math.cos(Om), math.sin(Om), math.cos(I), math.sin(I)
            return ((cw * cO - sw * sO * cI) * xp + (-sw * cO - cw * sO * cI) * yp,
                    (cw * sO + sw * cO * cI) * xp + (-sw * sO + cw * cO * cI) * yp,
                    (sw * sI) * xp + (cw * sI) * yp)

        ex, ey, ez = helio("earth")
        mx, my, mz = helio("mars")
        dx, dy, dz = mx - ex, my - ey, mz - ez
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        re = math.sqrt(ex * ex + ey * ey + ez * ez)
        # angle at Earth between the Sun direction (-E) and the Mars direction (M-E)
        cosang = (-ex * dx - ey * dy - ez * dz) / (re * d)
        ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
        return {
            "distance_au": round(d, 3),
            "one_way_light_min": round(d * 499.004784 / 60.0, 1),
            "sun_earth_mars_angle_deg": round(ang, 1),
        }

    @staticmethod
    def get_solar_declination(ls_deg: float) -> float:
        """
        Sub-solar latitude (declination delta in degrees) as function of Ls.
        """
        ls_rad = math.radians(ls_deg)
        obliquity_rad = math.radians(MARS_OBLIQUITY)
        delta_rad = math.asin(math.sin(obliquity_rad) * math.sin(ls_rad))
        return math.degrees(delta_rad)

    @classmethod
    def calculate_solar_irradiance(
        cls,
        latitude_deg: float,
        ls_deg: float,
        hour_of_sol: float,
        optical_depth_tau: float = 0.5
    ) -> Dict[str, float]:
        """
        Calculates instantaneous solar irradiance (W/m^2) at surface level:
        Accounts for:
        - Orbital eccentricity (aphelion vs perihelion distance)
        - Solar zenith angle based on latitude, declination, and sol hour
        - Atmospheric extinction using Beer-Lambert law with dust optical depth tau
        - Diffuse atmospheric scattered sky flux (Pollack/Appelbaum model)
        """
        r_au = cls.get_mars_heliocentric_distance(ls_deg)
        # Solar flux at top of Martian atmosphere (TOA)
        # At 1 AU, S0 ~ 1361 W/m^2 => at r AU, S_mars = 1361 / (r_au^2)
        s_toa = 1361.0 / (r_au ** 2)

        # Solar hour angle (h = 0 at noon = 12.0)
        # 24 hours of sol mapped to 360 degrees (15 deg per hour)
        hour_angle_deg = (hour_of_sol - 12.0) * 15.0
        h_rad = math.radians(hour_angle_deg)

        lat_rad = math.radians(latitude_deg)
        decl_deg = cls.get_solar_declination(ls_deg)
        decl_rad = math.radians(decl_deg)

        # Cosine of solar zenith angle theta_z
        cos_theta_z = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(lat_rad) * math.cos(decl_rad) * math.cos(h_rad)

        if cos_theta_z <= 0.0:
            # Sun below horizon (night)
            return {
                "direct_flux": 0.0,
                "diffuse_flux": 0.0,
                "total_flux": 0.0,
                "sun_elevation_deg": round(math.degrees(math.asin(max(-1.0, cos_theta_z))), 1),
                "toa_flux": round(s_toa, 1),
                "cos_zenith": 0.0
            }

        sun_elevation_deg = math.degrees(math.asin(cos_theta_z))

        # Optical airmass approximation
        airmass = 1.0 / max(0.05, cos_theta_z)

        # Direct beam transmission
        # Extinction: I_dir = S_toa * cos(theta_z) * exp(-tau * airmass)
        tau_effective = max(0.1, optical_depth_tau)
        direct_flux = s_toa * cos_theta_z * math.exp(-tau_effective * airmass)

        # Diffuse component (scattered light through dust haze)
        # Approx 25% of forward-scattered light reaches surface even in dusty atmosphere
        forward_scatter_factor = 0.28
        scattered_loss = s_toa * cos_theta_z * (1.0 - math.exp(-tau_effective * airmass))
        diffuse_flux = scattered_loss * forward_scatter_factor * max(0.2, (1.0 - (tau_effective * 0.15)))

        total_flux = direct_flux + diffuse_flux

        return {
            "direct_flux": round(direct_flux, 1),
            "diffuse_flux": round(diffuse_flux, 1),
            "total_flux": round(total_flux, 1),
            "sun_elevation_deg": round(sun_elevation_deg, 1),
            "toa_flux": round(s_toa, 1),
            "cos_zenith": round(cos_theta_z, 3)
        }

    @classmethod
    def generate_diurnal_profile(
        cls,
        latitude_deg: float,
        ls_deg: float,
        optical_depth_tau: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Generates 24-point hourly solar profile across one Martian sol.
        """
        profile = []
        for hour in range(25):
            res = cls.calculate_solar_irradiance(latitude_deg, ls_deg, float(hour), optical_depth_tau)
            profile.append({
                "hour": hour,
                "total_flux": res["total_flux"],
                "direct_flux": res["direct_flux"],
                "diffuse_flux": res["diffuse_flux"],
                "elevation": res["sun_elevation_deg"]
            })
        return profile

    @classmethod
    def generate_seasonal_variation(
        cls,
        latitude_deg: float,
        optical_depth_tau: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Generates insolation at solar noon across all 12 Martian seasonal milestones (Ls 0 to 360).
        """
        seasons = []
        ls_steps = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]
        season_names = {
            0: "N. Spring Equinox (Ls 0°)",
            90: "N. Summer Solstice / Aphelion (Ls 90°)",
            180: "N. Autumn Equinox (Ls 180°)",
            270: "N. Winter Solstice / Perihelion (Ls 270°)"
        }

        for ls in ls_steps:
            noon = cls.calculate_solar_irradiance(latitude_deg, float(ls), 12.0, optical_depth_tau)
            # Integrate daily average insolation
            sol_hours = cls.generate_diurnal_profile(latitude_deg, float(ls), optical_depth_tau)
            daily_kwh_m2 = sum(h["total_flux"] for h in sol_hours[:-1]) * 1.027 / 1000.0  # 1 sol-hour ~ 1.027 hr

            seasons.append({
                "ls": ls,
                "label": season_names.get(ls, f"Ls {ls}°"),
                "noon_flux": noon["total_flux"],
                "daily_energy_kwh_m2": round(daily_kwh_m2, 2),
                "distance_au": round(cls.get_mars_heliocentric_distance(float(ls)), 3),
                "subsolar_lat": round(cls.get_solar_declination(float(ls)), 1)
            })
        return seasons

    # ---------- shared habitat physics (used by monitor, cascade, ranking, crisis) ----------
    @staticmethod
    def ambient_temperature_c(lat: float, ls_deg: float, tau: float) -> float:
        """Daily-mean surface air temperature: colder at high latitude and in aphelion season;
        dust damps the diurnal swing (warmer nights, colder days)."""
        ls_phase = math.cos(math.radians(ls_deg - 250.87))
        t_high = -18.0 - 0.4 * abs(lat) + 12.0 * ls_phase - 15.0 * min(1.0, tau / 4.5)
        t_low = -88.0 - 0.3 * abs(lat) + 9.0 * ls_phase + 14.0 * min(1.0, tau / 4.5)
        return (t_high + t_low) / 2.0

    @classmethod
    def array_tilt_gain(cls, lat: float, ls_deg: float) -> float:
        """Gain of a fixed equator-tilted array over a flat one (largest in local winter)."""
        decl = cls.get_solar_declination(ls_deg)
        winter_sun = max(0.0, -math.sin(math.radians(decl))) if lat >= 0 else max(0.0, math.sin(math.radians(decl)))
        return 1.0 + (abs(lat) / 45.0) * winter_sun * 0.75

    @classmethod
    def daily_insolation_kwh_m2(cls, lat: float, ls_deg: float, tau: float) -> float:
        """Sol-integrated insolation on the tilted array (kWh/m^2/sol), before panel dust."""
        prof = cls.generate_diurnal_profile(lat, ls_deg, tau)
        flat = sum(h["total_flux"] for h in prof[:-1]) * 1.0274 / 1000.0
        return flat * cls.array_tilt_gain(lat, ls_deg)

    @classmethod
    def habitat_daily_loads(cls, lat: float, ls_deg: float, tau: float, crew: int,
                            extraction_energy_kwh_kg: float, greenhouse_on: bool = True,
                            water_recycling_eff: float = 0.9) -> Dict[str, float]:
        """Nominal (Tier 0) energy demand per sol, by subsystem (kWh/sol)."""
        t_mean = cls.ambient_temperature_c(lat, ls_deg, tau)
        e_thermal = (1.0 + 0.025 * max(0.0, 20.0 - t_mean)) * 24.6
        e_core = 2.4 * 24.6
        e_greenhouse = 4.0 * 14.0 if greenhouse_on else 0.0
        water_need = crew * NASA_BASELINE_WATER
        net_water = water_need * (1.0 - water_recycling_eff) + (3.5 if greenhouse_on else 0.0)
        e_well = net_water * extraction_energy_kwh_kg
        o2_need = crew * NASA_BASELINE_OXYGEN
        e_moxie = o2_need * 0.85
        return {
            "core": e_core, "thermal": e_thermal, "greenhouse": e_greenhouse, "well": e_well, "moxie": e_moxie,
            "total": e_core + e_thermal + e_greenhouse + e_well + e_moxie,
            "t_mean_c": t_mean, "net_water_l": net_water, "o2_need_kg": o2_need,
        }

    @classmethod
    def site_solar_profile(cls, lat: float, tau: float = 0.4) -> Dict[str, float]:
        """Annual mean and worst-season clear-sky array yield (kWh/m^2/sol), 24 seasonal samples."""
        vals = [cls.daily_insolation_kwh_m2(lat, float(ls), tau) for ls in range(0, 360, 15)]
        return {"mean": sum(vals) / len(vals), "min": min(vals), "max": max(vals)}

    @classmethod
    def simulate_dust_storm_scenario(
        cls,
        latitude_deg: float,
        ls_deg: float,
        scenario: str,
        array_area_m2: float = 250.0,
        pv_efficiency: float = 0.28,
        battery_capacity_kwh: float = 350.0,
        habitat_base_load_kw: float = 12.0
    ) -> Dict[str, Any]:
        """
        Simulates power production, battery reserve state-of-charge (SoC),
        and mission survival timeline under 4 atmospheric dust scenarios:
        - Nominal Clear Sky (tau = 0.4)
        - Moderate Regional Storm (tau = 1.5)
        - Global Planet-Encircling Dust Event [PEDE] (tau = 4.5, e.g. 2018 storm)
        - Winter Solstice High-Latitude Haze (tau = 1.0 + low sun angle)
        """
        scenarios_config = {
            "clear": {
                "name": "Nominal Clear Atmosphere",
                "tau": 0.4,
                "dust_accumulation_factor": 0.95,
                "description": "Standard Martian atmospheric optical depth; optimal PV generation."
            },
            "regional": {
                "name": "Regional Dust Storm",
                "tau": 1.6,
                "dust_accumulation_factor": 0.82,
                "description": "Localized convective storm obscuring direct sun; significant diffuse scattering."
            },
            "global_pede": {
                "name": "Planet-Encircling Dust Event (PEDE)",
                "tau": 4.5,
                "dust_accumulation_factor": 0.60,
                "description": "Severe global storm (similar to 2018 event that silenced Opportunity). >85% solar drop."
            },
            "winter_haze": {
                "name": "Polar Winter Twilight & Dust Haze",
                "tau": 1.1,
                "dust_accumulation_factor": 0.88,
                "description": "Low solar zenith angle combined with suspended atmospheric ice-dust condensates."
            }
        }

        cfg = scenarios_config.get(scenario, scenarios_config["clear"])
        tau = cfg["tau"]
        dust_factor = cfg["dust_accumulation_factor"]

        diurnal = cls.generate_diurnal_profile(latitude_deg, ls_deg, tau)
        tilt_gain = cls.array_tilt_gain(latitude_deg, ls_deg)  # same array model as the cascade

        # Calculate daily generation
        daily_kwh_generated = 0.0
        hourly_balance = []
        current_battery = battery_capacity_kwh  # start 100% full

        for h in diurnal[:24]:
            # PV Power (kW) = Irradiance (kW/m^2) * Area (m^2) * Efficiency * Dust Accumulation
            irradiance_kw_m2 = h["total_flux"] / 1000.0
            power_gen_kw = irradiance_kw_m2 * tilt_gain * array_area_m2 * pv_efficiency * dust_factor
            daily_kwh_generated += power_gen_kw * 1.027  # 1 sol-hour in Earth hours

            net_flow_kw = power_gen_kw - habitat_base_load_kw

            # Update battery
            if net_flow_kw >= 0:
                current_battery = min(battery_capacity_kwh, current_battery + (net_flow_kw * 1.027 * 0.92))  # 92% charge eff
            else:
                current_battery = max(0.0, current_battery + (net_flow_kw * 1.027))

            soc_pct = (current_battery / battery_capacity_kwh) * 100.0
            hourly_balance.append({
                "hour": h["hour"],
                "irradiance": h["total_flux"],
                "power_gen_kw": round(power_gen_kw, 2),
                "net_power_kw": round(net_flow_kw, 2),
                "battery_kwh": round(current_battery, 1),
                "battery_soc_pct": round(soc_pct, 1)
            })

        daily_kwh_required = habitat_base_load_kw * 24.65  # 1 sol in Earth hours
        daily_kwh_generated = round(daily_kwh_generated, 1)
        net_daily_margin_kwh = daily_kwh_generated - daily_kwh_required

        # Sols until battery exhaustion if negative
        if net_daily_margin_kwh < 0:
            daily_deficit = abs(net_daily_margin_kwh)
            sols_to_blackout = round(battery_capacity_kwh / daily_deficit, 1)
            status = "CRITICAL DEFICIT - Battery Depletion" if sols_to_blackout < 3 else "WARNING - Energy Rationing Required"
        else:
            sols_to_blackout = 999.0
            status = "STABLE - Sustained Daily Surplus"

        # Energy Reliability Rating (0 to 100)
        reliability_ratio = daily_kwh_generated / max(1.0, daily_kwh_required)
        energy_reliability_score = min(100.0, round(reliability_ratio * 100.0, 1))

        return {
            "scenario_key": scenario,
            "scenario_name": cfg["name"],
            "tau": tau,
            "description": cfg["description"],
            "daily_kwh_generated": round(daily_kwh_generated, 1),
            "daily_kwh_required": round(daily_kwh_required, 1),
            "net_daily_margin_kwh": round(net_daily_margin_kwh, 1),
            "energy_reliability_score": energy_reliability_score,
            "sols_to_blackout": sols_to_blackout,
            "status": status,
            "hourly_simulation": hourly_balance,
            "mitigation_directives": cls._get_energy_mitigation(status, net_daily_margin_kwh)
        }

    @staticmethod
    def _get_energy_mitigation(status: str, margin_kwh: float) -> List[str]:
        directives = []
        if "CRITICAL" in status:
            directives.append("Emergency Load Shedding: Shut down ISRU water extraction compressors immediately.")
            directives.append("Thermal Hab Consolidation: Isolate unpressurized laboratory bays; maintain crew module at 18°C.")
            directives.append("Nuclear / Fuel Cell Backup: Initiate emergency cold-start sequence on secondary Kilopower/FC units.")
            directives.append("Science Pause: Suspend all rover communications and external telemetry relays to survival-burst mode.")
        elif "WARNING" in status:
            directives.append("Ration secondary daytime experiments; shift water electrolysis to peak midday solar window.")
            directives.append("Deploy automated electrostatic/mechanical wiper blades to clear dust accumulation on PV panels.")
            directives.append("Monitor orbital MRO/THEMIS dust storm tracks for local wall front arrival.")
        else:
            directives.append("Nominal power operations: 100% Life Support and ISRU baseline maintained.")
            directives.append("Surplus energy routed to thermal ballast and water electrolysis oxygen buffers.")
        return directives

    # ==========================================
    # 3. DOMINO ENGINE: MULTI-SOL COMPOUND CRISIS CASCADER
    # ==========================================
    @classmethod
    def simulate_compound_crisis_cascade(
        cls,
        site_data: Dict[str, Any],
        crew_size: int = 6,
        timeline_sols: int = 60,
        storm_scenario: str = "global_pede",  # "none", "regional", "global_pede", "extreme_pede"
        storm_start_sol: int = 5,
        storm_duration_sols: int = 35,
        pv_area_m2: float = 450.0,
        battery_capacity_kwh: float = 250.0,
        initial_battery_pct: float = 100.0,
        nuclear_backup_kw: float = 0.0,
        dust_cleaners_active: bool = False,
        initial_water_l: float = 3500.0,
        water_recycling_eff: float = 0.90,
        initial_o2_kg: float = 150.0,
        initial_food_kg: float = 800.0,
        greenhouse_enabled: bool = True,
        rationing_strategy: str = "auto_adaptive",  # "nominal", "conservation", "survival", "auto_adaptive"
        start_ls_deg: float = 240.0,
        spe_event_sol: int = 14,
        storm_shelter_active: bool = True
    ) -> Dict[str, Any]:
        """
        The Domino Engine: Multi-Sol Dynamic Compound Crisis Cascader.
        Couples physical and life support subsystems into a closed-loop dynamic simulation:
        1. Solar mechanics, seasonal orbital distance, and evolving dust storm optical depth (tau).
        2. Habitat ambient thermal environment and heating power demand.
        3. PV array power with progressive dust deposition vs electrostatic dust shaker mitigation.
        4. Stateful Battery Energy Storage System (BESS) with depth-of-discharge tracking.
        5. 4-Tier Automated Emergency Load Shedding protocol (Greenhouse -> ISRU Well -> MOXIE -> Thermal Setback).
        6. Closed-loop Water Recovery System (WRS) + Subsurface Ice Well extraction vs reserves depletion.
        7. Atmospheric Oxygen balance: MOXIE CO2 electrolysis vs high-pressure accumulator discharge.
        8. Bioregenerative greenhouse LED lighting: light deprivation crop wilting vs fresh caloric yield.
        9. Dynamic food rationing: metabolic deficit, body weight loss %, and starvation runway.
        10. Curiosity RAD elevation-adjusted GCR dose + Solar Particle Event (SPE) shelter-in-place protocol.
        11. Chronological cascading milestone event detection and unified survival runway calculation.
        """
        crew = max(1, int(crew_size))
        timeline = max(10, min(180, int(timeline_sols)))
        site = site_data or {}

        lat = float(site.get("lat", 0.0))
        elevation_m = float(site.get("elevation_m", -1000.0))
        elevation_km = elevation_m / 1000.0
        site_name = site.get("name", "Unknown Zone")

        water_evidence = site.get("scientific_water_evidence", {})
        extraction_energy_kwh_kg = float(water_evidence.get("extraction_energy_kwh_kg", 0.35))

        # Initial Subsystem States
        b_cap = max(20.0, float(battery_capacity_kwh))
        b_current = max(0.0, min(b_cap, (float(initial_battery_pct) / 100.0) * b_cap))
        w_current = max(0.0, float(initial_water_l))
        o2_current = max(0.0, float(initial_o2_kg))
        food_current = max(0.0, float(initial_food_kg))
        crop_health = 100.0 if greenhouse_enabled else 0.0

        cum_weight_loss_kg = 0.0
        cum_rad_msv = 0.0
        consecutive_unlit_sols = 0
        consecutive_blackout_sols = 0
        storm_sols_elapsed = 0

        # Storm configuration
        scenario_map = {
            "none": {"peak_tau": 0.38, "label": "Clear Atmosphere (No Storm)"},
            "regional": {"peak_tau": 1.8, "label": "Regional Dust Storm (tau=1.8)"},
            "global_pede": {"peak_tau": 4.5, "label": "Global Planet-Encircling Dust Event (tau=4.5)"},
            "extreme_pede": {"peak_tau": 6.2, "label": "Severe Global PEDE (tau=6.2)"}
        }
        scen_info = scenario_map.get(storm_scenario, scenario_map["global_pede"])
        peak_tau = scen_info["peak_tau"]

        # The season is an explicit input and is identical for every storm scenario, so "storm vs
        # no storm" compares like with like. (Previously "no storm" silently ran at Ls 180 and the
        # storm runs at Ls 240, so northern winter was being blamed on the dust.)
        effective_start_ls = float(start_ls_deg) % 360.0

        t_start = max(1, int(storm_start_sol)) if storm_scenario != "none" else 999
        t_dur = max(5, int(storm_duration_sols))
        t_peak = t_start + max(2, int(t_dur * 0.3))

        timeline_data = []
        cascading_events = []
        observed_tiers = set()
        greenhouse_died = False
        limiting_bottleneck = "NONE - MISSION SUSTAINABLE"
        fatal_sol = None
        min_battery_soc = 100.0
        total_blackout_sols = 0

        for sol in range(1, timeline + 1):
            ls_deg = (effective_start_ls + (sol - 1) * 0.524) % 360.0

            # 1. Optical Depth (tau) Profile
            if storm_scenario == "none" or sol < t_start:
                tau = 0.38
            elif t_start <= sol <= t_peak:
                frac = (sol - t_start) / max(1, (t_peak - t_start))
                tau = 0.38 + (peak_tau - 0.38) * frac
                storm_sols_elapsed += 1
            elif t_peak < sol <= (t_start + t_dur):
                frac = (sol - t_peak) / max(1, (t_start + t_dur - t_peak))
                tau = 0.38 + (peak_tau - 0.38) * math.exp(-2.6 * frac)
                storm_sols_elapsed += 1
            else:
                tau = 0.38

            # Trigger event: Storm front arrival
            if sol == t_start and storm_scenario != "none":
                cascading_events.append({
                    "sol": sol,
                    "subsystem": "ENVIRONMENT",
                    "severity": "WARNING",
                    "title": f"Dust Storm Wall Front Inflow ({scen_info['label']})",
                    "directive": f"Atmospheric optical depth rising towards peak tau={peak_tau}. Secure EVA operations and switch PV array tracking to high-wind survival pitch."
                })

            # 2-4. Environment, solar generation and nominal demand (shared habitat model)
            gh_on = greenhouse_enabled and crop_health > 0
            loads = cls.habitat_daily_loads(lat, ls_deg, tau, crew, extraction_energy_kwh_kg, gh_on, float(water_recycling_eff))
            t_mean = loads["t_mean_c"]
            effective_insolation = cls.daily_insolation_kwh_m2(lat, ls_deg, tau)

            if dust_cleaners_active:
                dust_loss_pct = min(6.0, storm_sols_elapsed * 0.12)
            else:
                dust_loss_pct = min(45.0, storm_sols_elapsed * 0.45)
            dust_transmittance = 1.0 - (dust_loss_pct / 100.0)

            solar_gen_kwh = effective_insolation * pv_area_m2 * PV_EFFICIENCY * dust_transmittance
            aux_gen_kwh = float(nuclear_backup_kw) * 24.6
            total_available_kwh = solar_gen_kwh + aux_gen_kwh

            e_core = loads["core"]
            e_thermal = loads["thermal"]
            e_greenhouse = loads["greenhouse"]
            e_well = loads["well"]
            e_moxie = loads["moxie"]
            net_water_deficit = loads["net_water_l"]
            o2_crew_need = loads["o2_need_kg"]

            # 5. Stateful Battery & Automatic 4-Tier Load Shedding
            soc_pct = (b_current / b_cap) * 100.0
            min_battery_soc = min(min_battery_soc, soc_pct)

            # Determine Tier based on battery state-of-charge
            if soc_pct >= 40.0:
                tier = 0
                tier_label = "Nominal (Full ECLSS)"
                active_greenhouse = greenhouse_enabled and (crop_health > 0)
                active_well = True
                active_moxie = True
                actual_thermal = e_thermal
                actual_core = e_core
            elif soc_pct >= 25.0:
                tier = 1
                tier_label = "Tier 1: Greenhouse Shed"
                active_greenhouse = False
                active_well = True
                active_moxie = True
                actual_thermal = e_thermal
                actual_core = e_core
            elif soc_pct >= 12.0:
                tier = 2
                tier_label = "Tier 2: ISRU Well Shed"
                active_greenhouse = False
                active_well = False
                active_moxie = True
                actual_thermal = e_thermal
                actual_core = e_core
            elif soc_pct > 0.0:
                tier = 3
                tier_label = "Tier 3: MOXIE O2 Shed"
                active_greenhouse = False
                active_well = False
                active_moxie = False
                actual_thermal = e_thermal
                actual_core = e_core
            else:
                tier = 4
                tier_label = "Tier 4: Blackout Thermal Setback"
                active_greenhouse = False
                active_well = False
                active_moxie = False
                actual_thermal = e_thermal * 0.55  # Cabin allowed to chill to 10°C
                actual_core = e_core * 0.65       # Minimal avionics and CO2 scrubbers only

            # Log first occurrence of each load shedding tier
            if tier > 0 and tier not in observed_tiers:
                observed_tiers.add(tier)
                tier_directives = {
                    1: ("Greenhouse Grow Lights Powered Down", "CRITICAL", "Battery SoC < 40%. Hydroponic LED arrays isolated to save ~56 kWh/sol. Crops entering unlit dormancy."),
                    2: ("Subsurface Ice Extraction Well Halted", "CRITICAL", "Battery SoC < 25%. Thermal drill pumps powered off. Base operating exclusively on 90% closed-loop recycled water reserves."),
                    3: ("MOXIE Atmospheric O2 Electrolysis Suspended", "FATAL", "Battery SoC < 12%. Atmospheric CO2 electrolysis compressors shut down. Crew drawing from high-pressure O2 accumulator tanks."),
                    4: ("EMERGENCY POWER BLACKOUT: Habitat Thermal Setback", "FATAL", "Battery 0% depleted. Life support reduced to survival core. Habitat temperature setback to 10°C survival chill to avert structural cold-soak.")
                }
                t_title, t_sev, t_dir = tier_directives[tier]
                cascading_events.append({
                    "sol": sol,
                    "subsystem": "POWER",
                    "severity": t_sev,
                    "title": t_title,
                    "directive": t_dir
                })

            actual_demand = (
                actual_core + actual_thermal +
                (e_greenhouse if active_greenhouse else 0.0) +
                (e_well if active_well else 0.0) +
                (e_moxie if active_moxie else 0.0)
            )

            net_energy = total_available_kwh - actual_demand
            b_current = max(0.0, min(b_cap, b_current + net_energy))
            new_soc = (b_current / b_cap) * 100.0

            if new_soc <= 0.0:
                consecutive_blackout_sols += 1
                total_blackout_sols += 1
            else:
                consecutive_blackout_sols = 0

            # 6. Water Resource Dynamics
            if active_well:
                # Well extracts net deficit from ground ice/regolith
                pass
            else:
                # Water drawn from stored reserve
                w_current = max(0.0, w_current - net_water_deficit)

            if w_current <= 0.0 and fatal_sol is None:
                fatal_sol = sol + 2
                limiting_bottleneck = "WATER_EXHAUSTION"
                cascading_events.append({
                    "sol": sol,
                    "subsystem": "WATER",
                    "severity": "FATAL",
                    "title": "Water Reserves Exhausted",
                    "directive": "All potable water depleted. Urine recycling system insufficient for gross metabolic loss. Acute dehydration crisis within 48 hours."
                })

            # 7. Oxygen Resource Dynamics
            if active_moxie:
                # MOXIE replenishes crew respiration
                pass
            else:
                # Draw from stored O2 accumulator buffer
                o2_current = max(0.0, o2_current - o2_crew_need)

            if o2_current <= 0.0 and fatal_sol is None:
                fatal_sol = sol
                limiting_bottleneck = "OXYGEN_EXHAUSTION"
                cascading_events.append({
                    "sol": sol,
                    "subsystem": "ATMOSPHERE",
                    "severity": "FATAL",
                    "title": "High-Pressure Oxygen Accumulator Emptied",
                    "directive": "Cabin partial pressure of O2 falling below 16 kPa (hypoxia threshold). Crew must transition to EVA suit emergency O2 bottles immediately."
                })

            # 8. Food, Greenhouse & Metabolic State
            if active_greenhouse:
                consecutive_unlit_sols = 0
                greenhouse_fresh_kcal = (crop_health / 100.0) * 2100.0
            else:
                consecutive_unlit_sols += 1
                if consecutive_unlit_sols > 3:
                    crop_health = max(0.0, crop_health - 25.0)
                    if crop_health <= 0.0 and not greenhouse_died:
                        greenhouse_died = True
                        cascading_events.append({
                            "sol": sol,
                            "subsystem": "FOOD",
                            "severity": "WARNING",
                            "title": "Bioregenerative Greenhouse Crop Death",
                            "directive": "Prolonged darkness caused irreversible chlorophyll degradation and root freeze. Fresh biomass yield dropped to zero."
                        })
                greenhouse_fresh_kcal = (crop_health / 100.0) * 2100.0 if crop_health > 0 else 0.0

            # Rationing Strategy Target
            sols_food_left = (food_current * KCAL_PER_KG_RATION) / max(1.0, crew * 2800.0)
            if rationing_strategy == "auto_adaptive":
                if sols_food_left >= 45.0:
                    target_kcal = 2800.0
                elif sols_food_left >= 25.0:
                    target_kcal = 2100.0
                elif sols_food_left >= 12.0:
                    target_kcal = 1650.0
                else:
                    target_kcal = 1250.0
            elif rationing_strategy == "conservation":
                target_kcal = 2100.0
            elif rationing_strategy == "survival":
                target_kcal = 1550.0
            else:
                target_kcal = 2800.0

            crew_kcal_needed = target_kcal * crew
            kcal_from_stored = max(0.0, crew_kcal_needed - greenhouse_fresh_kcal)
            kg_stored_needed = kcal_from_stored / KCAL_PER_KG_RATION

            if food_current >= kg_stored_needed:
                food_current -= kg_stored_needed
                actual_kcal_person = target_kcal
            else:
                actual_store_kcal = food_current * KCAL_PER_KG_RATION
                food_current = 0.0
                actual_kcal_person = (actual_store_kcal + greenhouse_fresh_kcal) / crew

            # Metabolic Debt & Body Mass Loss
            caloric_deficit = max(0.0, 2200.0 - actual_kcal_person)
            cum_weight_loss_kg += (caloric_deficit / 7700.0)
            weight_loss_pct = (cum_weight_loss_kg / 75.0) * 100.0

            if (food_current <= 0.0 or weight_loss_pct >= 22.0) and fatal_sol is None:
                fatal_sol = sol
                limiting_bottleneck = "STARVATION_CACHEXIA"
                cascading_events.append({
                    "sol": sol,
                    "subsystem": "FOOD",
                    "severity": "FATAL",
                    "title": "Severe Starvation & Muscle Cachexia Threshold",
                    "directive": f"Crew body mass loss reached {round(weight_loss_pct, 1)}%. Cognitive function impaired; cardiac arrhythmia risk severe. Immediate supply capsule required."
                })

            # Check cold-soak blackout mortality
            if consecutive_blackout_sols >= 4 and t_mean < -50.0 and fatal_sol is None:
                fatal_sol = sol
                limiting_bottleneck = "HABITAT_COLD_SOAK"
                cascading_events.append({
                    "sol": sol,
                    "subsystem": "LIFE_SUPPORT",
                    "severity": "FATAL",
                    "title": "Catastrophic Habitat Cold-Soak Freeze",
                    "directive": "Power blackout exceeded 96 hours in sub-minus 60°C conditions. Environmental thermal seals compromised; life support electronics frozen."
                })

            # 9. Radiation Accumulation (Curiosity RAD elevation model)
            shielding_mult = math.exp(elevation_km / 15.0)  # Thicker atmosphere at low elevations reduces dose
            daily_gcr = NASA_GCR_SURFACE_BASELINE_MSV * shielding_mult
            daily_spe = 0.0

            if sol == int(spe_event_sol) and storm_scenario != "none":
                if storm_shelter_active:
                    daily_spe = 280.0 * 0.08  # Attenuated by 50cm regolith bunker
                    cascading_events.append({
                        "sol": sol,
                        "subsystem": "RADIATION",
                        "severity": "WARNING",
                        "title": "Solar Particle Event (SPE) Proton Storm Detected",
                        "directive": "Coronal mass ejection proton arrival. Crew safely hunkered in regolith core shelter (dose attenuated from 280 mSv to 22.4 mSv)."
                    })
                else:
                    daily_spe = 280.0
                    cascading_events.append({
                        "sol": sol,
                        "subsystem": "RADIATION",
                        "severity": "FATAL",
                        "title": "UNSHIELDED Solar Particle Event (SPE) Exposure",
                        "directive": "Major SPE proton burst received without regolith shelter. Crew received 280 mSv acute dose in 14 hours. Administer antiemetics."
                    })

            total_daily_rad = daily_gcr + daily_spe
            cum_rad_msv += total_daily_rad

            # 10. Composite Health / Survivability Index (0-100%)
            h_power = min(100.0, new_soc * 1.5)
            h_water = min(100.0, (w_current / max(1.0, float(initial_water_l))) * 100.0)
            h_o2 = min(100.0, (o2_current / max(1.0, float(initial_o2_kg))) * 100.0)
            h_food = max(0.0, 100.0 - (weight_loss_pct * 3.8))
            h_rad = max(0.0, 100.0 - (cum_rad_msv / NASA_RADIATION_CAREER_LIMIT_MSV) * 100.0)
            composite_health = round((h_power * 0.25) + (h_o2 * 0.30) + (h_water * 0.20) + (h_food * 0.15) + (h_rad * 0.10), 1)

            # Store Sol Telemetry
            timeline_data.append({
                "sol": sol,
                "ls_deg": round(ls_deg, 1),
                "tau": round(tau, 2),
                "t_mean_c": round(t_mean, 1),
                "solar_gen_kwh": round(solar_gen_kwh, 1),
                "aux_gen_kwh": round(aux_gen_kwh, 1),
                "total_available_kwh": round(total_available_kwh, 1),
                "actual_demand_kwh": round(actual_demand, 1),
                "battery_soc": round(new_soc, 1),
                "power_tier": tier,
                "power_tier_label": tier_label,
                "water_stored_l": round(w_current, 1),
                "water_well_active": active_well,
                "o2_stored_kg": round(o2_current, 1),
                "moxie_active": active_moxie,
                "food_stored_kg": round(food_current, 1),
                "daily_kcal_per_person": round(actual_kcal_person),
                "greenhouse_crop_health": round(crop_health, 1),
                "weight_loss_pct": round(weight_loss_pct, 1),
                "daily_rad_msv": round(total_daily_rad, 2),
                "cumulative_rad_msv": round(cum_rad_msv, 1),
                "composite_health_pct": composite_health,
                "crew_lost": fatal_sol is not None and sol >= fatal_sol
            })

        # Calculate Survival Runway
        survival_runway = fatal_sol if fatal_sol is not None else timeline

        # Resource specific runways
        runways = {
            "power": {
                "min_soc": round(min_battery_soc, 1),
                "blackout_sols": total_blackout_sols,
                "status": "SUSTAINED" if total_blackout_sols == 0 else f"{total_blackout_sols} Sols in Blackout Setback"
            },
            "oxygen": {
                "final_buffer_kg": round(o2_current, 1),
                "buffer_sols_left": round(o2_current / max(0.1, o2_crew_need), 1),
                "status": "DEPLETED" if o2_current <= 0 else "MAINTAINED"
            },
            "water": {
                "final_water_l": round(w_current, 1),
                "buffer_sols_left": round(w_current / max(0.1, net_water_deficit), 1),
                "status": "DEPLETED" if w_current <= 0 else "MAINTAINED"
            },
            "food": {
                "final_food_kg": round(food_current, 1),
                "weight_loss_max_pct": round(weight_loss_pct, 1),
                "status": "CRITICAL STARVATION" if weight_loss_pct >= 20.0 else "MANAGED DEFICIT"
            },
            "radiation": {
                "cumulative_msv": round(cum_rad_msv, 1),
                "pct_of_30day_limit": round((cum_rad_msv / NASA_RADIATION_30DAY_LIMIT_MSV) * 100.0, 1),
                "pct_of_career_limit": round((cum_rad_msv / NASA_RADIATION_CAREER_LIMIT_MSV) * 100.0, 1),
                "status": "WITHIN NASA LIMITS" if cum_rad_msv < NASA_RADIATION_30DAY_LIMIT_MSV else "EXCEEDS LIMITS"
            }
        }

        # Status categorization
        if survival_runway < timeline:
            overall_status = "LOSS OF CREW (LOC)"
            badge_color = "#dc2626"
        elif total_blackout_sols > 0 or weight_loss_pct > 12.0:
            overall_status = "CRITICAL SURVIVAL WITH MARGIN"
            badge_color = "#f59e0b"
        else:
            overall_status = "OPTIMAL SUSTAINED MISSION"
            badge_color = "#10b981"

        # Actionable Countermeasure Trade-offs
        countermeasures = [
            {
                "id": "cm_nuclear",
                "title": "Deploy 10 kW Kilopower Auxiliary Nuclear Generator",
                "tradeoff": "Adds 246 kWh/sol non-solar power. Prevents battery blackout completely and keeps MOXIE and Water Wells online throughout global PEDE.",
                "impact": "+100% Power Reliability; 0 Sols Blackout"
            },
            {
                "id": "cm_dust_cleaners",
                "title": "Activate Electrostatic & Mechanical Panel Wiper Arrays",
                "tradeoff": "Prevents 45% panel dust accumulation; caps dust degradation at 6%, boosting peak solar recovery by 35%.",
                "impact": "+35% Solar Power Recovery during Clearing"
            },
            {
                "id": "cm_shelter",
                "title": "Mandatory Regolith Storm Shelter Protocol",
                "tradeoff": "Requires crew confinement to 50cm regolith-shielded habitat core module during SPE peak window.",
                "impact": "Reduces acute SPE radiation dose by 92% (from 280 mSv to 22.4 mSv)"
            },
            {
                "id": "cm_early_rationing",
                "title": "Pre-Emptive Stage 2 Rationing (1,650 kcal/sol)",
                "tradeoff": "Initiate calorie conservation from Sol 1 rather than waiting for reserves to drain. Extends caloric runway by up to 28 sols.",
                "impact": "Extends survival runway by +28 sols; avoids sudden starvation crash"
            }
        ]

        return {
            "summary": {
                "site_id": site.get("id", "UNKNOWN"),
                "site_name": site_name,
                "crew_size": crew,
                "timeline_sols_simulated": timeline,
                "survival_runway_sols": survival_runway,
                "limiting_bottleneck": limiting_bottleneck,
                "overall_status": overall_status,
                "badge_color": badge_color,
                "min_battery_soc": round(min_battery_soc, 1),
                "total_blackout_sols": total_blackout_sols,
                "final_battery_soc": round(new_soc, 1),
                "final_water_l": round(w_current, 1),
                "final_o2_kg": round(o2_current, 1),
                "final_food_kg": round(food_current, 1),
                "max_weight_loss_pct": round(weight_loss_pct, 1),
                "cumulative_radiation_msv": round(cum_rad_msv, 1),
                "greenhouse_survived": not greenhouse_died,
                "scenario_name": scen_info["label"],
                "elevation_km": round(elevation_km, 2)
            },
            "runways": runways,
            "timeline": timeline_data,
            "events": cascading_events,
            "countermeasures": countermeasures
        }

    # ==========================================
    # 4. FOOD SHORTAGE & EXTENDED DURATION ENGINE
    # ==========================================
    @staticmethod
    def calculate_food_rationing_plan(
        crew_size: int,
        nominal_days: int,
        extended_days: int,
        food_stockpile_kg: float,
        greenhouse_daily_yield_kg: float = 0.0,
        crew_avg_weight_kg: float = 75.0
    ) -> Dict[str, Any]:
        """
        Calculates optimal survival food distribution and metabolic management
        when a mission experiences a food supply drop, contamination, or extended stay:
        - Energy density of dehydrated NASA flight rations ~ 4200 kcal/kg
        - Basal Metabolic Rate (BMR) using Mifflin-St Jeor / NASA Astronaut guidelines
        - Categorizes medical metabolic triage tiers (Nominal, Mild, Moderate, Severe, Starvation)
        - Projects body weight loss and organ failure threshold timelines
        - Generates phase-by-phase tactical rationing schedule
        """
        crew = max(1, crew_size)
        total_days = max(1, extended_days)
        stockpile = max(0.0, food_stockpile_kg)

        # NASA Ration Energy Density
        KCAL_PER_KG_RATION = 4200.0  # Dense freeze-dried space foods
        total_available_kcal = stockpile * KCAL_PER_KG_RATION

        # Greenhouse bioregenerative offset (microgreens, potatoes, chlorella ~ 600 kcal/kg fresh weight)
        greenhouse_kcal_per_day_total = greenhouse_daily_yield_kg * 600.0
        greenhouse_kcal_per_person_sol = greenhouse_kcal_per_day_total / crew

        # Baseline needs
        nominal_daily_kcal_per_person = NASA_BASELINE_CALORIES
        total_nominal_kcal_needed = crew * total_days * nominal_daily_kcal_per_person

        # Stored food calories that *could* be spread per astronaut per sol over the period
        affordable_stored_kcal = total_available_kcal / (crew * total_days)
        affordable_daily_kcal = affordable_stored_kcal + greenhouse_kcal_per_person_sol

        # The ration is capped at the nominal requirement: a large stockpile means a reserve
        # margin, never an instruction to eat more than nominal.
        effective_daily_kcal = min(nominal_daily_kcal_per_person, affordable_daily_kcal)
        stored_kcal_per_person_sol = max(0.0, effective_daily_kcal - greenhouse_kcal_per_person_sol)
        daily_grams_per_person = (stored_kcal_per_person_sol / KCAL_PER_KG_RATION) * 1000.0

        # Reserve left at the end of the period if the crew eats the (capped) ration
        consumed_kg = stored_kcal_per_person_sol * crew * total_days / KCAL_PER_KG_RATION
        reserve_kg_at_end = max(0.0, stockpile - consumed_kg)
        reserve_sols_at_nominal = reserve_kg_at_end * KCAL_PER_KG_RATION / max(
            1.0, crew * max(1.0, nominal_daily_kcal_per_person - greenhouse_kcal_per_person_sol))
        deficit_vs_nominal = max(0.0, nominal_daily_kcal_per_person - effective_daily_kcal)

        # Estimate Astronaut Basal Metabolic Rate (BMR)
        # Average adult astronaut BMR ~ 1650 kcal/day; with light activity ~ 2100 kcal
        bmr = 10 * crew_avg_weight_kg + 6.25 * 175 - 5 * 38 + 5  # ~ 1680 kcal
        active_maintenance_kcal = bmr * 1.35  # ~ 2270 kcal with light hab tasks

        # Deficit calculation
        daily_caloric_deficit = max(0.0, active_maintenance_kcal - effective_daily_kcal)

        # Triage Severity Classification
        if effective_daily_kcal >= 2500:
            severity = "NOMINAL"
            badge_color = "#10b981"  # Emerald Green
            if reserve_kg_at_end > 0.5:
                status_desc = (f"Stockpile covers the full period at nominal intake with "
                               f"{round(reserve_kg_at_end)} kg reserve (~{round(reserve_sols_at_nominal)} extra sols).")
            else:
                status_desc = "Optimal Nutritional State. Standard operational capacity."
            restriction_level = "Full Nutrition - Normal Operations"
        elif effective_daily_kcal >= 2000:
            severity = "MILD CONSERVATION"
            badge_color = "#3b82f6"  # Blue
            status_desc = "Mild Caloric Deficit. Safe for extended missions with targeted activity reductions."
            restriction_level = "Stage 1 Conservation - Light Cognitive & Hab Maintenance"
        elif effective_daily_kcal >= 1550:
            severity = "MODERATE RATIONING"
            badge_color = "#f59e0b"  # Amber
            status_desc = "Significant Deficit. Ketone adaptation required. Restrict EVAs to critical repairs only."
            restriction_level = "Stage 2 Severe Rationing - Emergency Operations Only"
        elif effective_daily_kcal >= 1200:
            severity = "CRITICAL SURVIVAL"
            badge_color = "#ef4444"  # Red
            status_desc = "Near Basal Limit. Rapid muscle mass & glycogen depletion. Crew confined to low-metabolism protocol."
            restriction_level = "Stage 3 Basal Survival - Strict Bedrest / Hibernation Profile"
        else:
            severity = "UNSURVIVABLE DEFICIT"
            badge_color = "#dc2626"  # Dark Red
            status_desc = "Immediate Starvation Hazard. Current reserves will induce fatal cachexia before mission end."
            restriction_level = "Stage 4 Emergency Distress - External Supply Airdrop Mandatory"

        # Projected weight loss over the period (7700 kcal deficit ~ 1 kg fat/muscle tissue)
        total_deficit_per_person = daily_caloric_deficit * total_days
        # Linear projection is only meaningful up to the lethal range, so cap it at 40% body mass
        # and report when the crew would cross the 18% danger threshold instead.
        raw_loss_kg = total_deficit_per_person / 7700.0
        est_total_weight_loss_kg = round(min(raw_loss_kg, 0.40 * crew_avg_weight_kg), 1)
        est_weight_loss_pct = round((est_total_weight_loss_kg / crew_avg_weight_kg) * 100.0, 1)
        sols_to_danger_mass_loss = (round((0.18 * crew_avg_weight_kg * 7700.0) / daily_caloric_deficit)
                                    if daily_caloric_deficit > 0 else None)

        # Survival runway: how many days could the crew survive at nominal 2800 kcal vs at minimum survival 1500 kcal
        sols_at_nominal = round(total_available_kcal / (crew * nominal_daily_kcal_per_person), 1)
        sols_at_emergency = round(total_available_kcal / (crew * 1500.0), 1)

        # Phased Distribution Guidelines.
        # Every phase uses the same calorie budget so the plan never spends more food than exists;
        # phases change macro composition and crew workload, not the total.
        ration = round(effective_daily_kcal)
        if deficit_vs_nominal < 1.0:
            phases = [{
                "phase": f"Nominal Operations (Days 1 - {total_days})",
                "daily_kcal": ration,
                "diet_focus": f"Standard {round(daily_grams_per_person)} g/sol dry ration. "
                              f"Hold the {round(reserve_kg_at_end)} kg surplus as a contingency reserve.",
                "crew_protocol": "No restrictions. Re-run this plan if the stockpile or the timeline changes."
            }]
        else:
            p1_end = min(5, total_days)
            p3_len = min(10, max(0, total_days - p1_end))
            p2_end = total_days - p3_len
            phases = [{
                "phase": f"Phase 1: Ketogenic Transition (Days 1 - {p1_end})",
                "daily_kcal": ration,
                "diet_focus": "Prioritize high-lipid & protein rations to adapt to ketone metabolism, reducing glucose crashes.",
                "crew_protocol": "Taper physical workload. Reduce treadmill/resistive exercise from 2.5h to 1h."
            }]
            if p2_end > p1_end:
                phases.append({
                    "phase": f"Phase 2: Steady Sustained Rationing (Days {p1_end + 1} - {p2_end})",
                    "daily_kcal": ration,
                    "diet_focus": f"Strict {round(daily_grams_per_person)} g/sol allocation. Split into 2 equal meal windows.",
                    "crew_protocol": "Maintain hydration (>3.0 L/sol) and electrolytes. Keep habitat warm enough to avoid shivering thermogenesis."
                })
            if p3_len > 0:
                phases.append({
                    "phase": f"Phase 3: Pre-Egress Metabolic Buffer (Days {p2_end + 1} - {total_days})",
                    "daily_kcal": ration,
                    "diet_focus": "Same calories, shifted toward carbohydrates 72 hours before ERV launch or EVA egress.",
                    "crew_protocol": "Regain neuromuscular coordination and blood pressure stability for high-G launch."
                })

        actionable_guidelines = [
            f"Daily Ration Budget: {round(effective_daily_kcal)} kcal per crew member per sol = "
            f"{round(daily_grams_per_person)} g dry ration + {round(greenhouse_kcal_per_person_sol)} kcal greenhouse produce.",
        ]
        if deficit_vs_nominal < 1.0:
            actionable_guidelines.append(
                f"Reserve: {round(reserve_kg_at_end)} kg of rations remain at the end of sol {total_days} "
                f"(~{round(reserve_sols_at_nominal)} extra sols at nominal intake). Keep it sealed as contingency stock.")
        else:
            actionable_guidelines += [
                "Water Multiplier: Increase fluid intake to 3.2+ L/sol. In caloric deficits, elevated protein oxidation increases blood urea nitrogen (BUN).",
                "Metabolic Conservation: Lower habitat ambient night temperature to 19°C; extend mandatory sleep window by 1.5 hours to suppress basal caloric burn.",
                "Exercise Modulation: Stop heavy endurance cardio; keep 30-min resistance training to limit bone and muscle loss without burning >200 kcal.",
                "Greenhouse Integration: Prioritize fast-cycle algae (Spirulina) and hydroponic microgreens for micronutrients (Vitamin C, B12, Magnesium) missing in depleted stores."
            ]

        if est_weight_loss_pct > 18.0:
            actionable_guidelines.insert(0, f"CRITICAL WARNING: Crew would pass 18% body-mass loss around sol {sols_to_danger_mass_loss} "
                                            f"(cardiac arrhythmia and immune-failure risk). This plan cannot reach sol {total_days}: "
                                            f"shorten the stay, evacuate, or obtain resupply.")

        return {
            "crew_size": crew,
            "nominal_days": nominal_days,
            "extended_days": total_days,
            "duration_delta_days": total_days - nominal_days,
            "food_stockpile_kg": stockpile,
            "total_available_kcal": round(total_available_kcal),
            "effective_daily_kcal_per_person": round(effective_daily_kcal),
            "daily_grams_per_person": round(daily_grams_per_person, 1),
            "daily_caloric_deficit": round(daily_caloric_deficit),
            "deficit_vs_nominal_kcal": round(deficit_vs_nominal),
            "affordable_daily_kcal_per_person": round(affordable_daily_kcal),
            "reserve_kg_at_end": round(reserve_kg_at_end, 1),
            "sols_to_danger_mass_loss": sols_to_danger_mass_loss,
            "reserve_sols_at_nominal": round(reserve_sols_at_nominal, 1),
            "greenhouse_supplement_kcal": round(greenhouse_kcal_per_person_sol),
            "severity": severity,
            "badge_color": badge_color,
            "status_desc": status_desc,
            "restriction_level": restriction_level,
            "est_weight_loss_kg": est_total_weight_loss_kg,
            "est_weight_loss_pct": est_weight_loss_pct,
            "sols_at_nominal": sols_at_nominal,
            "sols_at_emergency": sols_at_emergency,
            "phases": phases,
            "actionable_guidelines": actionable_guidelines
        }

    # ==========================================
    # 4. MULTI-CRITERIA EVALUATION & RANKING
    # ==========================================
    _solar_cache: Dict[float, Dict[str, float]] = {}

    @classmethod
    def modelled_solar_score(cls, lat: float) -> Dict[str, float]:
        """Solar score from the irradiance model itself (so ranking and monitor agree):
        40% annual-mean yield + 60% worst-season yield, relative to an equatorial site."""
        key = round(lat, 2)
        if key not in cls._solar_cache:
            eq = cls.site_solar_profile(0.0)
            sp = cls.site_solar_profile(lat)
            score = 100.0 * (0.4 * sp["mean"] / eq["mean"] + 0.6 * sp["min"] / eq["min"])
            cls._solar_cache[key] = {"score": round(min(100.0, score), 1), "mean_kwh_m2": round(sp["mean"], 2),
                                     "min_kwh_m2": round(sp["min"], 2)}
        return cls._solar_cache[key]

    @classmethod
    def storm_resilience(cls, site: Dict[str, Any], habitat: Dict[str, Any]) -> Dict[str, Any]:
        """Run the coupled cascade with a regional dust storm in the mission season using the
        shared habitat, and turn the outcome into a 0-100 score."""
        h = merge_habitat(habitat)
        r = cls.run_cascade_for_habitat(site, h, storm_scenario="regional")
        s = r["summary"]
        T = s["timeline_sols_simulated"]
        if s["survival_runway_sols"] < T:
            score = 55.0 * s["survival_runway_sols"] / T
        elif s["total_blackout_sols"] > 0:
            score = 60.0 - 20.0 * min(1.0, s["total_blackout_sols"] / T)
        else:
            score = 70.0 + 30.0 * s["min_battery_soc"] / 100.0
        return {"score": round(score, 1), "runway_sols": s["survival_runway_sols"], "timeline": T,
                "min_soc": s["min_battery_soc"], "bottleneck": s["limiting_bottleneck"],
                "status": s["overall_status"]}

    @classmethod
    def run_cascade_for_habitat(cls, site: Dict[str, Any], habitat: Dict[str, Any], storm_scenario: str = "regional",
                                storm_start_sol: int = 5, storm_duration_sols: int = 35, **overrides) -> Dict[str, Any]:
        """Cascade driven by the shared habitat config (single entry point for every module)."""
        h = merge_habitat(habitat)
        kw = dict(
            site_data=site, crew_size=h["crew"], timeline_sols=h["mission_sols"], storm_scenario=storm_scenario,
            storm_start_sol=storm_start_sol, storm_duration_sols=storm_duration_sols, pv_area_m2=h["pv_area_m2"],
            battery_capacity_kwh=h["battery_kwh"], nuclear_backup_kw=h["nuclear_kw"],
            initial_water_l=h["water_l"], water_recycling_eff=h["water_recycling_eff"], initial_o2_kg=h["o2_kg"],
            initial_food_kg=h["food_kg"], greenhouse_enabled=h["greenhouse"], start_ls_deg=h["start_ls"],
        )
        kw.update(overrides)
        return cls.simulate_compound_crisis_cascade(**kw)

    @classmethod
    def evaluate_settlement_site(
        cls,
        site: Dict[str, Any],
        crew: int,
        duration_sols: int,
        user_weights: Dict[str, float] = None,
        habitat: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Multi-criteria site suitability. Computed criteria: water (multi-sensor model), solar
        (irradiance model, mean + worst season), storm resilience (coupled cascade with the shared
        habitat). Assigned criteria (from the site data file): landing, terrain, thermal, comms.
        """
        weights = user_weights or {
            "water": 0.24, "landing": 0.18, "terrain": 0.12, "solar": 0.16,
            "temperature": 0.08, "communication": 0.07, "resilience": 0.15
        }
        weights = {k: float(weights.get(k, 0.0)) for k in
                   ("water", "landing", "terrain", "solar", "temperature", "communication", "resilience")}
        total_w = sum(weights.values()) or 1.0
        norm_weights = {k: v / total_w for k, v in weights.items()}

        h = merge_habitat(habitat)
        h["crew"] = int(crew)

        water_analysis = cls.calculate_water_potential(site.get("scientific_water_evidence", {}))
        water_score = water_analysis["score"]
        solar = cls.modelled_solar_score(site["lat"])
        solar_score = solar["score"]
        resilience = cls.storm_resilience(site, h)

        landing_score = site.get("landing_safety", 80)
        terrain_score = site.get("terrain_suitability", 85)
        temp_score = site.get("thermal_score", 75)
        comm_score = site.get("communication_score", 88)

        contributions = {
            "water": water_score * norm_weights["water"],
            "landing": landing_score * norm_weights["landing"],
            "terrain": terrain_score * norm_weights["terrain"],
            "solar": solar_score * norm_weights["solar"],
            "temperature": temp_score * norm_weights["temperature"],
            "communication": comm_score * norm_weights["communication"],
            "resilience": resilience["score"] * norm_weights["resilience"],
        }
        site_suitability = round(sum(contributions.values()), 1)

        req = {
            "water_l": round(crew * duration_sols * NASA_BASELINE_WATER),
            "oxygen_kg": round(crew * duration_sols * NASA_BASELINE_OXYGEN),
            "food_kg": round(crew * duration_sols * (NASA_BASELINE_CALORIES / KCAL_PER_KG_RATION), 1),
        }

        if resilience["runway_sols"] < resilience["timeline"]:
            status = "FAILS REGIONAL-STORM TEST"
        elif resilience["min_soc"] < 25:
            status = "SURVIVES WITH LOAD SHEDDING"
        else:
            status = "STORM-RESILIENT CANDIDATE"

        return {
            **site,
            "water_scientific": water_analysis,
            "solar_model": solar,
            "resilience": resilience,
            "calculated_scores": {
                "water": water_score,
                "solar": solar_score,
                "landing": landing_score,
                "terrain": terrain_score,
                "temperature": temp_score,
                "communication": comm_score,
                "resilience": resilience["score"],
                "site_suitability": site_suitability,
                "final_composite_score": site_suitability
            },
            "score_contributions": {k: round(v, 1) for k, v in contributions.items()},
            "assigned_criteria": ["landing", "terrain", "temperature", "communication"],
            "requirements": req,
            "status": status,
        }

    # ==========================================
    # 5. CRISIS DECISION SUPPORT (offline, no Earth link required)
    # ==========================================
    REGIONAL_STORM_RADIUS_KM = 1500.0   # typical regional storm footprint (order 10^6 km^2)
    CONJUNCTION_ANGLE_DEG = 3.0         # Sun-Earth-Mars angle below which the radio link is unusable

    @staticmethod
    def mars_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Great-circle surface distance on Mars (haversine, mean radius 3389.5 km)."""
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = p2 - p1, math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * MARS_RADIUS_KM * math.asin(math.sqrt(a))

    @staticmethod
    def _outcome(r: Dict[str, Any]) -> Dict[str, Any]:
        s = r["summary"]
        return {
            "runway_sols": s["survival_runway_sols"], "timeline": s["timeline_sols_simulated"],
            "survives": s["survival_runway_sols"] >= s["timeline_sols_simulated"],
            "bottleneck": s["limiting_bottleneck"], "min_soc": s["min_battery_soc"],
            "blackout_sols": s["total_blackout_sols"], "weight_loss_pct": s["max_weight_loss_pct"],
            "final_food_kg": s["final_food_kg"], "status": s["overall_status"],
        }

    @classmethod
    def evaluate_countermeasures(cls, site: Dict[str, Any], habitat: Dict[str, Any], storm_scenario: str,
                                 storm_start_sol: int = 5, storm_duration_sols: int = 35) -> Dict[str, Any]:
        """Re-runs the coupled simulation once per countermeasure and reports the real change in
        survival runway (replaces the previous hardcoded 'impact' text)."""
        h = merge_habitat(habitat)
        run = lambda **o: cls._outcome(cls.run_cascade_for_habitat(
            site, h, storm_scenario, storm_start_sol, storm_duration_sols, **o))
        base = run()
        options = [
            ("shed_greenhouse", "Power down greenhouse grow-lights now", "procedure",
             "Saves ~56 kWh/sol from sol 1 instead of waiting for the battery to hit 40%; costs ~2,100 kcal/sol of fresh food.",
             {"greenhouse_enabled": False}),
            ("ration_now", "Start 2,100 kcal conservation rations now", "procedure",
             "Stretches stored food; mild deficit (~0.1 kg/person/sol body-mass loss).",
             {"rationing_strategy": "conservation"}),
            ("clean_panels", "Clean PV arrays every sol (EVA brushing / electrostatic)", "procedure",
             "Caps dust deposition loss at 6% instead of up to 45%.",
             {"dust_cleaners_active": True}),
            ("combined", "All three procedures together", "procedure",
             "Greenhouse off + conservation rations + daily panel cleaning.",
             {"greenhouse_enabled": False, "rationing_strategy": "conservation", "dust_cleaners_active": True}),
            ("nuclear", "Add a 10 kW fission power unit", "hardware",
             "Design change, not an in-crisis action: adds ~246 kWh/sol independent of dust.",
             {"nuclear_backup_kw": h["nuclear_kw"] + 10.0}),
        ]
        results = []
        for key, title, kind, note, over in options:
            o = run(**over)
            results.append({"id": key, "title": title, "kind": kind, "note": note, **o,
                            "runway_gain_sols": o["runway_sols"] - base["runway_sols"],
                            "min_soc_gain": round(o["min_soc"] - base["min_soc"], 1),
                            "blackout_sols_saved": base["blackout_sols"] - o["blackout_sols"]})
        return {"baseline": base, "options": results}

    @classmethod
    def relocation_options(cls, origin: Dict[str, Any], sites: List[Dict[str, Any]], habitat: Dict[str, Any],
                           storm_scenario: str, storm_start_sol: int = 5, storm_duration_sols: int = 35) -> Dict[str, Any]:
        """
        'Where do we go?' Ranks every other candidate site as an evacuation destination.
        Assumptions (shown in the UI): crew leaves on sol 1 by pressurized rover; each destination
        hosts a pre-positioned outpost with the same habitat config; a regional storm only covers
        sites within REGIONAL_STORM_RADIUS_KM of the origin, a global storm covers all of Mars.
        """
        h = merge_habitat(habitat)
        T = h["mission_sols"]
        stay = cls._outcome(cls.run_cascade_for_habitat(origin, h, storm_scenario, storm_start_sol, storm_duration_sols))
        dests = []
        for d in sites:
            if d["id"] == origin["id"]:
                continue
            dist = cls.mars_distance_km(origin["lat"], origin["lon"], d["lat"], d["lon"])
            transit = max(1, math.ceil(dist / h["rover_km_per_sol"]))
            reachable = transit <= h["rover_endurance_sols"]
            if storm_scenario in ("global_pede", "extreme_pede"):
                d_scen = storm_scenario
            elif storm_scenario == "regional" and dist <= cls.REGIONAL_STORM_RADIUS_KM:
                d_scen = "regional"
            else:
                d_scen = "none"
            # Time-shift the storm and the season to the crew's arrival.
            elapsed = transit
            storm_label = d_scen
            d_start, d_dur = storm_start_sol - elapsed, storm_duration_sols
            if d_scen != "none":
                storm_end_rel = storm_start_sol + storm_duration_sols - elapsed
                if storm_end_rel < 1:
                    d_scen, storm_label = "none", "ended before arrival"
                elif d_start < 1:
                    d_dur, d_start = max(5, storm_end_rel), 1
            d_start = max(1, d_start)
            # The crew has to live at the destination afterwards: test a full horizon from arrival.
            h_d = dict(h, start_ls=(h["start_ls"] + elapsed * 0.524) % 360.0)
            o = cls._outcome(cls.run_cascade_for_habitat(d, h_d, d_scen, d_start, d_dur))
            total_runway = elapsed + o["runway_sols"]
            if not reachable:
                verdict = "OUT OF RANGE"
            elif o["survives"] and not stay["survives"]:
                verdict = "RELOCATE"
            elif o["survives"]:
                verdict = "SAFE ALTERNATIVE"
            elif o["runway_sols"] > stay["runway_sols"]:
                verdict = "BETTER, NOT SAFE"
            else:
                verdict = "WORSE"
            dests.append({
                "id": d["id"], "name": d["name"], "lat": d["lat"], "lon": d["lon"],
                "distance_km": round(dist), "transit_sols": transit, "reachable": reachable,
                "storm_at_destination": storm_label, "destination_outcome": o,
                "total_runway_sols": total_runway, "gain_vs_stay": min(T, total_runway) - stay["runway_sols"],
                "verdict": verdict,
            })
        order = {"RELOCATE": 0, "SAFE ALTERNATIVE": 1, "BETTER, NOT SAFE": 2, "WORSE": 3, "OUT OF RANGE": 4}
        dests.sort(key=lambda x: (order[x["verdict"]], -x["total_runway_sols"], x["transit_sols"]))
        best = next((x for x in dests if x["verdict"] == "RELOCATE"), None)
        return {
            "origin": {"id": origin["id"], "name": origin["name"]}, "stay": stay, "destinations": dests,
            "recommended": best,
            "rover_range_km": round(h["rover_km_per_sol"] * h["rover_endurance_sols"]),
            "assumptions": [
                f"Pressurized rover: {h['rover_km_per_sol']:.0f} km/sol, {h['rover_endurance_sols']} sols of life support "
                f"(max range ~{round(h['rover_km_per_sol'] * h['rover_endurance_sols'])} km).",
                "Each destination hosts a pre-positioned outpost with the same habitat configuration.",
                f"A regional storm covers sites within {cls.REGIONAL_STORM_RADIUS_KM:.0f} km of the origin; a global storm covers all of Mars.",
            ],
        }

    @classmethod
    def comm_outlook(cls, when_utc, horizon_days: int = 800) -> Dict[str, Any]:
        """Current Earth-Mars light time and the next solar-conjunction blackout window."""
        now = cls.earth_mars_geometry(when_utc, 0.0)
        in_conj = now["sun_earth_mars_angle_deg"] < cls.CONJUNCTION_ANGLE_DEG
        start = end = None
        for day in range(0, horizon_days):
            ang = cls.earth_mars_geometry(when_utc, float(day))["sun_earth_mars_angle_deg"]
            if start is None and ang < cls.CONJUNCTION_ANGLE_DEG:
                start = day
            elif start is not None and ang >= cls.CONJUNCTION_ANGLE_DEG:
                end = day
                break
        return {
            **now, "round_trip_min": round(2 * now["one_way_light_min"], 1), "in_conjunction": in_conj,
            "next_conjunction_in_days": start, "next_conjunction_length_days": (end - start) if (start is not None and end) else None,
        }

    @classmethod
    def crisis_assessment(cls, site: Dict[str, Any], sites: List[Dict[str, Any]], habitat: Dict[str, Any],
                          storm_scenario: str, storm_start_sol: int, storm_duration_sols: int, when_utc) -> Dict[str, Any]:
        """One-screen answer for the crew: how long do we have, what do we do first, where do we go."""
        h = merge_habitat(habitat)
        base_run = cls.run_cascade_for_habitat(site, h, storm_scenario, storm_start_sol, storm_duration_sols)
        base = cls._outcome(base_run)
        cms = cls.evaluate_countermeasures(site, h, storm_scenario, storm_start_sol, storm_duration_sols)
        reloc = cls.relocation_options(site, sites, h, storm_scenario, storm_start_sol, storm_duration_sols)
        comm = cls.comm_outlook(when_utc)
        T = base["timeline"]
        sol_days = 1.0275

        procs = [o for o in cms["options"] if o["kind"] == "procedure" and o["id"] != "combined"]
        combined = next(o for o in cms["options"] if o["id"] == "combined")
        helpful = sorted([o for o in procs if o["runway_gain_sols"] >= 0 and
                          (o["runway_gain_sols"] > 0 or o["blackout_sols_saved"] > 0 or o["min_soc_gain"] > 5)],
                         key=lambda o: (-o["runway_gain_sols"], -o["blackout_sols_saved"], -o["min_soc_gain"]))

        actions = []
        if base["survives"] and base["blackout_sols"] == 0 and base["min_soc"] >= 25:
            level = "STABLE"
        elif base["survives"]:
            level = "AT RISK"
        else:
            level = "CRITICAL"

        best = reloc["recommended"]
        best_proc_runway = combined["runway_sols"]
        if not base["survives"] and best and (combined["runway_sols"] < T):
            actions.append({"priority": 1, "kind": "RELOCATE",
                            "title": f"Evacuate to {best['name']}",
                            "detail": f"{best['distance_km']:,} km by pressurized rover, ~{best['transit_sols']} sols in transit. "
                                      f"Staying gives {base['runway_sols']} sols; even with every procedure, {combined['runway_sols']} sols. "
                                      f"The destination outlasts the {T}-sol horizon."})
        for o in helpful[:3]:
            gain = (f"+{o['runway_gain_sols']} sols survival runway" if o["runway_gain_sols"] > 0 else
                    f"{o['blackout_sols_saved']} fewer blackout sols" if o["blackout_sols_saved"] > 0 else
                    f"battery floor +{o['min_soc_gain']:.0f} pts")
            actions.append({"priority": len(actions) + 1, "kind": "PROCEDURE", "title": o["title"],
                            "detail": f"{gain}. {o['note']}"})
        if not base["survives"] and not best and combined["runway_sols"] < T:
            actions.append({"priority": len(actions) + 1, "kind": "ESCALATE",
                            "title": "No modelled option survives: prepare abort-to-orbit / resupply decision",
                            "detail": f"Best case with all procedures: {combined['runway_sols']} of {T} sols. "
                                      f"No candidate outpost is within rover range ({reloc['rover_range_km']:,} km) with a better outcome."})
        crisis_days = base["runway_sols"] * sol_days
        if comm["in_conjunction"]:
            actions.append({"priority": len(actions) + 1, "kind": "COMMS",
                            "title": "Earth link unavailable (solar conjunction): act autonomously",
                            "detail": "Mars is behind the Sun as seen from Earth. Log every decision locally; DTN will forward when the link returns."})
        elif comm["next_conjunction_in_days"] is not None and comm["next_conjunction_in_days"] <= crisis_days:
            actions.append({"priority": len(actions) + 1, "kind": "COMMS",
                            "title": f"Brief Earth now: blackout starts in {comm['next_conjunction_in_days']} days",
                            "detail": f"Solar conjunction (~{comm['next_conjunction_length_days']} days) falls inside this crisis window. "
                                      f"Current delay {comm['one_way_light_min']} min one way."})
        else:
            actions.append({"priority": len(actions) + 1, "kind": "COMMS",
                            "title": f"Send status to Earth (reply in ≥{comm['round_trip_min']} min)",
                            "detail": f"One-way light time {comm['one_way_light_min']} min, so decisions in the next hour are the crew's. "
                                      f"Next solar-conjunction blackout in {comm['next_conjunction_in_days']} days."})
        spe = next((e for e in base_run["events"] if e["subsystem"] == "RADIATION"), None)
        if spe and len(actions) < 5:
            actions.append({"priority": len(actions) + 1, "kind": "RADIATION",
                            "title": f"Keep the regolith storm shelter ready (SPE modelled on sol {spe['sol']})",
                            "detail": "Sheltering cuts a 280 mSv solar-particle dose to ~22 mSv."})

        first_events = [e for e in base_run["events"] if e["severity"] in ("CRITICAL", "FATAL")][:4]
        return {
            "site": {"id": site["id"], "name": site["name"], "lat": site["lat"], "lon": site["lon"]},
            "scenario": base_run["summary"]["scenario_name"], "level": level,
            "baseline": base, "with_all_procedures": {k: combined[k] for k in ("runway_sols", "survives", "min_soc", "blackout_sols")},
            "actions": actions[:5], "countermeasures": cms["options"], "relocation": reloc, "comm": comm,
            "key_events": first_events, "timeline": [
                {k: t[k] for k in ("sol", "battery_soc", "o2_stored_kg", "food_stored_kg", "water_stored_l", "power_tier", "crew_lost")}
                for t in base_run["timeline"]],
            "habitat": h,
        }
