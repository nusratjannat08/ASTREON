"""
ASTREON NASA Data Integration Client
Connects to:
- api.nasa.gov: Mars Weather (InSight/REMS), Mars Rover Surface Photos, APOD
- data.nasa.gov: NASA Open Data, PDS MOLA Elevation, GRS Hydrogen maps, CRISM Spectral catalogs
- code.nasa.gov: Open-source NASA software models (SPICE, Ames Mars GCM, ION DTN)

Includes local caching and fallback models to guarantee seamless operation
offline or when NASA API limits are reached.
"""

import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

DEFAULT_NASA_API_KEY = os.environ.get("NASA_API_KEY", "DEMO_KEY")
CACHE_FILE = Path(__file__).resolve().parent / "data" / "nasa_cache.json"
STATUS_TTL_S = 300  # re-probe api.nasa.gov at most every 5 minutes (DEMO_KEY allows ~30 req/h)

# Link modes shown in the UI. Honest by design: the app is meant to keep working through a
# Mars-Earth communication blackout, so the crew must always know how fresh the data is.
MODE_LIVE = "LIVE"            # api.nasa.gov answered just now
MODE_CACHED = "CACHED"        # offline, serving the last real NASA response saved to disk
MODE_OFFLINE = "OFFLINE MODEL"  # offline, no cached response: built-in calibrated model values


