/**
 * ASTREON - Mars Mission Site Intelligence Platform
 * Frontend Interactive Controller & Scientific Telemetry Engine
 */

// Global Application State
const state = {
    allSites: [],
    rankedSites: [],
    selectedSite: null,
    missionInputs: {
        crew: 6,
        days: 30,
        weights: { water: 0.24, solar: 0.16, landing: 0.18, terrain: 0.12, temperature: 0.08, communication: 0.07, resilience: 0.15 },
        filters: { maxSlope: 5.0, minWater: 30 }
    },
    monitor: {
        lsDeg: 180,
        solHour: 12.0,
        scenario: "global_pede",
        pvArea: 300,
        habLoad: 12.0,
        tickerTimer: null,
        isTickerRunning: false
    },
    cascade: {
        lastResult: null,
        scrubbedSol: 1
    },
    charts: {
        diurnal: null,
        battery: null,
        seasonal: null,
        waterRadar: null,
        foodTiers: null,
        cascadePower: null,
        cascadeResources: null,
        cascadePhysiology: null,
        crisis: null
    },
    map: null,
    habitat: null,
    mapMarkers: [],
    dtnConnected: true,
    nasaApiKey: "DEMO_KEY"
};

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", async () => {
    initClock();
    initStickyNav();
    switchTab("tab-evaluator");
    refreshNasaStatus(false);
    setInterval(() => refreshNasaStatus(false), 5 * 60 * 1000);
    await loadHabitat();          // shared habitat config first: every module reads it
    await loadInitialSites();
    await runMissionAnalysis();
    initMarsMap();
    initMonitorSiteSelector();
    loadMonitorTelemetry();
    loadWaterEvidenceForSelected();
    runFoodRationingCalculation();
    initCascadeSiteSelector();
    runCascadeSimulation();
    initCrisisSiteSelector();
    runCrisisAssessment();
    loadNasaWeather();
    loadRoverPhotos("perseverance");
    loadNasaCatalog();
    updateCommGeometry();
});

// Honest NASA data-link badge: LIVE / CACHED / OFFLINE MODEL (never hardcoded).
const LINK_BADGE_CLASS = { "LIVE": "live", "CACHED": "cached", "OFFLINE MODEL": "offline" };

function applyNasaStatus(st) {
    const pill = document.getElementById("nasaStatusPill");
    const txt = document.getElementById("nasaStatusText");
    if (!pill || !txt || !st) return;
    pill.className = `status-badge ${LINK_BADGE_CLASS[st.mode] || "offline"}`;
    txt.textContent = `NASA DATA: ${st.mode}`;
    pill.title = `${st.detail}\nChecked ${st.checked_at}${st.api_key_is_demo ? "\nUsing DEMO_KEY (rate-limited)" : ""}\nClick to re-check.`;
}

async function refreshNasaStatus(force) {
    const txt = document.getElementById("nasaStatusText");
    if (force && txt) txt.textContent = "NASA LINK: CHECKING…";
    try {
        const res = await fetch(`/api/nasa/status${force ? "?force=1" : ""}`);
        applyNasaStatus(await res.json());
    } catch (err) {
        applyNasaStatus({ mode: "OFFLINE MODEL", detail: "Local server unreachable", checked_at: new Date().toISOString() });
    }
}

// Live Sol Clock & Season Display
function initClock() {
    // Coordinated Mars Time (Allison & McEwen 2000, as used by NASA GISS Mars24).
    const tick = () => {
        const jdUT = Date.now() / 86400000 + 2440587.5;
        const jdTT = jdUT + (69.184 / 86400);           // TT - UTC (37 leap s + 32.184 s)
        const msd = (jdTT - 2405522.0028779) / 1.0274912517;
        const mtcHours = ((msd % 1) + 1) % 1 * 24;
        const h = Math.floor(mtcHours), m = Math.floor((mtcHours * 60) % 60), sec = Math.floor((mtcHours * 3600) % 60);
        const el = document.getElementById("topSolClock");
        if (el) el.textContent = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
        if (el) el.title = `Mars Sol Date ${Math.floor(msd)}`;
    };
    tick();
    setInterval(tick, 1000);
}

// ==========================================
// NAVIGATION: 4 stages (groups) x sub-views
// ==========================================
const NAV_GROUP_DEFAULT = { base: "tab-evaluator", stress: "tab-cascade", crisis: "tab-crisis", link: "tab-comm" };
const NAV_GROUP_HINT = {
    base: "Rank candidate sites by water, sunlight, terrain and storm resilience.",
    stress: "Throw dust storms and shortages at the chosen base and watch the cascade.",
    crisis: "",
    link: "Earth-Mars light time, conjunction blackouts and the NASA data behind the models."
};
const navLastView = { ...NAV_GROUP_DEFAULT };

function groupOfView(viewId) {
    const b = document.querySelector(`.tab-btn[data-tab="${viewId}"]`);
    return b ? b.dataset.group : "base";
}

function switchGroup(group) {
    switchTab(navLastView[group] || NAV_GROUP_DEFAULT[group]);
}

function switchTab(tabId) {
    const group = groupOfView(tabId);
    navLastView[group] = tabId;
    document.querySelectorAll(".nav-group-btn").forEach(b => b.classList.toggle("active", b.dataset.group === group));
    document.querySelectorAll("#navSub .tab-btn").forEach(btn => {
        btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
        btn.classList.toggle("in-group", btn.dataset.group === group);
    });
    const hint = document.getElementById("navSubHint");
    if (hint) hint.textContent = NAV_GROUP_HINT[group] || "";
    reserveNavSpace();
    document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.toggle("active", content.id === tabId);
    });

    // Leaflet must re-measure once its tab is visible, otherwise it fits to a 0x0 box.
    if (tabId === "tab-map" && state.map) {
        requestAnimationFrame(() => {
            refitMarsMap();
            setTimeout(refitMarsMap, 120);
        });
    }
    if (tabId === "tab-crisis" && typeof onCrisisViewShown === "function") onCrisisViewShown();

    // Keep the user oriented: jump to the top of the content (below the header when the bar is stuck).
    const shell = document.getElementById("navShell");
    if (shell && window.scrollY > shell.offsetTop) window.scrollTo({ top: shell.offsetTop });
}

// Reserve the full-size bar height in the page flow, so stick/compact never shifts content.
function reserveNavSpace() {
    const shell = document.getElementById("navShell");
    const nav = document.getElementById("navBar");
    if (!shell || !nav) return;
    const wasCompact = nav.classList.contains("compact");
    nav.classList.add("measuring");            // no transitions while measuring
    nav.classList.remove("compact");
    shell.style.height = nav.offsetHeight + "px";
    if (wasCompact) nav.classList.add("compact");
    void nav.offsetHeight;
    nav.classList.remove("measuring");
}

// Sticky navigation: full size at rest; compact while scrolling down; full again on scroll-up.
// The bar becomes position:fixed inside a shell that keeps its full height reserved, so
// resizing it never shifts the page (no jitter / feedback loop with scroll anchoring).
function initStickyNav() {
    const shell = document.getElementById("navShell");
    const nav = document.getElementById("navBar");
    if (!shell || !nav) return;

    reserveNavSpace();
    window.addEventListener("resize", reserveNavSpace);

    let lastY = window.scrollY, travel = 0, ticking = false;
    const THRESH = 24; // px of consistent travel before changing state

    const update = () => {
        ticking = false;
        const y = window.scrollY;
        const stuck = y > shell.offsetTop;
        nav.classList.toggle("stuck", stuck);
        if (!stuck) {
            nav.classList.remove("compact");
            travel = 0;
        } else {
            const dy = y - lastY;
            travel = (Math.sign(dy) === Math.sign(travel)) ? travel + dy : dy;
            if (travel > THRESH) nav.classList.add("compact");
            else if (travel < -THRESH) nav.classList.remove("compact");
        }
        lastY = y;
    };
    window.addEventListener("scroll", () => {
        if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }, { passive: true });
    update();
}

// ==========================================
// MISSION EVALUATOR & MCDA ENGINE (TAB 01)
// ==========================================
async function loadInitialSites() {
    try {
        const res = await fetch("/api/sites");
        state.allSites = await res.json();
        if (state.allSites.length > 0 && !state.selectedSite) {
            state.selectedSite = state.allSites[0];
        }
    } catch (err) {
        console.error("Failed to load sites:", err);
    }
}

const WEIGHT_INPUTS = [
    ["water", "weightWater", "valWeightWater", 24],
    ["solar", "weightSolar", "valWeightSolar", 16],
    ["landing", "weightLanding", "valWeightLanding", 18],
    ["terrain", "weightTerrain", "valWeightTerrain", 12],
    ["temperature", "weightTemp", "valWeightTemp", 8],
    ["communication", "weightComm", "valWeightComm", 7],
    ["resilience", "weightResilience", "valWeightResilience", 15],
];

function updateWeightDisplay() {
    const raw = {};
    WEIGHT_INPUTS.forEach(([k, inputId]) => { raw[k] = Number(document.getElementById(inputId)?.value || 0); });
    const total = Object.values(raw).reduce((a, b) => a + b, 0) || 1;
    WEIGHT_INPUTS.forEach(([k, , labelId]) => {
        const el = document.getElementById(labelId);
        if (el) el.textContent = `${Math.round(100 * raw[k] / total)}%`;   // shown as normalised share
    });
    state.missionInputs.weights = Object.fromEntries(Object.entries(raw).map(([k, v]) => [k, v / 100]));
}

