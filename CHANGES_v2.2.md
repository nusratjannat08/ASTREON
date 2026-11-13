# ASTREON v2.2 — fix pass (12 Nov 2026)

## UI review items (all fixed)
| Issue | Fix |
|---|---|
| Map tab empty, markers bunched in the middle | Leaflet is re-measured and re-fitted every time the tab opens (it was built while hidden, at 0×0). Real MOLA shaded-relief basemap bundled at `static/img/mars_mola_2k.jpg` (see `static/img/README.md`), 30° graticule, labelled markers, correct N/S/E/W coordinates. |
| "NASA API: CONNECTED" hardcoded | New `/api/nasa/status`. Badge shows **LIVE / CACHED / OFFLINE MODEL**, re-checks every 5 min, click to force. Real NASA responses are saved to `data/nasa_cache.json` so CACHED is genuine after a restart. |
| Food tab: 5,470 kcal labelled "Nominal" | Ration is capped at the 2,800 kcal nominal; the surplus is reported as reserve kg and extra sols. Phases no longer spend more food than exists. Weight-loss projection capped at 40% with a "sol when 18% loss is crossed" warning. Input limits enforced server-side. |
| Unstyled white dropdowns in the Domino tab | Global dark `select` style, `.form-group-block` styling, no overflow. |
| Offline leaks (Google Fonts, rover photos, CDN fallbacks) | Inter / JetBrains Mono / Orbitron bundled (`static/vendor/fonts`, SIL OFL). CDN fallbacks removed. Rover cards show "Cached image unavailable" when offline. |
| 91.2% overlapping the TOP RECOMMENDATION badge | Badge moved into normal flow. |
| Tabs 07/08 cut off | Tab bar wraps. |
| Phone overflow | Responsive rules; verified no horizontal overflow at 390, 820, 1280 and 1440 px. |

## Additional bugs found and fixed
- **"Model full cascade with these rations"** button did nothing: it read non-existent input IDs. Now it carries crew, duration and stockpile into the Domino tab.
- **Greenhouse yield of 0** was silently replaced by 1.5 kg/day.
- **Top-bar "SOL TIME"** was UTC wrapped at 88,775 s. Now real Coordinated Mars Time (Allison & McEwen / Mars24 formula).
- **DTN latency** used `|r_mars − 1 AU| + 0.3` and placed "solar conjunction" at Ls 240–260 (a Mars season, physically unrelated). Now computed from JPL Keplerian elements for any date; validated against the Aug-2003 close approach (0.373 AU), Oct-2021 conjunction and Jan-2025 opposition. Date slider added.
- Weather panel no longer calls itself "NASA LIVE" when showing fallback values; it states that InSight's feed is archival (mission ended 2022).
- Rover-photo endpoint validates `rover` and `sol`.
