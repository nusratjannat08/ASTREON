/**
 * ASTREON v2.3 — shared habitat configuration + Crisis Mode.
 * Everything here runs against the local Flask server: no Earth link required.
 */

// ==========================================
// SHARED HABITAT CONFIGURATION
// ==========================================
const HABITAT_FIELDS = [
    { key: "crew", label: "Crew size", unit: "people", step: 1, min: 1, max: 24 },
    { key: "pv_area_m2", label: "Solar array area", unit: "m²", step: 10, min: 20, max: 5000 },
    { key: "battery_kwh", label: "Battery storage", unit: "kWh", step: 10, min: 20, max: 5000 },
    { key: "nuclear_kw", label: "Fission power (0 = none)", unit: "kW", step: 1, min: 0, max: 100 },
    { key: "food_kg", label: "Stored food", unit: "kg", step: 10, min: 0, max: 50000 },
    { key: "water_l", label: "Stored water", unit: "L", step: 50, min: 0, max: 100000 },
    { key: "o2_kg", label: "O₂ reserve", unit: "kg", step: 5, min: 0, max: 10000 },
    { key: "water_recycling_eff", label: "Water recycling efficiency", unit: "0–0.99", step: 0.01, min: 0, max: 0.99 },
    { key: "greenhouse", label: "Greenhouse installed", type: "bool" },
    { key: "mission_sols", label: "Simulation horizon", unit: "sols", step: 5, min: 10, max: 180 },
    { key: "start_ls", label: "Season at sol 1 (Ls)", unit: "° (180–330 = dust season)", step: 5, min: 0, max: 360 },
    { key: "rover_km_per_sol", label: "Rover traverse speed", unit: "km/sol", step: 5, min: 5, max: 500 },
    { key: "rover_endurance_sols", label: "Rover life-support endurance", unit: "sols", step: 1, min: 1, max: 120 },
];
const HABITAT_STORE_KEY = "astreon.habitat.v1";
let HABITAT_DEFAULTS = null;

function storeGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function storeSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } }

async function loadHabitat() {
    try {
        HABITAT_DEFAULTS = await (await fetch("/api/habitat/defaults")).json();
    } catch (e) {
        HABITAT_DEFAULTS = { crew: 6, pv_area_m2: 450, battery_kwh: 300, nuclear_kw: 0, food_kg: 800, water_l: 3500,
            o2_kg: 150, water_recycling_eff: 0.9, greenhouse: true, mission_sols: 60, start_ls: 240,
            rover_km_per_sol: 80, rover_endurance_sols: 21 };
    }
    let saved = null;
    try { saved = JSON.parse(storeGet(HABITAT_STORE_KEY) || "null"); } catch (e) { saved = null; }
    state.habitat = { ...HABITAT_DEFAULTS, ...(saved || {}) };
    applyHabitatToInputs();
    renderHabitatSummary();
}

function renderHabitatSummary() {
    const h = state.habitat;
    const el = document.getElementById("habitatSummary");
    if (el && h) el.textContent = `${h.crew} crew · ${h.pv_area_m2} m² PV · ${h.battery_kwh} kWh${h.nuclear_kw > 0 ? ` · ${h.nuclear_kw} kW fission` : ""}`;
}

// Push the shared values into the per-screen inputs so every screen starts from the same base.
function applyHabitatToInputs() {
    const h = state.habitat;
    const set = (id, v) => { const el = document.getElementById(id); if (el && v !== undefined) el.value = v; };
    set("inputCrew", h.crew);
    set("inputDays", h.mission_sols);
    set("foodCrew", h.crew);
    set("foodRemainingKg", h.food_kg);
    set("cascadeCrewInput", h.crew);
    set("cascadeTimelineInput", h.mission_sols);
    set("cascadeBatteryInput", h.battery_kwh);
    set("cascadeFoodInput", h.food_kg);
    set("monitorLsSlider", h.start_ls);
    const gh = document.getElementById("toggleGreenhouse");
    if (gh) gh.checked = !!h.greenhouse;
    if (typeof state.monitor === "object") state.monitor.lsDeg = Number(h.start_ls);
    const lsDisp = document.getElementById("monitorLsDisplay");
    if (lsDisp) lsDisp.textContent = `${h.start_ls}°`;
    const top = document.getElementById("topSeasonLs");
    if (top) top.textContent = `Ls ${h.start_ls}°`;
}