function resetDefaultWeights() {
    WEIGHT_INPUTS.forEach(([, inputId, , def]) => { const el = document.getElementById(inputId); if (el) el.value = def; });
    updateWeightDisplay();
    runMissionAnalysis();
}

async function runMissionAnalysis() {
    updateWeightDisplay();
    const crew = Number(document.getElementById("inputCrew").value) || 6;
    const days = Number(document.getElementById("inputDays").value) || 30;
    const maxSlope = Number(document.getElementById("filterMaxSlope").value) || 5.0;
    const minWater = Number(document.getElementById("filterMinWater").value) || 0;

    state.missionInputs.crew = crew;
    state.missionInputs.days = days;
    state.missionInputs.filters = { max_slope: maxSlope, min_water_score: minWater };

    try {
        const response = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                crew: crew,
                days: days,
                weights: state.missionInputs.weights,
                filters: state.missionInputs.filters,
                habitat: { ...state.habitat, crew: crew, mission_sols: Math.min(180, Math.max(10, days)) }
            })
        });

        if (!response.ok) {
            const err = await response.json();
            alert(err.error || "Mission analysis failed.");
            return;
        }

        const data = await response.json();
        state.rankedSites = data.ranked_sites;
        // First load: the working base is the top recommendation, so every stage starts from it.
        if (!state.baseChosen || !state.selectedSite || !state.rankedSites.some(s => s.id === state.selectedSite.id)) {
            state.selectedSite = data.best_site;
            state.baseChosen = true;
            ["cascadeSiteSelect", "crisisSite", "monitorSiteSelect", "waterSiteSelect"].forEach(id => {
                const el = document.getElementById(id);
                if (el && el.dataset.userPicked !== "1" && [...el.options].some(o => o.value === data.best_site.id)) el.value = data.best_site.id;
            });
        }

        renderBestSiteSpotlight(data.best_site, crew, days);
        renderRankedSiteCards(data.ranked_sites);
        updateMapMarkers();
        initMonitorSiteSelector();
        if (typeof initCrisisSiteSelector === "function") initCrisisSiteSelector();
    } catch (err) {
        console.error("Analysis execution error:", err);
    }
}

function renderBestSiteSpotlight(best, crew, days) {
    const el = document.getElementById("bestSiteSpotlight");
    if (!el) return;

    const scores = best.calculated_scores;
    const res = best.resilience;
    const sm = best.solar_model;
    const cls = (v) => v >= 80 ? "optimal" : v >= 55 ? "warning" : "danger";
    const resText = res.runway_sols >= res.timeline ? `${res.timeline}+ sols` : `${res.runway_sols} sols`;

    el.innerHTML = `
        <div class="best-badge-ribbon">★ TOP RECOMMENDATION</div>
        <div class="best-top-row">
            <div>
                <span class="section-tag">${best.id} • ${best.region}</span>
                <h2 class="best-title">${best.name}</h2>
                <p class="best-sub">${best.geological_context}</p>
            </div>
            <div class="best-score-display">
                <div class="best-score-num">${scores.final_composite_score}%</div>
                <div class="best-score-label">MCDA SUITABILITY INDEX</div>
            </div>
        </div>

        <div class="resource-coverage-grid">
            <div class="coverage-box">
                <span class="coverage-k">Water evidence</span>
                <div class="coverage-v ${cls(scores.water)}">${scores.water}%</div>
                <span class="coverage-note">SHARAD · GRS · CRISM</span>
            </div>
            <div class="coverage-box">
                <span class="coverage-k">Solar (modelled)</span>
                <div class="coverage-v ${cls(scores.solar)}">${scores.solar}%</div>
                <span class="coverage-note">worst season ${sm.min_kwh_m2} kWh/m²/sol</span>
            </div>
            <div class="coverage-box">
                <span class="coverage-k">Storm resilience</span>
                <div class="coverage-v ${cls(scores.resilience)}">${scores.resilience}%</div>
                <span class="coverage-note">regional storm: ${resText}</span>
            </div>
            <div class="coverage-box">
                <span class="coverage-k">Landing safety</span>
                <div class="coverage-v ${cls(scores.landing)}">${scores.landing}%</div>
                <span class="coverage-note">assigned score</span>
            </div>
            <div class="coverage-box coverage-wide">
                <span class="coverage-k">Verdict for ${crew} crew</span>
                <div class="coverage-v ${best.status.includes("FAILS") ? "danger" : best.status.includes("SHEDDING") ? "warning" : "optimal"}">${best.status}</div>
            </div>
        </div>

        <div class="data-provenance-callout">
            <div class="callout-icon">🔬</div>
            <div class="callout-body">
                <strong>Why this site:</strong> ${best.water_scientific.resource_type}; annual array yield
                ${sm.mean_kwh_m2} kWh/m²/sol (worst season ${sm.min_kwh_m2}); in a dust-season regional storm the shared
                habitat ${res.runway_sols >= res.timeline ? `keeps running for the full ${res.timeline} sols (battery floor ${res.min_soc}%)` : `fails on sol ${res.runway_sols}`}.
            </div>
        </div>

        <div class="best-actions-row">
            <button class="btn-primary-action compact" onclick="stressTestSite('${best.id}')">
                STRESS-TEST THIS BASE →
            </button>
            <button class="btn-secondary-action" onclick="crisisForSite('${best.id}')">
                RUN CRISIS MODE
            </button>
            <button class="btn-ghost-sm" onclick="selectAndInspectWater('${best.id}')">
                WATER EVIDENCE
            </button>
        </div>
    `;
}

function stressTestSite(siteId) {
    const site = state.allSites.find(s => s.id === siteId);
    if (site) state.selectedSite = site;
    const sel = document.getElementById("cascadeSiteSelect");
    if (sel) sel.value = siteId;
    switchTab("tab-cascade");
    runCascadeSimulation();
}

function crisisForSite(siteId) {
    const site = state.allSites.find(s => s.id === siteId);
    if (site) state.selectedSite = site;
    const sel = document.getElementById("crisisSite");
    if (sel) { sel.value = siteId; sel.dataset.userPicked = "1"; }
    switchTab("tab-crisis");
    runCrisisAssessment();
}

function renderRankedSiteCards(sites) {
    const container = document.getElementById("rankedSiteCards");
    if (!container) return;

    container.innerHTML = sites.map(site => {
        const sc = site.calculated_scores;
        return `
            <div class="site-card">
                <div>
                    <div class="site-card-top">
                        <div>
                            <span class="section-tag">${site.id}</span>
                            <h4 class="site-card-title">${site.name}</h4>
                            <span class="site-card-sub">${fmtLatLon(site.lat, site.lon)} • Elev: ${Number(site.elevation_m).toLocaleString()} m</span>
                        </div>
                        <div class="site-card-score">${sc.final_composite_score}%</div>
                    </div>

                    <div class="score-bar-bg">
                        <div class="score-bar-fill" style="width: ${sc.final_composite_score}%;"></div>
                    </div>

                    <div class="site-metrics-list">
                        <div class="metric-row">
                            <span class="metric-key">Scientific Water Potential:</span>
                            <span class="metric-val text-cyan">${sc.water}%</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-key">Solar (modelled):</span>
                            <span class="metric-val text-yellow">${sc.solar}%</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-key">Storm Resilience:</span>
                            <span class="metric-val ${site.resilience.runway_sols >= site.resilience.timeline ? "text-green" : "text-red"}">${sc.resilience}% · ${site.resilience.runway_sols >= site.resilience.timeline ? "survives" : "fails sol " + site.resilience.runway_sols}</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-key">Landing & EDL Safety:</span>
                            <span class="metric-val text-green">${sc.landing}%</span>
                        </div>
                        <div class="metric-row">
                            <span class="metric-key">Regional Slope:</span>
                            <span class="metric-val">${site.slope_deg}°</span>
                        </div>
                    </div>
                </div>

                <div class="site-card-actions">
                    <button class="btn-primary-action compact" style="width:100%;" onclick="stressTestSite('${site.id}')">
                        STRESS-TEST THIS ZONE
                    </button>
                </div>
            </div>
        `;
    }).join("");
}

function selectAndMonitorSite(siteId) {
    const site = state.allSites.find(s => s.id === siteId);
    if (!site) return;
    state.selectedSite = site;

    const picker = document.getElementById("monitorSiteSelect");
    if (picker) picker.value = siteId;

    loadMonitorTelemetry();
    switchTab("tab-monitor");
}

function selectAndInspectWater(siteId) {
    const site = state.allSites.find(s => s.id === siteId);
    if (!site) return;
    state.selectedSite = site;

    const picker = document.getElementById("waterSiteSelect");
    if (picker) picker.value = siteId;

    loadWaterEvidenceForSelected();
    switchTab("tab-water");
}

// ==========================================
// MARS CARTOGRAPHIC MAP (TAB 02)
// ==========================================
const MARS_BOUNDS = [[-90, -180], [90, 180]];

