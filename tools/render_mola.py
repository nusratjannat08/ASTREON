"""Render a colorised MOLA shaded-relief basemap (equirectangular, lon -180..180, lat 90..-90)
from the MGS/MOLA spherical-harmonic shape model MarsTopo719 (SHTOOLS / Wieczorek).
Usage: python render_mola.py MarsTopo719.shape out.jpg
"""
import sys
import numpy as np
import pyshtools as pysh
from PIL import Image

src, out = sys.argv[1], sys.argv[2]
clm = pysh.SHCoeffs.from_file(src, lmax=719, format="shtools")
# Remove the mean radius and the rotational flattening term so values approximate MOLA
# elevations relative to the areoid (the 2,0 term dominates both shape and areoid flattening).
clm.coeffs[0, 0, 0] = 0.0
clm.coeffs[0, 2, 0] = 0.0
grid = clm.expand(grid="DH2", extend=False).to_array() / 1000.0  # km, lat 90 -> -90, lon 0 -> 360
grid = np.roll(grid, grid.shape[1] // 2, axis=1)  # lon -180 -> 180
grid -= np.median(grid) + 1.5  # median MOLA elevation is roughly -1.5 km
print("elev range km:", grid.min().round(1), grid.max().round(1), grid.shape)

# Hillshade
gy, gx = np.gradient(grid)
az, alt = np.radians(315), np.radians(40)
slope = np.arctan(6.0 * np.hypot(gx, gy))
aspect = np.arctan2(-gx, gy)
shade = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)
shade = np.clip(shade, 0, 1)

# Classic MOLA-style elevation ramp (km -> RGB)
stops = np.array([-8, -5, -3, -1, 1, 3, 6, 10, 21], float)
cols = np.array([
    [40, 0, 110], [20, 60, 200], [30, 160, 220], [60, 190, 110], [190, 210, 70],
    [230, 170, 50], [200, 90, 50], [160, 110, 100], [250, 250, 250]], float)
e = np.clip(grid, stops[0], stops[-1])
rgb = np.stack([np.interp(e, stops, cols[:, i]) for i in range(3)], axis=-1)
rgb = rgb * (0.45 + 0.65 * shade[..., None])
# Mute it slightly so it sits well under the dark HUD theme
rgb = rgb * 0.82
img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).resize((2048, 1024), Image.LANCZOS)
img.save(out, quality=84, optimize=True, progressive=True)
print("saved", out)