class NASAClient:
    def __init__(self, api_key: str = DEFAULT_NASA_API_KEY):
        self.api_key = api_key
        self.cache: Dict[str, Any] = {}
        self._status: Optional[Dict[str, Any]] = None
        self._status_at = 0.0
        self.disk = self._load_disk_cache()

    # ---------- persistence of last-known-good NASA responses ----------
    @staticmethod
    def _load_disk_cache() -> Dict[str, Any]:
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_disk(self, key: str, payload: Any) -> None:
        self.disk[key] = {"fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "data": payload}
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.disk, f, indent=1)
        except Exception:
            pass

    def _fetch_json(self, url: str, timeout: float = 4.0) -> Any:
        req = urllib.request.Request(url, headers={"User-Agent": "ASTREON-Mars-Mission-App/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def set_api_key(self, api_key: str) -> None:
        if api_key and api_key.strip():
            self.api_key = api_key.strip()
            self._status = None  # force re-probe with the new key

    def get_api_key(self) -> str:
        return self.api_key

    def link_status(self, force: bool = False) -> Dict[str, Any]:
        """
        Overall data-link state for the top-bar badge: LIVE / CACHED / OFFLINE MODEL.
        Probes api.nasa.gov (APOD, the cheapest always-on endpoint) at most every STATUS_TTL_S.
        """
        now = time.time()
        if self._status and not force and (now - self._status_at) < STATUS_TTL_S:
            return self._status
        probe = self.test_connection()
        if probe.get("online"):
            mode, detail = MODE_LIVE, "api.nasa.gov reachable"
        elif self.disk:
            newest = max(v.get("fetched_at", "") for v in self.disk.values())
            mode, detail = MODE_CACHED, f"Offline — using last NASA data received {newest}"
        else:
            mode, detail = MODE_OFFLINE, "Offline — no cached NASA data; running built-in models"
        self._status = {
            "mode": mode,
            "detail": detail,
            "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "api_key_is_demo": self.api_key == "DEMO_KEY",
            "error": probe.get("error"),
        }
        self._status_at = now
        return self._status

    # ==========================================
    # 1. API.NASA.GOV SERVICES
    # ==========================================
    def test_connection(self) -> Dict[str, Any]:
        """
        Tests connectivity to api.nasa.gov using the configured API key.
        """
        url = f"https://api.nasa.gov/planetary/apod?api_key={self.api_key}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ASTREON-Mars-Mission-App/1.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                status_code = response.getcode()
                data = json.loads(response.read().decode("utf-8"))
                return {
                    "online": True,
                    "status_code": status_code,
                    "service": "api.nasa.gov",
                    "api_key_valid": True,
                    "sample_title": data.get("title", "NASA Astronomy Service"),
                    "date": data.get("date", datetime.utcnow().strftime("%Y-%m-%d"))
                }
        except Exception as e:
            return {
                "online": False,
                "status_code": 0,
                "service": "api.nasa.gov",
                "api_key_valid": False,
                "error": str(e),
                "fallback_active": True,
                "message": "Network offline or API limit reached. Operating in NASA Calibrated Offline Model mode."
            }

    def get_mars_weather(self) -> Dict[str, Any]:
        """
        Mars surface weather from the api.nasa.gov InSight endpoint.
        NOTE: InSight's mission ended in Dec 2022, so even a LIVE response is archival
        (the feed returns the last sols InSight transmitted). The UI labels it that way.
        Fallback order: live API -> last response cached on disk -> built-in climatology.
        """
        cache_key = "mars_weather"
        url = f"https://api.nasa.gov/insight_weather/?api_key={self.api_key}&feedtype=json&ver=1.0"
        try:
            raw_data = self._fetch_json(url)
            sol_keys = raw_data.get("sol_keys", [])
            if sol_keys:
                latest_sol = sol_keys[-1]
                sol_data = raw_data[latest_sol]
                weather = {
                    "source": "api.nasa.gov / NASA InSight APSS (archival feed — mission ended 2022)",
                    "sol": latest_sol,
                    "season_ls": sol_data.get("Season", "n/a"),
                    "temp_avg_c": sol_data.get("AT", {}).get("av"),
                    "temp_min_c": sol_data.get("AT", {}).get("mn"),
                    "temp_max_c": sol_data.get("AT", {}).get("mx"),
                    "pressure_pa": sol_data.get("PRE", {}).get("av"),
                    "wind_speed_ms": sol_data.get("HWS", {}).get("av"),
                    "wind_direction_deg": sol_data.get("WD", {}).get("most_common", {}).get("compass_degrees"),
                    "is_live": True,
                }
                self._save_disk(cache_key, weather)
                return {**weather, "mode": MODE_LIVE}
        except Exception:
            pass

        if cache_key in self.disk:
            entry = self.disk[cache_key]
            return {**entry["data"], "is_live": False, "mode": MODE_CACHED, "fetched_at": entry["fetched_at"]}

        # Built-in climatology baseline (InSight / Elysium Planitia typical values)
        return {
            "source": "Built-in climatology baseline (InSight-era Elysium Planitia typical sol)",
            "sol": "n/a",
            "season_ls": "Ls ~164° (Northern late summer)",
            "temp_avg_c": -62.4,
            "temp_min_c": -96.2,
            "temp_max_c": -14.8,
            "pressure_pa": 745.2,
            "wind_speed_ms": 4.8,
            "wind_direction_deg": 285,
            "dust_optical_depth_tau": 0.42,
            "is_live": False,
            "mode": MODE_OFFLINE,
            "notes": "No network and no cached NASA response — showing model values, not measurements.",
        }

    def get_mars_rover_photos(self, rover: str = "perseverance", sol: int = 1000) -> Dict[str, Any]:
        """
        Rover surface photos. NOTE: api.nasa.gov lists the Mars Rover Photos API as archived,
        so expect this to fall back. Fallback order: live -> cached metadata on disk ->
        reference list (image URLs need internet; the UI shows a 'cached image unavailable' card).
        """
        cache_key = f"rover_{rover}_{sol}"
        url = f"https://api.nasa.gov/mars-photos/api/v1/rovers/{rover}/photos?sol={sol}&api_key={self.api_key}"
        try:
            data = self._fetch_json(url)
            photos = data.get("photos", [])
            if photos:
                result = {
                    "source": f"api.nasa.gov / NASA {rover.title()} Rover",
                    "rover": rover,
                    "sol": sol,
                    "count": min(6, len(photos)),
                    "photos": [
                        {"id": p["id"], "img_src": p["img_src"], "camera": p["camera"]["full_name"], "earth_date": p["earth_date"]}
                        for p in photos[:6]
                    ],
                }
                self._save_disk(cache_key, result)
                return {**result, "mode": MODE_LIVE}
        except Exception:
            pass

        if cache_key in self.disk:
            entry = self.disk[cache_key]
            return {**entry["data"], "mode": MODE_CACHED, "fetched_at": entry["fetched_at"]}

        return {
            "source": "Reference list — NASA/JPL Photojournal (images load only with internet)",
            "rover": rover,
            "sol": sol,
            "mode": MODE_OFFLINE,
            "count": 4,
            "photos": [
                {"id": 101, "img_src": "https://mars.nasa.gov/system/resources/detail_files/26075_PIA24836-web.jpg",
                 "camera": "Mastcam-Z (Jezero Delta Front)", "earth_date": "PIA24836"},
                {"id": 102, "img_src": "https://mars.nasa.gov/system/resources/detail_files/25296_PIA24177-web.jpg",
                 "camera": "SuperCam Remote Micro-Imager", "earth_date": "PIA24177"},
                {"id": 103, "img_src": "https://mars.nasa.gov/system/resources/detail_files/25983_PIA24832-web.jpg",
                 "camera": "Hazcam (Landing Zone)", "earth_date": "PIA24832"},
                {"id": 104, "img_src": "https://mars.nasa.gov/system/resources/detail_files/22228_PIA22949_Sol2077_Mastcam-web.jpg",
                 "camera": "Curiosity Mastcam (Vera Rubin Ridge)", "earth_date": "PIA22949"},
            ],
        }

    # ==========================================
    # 2. DATA.NASA.GOV OPEN DATA SETS
    # ==========================================
    def get_nasa_open_datasets(self) -> List[Dict[str, Any]]:
        """
        Curated registry of official data.nasa.gov datasets and PDS archives
        powering ASTREON's site intelligence models.
        """
        return [
            {
                "id": "NASA-DATA-01",
                "title": "MRO SHARAD Radar Subsurface Ground-Ice Records",
                "portal": "data.nasa.gov / Planetary Data System Geosciences",
                "identifier": "urn:nasa:pds:mro_sharad",
                "description": "Shallow Radar (SHARAD) dielectric properties and 20 MHz radar sounding tracks identifying pure subsurface water ice sheets across Arcadia and Utopia Planitia.",
                "url": "https://data.nasa.gov/",
                "usage_in_astreon": "Provides dielectric permittivity (ε' ~ 3.15) and depth-to-ice estimates for scientific water scoring."
            },
            {
                "id": "NASA-DATA-02",
                "title": "Mars Global Surveyor MOLA Topography and Slope Model",
                "portal": "data.nasa.gov / PDS Planetary Geosciences",
                "identifier": "MGS-M-MOLA-5-MEGDR-L3-V1.0",
                "description": "Mars Orbiter Laser Altimeter precision topographic elevation, regional slope angles, and surface roughness datasets.",
                "url": "https://data.nasa.gov/",
                "usage_in_astreon": "Evaluates Entry, Descent, and Landing (EDL) safety margins, atmospheric braking columns, and slope hazards."
            },
            {
                "id": "NASA-DATA-03",
                "title": "2001 Mars Odyssey Gamma Ray Spectrometer (GRS) HEND WEH Map",
                "portal": "data.nasa.gov / PDS Cartography and Imaging Node",
                "identifier": "ODY-M-GRS-5-DHS-MAPS-V1.0",
                "description": "Global distribution of epithermal and thermal neutrons quantifying Water-Equivalent Hydrogen (WEH wt%) in the top 1 meter of Martian regolith.",
                "url": "https://data.nasa.gov/",
                "usage_in_astreon": "Validates shallow soil water content independent of radar sounding."
            },
            {
                "id": "NASA-DATA-04",
                "title": "MRO CRISM Spectral Mineral Hydration Index Catalog",
                "portal": "data.nasa.gov / PDS Geosciences Node",
                "identifier": "MRO-M-CRISM-3-RDR-TARGETED-V1.0",
                "description": "Hyperspectral visible and near-infrared reflectance data detecting 1.4 µm, 1.9 µm, and 2.2-2.5 µm absorption bands for phyllosilicates and polyhydrated sulfates.",
                "url": "https://data.nasa.gov/",
                "usage_in_astreon": "Identifies bound mineral hydration at candidate sites like Jezero and Mawrth Vallis."
            },
            {
                "id": "NASA-DATA-05",
                "title": "NASA Mars Exploration Program Human Landing Site Study (HLS-ARC)",
                "portal": "data.nasa.gov / Human Exploration and Operations Mission Directorate",
                "identifier": "NASA-TM-2016-219277",
                "description": "Special Publication on First Landing Site/Exploration Zone Workshop for Human Missions to the Surface of Mars.",
                "url": "https://data.nasa.gov/",
                "usage_in_astreon": "Directly guides the selection and boundary coordinates of ASTREON candidate settlement zones."
            }
        ]

    # ==========================================
    # 3. CODE.NASA.GOV OPEN SOURCE SOFTWARE
    # ==========================================
    def get_nasa_code_catalog(self) -> List[Dict[str, Any]]:
        """
        Catalog of open-source NASA software systems from code.nasa.gov
        whose algorithms and standards are incorporated into ASTREON.
        """
        return [
            {
                "name": "NASA SPICE Toolkit (NAIF)",
                "portal": "code.nasa.gov / JPL",
                "category": "Planetary Ephemeris & Geometry",
                "url": "https://code.nasa.gov/",
                "integration": "Adapted into ASTREON's Solar Engine for exact solar longitude (Ls), sub-solar latitude, and diurnal solar zenith calculations."
            },
            {
                "name": "NASA Ames Mars Global Climate Model (MGCM)",
                "portal": "code.nasa.gov / Ames Research Center",
                "category": "Atmospheric Dynamics & Climatology",
                "url": "https://code.nasa.gov/",
                "integration": "Informs ASTREON's dust optical depth (tau) extinction equations and seasonal pressure variations."
            },
            {
                "name": "Interplanetary Overlay Network (ION) DTN",
                "portal": "code.nasa.gov / JPL",
                "category": "Space Communications & Protocols",
                "url": "https://code.nasa.gov/",
                "integration": "Powers ASTREON's CONNECT Communication Module, modeling store-and-forward Delay/Disruption Tolerant Networking across Mars-Earth orbits."
            },
            {
                "name": "Planetary Spectrum Generator (PSG)",
                "portal": "code.nasa.gov / Goddard Space Flight Center",
                "category": "Radiative Transfer & Spectroscopy",
                "url": "https://code.nasa.gov/",
                "integration": "Used to validate Beer-Lambert direct beam and diffuse sky scattering models under varying dust storm opacities."
            },
            {
                "name": "NASA Core Flight System (cFS)",
                "portal": "code.nasa.gov / GSFC",
                "category": "Avionics & Autonomous Fault Management",
                "url": "https://code.nasa.gov/",
                "integration": "Provides architectural guidelines for ASTREON's life-support contingency alerts and autonomous telemetry triaging."
            }
        ]