function initMarsMap() {
    const mapEl = document.getElementById("marsMapCanvas");
    if (!mapEl || typeof L === "undefined") return;

    // Equirectangular Mars: CRS.Simple with y = latitude, x = east longitude (-180..180).
    state.map = L.map("marsMapCanvas", {
        crs: L.CRS.Simple,
        minZoom: -1,
        maxZoom: 4,
        zoomSnap: 0.25,
        zoomControl: true,
        maxBounds: [[-110, -220], [110, 220]],
        maxBoundsViscosity: 0.8,
        attributionControl: true
    });

    // Bundled locally (offline-safe): MGS MOLA colourised shaded relief rendered from the
    // MarsTopo719 spherical-harmonic shape model. See static/img/README.md for provenance.
    L.imageOverlay("/static/img/mars_mola_2k.jpg", MARS_BOUNDS, {
        attribution: "Basemap: NASA MGS / MOLA topography",
        interactive: false
    }).addTo(state.map);

    // Light 30° graticule
    const gridStyle = { color: "rgba(255,255,255,0.18)", weight: 1, interactive: false };
    for (let lat = -60; lat <= 60; lat += 30) {
        L.polyline([[lat, -180], [lat, 180]], gridStyle).addTo(state.map);
    }
    for (let lon = -150; lon <= 150; lon += 30) {
        L.polyline([[-90, lon], [90, lon]], gridStyle).addTo(state.map);
    }

    state.map.fitBounds(MARS_BOUNDS);
    updateMapMarkers();
    if (state.selectedSite) updateMapInfobar(state.selectedSite);
}

// Leaflet measures its container on creation; the map tab is hidden at that time,
// so it must be re-measured and re-fitted whenever the tab becomes visible.
function refitMarsMap() {
    if (!state.map) return;
    state.map.invalidateSize();
    state.map.fitBounds(MARS_BOUNDS, { padding: [8, 8] });
}

function fmtLatLon(lat, lon) {
    const ns = lat >= 0 ? "N" : "S";
    const ew = lon >= 0 ? "E" : "W";
    return `${Math.abs(lat).toFixed(1)}° ${ns}, ${Math.abs(lon).toFixed(1)}° ${ew}`;
}

function updateMapInfobar(site) {
    const ws = site.water_scientific || {};
    const score = site.water_score ?? (site.calculated_scores ? site.calculated_scores.water : null);
    const setT = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };
    setT("mapSelectedName", site.name);
    setT("mapSelectedCoords", fmtLatLon(site.lat, site.lon));
    setT("mapSelectedElev", `${Number(site.elevation_m).toLocaleString()} m`);
    setT("mapSelectedWater", score != null ? `${score}% (${ws.resource_type ? ws.resource_type.split("(")[0].trim() : "see Water tab"})` : "--");
}

function updateMapMarkers() {
    if (!state.map) return;

    // Clear existing
    state.mapMarkers.forEach(m => state.map.removeLayer(m));
    state.mapMarkers = [];

    const sitesToMap = state.rankedSites.length > 0 ? state.rankedSites : state.allSites;

    sitesToMap.forEach(site => {
        const score = site.calculated_scores ? site.calculated_scores.final_composite_score : 80;
        const color = score >= 80 ? "#10b981" : score >= 65 ? "#f59e0b" : "#ef4444";

        const marker = L.circleMarker([site.lat, site.lon], {
            radius: 9,
            color: "#0b0f17",
            fillColor: color,
            fillOpacity: 0.95,
            weight: 2
        }).addTo(state.map);

        const waterScore = site.calculated_scores ? site.calculated_scores.water : site.water_score;
        marker.bindTooltip(`${site.name.split(" ")[0]} · ${score}%`, {
            permanent: true, direction: "right", offset: [10, 0], className: "mars-site-label"
        });
        marker.bindPopup(`
            <div style="font-family:sans-serif; color:#0e1420; padding:4px;">
                <strong>${site.name}</strong> (${site.id})<br>
                <span>${fmtLatLon(site.lat, site.lon)}</span><br>
                <span>MOLA Elevation: ${Number(site.elevation_m).toLocaleString()} m</span><br>
                <span>Suitability: <strong>${score}%</strong> · Water: <strong>${waterScore ?? "--"}%</strong></span><br>
                <button onclick="selectAndMonitorSite('${site.id}')" style="margin-top:6px; background:#ff5722; color:#fff; border:none; padding:4px 8px; border-radius:4px; cursor:pointer;">
                    Monitor Zone
                </button>
            </div>
        `);

        marker.on("click", () => {
            state.selectedSite = site;
            updateMapInfobar(site);
        });

        state.mapMarkers.push(marker);
    });
}

function navigateToMonitorForSelected() {
    if (state.selectedSite) {
        selectAndMonitorSite(state.selectedSite.id);
    }
}

// ==========================================
// CONTINUOUS SOLAR & DUST RISK MONITOR (TAB 03)
// ==========================================
function initMonitorSiteSelector() {
    const picker = document.getElementById("monitorSiteSelect");
    const waterPicker = document.getElementById("waterSiteSelect");
    if (!picker || state.allSites.length === 0) return;

    const options = state.allSites.map(s => `
        <option value="${s.id}" ${state.selectedSite && state.selectedSite.id === s.id ? 'selected' : ''}>
            ${s.name} (${s.id})
        </option>
    `).join("");

    picker.innerHTML = options;
    if (waterPicker) waterPicker.innerHTML = options;
}

function onMonitorSiteChange() {
    const siteId = document.getElementById("monitorSiteSelect").value;
    const site = state.allSites.find(s => s.id === siteId);
    if (site) {
        state.selectedSite = site;
        loadMonitorTelemetry();
    }
}

function onMonitorParamChange() {
    const ls = Number(document.getElementById("monitorLsSlider").value);
    const hour = Number(document.getElementById("monitorHourSlider").value);
    const scenario = document.getElementById("monitorScenarioSelect").value;

    state.monitor.lsDeg = ls;
    state.monitor.solHour = hour;
    state.monitor.scenario = scenario;

    document.getElementById("monitorLsDisplay").textContent = `${ls}°`;
    document.getElementById("topSeasonLs").textContent = `Ls ${ls}°`;
    document.getElementById("topSeasonLs").title = getSeasonName(ls);

    const hourInt = Math.floor(hour);
    const minInt = Math.floor((hour % 1) * 60);
    document.getElementById("monitorHourDisplay").textContent = `${String(hourInt).padStart(2, '0')}:${String(minInt).padStart(2, '0')}`;

    loadMonitorTelemetry();
}

function getSeasonName(ls) {
    if (ls < 45 || ls >= 315) return "N. Spring / Perihelion Approach";
    if (ls < 135) return "N. Summer / Aphelion";
    if (ls < 225) return "N. Autumn Equinox";
    return "N. Winter / Perihelion Dust Season";
}

async function loadMonitorTelemetry() {
    if (!state.selectedSite) return;

    const siteId = state.selectedSite.id;
    const ls = state.monitor.lsDeg;
    const hour = state.monitor.solHour;
    const sc = state.monitor.scenario;

    try {
        const hab = encodeURIComponent(JSON.stringify(state.habitat || {}));
        const res = await fetch(`/api/site/${siteId}/monitor?ls=${ls}&hour=${hour}&scenario=${sc}&habitat=${hab}`);
        const data = await res.json();
        const q = data.query_state;
        const bDesc = document.getElementById("batteryChartDesc");
        if (bDesc && q) bDesc.textContent = `Shared habitat: ${q.pv_area_m2} m² array, ${q.battery_kwh} kWh battery, ${q.hab_load_kw} kW average load (same model as the cascade).`;

        // Update KPIs
        const instant = data.instant_irradiance;
        const storm = data.dust_storm_simulation;

        document.getElementById("kpiFlux").textContent = instant.total_flux;
        document.getElementById("kpiFluxDetail").textContent = `Direct: ${instant.direct_flux} | Diffuse: ${instant.diffuse_flux} W/m²`;

        document.getElementById("kpiDailyKwh").textContent = storm.daily_kwh_generated;
        document.getElementById("kpiDailyMargin").textContent = `Net: ${storm.net_daily_margin_kwh > 0 ? '+' : ''}${storm.net_daily_margin_kwh} kWh (Demand: ${storm.daily_kwh_required} kWh)`;

        document.getElementById("kpiReliability").textContent = storm.energy_reliability_score;
        document.getElementById("kpiReliabilityStatus").textContent = storm.status;

        document.getElementById("kpiRunway").textContent = storm.sols_to_blackout >= 900 ? "∞ (Surplus)" : storm.sols_to_blackout;
        document.getElementById("kpiBlackoutStatus").textContent = storm.net_daily_margin_kwh < 0 ? `Battery depleting at τ=${storm.tau}` : "Sustained positive energy margin";

        // Update Directives
        const directivesList = document.getElementById("mitigationDirectivesList");
        if (directivesList && storm.mitigation_directives) {
            directivesList.innerHTML = storm.mitigation_directives.map(d => `<li>${d}</li>`).join("");
        }

        // Render Charts
        renderDiurnalChart(data.diurnal_curve, hour);
        renderBatteryChart(storm.hourly_simulation, hour);
        renderSeasonalChart(data.seasonal_curve, ls);
    } catch (err) {
        console.error("Monitor telemetry error:", err);
    }
}