function openHabitatModal() {
    const form = document.getElementById("habitatForm");
    const h = state.habitat;
    form.innerHTML = HABITAT_FIELDS.map(f => f.type === "bool"
        ? `<label class="toggle-card"><input id="hab_${f.key}" type="checkbox" ${h[f.key] ? "checked" : ""}>
             <div class="toggle-text"><span class="toggle-title">${f.label}</span></div></label>`
        : `<div class="input-block"><label for="hab_${f.key}">${f.label}</label>
             <input id="hab_${f.key}" type="number" step="${f.step}" min="${f.min}" max="${f.max}" value="${h[f.key]}">
             <span class="input-hint">${f.unit}</span></div>`).join("");
    document.getElementById("habitatModal").classList.remove("hidden");
}

function closeHabitatModal() { document.getElementById("habitatModal").classList.add("hidden"); }

function readHabitatForm() {
    const out = {};
    HABITAT_FIELDS.forEach(f => {
        const el = document.getElementById(`hab_${f.key}`);
        if (!el) return;
        if (f.type === "bool") out[f.key] = el.checked;
        else {
            const v = Number(el.value);
            out[f.key] = Number.isFinite(v) ? Math.min(f.max, Math.max(f.min, v)) : HABITAT_DEFAULTS[f.key];
        }
    });
    return out;
}

async function saveHabitat() {
    state.habitat = { ...state.habitat, ...readHabitatForm() };
    storeSet(HABITAT_STORE_KEY, JSON.stringify(state.habitat));
    closeHabitatModal();
    await refreshAllForHabitat();
}

async function resetHabitat() {
    state.habitat = { ...HABITAT_DEFAULTS };
    storeSet(HABITAT_STORE_KEY, JSON.stringify(state.habitat));
    closeHabitatModal();
    await refreshAllForHabitat();
}

async function refreshAllForHabitat() {
    applyHabitatToInputs();
    renderHabitatSummary();
    await runMissionAnalysis();
    loadMonitorTelemetry();
    runFoodRationingCalculation();
    runCascadeSimulation();
    runCrisisAssessment();
}

// ==========================================
// CRISIS MODE
// ==========================================
const BOTTLENECK_TEXT = {
    "HABITAT_COLD_SOAK": "Habitat freezes after a multi-sol power blackout",
    "OXYGEN_EXHAUSTION": "Oxygen reserve runs out after MOXIE is shed",
    "WATER_EXHAUSTION": "Water reserve runs out after the ice well is shed",
    "STARVATION_CACHEXIA": "Food runs out / dangerous body-mass loss",
};
const VERDICT_CLASS = { "RELOCATE": "v-go", "SAFE ALTERNATIVE": "v-ok", "BETTER, NOT SAFE": "v-warn", "WORSE": "v-bad", "OUT OF RANGE": "v-off" };
let crisisRunToken = 0;

function initCrisisSiteSelector() {
    const sel = document.getElementById("crisisSite");
    if (!sel || !state.allSites.length) return;
    const current = (sel.dataset.userPicked === "1" && sel.value) || (state.selectedSite && state.selectedSite.id) || sel.value;
    sel.innerHTML = state.allSites.map(s => `<option value="${s.id}">${s.name}</option>`).join("");
    if (current) sel.value = current;
}

function onCrisisViewShown() {
    const sel = document.getElementById("crisisSite");
    if (sel && state.selectedSite && sel.dataset.userPicked !== "1") {
        if (sel.value !== state.selectedSite.id) { sel.value = state.selectedSite.id; runCrisisAssessment(); }
    }
}

