# ASTREON v2.3 — restructure (13 Nov 2026)

## 3-minute judge demo
1. **Choose a Base → Site Ranking.** Gale Crater ranks #1. The water-rich northern ice sites (Arcadia, Utopia, Deuteronilus) rank lower because they *fail a dust-season storm test*: their score now includes a simulated storm, not a typed-in number.
2. **Crisis Mode.** Switch the base to *Arcadia*, threat *Regional dust storm*. ASTREON answers in under a second, offline: **16 sols to crew loss, CRITICAL**, the limiting factor (habitat freezes after blackout), the procedures ranked by how many sols each buys (re-simulated), every evacuation destination with distance, transit time and verdict, and the Earth link (11 min one way; next conjunction blackout date).
3. Change *Evacuation vehicle* to *Long-range convoy (45 sols)* → the top action becomes **"Evacuate to Elysium Spaceport"**.
4. **🏠 Habitat → Fission power 10 kW → Apply everywhere.** Arcadia becomes STABLE and jumps to #1 in the ranking: the power architecture decides which site is best.
5. **Stress Test** shows the full sol-by-sol cascade behind those numbers.

## What changed
### One shared habitat (🏠 button in the top bar)
Crew, PV area, battery, fission power, food, water, O₂, recycling, horizon, season, rover speed/endurance. Ranking, Solar & Power, Food, Compound Cascade and Crisis Mode all read it, so the screens can no longer contradict each other. Saved in the browser; "Reset defaults" restores the built-in values.

### Navigation: 8 tabs → 4 stages
| Stage | Sub-views |
|---|---|
| 01 Choose a Base | Site Ranking · Mars Map · Water Evidence |
| 02 Stress Test | Compound Cascade · Solar & Power (one sol) · Food Rationing |
| 03 Crisis Mode (new) | Crisis Assessment |
| 04 Data & Earth Link | Earth Link (DTN) · NASA Data Sources |

The bar sticks to the top of the screen. Scrolling down shrinks it to one slim row (stages, sub-views, runway and Earth-delay pills); scrolling up restores full size. Page space is reserved, so the content never jumps. On phones the compact row shows the four stages.

### Engine
- **Season/storm confound fixed.** "No storm" used to run at Ls 180 and storm runs at Ls 240, so northern winter was blamed on dust. The season is now an explicit habitat input.
- **Shared load model.** The single-sol solar view and the cascade use the same array, battery, tilt and demand model; they now agree.
- **Array tilt bug fixed.** Southern sites used to get a winter tilt bonus in *northern* winter.
- **Solar score computed** from the irradiance model (40% annual mean + 60% worst season vs. the equator), replacing hand-entered values.
- **New criterion: Dust-storm resilience**, a regional storm run through the coupled cascade with the shared habitat.
- **Removed the invented "resource coverage"** term (35% of the old score, 100% for every site at default settings).
- **Countermeasure impacts are re-simulated**, replacing hardcoded text such as "+28 sols".
- **Relocation advisor:** great-circle distance on Mars, rover transit time vs. endurance, storm footprint (regional ≤1,500 km; global = everywhere), and the destination tested for a full horizon after arrival.
- **Comms outlook:** current light time plus the next solar-conjunction blackout (start and length) from JPL orbital elements.
- **Crisis assessment:** status level, survival runway, up to 5 ordered actions (relocate / procedures / escalate / comms / radiation shelter).

### Removed from the UI
Settlement registry ("Authorize settlement"), "Live tick" button, filler "PLANET" pill. The backend endpoints remain if you want them back.

### Assumptions stated in the UI (be ready to defend them)
- Each evacuation destination hosts a pre-positioned outpost with the same habitat config.
- Regional storm footprint radius 1,500 km.
- Landing, terrain, thermal and comms scores are still assigned in `data/candidate_sites.json` (labelled as such).