function renderDiurnalChart(diurnal, currentHour) {
    const ctx = document.getElementById("chartDiurnal")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.diurnal) {
        state.charts.diurnal.destroy();
    }

    const labels = diurnal.map(d => `${d.hour}:00`);
    const totalFlux = diurnal.map(d => d.total_flux);
    const directFlux = diurnal.map(d => d.direct_flux);
    const diffuseFlux = diurnal.map(d => d.diffuse_flux);

    state.charts.diurnal = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Total Surface Insolation (W/m²)",
                    data: totalFlux,
                    borderColor: "#ff7849",
                    backgroundColor: "rgba(255, 120, 73, 0.15)",
                    fill: true,
                    tension: 0.35,
                    borderWidth: 2
                },
                {
                    label: "Direct Beam (W/m²)",
                    data: directFlux,
                    borderColor: "#00e5ff",
                    borderDash: [4, 4],
                    borderWidth: 1.5,
                    tension: 0.35
                },
                {
                    label: "Diffuse Sky Flux (W/m²)",
                    data: diffuseFlux,
                    borderColor: "#fbbf24",
                    borderWidth: 1.5,
                    tension: 0.35
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } } },
                tooltip: { mode: "index", intersect: false }
            },
            scales: {
                x: { ticks: { color: "#6b7280" }, grid: { color: "rgba(255,255,255,0.05)" } },
                y: { ticks: { color: "#6b7280" }, grid: { color: "rgba(255,255,255,0.05)" }, title: { display: true, text: "Flux (W/m²)", color: "#9ca3af" } }
            }
        }
    });
}

function renderBatteryChart(hourlySim, currentHour) {
    const ctx = document.getElementById("chartBattery")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.battery) {
        state.charts.battery.destroy();
    }

    const labels = hourlySim.map(h => `${h.hour}:00`);
    const soc = hourlySim.map(h => h.battery_soc_pct);
    const powerGen = hourlySim.map(h => h.power_gen_kw);

    state.charts.battery = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Battery State-of-Charge (%)",
                    data: soc,
                    borderColor: "#10b981",
                    backgroundColor: "rgba(16, 185, 129, 0.1)",
                    fill: true,
                    tension: 0.3,
                    borderWidth: 2,
                    yAxisID: "ySoC"
                },
                {
                    label: "Solar PV Generation (kW)",
                    data: powerGen,
                    borderColor: "#ff5722",
                    backgroundColor: "rgba(255, 87, 34, 0.2)",
                    fill: false,
                    tension: 0.3,
                    borderWidth: 2,
                    yAxisID: "yPower"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } } }
            },
            scales: {
                x: { ticks: { color: "#6b7280" }, grid: { color: "rgba(255,255,255,0.05)" } },
                ySoC: {
                    type: "linear",
                    position: "left",
                    min: 0,
                    max: 100,
                    ticks: { color: "#10b981" },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    title: { display: true, text: "Battery SoC %", color: "#10b981" }
                },
                yPower: {
                    type: "linear",
                    position: "right",
                    ticks: { color: "#ff5722" },
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: "PV Power (kW)", color: "#ff5722" }
                }
            }
        }
    });
}

function renderSeasonalChart(seasonal, currentLs) {
    const ctx = document.getElementById("chartSeasonal")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.seasonal) {
        state.charts.seasonal.destroy();
    }

    const labels = seasonal.map(s => s.label);
    const noonFlux = seasonal.map(s => s.noon_flux);
    const dailyKwh = seasonal.map(s => s.daily_energy_kwh_m2);

    state.charts.seasonal = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [
                {
                    type: "bar",
                    label: "Daily Energy Yield (kWh/m²/sol)",
                    data: dailyKwh,
                    backgroundColor: "rgba(0, 229, 255, 0.4)",
                    borderColor: "#00e5ff",
                    borderWidth: 1,
                    yAxisID: "yEnergy"
                },
                {
                    type: "line",
                    label: "Solar Noon Peak Flux (W/m²)",
                    data: noonFlux,
                    borderColor: "#f59e0b",
                    tension: 0.35,
                    borderWidth: 2,
                    yAxisID: "yFlux"
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } } }
            },
            scales: {
                x: { ticks: { color: "#6b7280" }, grid: { color: "rgba(255,255,255,0.05)" } },
                yEnergy: {
                    type: "linear",
                    position: "left",
                    ticks: { color: "#00e5ff" },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    title: { display: true, text: "Daily kWh/m²", color: "#00e5ff" }
                },
                yFlux: {
                    type: "linear",
                    position: "right",
                    ticks: { color: "#f59e0b" },
                    grid: { drawOnChartArea: false },
                    title: { display: true, text: "Noon W/m²", color: "#f59e0b" }
                }
            }
        }
    });
}

function toggleLiveTelemetryTicker() {
    state.monitor.isTickerRunning = !state.monitor.isTickerRunning;
    const btn = document.getElementById("btnLiveTicker");
    const txt = document.getElementById("tickerBtnText");

    if (state.monitor.isTickerRunning) {
        btn.classList.add("running");
        txt.textContent = "STOP LIVE TICK";
        state.monitor.tickerTimer = setInterval(() => {
            let h = state.monitor.solHour + 0.25;
            if (h > 24) h = 0;
            state.monitor.solHour = Math.round(h * 100) / 100;
            document.getElementById("monitorHourSlider").value = state.monitor.solHour;
            onMonitorParamChange();
        }, 750);
    } else {
        btn.classList.remove("running");
        txt.textContent = "START LIVE TICK";
        clearInterval(state.monitor.tickerTimer);
    }
}

// ==========================================
// SCIENTIFIC WATER EVIDENCE LAB (TAB 04)
// ==========================================
async function loadWaterEvidenceForSelected() {
    const picker = document.getElementById("waterSiteSelect");
    const siteId = picker ? picker.value : (state.selectedSite ? state.selectedSite.id : "MSA-001");

    try {
        const res = await fetch(`/api/site/${siteId}/water_evidence`);
        const data = await res.json();
        const wa = data.water_analysis;

        document.getElementById("evDielectric").textContent = wa.dielectric_permittivity.toFixed(2);
        document.getElementById("evRadarSummary").textContent = data.evidence_raw.summary || "SHARAD radar sounding profile";
        document.getElementById("evIcePurity").textContent = `${wa.ice_purity_pct}%`;
        document.getElementById("evSlabIce").textContent = wa.ice_purity_pct > 50 ? "CONFIRMED (Massive Glacier)" : "ABSENT";

        document.getElementById("evGrs").textContent = `${wa.grs_weh_wt_pct.toFixed(1)}%`;
        document.getElementById("evGrsGrade").textContent = wa.grs_weh_wt_pct >= 8.0 ? "Grade A (High WEH)" : wa.grs_weh_wt_pct >= 4.0 ? "Grade B (Moderate)" : "Grade C (Low)";

        document.getElementById("evCrism").textContent = wa.crism_hydration_index.toFixed(2);
        document.getElementById("evCrismStatus").textContent = wa.crism_hydration_index >= 0.7 ? "Abundant Phyllosilicates/Sulfates" : "Trace bound hydration";

        document.getElementById("evEnergy").textContent = wa.extraction_energy_kwh_kg.toFixed(2);
        document.getElementById("evOverburden").textContent = `${wa.overburden_depth_m} m`;
        document.getElementById("evMethod").textContent = wa.feasibility;

        document.getElementById("evExtractionDesc").textContent = 
            `Extraction feasibility: ${wa.feasibility}. Method: ${wa.resource_type}. Primary energy cost is ${wa.extraction_energy_kwh_kg} kWh per liter of potable water produced.`;

        // Extraction Rationale Box
        document.getElementById("extractionRationaleContent").innerHTML = `
            <p><strong>Primary Resource Category:</strong> ${wa.resource_type}</p>
            <p style="margin-top:6px;"><strong>Extraction Thermodynamics:</strong> At this site, the extraction mechanism requires <strong>${wa.extraction_energy_kwh_kg} kWh/kg</strong> of thermal and pumping power. For an astronaut crew consuming 21 L/sol, this consumes <strong>${(21 * wa.extraction_energy_kwh_kg).toFixed(1)} kWh/sol</strong> of continuous life support power.</p>
            <p style="margin-top:6px;"><strong>Geological Context:</strong> ${data.geological_context}</p>
        `;

        renderWaterRadarChart(wa);
    } catch (err) {
        console.error("Water evidence load error:", err);
    }
}