async function runCrisisAssessment() {
    const sel = document.getElementById("crisisSite");
    if (!sel || !state.habitat) return;
    if (!sel.options.length) initCrisisSiteSelector();
    const token = ++crisisRunToken;
    const transport = document.getElementById("crisisTransport")?.value || "habitat";
    const habitat = { ...state.habitat };
    if (transport !== "habitat") habitat.rover_endurance_sols = Number(transport);

    const payload = {
        site_id: sel.value,
        storm_scenario: document.getElementById("crisisScenario").value,
        storm_start_sol: Number(document.getElementById("crisisStart").value) || 5,
        storm_duration_sols: Number(document.getElementById("crisisDuration").value) || 35,
        habitat,
    };
    try {
        const res = await fetch("/api/crisis/assess", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (token !== crisisRunToken) return; // a newer request superseded this one
        if (!res.ok) throw new Error(data.error || "assessment failed");
        renderCrisis(data);
    } catch (err) {
        document.getElementById("crisisActions").innerHTML = `<li class="crisis-action kind-ESCALATE"><div class="ca-title">Assessment failed</div><div class="ca-detail">${err.message}</div></li>`;
    }
}

function renderCrisis(d) {
    const b = d.baseline;
    const T = b.timeline;
    const levelClass = { STABLE: "level-stable", "AT RISK": "level-risk", CRITICAL: "level-critical" }[d.level] || "level-unknown";
    const hero = document.getElementById("crisisHero");
    hero.className = `crisis-hero ${levelClass}`;
    const setT = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };

    setT("crisisSiteName", `${d.site.name} · ${d.scenario}`);
    setT("crisisRunway", b.survives ? `${T}+` : b.runway_sols);
    setT("crisisRunwayOf", b.survives ? `sols — outlasts the ${T}-sol horizon` : `of ${T} sols until crew loss`);
    setT("crisisLevel", d.level);
    setT("crisisLimiting", b.survives
        ? (b.blackout_sols > 0 ? `Survives, but with ${b.blackout_sols} sols of power blackout and a ${b.min_soc}% battery floor.`
                               : `Survives. Battery never drops below ${b.min_soc}%.`)
        : `Limiting factor: ${BOTTLENECK_TEXT[b.bottleneck] || b.bottleneck}.`);
    const wp = d.with_all_procedures;
    setT("crisisBest", b.survives ? "" : (wp.survives
        ? `With all in-habitat procedures the crew survives the full ${T} sols.`
        : `With all in-habitat procedures: ${wp.runway_sols} sols.`));

    // Earth link
    const c = d.comm;
    setT("crisisDelay", c.in_conjunction ? "NO LINK" : `${c.one_way_light_min} min`);
    setT("crisisDelaySub", c.in_conjunction ? "solar conjunction" : `one-way · ${c.round_trip_min} min round trip · ${c.distance_au} AU`);
    setT("crisisConj", c.next_conjunction_in_days != null
        ? `Next conjunction blackout in ${c.next_conjunction_in_days} days (~${c.next_conjunction_length_days} days long)`
        : "No conjunction in the next ~2 years");

    // Ordered actions
    document.getElementById("crisisActions").innerHTML = d.actions.map(a => `
        <li class="crisis-action kind-${a.kind}">
            <div class="ca-head"><span class="ca-kind">${a.kind}</span><span class="ca-title">${a.title}</span></div>
            <div class="ca-detail">${a.detail}</div>
        </li>`).join("");

    // Destinations
    const r = d.relocation;
    setT("crisisRange", `rover range ~${r.rover_range_km.toLocaleString()} km`);
    document.getElementById("crisisDestinations").innerHTML = r.destinations.map(x => `
        <tr class="${x.reachable ? "" : "row-dim"}">
            <td><strong>${x.name}</strong></td>
            <td>${x.distance_km.toLocaleString()} km</td>
            <td>${x.transit_sols} sols</td>
            <td>${x.storm_at_destination === "none" ? "clear" : x.storm_at_destination.replace("_pede", " storm")}</td>
            <td><span class="verdict ${VERDICT_CLASS[x.verdict] || ""}">${x.verdict}</span>
                ${x.reachable ? `<small class="verdict-sub">${x.destination_outcome.survives ? "survives there" : `${x.destination_outcome.runway_sols} sols there`}</small>` : ""}</td>
        </tr>`).join("");
    document.getElementById("crisisAssumptions").innerHTML = r.assumptions.map(a => `<li>${a}</li>`).join("");

    // What-ifs
    const row = (title, o, gain, kind) => `
        <tr>
            <td>${title}${kind === "hardware" ? ' <span class="badge-micro">design change</span>' : ""}</td>
            <td>${o.survives ? `${o.timeline}+` : o.runway_sols}</td>
            <td class="${gain > 0 ? "text-green" : gain < 0 ? "text-red" : ""}">${gain > 0 ? "+" : ""}${gain}</td>
            <td>${o.blackout_sols}</td>
            <td>${o.min_soc}%</td>
        </tr>`;
    document.getElementById("crisisWhatIfs").innerHTML =
        row("<em>Do nothing (baseline)</em>", b, 0, "") +
        d.countermeasures.map(o => row(o.title, o, o.runway_gain_sols, o.kind)).join("");

    renderCrisisChart(d.timeline, b);
    updateRunwayIndicators(d);
}

