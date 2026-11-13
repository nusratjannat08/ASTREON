# ASTREON Architecture Audit
## Mission-Systems Architect's Review: What's Missing, Weak, or Unrealistic

> [!NOTE]
> This audit evaluates ASTREON as a **Mars emergency-guidance application**—software that astronauts, flight controllers, or mission planners would depend on for life-critical decisions. Every finding is measured against that bar, not against "student project" expectations.

---

## 1. FEATURE GAPS — What's Not Built Yet

### 1.1 No Radiation Hazard Model (Critical Omission)
Radiation is the **#1 crew health threat** on Mars and the app doesn't model it at all.
- **Galactic Cosmic Rays (GCR):** ~0.67 mSv/day on the Martian surface (Curiosity RAD data). Cumulative dose drives mission duration limits.
- **Solar Particle Events (SPEs):** An unshielded crew caught outside during a major SPE can receive a lethal dose in hours.
- **What's needed:** A radiation dose accumulator that ticks daily GCR dose per site (factoring in elevation/atmospheric column, regolith shielding, canyon walls), tracks cumulative crew exposure against NASA's career dose limits, and triggers SPE shelter-in-place alerts.

### 1.2 No Oxygen / CO₂ / Atmospheric ISRU Model
The app tracks oxygen as a static "capacity" number but never models:
- **MOXIE-style atmospheric CO₂ electrolysis** (demonstrated by Perseverance — actual flight data exists).
- **Oxygen generation rate vs. consumption rate** — this is a closed-loop life-support coupling that determines whether the crew can actually breathe long-term.
- **CO₂ scrubbing and cabin atmosphere management** — critical during load-shedding events when ECLSS power drops.

### 1.3 No Medical Emergency Decision Support
For an "emergency guidance app," there is no:
- **Crew health status tracker** (individual astronaut health, injury, illness states).
- **Medical triage beyond food** — decompression, radiation sickness, bone fracture, psychological isolation stress.
- **Evacuation decision logic** — "When do we abort to orbit?" This is the single most important emergency decision on Mars and the app has no opinion on it.

### 1.4 No Thermal Management Model
Mars surface temperatures swing from −95°C to −14°C daily. The app shows `thermal_score` as a static integer but never models:
- **Habitat heating power budget** — this is often the dominant energy consumer at night, not ECLSS.
- **Thermal coupling between power system and habitability** — during a dust storm, solar drops AND heating demand spikes. This compound failure mode is the real crisis, and the app simulates them independently.

### 1.5 No Multi-Sol Simulation / Timeline Projection
The monitor shows a **single sol** diurnal curve. A real emergency tool needs:
- **30-day or 90-day forward projection** — "If this storm persists, when do we hit blackout?"
- **Storm duration modeling** — regional storms last ~days, global PEDEs last ~months. The app treats them as a static τ value but never simulates a storm arriving, worsening, peaking, and clearing.
- **Compound crisis cascading** — a dust storm reduces power, which reduces water extraction, which reduces O₂ production, which triggers crew metabolic stress. None of these chains are connected.

### 1.6 No Water Consumption / Production Budget
The water evidence engine is impressive for **site selection**, but once a site is chosen and occupied, there is no:
- **Daily water balance** (consumption vs. ISRU extraction rate vs. recycling efficiency).
- **Water recycling loop** — NASA's ISS Water Recovery System recycles ~93% of water. This dramatically changes how much raw extraction matters.
- **Contamination / equipment failure scenarios** — "The water recycler just broke. How many days of reserve do we have?"

### 1.7 No EVA Planning or Traverse Safety
No modeling of:
- Surface traversability (how far can a crew member walk/drive from the habitat?)
- Terrain hazard mapping within a chosen zone
- EVA suit consumables (O₂, battery, thermal) and safe return calculations
- Dust storm approach warnings that would abort an EVA in progress

---

## 2. SAFETY & RELIABILITY WEAKNESSES

### 2.1 No Input Validation Boundaries on Life-Critical Calculations
The food rationing engine will happily accept `food_stockpile_kg = 0.001` and `extended_days = 1500` and return a plan with sub-starvation calorie counts without any hard guardrails. A real system needs:
- **Hard floors:** "Below 800 kcal/day for >5 days, the system must refuse to generate a 'plan' and instead show EVACUATION REQUIRED."
- **Sanity checks on inputs:** crew of 200? Duration of 10,000 sols? Negative food? These should be caught and rejected, not computed.