function renderWaterRadarChart(wa) {
    const ctx = document.getElementById("chartWaterEvidence")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.waterRadar) {
        state.charts.waterRadar.destroy();
    }

    state.charts.waterRadar = new Chart(ctx, {
        type: "radar",
        data: {
            labels: [
                "SHARAD Radar Ice",
                "Odyssey GRS Hydrogen",
                "CRISM Mineral Hydration",
                "Overburden Accessibility",
                "Thermal Energy Efficiency"
            ],
            datasets: [{
                label: "Evidence Metric Score (0-100)",
                data: [
                    wa.radar_score,
                    wa.grs_score,
                    wa.crism_score,
                    wa.depth_score,
                    wa.energy_score
                ],
                backgroundColor: "rgba(0, 229, 255, 0.2)",
                borderColor: "#00e5ff",
                borderWidth: 2,
                pointBackgroundColor: "#ff7849",
                pointBorderColor: "#fff",
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    angleLines: { color: "rgba(255,255,255,0.08)" },
                    grid: { color: "rgba(255,255,255,0.08)" },
                    pointLabels: { color: "#9ca3af", font: { size: 11, family: "Inter" } },
                    ticks: { display: false, min: 0, max: 100 }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });
}

// ==========================================
// LIFE SUPPORT CRISIS & FOOD RATIONING (TAB 05)
// ==========================================
async function runFoodRationingCalculation() {
    const crew = Number(document.getElementById("foodCrew")?.value) || 6;
    const nomDays = Number(document.getElementById("foodNominalDays")?.value) || 30;
    const extDays = Number(document.getElementById("foodExtendedDays")?.value) || 50;
    const foodKg = Number(document.getElementById("foodRemainingKg")?.value) || 380;
    const ghRaw = document.getElementById("foodGreenhouseYield")?.value;
    const ghYield = ghRaw === "" || ghRaw === undefined ? 1.5 : Number(ghRaw);
    const weightKg = Number(document.getElementById("foodCrewWeight")?.value) || 75;
    const extHint = document.getElementById("foodExtensionHint");
    if (extHint) {
        const d = extDays - nomDays;
        extHint.textContent = d > 0 ? `+${d} sols extension` : d < 0 ? `${d} sols (shortened)` : "No extension";
    }

    try {
        const res = await fetch("/api/food_rationing/calculate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                crew_size: crew,
                nominal_days: nomDays,
                extended_days: extDays,
                food_stockpile_kg: foodKg,
                greenhouse_daily_yield_kg: ghYield,
                crew_avg_weight_kg: weightKg,
                habitat: state.habitat
            })
        });

        const plan = await res.json();
        if (!res.ok) {
            const banner = document.getElementById("foodTriageBanner");
            if (banner) banner.innerHTML = `<div><span class="section-tag text-red">INPUT REJECTED</span><p class="triage-desc">${plan.error}</p></div>`;
            return;
        }

        // Render Triage Banner
        const banner = document.getElementById("foodTriageBanner");
        if (banner) {
            banner.style.backgroundColor = `${plan.badge_color}22`;
            banner.style.border = `1px solid ${plan.badge_color}66`;
            banner.innerHTML = `
                <div>
                    <span class="section-tag" style="color:${plan.badge_color};">TRIAGE LEVEL: ${plan.severity}</span>
                    <h3 class="triage-title" style="color:${plan.badge_color};">${plan.restriction_level}</h3>
                    <p class="triage-desc">${plan.status_desc}</p>
                </div>
                <div style="text-align:right;">
                    <div style="font-family:var(--font-mono); font-size:1.4rem; font-weight:800; color:${plan.badge_color};">
                        ${plan.effective_daily_kcal_per_person} kcal/sol
                    </div>
                    <span style="font-size:0.72rem; color:var(--text-muted);">Per Astronaut Baseline</span>
                </div>
            `;
        }

        // Update KPIs
        document.getElementById("kpiFoodKcal").textContent = plan.effective_daily_kcal_per_person;
        document.getElementById("kpiFoodKcalDetail").textContent = plan.deficit_vs_nominal_kcal > 0
            ? `${plan.deficit_vs_nominal_kcal} kcal/sol below 2,800 nominal`
            : `Capped at 2,800 nominal (stock could fund ${plan.affordable_daily_kcal_per_person})`;

        document.getElementById("kpiFoodGrams").textContent = plan.daily_grams_per_person;
        document.getElementById("kpiFoodGramsDetail").textContent = `From ${plan.food_stockpile_kg} kg stockpile (+${plan.greenhouse_supplement_kcal} kcal greenhouse)`;

        document.getElementById("kpiFoodWeightLoss").textContent = `${plan.est_weight_loss_kg} kg`;
        document.getElementById("kpiFoodWeightPct").textContent = plan.est_weight_loss_pct >= 40
            ? `≥40% body mass — not survivable` : `${plan.est_weight_loss_pct}% projected body weight loss`;

        document.getElementById("kpiFoodRunway").textContent = plan.sols_at_nominal;
        document.getElementById("kpiFoodRunwayDetail").textContent = plan.reserve_kg_at_end > 0
            ? `Stored food at full 2,800 kcal (reserve after sol ${plan.extended_days}: ${Math.round(plan.reserve_kg_at_end)} kg)`
            : `Stored food at full 2,800 kcal · ${plan.sols_at_emergency} sols at 1,500 kcal`;

        // Render Phases Timeline
        const phasesContainer = document.getElementById("foodPhasesContainer");
        if (phasesContainer && plan.phases) {
            phasesContainer.innerHTML = plan.phases.map(p => `
                <div class="phase-card">
                    <div class="phase-header-row">
                        <span class="phase-title">${p.phase}</span>
                        <span class="phase-kcal">${p.daily_kcal} kcal/sol</span>
                    </div>
                    <div class="phase-body">
                        <p><strong>Nutrition:</strong> ${p.diet_focus}</p>
                        <p style="margin-top:4px;"><strong>Metabolic Management:</strong> ${p.crew_protocol}</p>
                    </div>
                </div>
            `).join("");
        }

        // Render Flight Surgeon Guidelines
        const guidelinesList = document.getElementById("foodGuidelinesList");
        if (guidelinesList && plan.actionable_guidelines) {
            guidelinesList.innerHTML = plan.actionable_guidelines.map(g => `<li>${g}</li>`).join("");
        }

        renderFoodTiersChart(plan.effective_daily_kcal_per_person);
    } catch (err) {
        console.error("Food rationing calculation error:", err);
    }
}

function renderFoodTiersChart(currentKcal) {
    const ctx = document.getElementById("chartFoodTiers")?.getContext("2d");
    if (!ctx) return;

    if (state.charts.foodTiers) {
        state.charts.foodTiers.destroy();
    }

    state.charts.foodTiers = new Chart(ctx, {
        type: "bar",
        data: {
            labels: [
                "Starvation Hazard",
                "Basal Survival Floor",
                "Mild Conservation",
                "Current Allocated Rations",
                "NASA Nominal Astronaut"
            ],
            datasets: [{
                label: "Daily Energy (kcal/person/sol)",
                data: [1200, 1550, 2100, currentKcal, 2800],
                backgroundColor: [
                    "rgba(239, 68, 68, 0.4)",
                    "rgba(245, 158, 11, 0.4)",
                    "rgba(59, 130, 246, 0.4)",
                    "rgba(0, 229, 255, 0.75)",
                    "rgba(16, 185, 129, 0.4)"
                ],
                borderColor: [
                    "#ef4444",
                    "#f59e0b",
                    "#3b82f6",
                    "#00e5ff",
                    "#10b981"
                ],
                borderWidth: 2
            }]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    min: 0,
                    max: 3200,
                    ticks: { color: "#6b7280" },
                    grid: { color: "rgba(255,255,255,0.05)" },
                    title: { display: true, text: "kcal / person / sol", color: "#9ca3af" }
                },
                y: {
                    ticks: { color: "#f3f4f6", font: { family: "Inter", weight: 500 } },
                    grid: { color: "rgba(255,255,255,0.05)" }
                }
            }
        }
    });
}

function setFoodPreset(preset) {
    if (preset === "nominal") {
        document.getElementById("foodNominalDays").value = 30;
        document.getElementById("foodExtendedDays").value = 30;
        document.getElementById("foodRemainingKg").value = 500;
    } else if (preset === "moderate") {
        document.getElementById("foodNominalDays").value = 30;
        document.getElementById("foodExtendedDays").value = 45;
        document.getElementById("foodRemainingKg").value = 350;
    } else if (preset === "severe") {
        document.getElementById("foodNominalDays").value = 30;
        document.getElementById("foodExtendedDays").value = 70;
        document.getElementById("foodRemainingKg").value = 220;
    }
    runFoodRationingCalculation();
}

function printFoodDirective() {
    window.print();
}

// ==========================================
// NASA OPEN DATA & WEATHER (TAB 06)
// ==========================================
async function loadNasaWeather() {
    try {
        const res = await fetch("/api/nasa/weather");
        const w = await res.json();

        const v = (x, unit = "") => (x === null || x === undefined ? "n/a" : `${x}${unit}`);
        document.getElementById("wTempAvg").textContent = v(w.temp_avg_c, "° C");
        document.getElementById("wTempRange").textContent = `Min: ${v(w.temp_min_c, "°C")} | Max: ${v(w.temp_max_c, "°C")}`;
        document.getElementById("wPressure").textContent = v(w.pressure_pa, " Pa");
        document.getElementById("wWind").textContent = v(w.wind_speed_ms, " m/s");
        document.getElementById("wWindDir").textContent = `Direction: ${v(w.wind_direction_deg, "°")}`;
        document.getElementById("wSol").textContent = w.sol === "n/a" ? "Model sol" : `Sol ${w.sol}`;
        document.getElementById("wSeason").textContent = w.season_ls;

        const badge = document.getElementById("weatherSourceBadge");
        if (badge) {
            badge.textContent = w.mode === "LIVE" ? "LIVE · INSIGHT ARCHIVE" : w.mode === "CACHED" ? `CACHED · ${(w.fetched_at || "").slice(0, 10)}` : "OFFLINE MODEL";
            badge.title = w.source + (w.notes ? `\n${w.notes}` : "");
        }
        const src = document.getElementById("weatherSourceNote");
        if (src) src.textContent = w.source;
    } catch (err) {
        console.error("NASA weather fetch error:", err);
    }
}

