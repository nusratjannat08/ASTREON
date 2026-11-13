# ASTREON — Mission Match Mars
### NASA Space Apps Challenge 2026

> **Advanced Planetary Decision Support & Mission Site Intelligence Platform for Human Settlement Selection, Solar/Environmental Risk Telemetry, and Life-Support Contingency Management.**

ASTREON (Mission Match Mars) is an application-based software designed to evaluate, rank, and continuously monitor candidate human settlement locations across Mars. Moving beyond static estimates, ASTREON integrates scientific data and physical models from NASA's primary data portals:
- **NASA Open Data:** [https://data.nasa.gov/](https://data.nasa.gov/)
- **NASA Open Source Code:** [https://code.nasa.gov/](https://code.nasa.gov/)
- **NASA APIs:** [https://api.nasa.gov/](https://api.nasa.gov/)

---

## 🧭 System Organization (v2.3)

1. **Choose a Base**: Rank 8 candidate sites using empirical water evidence, physical solar irradiance, and simulated dust-storm resilience. Interactive 2D Mars MOLA map with 30° graticule.
2. **Stress Test**: Sol-by-sol compound cascade (power → water → O₂ → food → crew), diurnal single-sol solar view, dynamic caloric triaging, and weight-loss forecasting.
3. **Crisis Mode**: Autonomous offline survival runway calculation, prioritized emergency procedures ranked by sols gained, evacuation routing with great-circle transit times, and Earth-link outlook.
4. **Data & Earth Link**: Real-time Earth–Mars light-time calculation, orbital conjunction forecasts via JPL Keplerian elements, and NASA telemetry client with LIVE, CACHED, and OFFLINE modes.

All modules share a unified **Habitat Configuration Engine** (accessible via the 🏠 button), guaranteeing synchronized parameters across all simulation models.

---

## 🛰️ NASA Data & Open Source Resources Used

In strict accordance with the **NASA Space Apps Challenge 2026 Guidelines**, ASTREON is built entirely on open NASA data archives, mission instruments, and open-source models:

| NASA Mission / Portal | Instrument / Dataset | Application in ASTREON |
|---|---|---|
| **Mars Reconnaissance Orbiter (MRO)** | **SHARAD (Shallow Radar)** | Dielectric permittivity ($\varepsilon' \approx 3.15$) to detect pure subsurface glacial ice sheets (40–100 m thick) beneath regolith in Arcadia and Utopia Planitia. |
| **2001 Mars Odyssey** | **GRS / HEND (Gamma & Neutron Spectrometer)** | Epithermal neutron suppression mapping to quantify Water-Equivalent Hydrogen (WEH wt%) in the top 1 meter of Martian soil. |
| **Mars Reconnaissance Orbiter (MRO)** | **CRISM (Hyperspectral Spectrometer)** | $1.4\ \mu\text{m}$, $1.9\ \mu\text{m}$, and $2.2\text{--}2.5\ \mu\text{m}$ absorption bands for phyllosilicates (smectite clays) and polyhydrated sulfates at Jezero, Mawrth Vallis, and Gale. |
| **Mars Global Surveyor (MGS)** | **MOLA (Laser Altimeter)** | Topographic elevation and slope basemap (`MarsTopo719` spherical-harmonic model) rendered to a 2048x1024 equirectangular shaded-relief HUD map. |
| **InSight Lander** | **api.nasa.gov (Mars Weather / REMS)** | Archival atmospheric pressure, air temperature, and wind speed telemetry for Elysium Planitia. |
| **Curiosity Rover (MSL)** | **RAD (Radiation Assessment Detector)** | Elevation-adjusted Galactic Cosmic Ray (GCR) surface dosage ($\sim 0.67\ \text{mSv/sol}$ datum baseline) and Solar Particle Event (SPE) shelter protocols. |
| **NASA JPL / SPICE** | **Keplerian Orbital Elements** | Real-time computation of Earth–Mars distance, light-time communications latency (3–22 min one-way), and solar conjunction blackout dates. |
| **NASA Ames** | **Mars Global Climate Model (MGCM)** | Optical depth ($\tau$) atmospheric dust extinction models and diurnal solar irradiance via the Beer-Lambert extinction law. |

---

## 🚀 Key Modules & Capabilities

### 1. Multi-Sensor Evidence-Based Water Potential Engine
*Replaces arbitrary manual scores with empirical planetary science.*
- **MRO SHARAD Shallow Radar:** Dielectric permittivity ($\varepsilon' \approx 3.15$) detecting pure subsurface glacial ice sheets in **Arcadia Planitia** and **Utopia Planitia**.
- **2001 Mars Odyssey GRS / HEND:** Epithermal neutron suppression quantifying Water-Equivalent Hydrogen (WEH wt%).
- **MRO CRISM Hyperspectral Mineralogy:** Diagnostic absorption bands for bound phyllosilicates (smectite clays) and polyhydrated sulfates (gypsum, epsomite).
- **Extraction Feasibility & Energy Footprint:** Computes specific extraction energy in $\text{kWh/kg H}_2\text{O}$ ($0.18\text{--}0.22\ \text{kWh/kg}$ for Rodriguez sublimation wells vs. $>0.7\ \text{kWh/kg}$ for high-temperature clay thermal desorption).

### 2. Continuous Solar Energy & Environmental Risk Monitor
*Monitors the selected settlement zone in real time across the Martian sol and year.*
- **Diurnal Solar Irradiance Model:** Accounts for solar zenith angle, sub-solar latitude, and atmospheric extinction via the Beer-Lambert law:
  $$I_{\text{dir}} = S_{\text{TOA}}(L_s) \cdot \cos(\theta_z) \cdot \exp(-\tau \cdot m)$$
  plus diffuse forward-scattered skylight flux.
- **Seasonal Variations Across Mars Year ($L_s = 0^\circ \text{ to } 360^\circ$):** Models solar flux fluctuations caused by Mars' orbital eccentricity ($e = 0.0934$, heliocentric distance $1.381\text{ AU}$ at perihelion to $1.666\text{ AU}$ at aphelion).
- **Atmospheric Dust Storm Scenarios:**
  - *Nominal Clear Sky* ($\tau = 0.4$)
  - *Regional Dust Storm* ($\tau = 1.6$)
  - *Planet-Encircling Dust Event (PEDE)* ($\tau = 4.5$)
  - *Winter Polar Twilight & Dust Haze* ($\tau = 1.1$)
- **Energy Reliability & Battery Simulation:** Simulates habitat power balance, PV array production, and lithium-ion battery buffer.

### 3. Life Support Crisis & Dynamic Food Rationing Engine
*Handles food reserve drops and mission duration extensions.*
- **Metabolic Baseline & Caloric Triaging:**
  - *Nominal Operational Baseline:* $\sim 2,800\ \text{kcal/person/sol}$
  - *Mild Conservation:* $2,000\text{--}2,500\ \text{kcal/sol}$
  - *Moderate Rationing:* $1,550\text{--}2,000\ \text{kcal/sol}$ (EVAs suspended)
  - *Critical Survival Floor:* $1,200\text{--}1,550\ \text{kcal/sol}$ (near-basal metabolic rate)
  - *Starvation Hazard:* $<1,200\ \text{kcal/sol}$ (emergency abort/airdrop required)
- **Physiological Projections:** Forecasts total body mass loss ($\text{kg}$ and $\%$ of body weight) based on accumulated caloric deficits.
- **Bioregenerative Offsets:** Incorporates fresh yields from habitat greenhouses (microgreens, chlorella algae).

### 4. The Domino Engine — Dynamic Compound Crisis Cascader
*Models closed-loop subsystem coupling across 30 to 180 Martian sols:*
$$\text{Global Dust Storm } (\tau \ge 4.5) \implies \text{Solar Deficit} \implies \text{Battery Depletion} \implies \text{ISRU/MOXIE Shedding} \implies \text{O}_2\text{/Water Loss} \implies \text{Metabolic Starvation}$$
- **4-Tier Automated Load Shedding (FDIR):**
  - *Tier 0 (Nominal):* Full life support, thermal heating, MOXIE O₂ electrolysis, water extraction well, and greenhouse grow lights.
  - *Tier 1 (Battery SoC < 40%):* Greenhouse LED arrays isolated to save $56\ \text{kWh/sol}$.
  - *Tier 2 (Battery SoC < 25%):* Subsurface water well pumps offline; settlement shifts to closed-loop recycled water reserves.
  - *Tier 3 (Battery SoC < 12%):* MOXIE oxygen generation shut down; crew taps high-pressure accumulator buffer.
  - *Tier 4 (Battery 0% Blackout):* Habitat thermal setback to $10^\circ\text{C}$ survival chill; non-essential electronics cold-isolated.
- **Curiosity RAD Radiation Accumulation & SPE Shelter Protocol:** Elevation-adjusted GCR dose calculation plus Solar Particle Event (SPE) proton flare protection.
- **Actionable Countermeasure Testing:** Evaluates tactical trade-offs (10 kW Kilopower auxiliary nuclear generator, electrostatic dust-wipers, regolith storm shelter, auto-adaptive rationing).

### 5. 100% Offline Capability
- Bundled Chart.js, Leaflet.js, typography (Inter, JetBrains Mono, Orbitron), and MOLA basemap.
- The platform operates reliably in air-gapped environments or during interplanetary communication blackouts.

---

## 🛠️ Installation & Running the Application

### Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Modern web browser (Chrome, Edge, Firefox, Safari)

### Option A: One-Click Startup (Windows)
Double-click:
```bat
run_astreon.bat
```
This automatically launches the local server and opens the application in your default browser.

### Option B: Terminal Command (Cross-Platform)
1. **Clone the repository:**
   ```bash
   git clone https://github.com/nusratjannat08/ASTREON.git
   cd ASTREON
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Launch the platform:**
   ```bash
   python run.py
   ```
4. **Access the Mission Control Dashboard:**
   ```
   http://127.0.0.1:5000
   ```

---

## 📁 Project Architecture

```
ASTREON/
├── app.py                     # Flask server with REST API routes & SQLite persistence
├── scientific_engine.py       # Core physics: Water potential, Solar/Dust/Power, Domino cascade
├── nasa_client.py             # Client for api.nasa.gov, data.nasa.gov & code.nasa.gov
├── run.py                     # Application runner with automated browser launch
├── run_astreon.bat            # Windows 1-click batch launcher
├── requirements.txt           # Python dependencies (Flask>=3.0.0)
├── LICENSE                    # MIT Open Source License
├── .gitignore                 # Standard Python & OS ignore rules
├── data/
│   └── candidate_sites.json   # 8 Candidate settlement sites with deep planetary telemetry
├── templates/
│   └── index.html             # Mission Control dashboard UI
├── static/
│   ├── css/
│   │   └── style.css          # Aerospace dark HUD theme styling
│   ├── js/
│   │   ├── app.js             # Interactive controller, Chart.js graphs, Leaflet Mars map
│   │   └── crisis.js          # Offline crisis mode controller & survival runway
│   ├── img/
│   │   └── mars_mola_2k.jpg   # Bundled MGS MOLA 2k shaded relief basemap
│   └── vendor/
│       ├── chart.min.js       # Offline Chart.js library
│       ├── leaflet.js         # Offline Leaflet map library
│       └── fonts/             # Bundled typography (Orbitron, Inter, JetBrains Mono)
└── tools/
    └── render_mola.py         # MOLA spherical-harmonic basemap generator (Wieczorek model)
```

---

## 🛰️ Evaluated Candidate Settlement Zones

1. **Arcadia Settlement Zone (Arcadia Planitia):** Massive pure subsurface ice sheet (SHARAD $\varepsilon' = 3.15$, $94\%$ purity), ultra-flat terrain ($1.2^\circ$ slope), $-3.8\ \text{km}$ elevation.
2. **Utopia Deep Ice Oasis (Utopia Planitia):** Ice volume $>14,300\ \text{km}^3$, GRS WEH $9.2\ \text{wt}\%$, deep $-4.2\ \text{km}$ elevation for aerodynamic landing deceleration.
3. **Jezero Delta Research Station (Nili Planum):** Smectite clays and carbonates (CRISM index $0.88$), Perseverance rover exploration context, equatorial solar stability.
4. **Elysium Spaceport & Logistics Hub (Elysium Planitia):** InSight lander site, highest landing safety rating ($>95\%$), basaltic plains, prime spaceport location.
5. **Melas Chasma Canyon Biosphere (Valles Marineris):** Deep canyon floor ($-5.2\ \text{km}$ elevation, high atmospheric pressure $\sim 1.1\ \text{kPa}$), natural cosmic ray shielding.
6. **Mawrth Vallis Ancient Clay Outpost:** Hundreds of square kilometers of thick phyllosilicate clay sequences for water and ceramic construction.
7. **Deuteronilus Glacial Colony (Deuteronilus Mensae):** Lobate Debris Aprons (LDAs) containing debris-covered alpine glaciers with $>85\%$ ice purity.
8. **Gale Crater Science Base (Aeolis Mons / Mount Sharp):** Curiosity rover site, $-4.5\ \text{km}$ elevation, layered sulfate salts, equatorial solar reliability.

---

## ⚖️ License & Open Source

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details. Built for the **NASA Space Apps Challenge 2026**.
