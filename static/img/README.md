# Bundled imagery

## mars_mola_2k.jpg
Colourised shaded-relief map of Mars, 2048 × 1024, simple cylindrical (equirectangular),
longitude −180°E (left) → +180°E (right), latitude +90° (top) → −90° (bottom).

- **Source data:** NASA Mars Global Surveyor, Mars Orbiter Laser Altimeter (MOLA) topography,
  via the spherical-harmonic shape model `MarsTopo719` distributed with SHTOOLS
  (Wieczorek & Meschede, 2018). Expanded to degree 719 (~15 km resolution).
- **Processing:** mean radius and the degree-2 zonal flattening term removed to approximate
  elevation above the areoid; hillshade (sun az 315°, alt 40°) multiplied over a
  MOLA-style elevation colour ramp (−8 km deep blue → +21 km white).
- **Elevation range in the image:** about −9 km (Hellas floor) to +21.5 km (Olympus Mons).
- Bundled locally so the map works with no network (the habitat's normal state).

Regenerate with `tools/render_mola.py` (needs `pyshtools`, `numpy`, `Pillow`).