function renderCrisisChart(timeline, base) {
    const ctx = document.getElementById("chartCrisis");
    if (!ctx || typeof Chart === "undefined") return;
    if (state.charts.crisis) state.charts.crisis.destroy();
    const lost = timeline.findIndex(t => t.crew_lost);
    const cut = lost >= 0 ? lost + 1 : timeline.length;
    const tl = timeline.slice(0, cut);
    const pct = (arr, key) => { const m = Math.max(1, arr[0][key]); return arr.map(t => Math.round(100 * t[key] / m)); };
    state.charts.crisis = new Chart(ctx, {
        type: "line",
        data: {
            labels: tl.map(t => `Sol ${t.sol}`),
            datasets: [
                { label: "Battery %", data: tl.map(t => t.battery_soc), borderColor: "#10b981", borderWidth: 2, pointRadius: 0, tension: 0.2 },
                { label: "O₂ reserve %", data: pct(tl, "o2_stored_kg"), borderColor: "#00e5ff", borderWidth: 2, pointRadius: 0, tension: 0.2 },
                { label: "Food %", data: pct(tl, "food_stored_kg"), borderColor: "#f59e0b", borderWidth: 2, pointRadius: 0, tension: 0.2 },
                { label: "Water %", data: pct(tl, "water_stored_l"), borderColor: "#3b82f6", borderWidth: 2, pointRadius: 0, tension: 0.2 },
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { labels: { color: "#9ca3af", boxWidth: 12, font: { size: 11 } } },
                title: { display: true, color: "#9ca3af", font: { size: 11, weight: "normal" },
                         text: lost >= 0 ? `Reserves until crew loss on sol ${base.runway_sols}` : "Reserves over the simulation horizon (doing nothing)" }
            },
            scales: {
                x: { ticks: { color: "#6b7280", maxTicksLimit: 10 }, grid: { color: "rgba(255,255,255,0.04)" } },
                y: { min: 0, max: 100, ticks: { color: "#6b7280", callback: v => v + "%" }, grid: { color: "rgba(255,255,255,0.04)" } }
            }
        }
    });
}

// Top-bar runway pill + compact-nav mini pills reflect the Crisis assessment of the current base.
function updateRunwayIndicators(d) {
    const b = d.baseline;
    const cls = d.level === "STABLE" ? "ok" : d.level === "AT RISK" ? "warn" : "bad";
    const color = { ok: "#10b981", warn: "#f59e0b", bad: "#ef4444" }[cls];
    const txt = b.survives ? `${b.timeline}+ SOLS [${d.level}]` : `${b.runway_sols} SOLS [${d.level}]`;
    const top = document.getElementById("topRunwayPill");
    if (top) { top.textContent = txt; top.style.color = color; top.title = `${d.site.name} · ${d.scenario}`; }
    const mini = document.getElementById("miniRunway");
    if (mini) { mini.textContent = `RUNWAY ${b.survives ? b.timeline + "+" : b.runway_sols}`; mini.className = `mini-pill ${cls}`; }
    const link = document.getElementById("miniLink");
    if (link && d.comm) {
        link.textContent = d.comm.in_conjunction ? "EARTH: BLACKOUT" : `EARTH ${d.comm.one_way_light_min} MIN`;
        link.className = `mini-pill ${d.comm.in_conjunction ? "bad" : "ok"}`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const sel = document.getElementById("crisisSite");
    if (sel) sel.addEventListener("change", () => { sel.dataset.userPicked = "1"; });
});