### 2.2 Battery Simulation Starts at 100% Every Time
[`scientific_engine.py` line 348](file:///d:/Study/NASA/New%20App%20ASTREON/scientific_engine.py#L348): `current_battery = battery_capacity_kwh` — the battery always starts full. In reality, if the crew opens the monitor on sol 15 of a dust storm, the battery is already partially depleted. The simulation has no concept of **persistent state** across queries.

### 2.3 Base Capacities Are Static Fiction
Every site has hardcoded `base_capacities` (e.g., `water_l: 25000`, `food_kg: 15000`). These numbers:
- Have no source or derivation method documented.
- Don't deplete over time as the mission runs.
- Don't connect to the food rationing engine (the food crisis module uses its own separate `food_stockpile_kg` input, ignoring the site's `food_kg` capacity entirely).
- Represent a **pre-deployed infrastructure assumption** that is never explained. Where did 25,000 liters of water come from? Pre-supply missions? ISRU ramp-up?

### 2.4 Solar Score Used for Ranking ≠ Solar Model Used for Monitoring
The MCDA ranking uses a static [`solar_baseline_score`](file:///d:/Study/NASA/New%20App%20ASTREON/scientific_engine.py#L602-L613) (a stepped function of latitude). But the monitoring tab uses a full orbital mechanics irradiance model. These two systems should be **the same calculation**. Currently, Elysium can rank #1 on solar with score 95, but the monitor might show it generating less power than Jezero at certain seasons. The ranking and the monitoring disagree.

### 2.5 No Uncertainty / Confidence Intervals
Every score is presented as a crisp single number (e.g., "Water Potential: 83.9%"). Real planetary science data has significant uncertainty:
- SHARAD dielectric measurements have instrument noise.
- GRS WEH values have ±1–2 wt% uncertainty.
- CRISM hydration indices depend on calibration pipelines.

Presenting a single decimal-place score with no error bars gives **false confidence** that could lead to bad site selection decisions.

### 2.6 No Audit Trail or Decision Logging
If a crew uses this app to decide "we'll ration food at 1,600 kcal/day," there is no record of:
- What inputs they entered.
- What the app recommended.
- Whether they accepted or overrode the recommendation.
- Timestamps for accountability.

The reservation system logs site picks, but not the actual emergency decisions that matter.

---

## 3. UX UNDER STRESS — Would This Work in a Crisis?

### 3.1 Information Overload During Emergencies
The app has **7 tabs**, each dense with data, sliders, charts, KPIs, and technical jargon ("Beer-Lambert atmospheric transmission", "Ketogenic Transition"). During a real emergency:
- An astronaut with elevated cortisol, possible hypoglycemia, and communication-delayed ground support needs **one screen** that says: "Here is what to do right now."
- The current design requires navigating between tabs, adjusting sliders, reading multi-paragraph scientific rationales, and interpreting radar charts. This is a **planning tool UI** bolted onto an **emergency guidance** promise.

### 3.2 No Emergency Mode / Red Alert Dashboard
There should be a single unified "EMERGENCY STATUS" view that:
- Aggregates the worst-case finding across power, food, water, O₂, and radiation into one composite survival status.
- Shows a **countdown** (sols remaining on each resource).
- Gives exactly 3–5 ordered directives: "Do THIS. Then THIS. Then THIS."
- Uses enormous text, high-contrast colors, and requires zero slider interaction.

### 3.3 No Offline Resilience for the App Itself
The HTML loads Google Fonts, Chart.js from CDN, and Leaflet from CDN. If the Mars habitat loses internet (which is... always), the app's UI breaks. All external dependencies should be bundled locally.

### 3.4 No Keyboard Navigation or Accessibility
In a pressurized suit with thick gloves, or in low gravity with limited fine motor control:
- Small range sliders are nearly unusable.
- Tiny "btn-micro" buttons (`.btn-micro { font-size: 0.7rem; padding: 3px 8px }`) are impossible to hit.
- No keyboard shortcuts for critical actions.
- No voice command integration concept.

### 3.5 Alert Fatigue Risk
The mitigation directives are long prose paragraphs that all look the same visually. After 3 dust storm warnings, the crew will stop reading them. Needs:
- Severity escalation (yellow → orange → red → flashing) that changes the visual weight of alerts dramatically.
- De-duplication: don't repeat the same directive unchanged across queries.
- Acknowledgment tracking: "Crew acknowledged directive X at Sol 42, 14:30."

---

## 4. SCIENTIFIC & ENGINEERING REALISM GAPS

### 4.1 The "Continuous Monitoring" Is Not Continuous
The monitor only updates when the user moves a slider or clicks. There is no background process tracking time progression across sols. The "Live Tick" button advances 15 minutes every 750ms — that's a UI animation, not a simulation. A real monitoring system would:
- Track the actual current Martian sol and Ls for the selected site.
- Persist state between page loads.
- Log telemetry history to the database (the `telemetry_logs` table exists but is never written to).

### 4.2 Food Rationing Ignores Individual Crew Differences
The BMR calculation uses a single hardcoded height (175 cm), age (38), and sex (male):
```python
bmr = 10 * crew_avg_weight_kg + 6.25 * 175 - 5 * 38 + 5  # ~ 1680 kcal
```
Real crews are mixed-gender, different ages and body masses. A 55 kg female astronaut and a 95 kg male astronaut have radically different metabolic needs. The rationing plan should accept individual crew profiles.

### 4.3 Greenhouse Yield Is Constant
`greenhouse_daily_yield_kg` is treated as a fixed number, but greenhouse output depends on:
- Available power for grow lights (which drops during dust storms).
- Water availability for hydroponics.
- Crew time available for maintenance.
This should be coupled to the power and water models.

### 4.4 Mars-Earth Distance Calculation Is Approximate
[`app.py` line 410](file:///d:/Study/NASA/New%20App%20ASTREON/app.py#L410): `dist_au = max(0.4, min(2.5, abs(r_mars - 1.0) + 0.3))` — this approximates Mars-Earth distance as `|Mars heliocentric radius - 1 AU| + 0.3`. The actual distance depends on the relative orbital phases (synodic period), not just Mars' radial distance. The error can be >1 AU during quadrature.

### 4.5 Landing Safety Scores Are Unverifiable
`landing_safety: 96` for Elysium. Where does 96 come from? There's no formula, no reference to MOLA roughness data resolution, no EDL simulation. These are author-assigned integers with scientific-sounding prose attached. The water evidence model at least has a derivable formula; the landing/terrain/thermal/comm scores do not.

---

## 5. WHAT WOULD MAKE THIS UNIQUE & COMPETITION-WINNING

### 5.1 Integrated Crisis Cascade Simulator
**No competing Mars settlement tool connects power → water → oxygen → food → crew health into one chain.** Build a single "What If" engine:
> "Dust storm hits at τ=3.0 on Sol 15. Solar drops 70%. Water ISRU stops. O₂ buffer depletes in 8 sols. Food rationing kicks in at Day 3. Show me the entire cascade on one timeline."

This is what would make ASTREON genuinely novel.

### 5.2 Scenario Comparison Mode
Let planners run **two or three sites side-by-side** under the same crisis scenario. "Show me Arcadia vs. Jezero vs. Elysium during a 60-day global dust storm." A split-screen comparison with synchronized timeline scrubbing would be immediately compelling.

### 5.3 Mission Phase Awareness
Mars missions have distinct phases: **Transit → EDL → Surface Operations → Ascent Prep → Earth Return**. The app treats everything as "surface operations." Adding phase-aware logic (e.g., "you're in ascent prep phase, food rationing rules change because you need carb-loading for high-G") would show systems-engineering thinking.

### 5.4 Export a Survival Checklist PDF
The "Print Directive" button does `window.print()`. Instead, generate a structured **Mars Emergency Operations Checklist** as a proper formatted PDF with:
- Situation summary
- Decision matrix
- Ordered action items
- Crew signatures/acknowledgment lines
- Timestamp and mission ID

This is a tangible artifact that mission planners would actually use.

### 5.5 Decision Justification Engine
When the app recommends a site or a rationing level, it should explain **why** in a structured argument, not just show numbers:
> "Arcadia is ranked #1 because: (1) It has the lowest water extraction energy among ice-bearing sites (0.19 kWh/kg), which matters most in your scenario because you weighted water at 28%. (2) Its landing slope of 1.2° is well within the 5° safety threshold. (3) However, its winter solar reliability at 39°N is a known weakness — switching to the Monitor tab at Ls=270° will show the seasonal low point."

This kind of transparent reasoning is what separates a dashboard from a decision-support system.

---

## Summary Priority Matrix

| Priority | Finding | Impact |
|:---|:---|:---|
| 🔴 Critical | No radiation model | Crew health unaddressed |
| 🔴 Critical | No O₂/atmosphere ISRU model | Life support incomplete |
| 🔴 Critical | No compound crisis cascading | Emergencies happen together, not in tabs |
| 🔴 Critical | CDN dependencies break offline | App unusable on Mars |
| 🟠 High | No emergency dashboard mode | Unusable under actual stress |
| 🟠 High | Static base capacities, no depletion | Fake mission progression |
| 🟠 High | Solar ranking ≠ solar monitor model | Internal self-contradiction |
| 🟠 High | No input validation on life-critical calcs | Dangerous garbage-in / garbage-out |
| 🟠 High | No uncertainty/confidence intervals | False precision on decisions |
| 🟡 Medium | Food BMR ignores crew diversity | Medically unrealistic |
| 🟡 Medium | No multi-sol forward projection | Can't answer "what happens next week?" |
| 🟡 Medium | No decision audit trail | No accountability |
| 🟡 Medium | No water consumption/production loop | Post-landing resource blind spot |
| 🟡 Medium | Battery always starts at 100% | Stateless simulation |
| 🟢 Nice-to-have | Scenario comparison mode | Competition differentiator |
| 🟢 Nice-to-have | Crisis cascade simulator | Unique selling point |
| 🟢 Nice-to-have | PDF survival checklist export | Professional deliverable |
| 🟢 Nice-to-have | Mission phase awareness | Systems-engineering depth |