async function loadRoverPhotos(rover) {
    document.querySelectorAll(".rover-toggle-group button").forEach(b => b.classList.remove("active"));
    const activeBtn = rover === "perseverance" ? document.getElementById("btnRoverPerseverance") : document.getElementById("btnRoverCuriosity");
    if (activeBtn) activeBtn.classList.add("active");

    const container = document.getElementById("roverPhotosGrid");
    if (!container) return;

    container.innerHTML = `<div class="loading-state">Accessing NASA ${rover.toUpperCase()} Rover telemetry cache...</div>`;

    try {
        const sol = rover === "perseverance" ? 950 : 2200;
        const res = await fetch(`/api/nasa/rover_photos?rover=${rover}&sol=${sol}`);
        const data = await res.json();

        const modeNote = data.mode === "LIVE" ? "Live from api.nasa.gov"
            : data.mode === "CACHED" ? `Cached metadata from ${data.fetched_at}`
            : "Offline — reference list only (rover photo API is archived)";
        container.innerHTML = `<div class="rover-mode-note">${modeNote}</div>` + data.photos.map(p => `
            <div class="rover-photo-card">
                <div class="rover-img-frame">
                    <img src="${p.img_src}" alt="${p.camera}" class="rover-img" loading="lazy"
                         onerror="this.closest('.rover-img-frame').classList.add('img-missing'); this.remove();">
                    <div class="img-missing-placeholder">
                        <span class="img-missing-icon">◌</span>
                        <span>Cached image unavailable</span>
                        <small>Needs Earth link to load</small>
                    </div>
                </div>
                <div class="rover-meta">
                    <strong>${p.camera}</strong><br>
                    <span>${rover.toUpperCase()} • ${data.mode === "LIVE" ? `Sol ${sol} • ${p.earth_date}` : p.earth_date}</span>
                </div>
            </div>
        `).join("");
    } catch (err) {
        container.innerHTML = `<div class="loading-state">Unable to load rover photography.</div>`;
    }
}

async function loadNasaCatalog() {
    const tableBody = document.getElementById("nasaDatasetsTableBody");
    if (!tableBody) return;

    try {
        const [resData, resCode] = await Promise.all([
            fetch("/api/nasa/datasets"),
            fetch("/api/nasa/code_tools")
        ]);

        const datasets = (await resData.json()).datasets || [];
        const codeTools = (await resCode.json()).tools || [];

        const rows = [
            ...datasets.map(d => `
                <tr>
                    <td><strong>${d.title}</strong><br><small style="color:var(--text-muted);">${d.identifier}</small></td>
                    <td><a href="${d.url}" target="_blank" style="color:var(--mars-orange);">${d.portal}</a></td>
                    <td>Planetary Science Data</td>
                    <td>${d.usage_in_astreon}</td>
                </tr>
            `),
            ...codeTools.map(c => `
                <tr>
                    <td><strong>${c.name}</strong></td>
                    <td><a href="${c.url}" target="_blank" style="color:var(--telemetry-cyan);">${c.portal}</a></td>
                    <td>${c.category}</td>
                    <td>${c.integration}</td>
                </tr>
            `)
        ];

        tableBody.innerHTML = rows.join("");
    } catch (err) {
        console.error("NASA Catalog load error:", err);
    }
}

// ==========================================
// DTN COMMUNICATIONS (TAB 07)
// ==========================================
async function sendDtnTelemetry() {
    const msg = document.getElementById("commMessageInput").value.trim();
    if (!msg) return;

    try {
        const res = await fetch("/api/network/telemetry", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: msg,
                connected: state.dtnConnected,
                day_offset: Number(document.getElementById("commDayOffset")?.value || 0)
            })
        });

        const data = await res.json();
        renderCommGeometry(data);

        const logStream = document.getElementById("commLogStream");
        const entry = document.createElement("div");

        if (data.status === "DELIVERED_DSN") {
            entry.className = "log-entry ok";
            entry.textContent = `[${new Date().toLocaleTimeString()}] DELIVERED (Delay ${data.latency_minutes}m): "${data.message}" -> DSN confirmed.`;
        } else if (data.status === "SOLAR_CONJUNCTION_BLACKOUT") {
            entry.className = "log-entry warn";
            entry.textContent = `[${new Date().toLocaleTimeString()}] BLACKOUT: Solar Conjunction. Stored bundle ${data.bundle_id}.`;
        } else {
            entry.className = "log-entry err";
            entry.textContent = `[${new Date().toLocaleTimeString()}] LINK SEVERED: Stored in DTN custody: "${data.message}".`;
        }

        logStream.prepend(entry);
    } catch (err) {
        console.error("DTN send error:", err);
    }
}

function toggleEarthLink() {
    state.dtnConnected = !state.dtnConnected;
    const badge = document.getElementById("commStatusBadge");
    const desc = document.getElementById("linkDesc");
    const btn = document.getElementById("btnToggleLink");
    const beam = document.getElementById("beamInterplanetary");

    if (state.dtnConnected) {
        badge.className = "status-badge live";
        badge.textContent = "LINK ONLINE";
        desc.className = "link-desc text-green";
        desc.textContent = "Direct RF line-of-sight to Earth DSN active.";
        btn.textContent = "SIMULATE LINK DISRUPTION";
        beam.classList.add("active");
    } else {
        badge.className = "status-badge offline";
        badge.textContent = "LINK DISRUPTED";
        desc.className = "link-desc text-red";
        desc.textContent = "RF carrier lost. Messages stored in DTN non-volatile buffer.";
        btn.textContent = "RESTORE RF LINK";
        beam.classList.remove("active");
    }
}

function renderCommGeometry(data) {
    document.getElementById("commLatencyDisplay").textContent = `${data.latency_minutes} min`;
    if (data.distance_au) {
        document.getElementById("commDistDisplay").textContent =
            `Earth–Mars ${data.distance_au} AU · round trip ${(2 * data.latency_minutes).toFixed(1)} min · Sun angle ${data.sun_angle_deg ?? "--"}°`;
    }
}

// Ask the backend for geometry without logging a bundle (connected=false path never "delivers").
let commGeoTimer = null;
function updateCommGeometry() {
    const off = Number(document.getElementById("commDayOffset")?.value || 0);
    const d = new Date(Date.now() + off * 86400000);
    const lbl = document.getElementById("commDateLabel");
    if (lbl) lbl.textContent = off === 0 ? "today" : `${d.toISOString().slice(0, 10)} (+${off} days)`;
    clearTimeout(commGeoTimer);
    commGeoTimer = setTimeout(async () => {
        try {
            const res = await fetch("/api/network/telemetry", {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: "geometry probe", connected: state.dtnConnected, day_offset: off, probe: true })
            });
            const data = await res.json();
            renderCommGeometry(data);
            const desc = document.getElementById("linkDesc");
            if (desc && data.status === "SOLAR_CONJUNCTION_BLACKOUT") {
                desc.className = "link-desc text-red";
                desc.textContent = `Solar conjunction: Mars only ${data.sun_angle_deg}° from the Sun — Earth link unusable, crew fully autonomous.`;
            } else if (desc && state.dtnConnected) {
                desc.className = "link-desc text-green";
                desc.textContent = "Direct RF line-of-sight to Earth DSN active.";
            }
        } catch (e) { /* offline local server: nothing to show */ }
    }, 120);
}

function clearCommLog() {
    document.getElementById("commLogStream").innerHTML = `<div class="log-entry sys">[SYSTEM] Log cleared. DTN ready.</div>`;
}

// ==========================================
// MODALS & RESERVATIONS
// ==========================================
function openNasaModal() {
    document.getElementById("nasaKeyModal").classList.remove("hidden");
}

function closeNasaModal() {
    document.getElementById("nasaKeyModal").classList.add("hidden");
}

async function saveNasaApiKey() {
    const key = document.getElementById("inputNasaKey").value.trim() || "DEMO_KEY";
    const feedback = document.getElementById("nasaKeyFeedback");

    feedback.classList.remove("hidden");
    feedback.textContent = "Verifying key with api.nasa.gov...";

    try {
        const res = await fetch("/api/nasa/config_key", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ api_key: key })
        });
        const data = await res.json();

        if (data.link) applyNasaStatus(data.link);
        if (data.online) {
            feedback.style.color = "var(--telemetry-green)";
            feedback.textContent = `✓ Key validated! Connected to ${data.service} (${data.sample_title})`;
            state.nasaApiKey = key;
            setTimeout(closeNasaModal, 1500);
        } else {
            feedback.style.color = "var(--mars-amber)";
            feedback.textContent = `⚠ ${data.message || data.error}`;
        }
    } catch (err) {
        feedback.style.color = "var(--telemetry-red)";
        feedback.textContent = "Error testing key connection.";
    }
}

let pendingReserveSiteId = null;

function openConfirmReserveModal(siteId) {
    const site = state.allSites.find(s => s.id === siteId);
    if (!site) return;
    pendingReserveSiteId = siteId;

    const crew = state.missionInputs.crew;
    const days = state.missionInputs.days;

    document.getElementById("confirmDetailsContent").innerHTML = `
        <p>You are authorizing a formal mission allocation for:</p>
        <div style="background:rgba(0,0,0,0.3); border:1px solid var(--border-color); padding:12px; border-radius:6px; margin:12px 0;">
            <strong style="color:var(--mars-orange);">${site.name} (${site.id})</strong><br>
            <span>Coordinates: ${fmtLatLon(site.lat, site.lon)}</span><br>
            <span>Assigned Crew Size: <strong>${crew} Astronauts</strong></span><br>
            <span>Mission Surface Duration: <strong>${days} Sols</strong></span>
        </div>
        <p style="font-size:0.78rem; color:var(--text-muted);">
            This record will be saved directly into the ASTREON SQLite database (astreon.db) with authorization timestamp.
        </p>
    `;
    document.getElementById("confirmReserveModal").classList.remove("hidden");
}

function closeConfirmModal() {
    document.getElementById("confirmReserveModal").classList.add("hidden");
}

