#!/usr/bin/env python3
"""
🐬 Dolphin dH_curl — 2026-07-31 06z GFS 實測
============================================
用 NOMADS filter service 下載 GFS 0.25° 850hPa U/V subset，
計算 dH_curl = H_shell − H_core（Core=5°, Shell=8° protocol，同 pyc 一致）
"""
import eccodes
import numpy as np
from scipy.ndimage import gaussian_filter
import json, os

GRIB = '/tmp/gfs_dolphin_20260731_06z.grb2'
CORE_DEG = 5.0
SHELL_DEG = 8.0
SIGMA = 0.0
ROLL_WIN = 12

def read_u_v(path):
    lats = lons = None
    u850 = v850 = None
    f = open(path, 'rb')
    while True:
        try:
            gid = eccodes.codes_grib_new_from_file(f)
        except Exception:
            break
        if gid is None:
            break
        try:
            name = eccodes.codes_get(gid, 'name')
            level = eccodes.codes_get(gid, 'level')
            vals = eccodes.codes_get_values(gid)
            if level == 850:
                if 'U' in name:
                    u850 = vals
                    lats = eccodes.codes_get_array(gid, 'latitudes')
                    lons = eccodes.codes_get_array(gid, 'longitudes')
                elif 'V' in name:
                    v850 = vals
        except Exception:
            pass
        finally:
            eccodes.codes_release(gid)
    f.close()
    return u850, v850, lats, lons

def gradmag2d(field, lats, lons):
    """Gradient magnitude of scalar field (per degree)."""
    dlat = abs(lats[1] - lats[0]) if len(lats) > 1 else 1.0
    dlon = abs(lons[1] - lons[0]) if len(lons) > 1 else 1.0
    gy, gx = np.gradient(field, dlat, dlon)
    return np.sqrt(gx**2 + gy**2)

def helicity(u, v, lats, lons):
    """H = curl(v) · ∇|v| — kinetic helicity proxy."""
    dlat = abs(lats[1] - lats[0]) if len(lats) > 1 else 1.0
    dlon = abs(lons[1] - lons[0]) if len(lons) > 1 else 1.0
    # relative vorticity ζ = dv/dx − du/dy (on lat/lon grid, degree-based)
    dvdx, dvdy = np.gradient(v, dlon, dlat)
    dudy, dudx = np.gradient(u, dlat, dlon)
    zeta = dvdx - dudy
    speed = np.sqrt(u**2 + v**2)
    gmag = gradmag2d(speed, lats, lons)
    return zeta * gmag

def make_masks(lats, lons, clat, clon, core_deg, shell_deg):
    """Core/shell masks from center."""
    lat2d, lon2d = np.meshgrid(lats, lons, indexing='ij')
    # handle lon wrap
    dlon = np.abs(lon2d - clon)
    dlon = np.minimum(dlon, 360 - dlon)
    dlat = np.abs(lat2d - clat)
    dist = np.sqrt(dlat**2 + dlon**2)
    core = dist <= core_deg
    shell = (dist > core_deg) & (dist <= shell_deg)
    return core, shell

def classify(dh_curl, u_strength=None):
    """Classify storm strength from dH_curl value."""
    # 參考: 6 typhoon dH_range 2.31-9.79 (ERA5, 5/10 protocol)
    # GFS 飽和平台約 -4.4e-05
    if dh_curl < -3.0e-05:
        return 'Super Typhoon (GFS saturated)'
    elif dh_curl < -1.5e-05:
        return 'TY/STS (deep)'
    elif dh_curl < -0.5e-05:
        return 'STS/TS (moderate)'
    elif dh_curl < 0:
        return 'TS (weak)'
    else:
        return 'Neutral/Transition'

# ─── Main ───
print('=== 🐬 Dolphin dH_curl — GFS 2026-07-31 06z ===')
print(f'Protocol: Core={CORE_DEG}°, Shell={SHELL_DEG}°')
print(f'Center: 16.9°N, 164.9°E (JTWC 140 kts)')

u, v, lats, lons = read_u_v(GRIB)
if u is None or v is None:
    raise SystemExit('❌ Failed to read U/V 850hPa')

# 組織成 2D grid
nlats = len(np.unique(lats))
nlons = len(np.unique(lons))
print(f'Grid: {nlats} lats × {nlons} lons = {nlats*nlons}')

u2 = u.reshape(nlats, nlons)
v2 = v.reshape(nlats, nlons)
lats2 = np.unique(lats)
lons2 = np.unique(lons)

clat, clon = 16.9, 164.9
core, shell = make_masks(lats2, lons2, clat, clon, CORE_DEG, SHELL_DEG)
print(f'Core mask: {core.sum()} pts, Shell mask: {shell.sum()} pts')

# Helicity field (optional smoothing)
H = helicity(u2, v2, lats2, lons2)
if SIGMA > 0:
    H = gaussian_filter(H, sigma=SIGMA)

# H_core / H_shell
H_core = float(np.mean(H[core]))
H_shell = float(np.mean(H[shell]))
dh_curl = H_shell - H_core

print(f'\nH_core  = {H_core:.6e}  (n={core.sum()})')
print(f'H_shell = {H_shell:.6e}  (n={shell.sum()})')
print(f'dH_curl = {dh_curl:.6e} s⁻¹')
print(f'分類: {classify(dh_curl)}')

# 時間序列對比
history = [
    ('2026-07-24 12Z', 'ERA5', 'TS (55 kts)', -9.51e-06),
    ('2026-07-25 06Z', 'ERA5', 'TS', 8.47e-06),
    ('2026-07-26 06Z', 'ERA5', 'TS', 4.22e-06),
    ('2026-07-29 06Z', 'GFS', 'STS/TY (~85 kts)', -2.40e-05),
    ('2026-07-30 00Z', 'GFS', 'Super TY (~130 kts)', -3.35e-05),
    ('2026-07-31 06Z', 'GFS', 'Super TY (140 kts)', dh_curl),
]
print('\n時間序列:')
print(f'{"日期":<22s} {"源":<6s} {"強度":<22s} {"dH_curl":>12s}')
for d, src, s, v in history:
    print(f'{d:<22s} {src:<6s} {s:<22s} {v:12.2e}')

# Save result
result = {
    'dh_curl': dh_curl,
    'H_core': H_core,
    'H_shell': H_shell,
    'core_n': int(core.sum()),
    'shell_n': int(shell.sum()),
    'center_lat': clat,
    'center_lon': clon,
    'core_deg': CORE_DEG,
    'shell_deg': SHELL_DEG,
    'mode': classify(dh_curl),
    'timestamp': '2026073106',
    'data_source': 'GFS_0p25_filter',
    'storm': 'DOLPHIN',
    'date': '20260731',
    'hour': '06',
    'wind_kts': 140,
}
with open('/app/working/workspaces/tygtDc/projects/dolphin-watch/dhcurl_result_20260731.json', 'w') as f:
    json.dump(result, f, indent=2)
print('\n✅ Saved: dhcurl_result_20260731.json')