async function executeReservation() {
    if (!pendingReserveSiteId) return;

    try {
        const res = await fetch("/api/reserve", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                site_id: pendingReserveSiteId,
                crew: state.missionInputs.crew,
                duration: state.missionInputs.days,
                food_kg: 500,
                ration_kcal: 2800
            })
        });

        const data = await res.json();
        closeConfirmModal();
        alert(`✓ Settlement Authorized!\nMission ID: ${data.mission_id}\nSite: ${data.site_name}\nCrew: ${data.crew}`);
        openReservationsModal();
    } catch (err) {
        alert("Failed to save reservation.");
    }
}

async function openReservationsModal() {
    document.getElementById("reservationsModal").classList.remove("hidden");
    const tbody = document.getElementById("reservationsTableBody");
    tbody.innerHTML = `<tr><td colspan="7">Loading reservations...</td></tr>`;

    try {
        const res = await fetch("/api/reservations");
        const list = await res.json();

        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">No reservations recorded yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = list.map(r => `
            <tr>
                <td><strong class="text-cyan">${r.mission_id}</strong></td>
                <td>${r.site_name} (${r.site_id})</td>
                <td>${r.crew}</td>
                <td>${r.duration} sols</td>
                <td>${r.ration_kcal} kcal</td>
                <td><span class="status-badge live" style="padding:2px 8px; font-size:0.68rem;">${r.status}</span></td>
                <td style="font-size:0.72rem; color:var(--text-muted);">${r.created_at}</td>
            </tr>
        `).join("");
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7">Failed to load reservations.</td></tr>`;
    }
}

function closeReservationsModal() {
    document.getElementById("reservationsModal").classList.add("hidden");
}

// ==========================================
// TAB 06: DOMINO ENGINE - MULTI-SOL COMPOUND CRISIS CASCADER
// ==========================================

function initCascadeSiteSelector() {
    const sel = document.getElementById("cascadeSiteSelect");
    if (!sel || !state.allSites) return;

    sel.innerHTML = state.allSites.map(s => `
        <option value="${s.id}" ${state.selectedSite && state.selectedSite.id === s.id ? 'selected' : ''}>
            ${s.name} (${fmtLatLon(s.lat, s.lon)}, ${(s.elevation_m/1000).toFixed(1)} km)
        </option>
    `).join("");
}

async function runCascadeSimulation() {
    const siteSelect = document.getElementById("cascadeSiteSelect");
    const siteId = siteSelect ? siteSelect.value : (state.selectedSite ? state.selectedSite.id : "MSA-001");

    const crew = parseInt(document.getElementById("cascadeCrewInput")?.value || 6, 10);
    const timeline = parseInt(document.getElementById("cascadeTimelineInput")?.value || 60, 10);
    const scenario = document.getElementById("cascadeScenarioSelect")?.value || "global_pede";
    const startSol = parseInt(document.getElementById("cascadeStartSolInput")?.value || 5, 10);
    const durSol = parseInt(document.getElementById("cascadeDurationInput")?.value || 35, 10);

    const hasNuclear = document.getElementById("toggleNuclear")?.checked || false;
    const hasCleaners = document.getElementById("toggleDustCleaners")?.checked || false;
    const hasShelter = document.getElementById("toggleShelter")?.checked ?? true;
    const hasGreenhouse = document.getElementById("toggleGreenhouse")?.checked ?? true;

    const rationingPolicy = document.getElementById("cascadeRationingSelect")?.value || "auto_adaptive";
    const batteryCap = parseFloat(document.getElementById("cascadeBatteryInput")?.value || 250);
    const foodKg = parseFloat(document.getElementById("cascadeFoodInput")?.value || 800);

    const payload = {
        site_id: siteId,
        crew_size: crew,
        timeline_sols: timeline,
        storm_scenario: scenario,
        storm_start_sol: startSol,
        storm_duration_sols: durSol,
        habitat: state.habitat,
        nuclear_backup_kw: (state.habitat ? Number(state.habitat.nuclear_kw) : 0) + (hasNuclear ? 10.0 : 0.0),
        dust_cleaners_active: hasCleaners,
        storm_shelter_active: hasShelter,
        greenhouse_enabled: hasGreenhouse,
        rationing_strategy: rationingPolicy,
        battery_capacity_kwh: batteryCap,
        initial_food_kg: foodKg
    };

    try {
        const res = await fetch("/api/cascade/simulate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!res.ok) throw new Error("Simulation endpoint error " + res.status);
        const data = await res.json();
        state.cascade.lastResult = data;

        renderCascadeSummary(data);
        renderCascadeCharts(data.timeline);
        setupCascadeScrubber(data.timeline);
        renderCascadeEvents(data.events);
        renderCascadeCountermeasures(data.countermeasures);
    } catch (err) {
        console.error("Cascade simulation failed:", err);
    }
}

function renderCascadeSummary(data) {
    if (!data || !data.summary) return;
    const s = data.summary;
    const r = data.runways || {};

    // Hero Runway Counter
    const valEl = document.getElementById("cascadeRunwayValue");
    if (valEl) {
        valEl.textContent = s.survival_runway_sols;
        valEl.style.color = s.badge_color || "#10b981";
    }

    const statusBadge = document.getElementById("cascadeRunwayStatus");
    if (statusBadge) {
        statusBadge.textContent = s.overall_status;
        statusBadge.style.color = s.badge_color || "#34d399";
        statusBadge.style.borderColor = s.badge_color || "rgba(16, 185, 129, 0.4)";
    }

    const bottleneckText = document.getElementById("cascadeBottleneckText");
    if (bottleneckText) {
        bottleneckText.textContent = s.limiting_bottleneck.replace(/_/g, " ");
        if (s.limiting_bottleneck.includes("NONE")) {
            bottleneckText.style.color = "#34d399";
        } else {
            bottleneckText.style.color = "#ef4444";
        }
    }

    // (Top-bar runway pill now follows Crisis Mode for the current base.)

    // Subsystem Cards
    const cardPower = document.getElementById("cardPowerRunway");
    const cardPowerSub = document.getElementById("cardPowerStatus");
    if (cardPower) cardPower.textContent = `${s.min_battery_soc}% min SoC`;
    if (cardPowerSub) cardPowerSub.textContent = r.power ? r.power.status : `${s.total_blackout_sols} Blackout Sols`;

    const cardO2 = document.getElementById("cardO2Runway");
    const cardO2Sub = document.getElementById("cardO2Status");
    if (cardO2) cardO2.textContent = `${s.final_o2_kg} kg buffer`;
    if (cardO2Sub) cardO2Sub.textContent = r.oxygen ? r.oxygen.status : "Buffer Status";

    const cardWater = document.getElementById("cardWaterRunway");
    const cardWaterSub = document.getElementById("cardWaterStatus");
    if (cardWater) cardWater.textContent = `${Math.round(s.final_water_l).toLocaleString()} L`;
    if (cardWaterSub) cardWaterSub.textContent = r.water ? r.water.status : "ISRU & Recycle";

    const cardFood = document.getElementById("cardFoodRunway");
    const cardWeight = document.getElementById("cardWeightLoss");
    if (cardFood) cardFood.textContent = `${Math.round(s.final_food_kg)} kg left`;
    if (cardWeight) cardWeight.textContent = `${s.max_weight_loss_pct}% max loss`;

    const cardRad = document.getElementById("cardRadRunway");
    const cardRadLimit = document.getElementById("cardRadLimit");
    if (cardRad) cardRad.textContent = `${s.cumulative_radiation_msv} mSv`;
    if (cardRadLimit && r.radiation) cardRadLimit.textContent = `${r.radiation.pct_of_30day_limit}% of 30d Limit`;
}

function renderCascadeCharts(timeline) {
    if (!timeline || timeline.length === 0) return;
    const labels = timeline.map(t => `Sol ${t.sol}`);

    // 1. Chart Cascade Power
    const ctxPower = document.getElementById("chartCascadePower");
    if (ctxPower) {
        if (state.charts.cascadePower) state.charts.cascadePower.destroy();
        state.charts.cascadePower = new Chart(ctxPower, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Available Energy (kWh/sol)",
                        data: timeline.map(t => t.total_available_kwh),
                        borderColor: "#00e5ff",
                        backgroundColor: "rgba(0, 229, 255, 0.08)",
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y"
                    },
                    {
                        label: "Actual Energy Demand (kWh/sol)",
                        data: timeline.map(t => t.actual_demand_kwh),
                        borderColor: "#ff7849",
                        borderWidth: 2,
                        borderDash: [4, 4],
                        tension: 0.2,
                        yAxisID: "y"
                    },
                    {
                        label: "Battery SoC (%)",
                        data: timeline.map(t => t.battery_soc),
                        borderColor: "#10b981",
                        backgroundColor: "rgba(16, 185, 129, 0.12)",
                        fill: true,
                        borderWidth: 2.5,
                        tension: 0.2,
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } } },
                    tooltip: { backgroundColor: "rgba(14, 20, 32, 0.95)", titleColor: "#00e5ff" }
                },
                scales: {
                    x: { ticks: { color: "#6b7280", maxTicksLimit: 12 }, grid: { color: "rgba(255,255,255,0.04)" } },
                    y: {
                        position: "left",
                        title: { display: true, text: "Energy (kWh/sol)", color: "#9ca3af" },
                        ticks: { color: "#9ca3af" },
                        grid: { color: "rgba(255,255,255,0.04)" }
                    },
                    y1: {
                        position: "right",
                        min: 0,
                        max: 100,
                        title: { display: true, text: "Battery SoC (%)", color: "#10b981" },
                        ticks: { color: "#10b981", callback: v => v + "%" },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    // 2. Chart Cascade Resources
    const ctxRes = document.getElementById("chartCascadeResources");
    if (ctxRes) {
        if (state.charts.cascadeResources) state.charts.cascadeResources.destroy();
        state.charts.cascadeResources = new Chart(ctxRes, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Stored Water (L)",
                        data: timeline.map(t => t.water_stored_l),
                        borderColor: "#3b82f6",
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y"
                    },
                    {
                        label: "Oxygen Buffer (kg)",
                        data: timeline.map(t => t.o2_stored_kg),
                        borderColor: "#00e5ff",
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y1"
                    },
                    {
                        label: "Stored Food (kg)",
                        data: timeline.map(t => t.food_stored_kg),
                        borderColor: "#f59e0b",
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } } },
                    tooltip: { backgroundColor: "rgba(14, 20, 32, 0.95)" }
                },
                scales: {
                    x: { ticks: { color: "#6b7280", maxTicksLimit: 12 }, grid: { color: "rgba(255,255,255,0.04)" } },
                    y: {
                        position: "left",
                        title: { display: true, text: "Water (Liters)", color: "#3b82f6" },
                        ticks: { color: "#3b82f6" },
                        grid: { color: "rgba(255,255,255,0.04)" }
                    },
                    y1: {
                        position: "right",
                        title: { display: true, text: "O₂ Buffer & Food (kg)", color: "#00e5ff" },
                        ticks: { color: "#00e5ff" },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }

    // 3. Chart Cascade Physiology
    const ctxPhys = document.getElementById("chartCascadePhysiology");
    if (ctxPhys) {
        if (state.charts.cascadePhysiology) state.charts.cascadePhysiology.destroy();
        state.charts.cascadePhysiology = new Chart(ctxPhys, {
            type: "line",
            data: {
                labels: labels,
                datasets: [
                    {
                        label: "Daily Intake (kcal/person)",
                        data: timeline.map(t => t.daily_kcal_per_person),
                        borderColor: "#ff7849",
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y"
                    },
                    {
                        label: "Cumulative Radiation (mSv)",
                        data: timeline.map(t => t.cumulative_rad_msv),
                        borderColor: "#ec4899",
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y1"
                    },
                    {
                        label: "Crew Body Mass Loss (%)",
                        data: timeline.map(t => t.weight_loss_pct),
                        borderColor: "#ef4444",
                        borderDash: [5, 5],
                        borderWidth: 2,
                        tension: 0.2,
                        yAxisID: "y1"
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { labels: { color: "#9ca3af", font: { family: "Inter", size: 11 } } },
                    tooltip: { backgroundColor: "rgba(14, 20, 32, 0.95)" }
                },
                scales: {
                    x: { ticks: { color: "#6b7280", maxTicksLimit: 12 }, grid: { color: "rgba(255,255,255,0.04)" } },
                    y: {
                        position: "left",
                        title: { display: true, text: "Caloric Intake (kcal)", color: "#ff7849" },
                        ticks: { color: "#ff7849" },
                        grid: { color: "rgba(255,255,255,0.04)" }
                    },
                    y1: {
                        position: "right",
                        title: { display: true, text: "Rad (mSv) & Weight Loss (%)", color: "#ec4899" },
                        ticks: { color: "#ec4899" },
                        grid: { drawOnChartArea: false }
                    }
                }
            }
        });
    }
}

function setupCascadeScrubber(timeline) {
    const slider = document.getElementById("cascadeSolSlider");
    if (!slider || !timeline || timeline.length === 0) return;

    slider.max = timeline.length;
    slider.value = 1;

    const maxTick = document.getElementById("scrubberMaxTick");
    if (maxTick) maxTick.textContent = `Sol ${timeline.length}`;
    const midTick = document.getElementById("scrubberMidTick");
    if (midTick) midTick.textContent = `Sol ${Math.round(timeline.length / 2)}`;

    onCascadeSolScrub(1);
}

function onCascadeSolScrub(solNum) {
    const solIdx = parseInt(solNum, 10) - 1;
    if (!state.cascade.lastResult || !state.cascade.lastResult.timeline) return;
    const sol = state.cascade.lastResult.timeline[solIdx];
    if (!sol) return;

    state.cascade.scrubbedSol = solNum;

    const lbl = document.getElementById("scrubberSolLabel");
    if (lbl) lbl.textContent = `Sol ${sol.sol}`;

    const tierBadge = document.getElementById("scrubberTierBadge");
    if (tierBadge) {
        tierBadge.className = `tier-pill tier-${sol.power_tier}`;
        tierBadge.textContent = sol.power_tier_label;
    }

    const setT = (id, text) => {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    };

    setT("hudTau", sol.tau.toFixed(2));
    setT("hudPowerAvail", `${Math.round(sol.total_available_kwh)} kWh`);
    setT("hudBatterySoc", `${sol.battery_soc}%`);
    setT("hudWater", `${Math.round(sol.water_stored_l).toLocaleString()} L`);
    setT("hudO2", `${sol.o2_stored_kg} kg`);
    setT("hudKcal", `${sol.daily_kcal_per_person} kcal`);
    setT("hudWeight", `${sol.weight_loss_pct}%`);
    setT("hudRad", `${sol.cumulative_rad_msv} mSv`);
}

function renderCascadeEvents(events) {
    const container = document.getElementById("cascadeEventsList");
    const countBadge = document.getElementById("eventsCountBadge");
    if (!container) return;

    if (countBadge) countBadge.textContent = `${events ? events.length : 0} Events`;

    if (!events || events.length === 0) {
        container.innerHTML = `<div style="color:var(--text-muted); font-size:0.8rem; padding:12px;">No anomalous cascade events triggered. All systems sustained nominally.</div>`;
        return;
    }

    container.innerHTML = events.map(e => {
        const sevClass = e.severity === 'FATAL' ? 'event-fatal' : (e.severity === 'CRITICAL' ? 'event-critical' : 'event-warning');
        return `
            <div class="cascade-event-card ${sevClass}">
                <div class="event-meta-row">
                    <span class="event-sol-badge">SOL ${e.sol}</span>
                    <span class="event-subsystem-tag">${e.subsystem} • ${e.severity}</span>
                </div>
                <div class="event-card-title">${e.title}</div>
                <div class="event-card-directive">${e.directive}</div>
            </div>
        `;
    }).join("");
}

function renderCascadeCountermeasures(cms) {
    const container = document.getElementById("countermeasuresList");
    if (!container || !cms) return;
    const base = state.cascade.lastResult && state.cascade.lastResult.countermeasure_baseline;
    const fmt = (o) => o.survives ? `${o.timeline}+ sols` : `${o.runway_sols} sols`;
    container.innerHTML = (base ? `<div class="cm-baseline">Baseline (as configured): <strong>${fmt(base)}</strong>, ${base.blackout_sols} blackout sols, battery floor ${base.min_soc}%</div>` : "") +
        cms.map(cm => {
            const gain = cm.runway_gain_sols;
            const impact = gain > 0 ? `+${gain} sols survival runway`
                : cm.blackout_sols_saved > 0 ? `${cm.blackout_sols_saved} fewer blackout sols`
                : cm.min_soc_gain > 0 ? `battery floor +${cm.min_soc_gain} pts`
                : gain < 0 ? `${gain} sols (worse)` : "no measurable change in this scenario";
            return `
            <div class="cm-card ${gain > 0 ? "cm-good" : gain < 0 ? "cm-bad" : ""}">
                <div class="cm-card-head">${cm.title}${cm.kind === "hardware" ? ' <span class="badge-micro">design change</span>' : ""}</div>
                <div class="cm-card-impact">Re-simulated: ${impact} → ${fmt(cm)}</div>
                <div class="cm-card-tradeoff">${cm.note}</div>
            </div>`;
        }).join("");
}

function launchCascadeFromMonitor() {
    const monSite = document.getElementById("monitorSiteSelect")?.value;
    const casSite = document.getElementById("cascadeSiteSelect");
    if (monSite && casSite) casSite.value = monSite;

    const monScen = document.getElementById("monitorScenarioSelect")?.value;
    const casScen = document.getElementById("cascadeScenarioSelect");
    if (monScen && casScen) {
        const scenMap = { "clear": "none", "regional": "regional", "global_pede": "global_pede", "winter_haze": "regional" };
        casScen.value = scenMap[monScen] || "global_pede";
    }

    switchTab("tab-cascade");
    runCascadeSimulation();
}

function launchCascadeFromFood() {
    // (IDs previously pointed at non-existent inputs, so this link silently did nothing.)
    const foodCrew = document.getElementById("foodCrew")?.value;
    const casCrew = document.getElementById("cascadeCrewInput");
    if (foodCrew && casCrew) casCrew.value = foodCrew;

    const foodExt = document.getElementById("foodExtendedDays")?.value;
    const casTimeline = document.getElementById("cascadeTimelineInput");
    if (foodExt && casTimeline) casTimeline.value = Math.min(180, Math.max(15, Number(foodExt)));

    const foodStock = document.getElementById("foodRemainingKg")?.value;
    const casFood = document.getElementById("cascadeFoodInput");
    if (foodStock && casFood) casFood.value = foodStock;

    switchTab("tab-cascade");
    runCascadeSimulation();
}

function exportCascadeBriefing() {
    if (!state.cascade.lastResult) {
        alert("Please run a simulation before exporting the briefing.");
        return;
    }
    window.print();
}
