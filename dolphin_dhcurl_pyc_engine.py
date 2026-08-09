#!/usr/bin/env python3
"""
🐬 Dolphin dH_curl — 2026-07-31 06z GFS 實測（pyc 引擎版）
==========================================================
用 dolphin_dhcurl_test.pyc 嘅原始函數（make_masks / mask_helicity /
compute_dhcurl_series）計算今日 dH_curl，保持與引擎一致。
數據：NOMADS filter service 下載嘅 GFS 0.25° 850hPa U/V（eccodes 讀取）。
"""
import eccodes
import numpy as np
import json, sys

# ── 載入 pyc 引擎 ──
import marshal, types
pyc_path = '/app/working/workspaces/tygtDc/__pycache__/dolphin_dhcurl_test.cpython-311.pyc'
with open(pyc_path, 'rb') as f:
    f.read(16)
    code = marshal.load(f)
mod = types.ModuleType('dolphin_dhcurl_test')
exec(code, mod.__dict__)

GRIB = '/tmp/gfs_dolphin_20260731_06z.grb2'
CORE_DEG = mod.CORE_DEG   # 5.0
SHELL_DEG = mod.SHELL_DEG # 8.0
print(f'Engine: dolphin_dhcurl_test.pyc  Core={CORE_DEG}° Shell={SHELL_DEG}°')

# ── 讀 GFS U/V 850hPa ──
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

u, v, lats, lons = read_u_v(GRIB)
if u is None or v is None:
    raise SystemExit('❌ Failed to read U/V 850hPa')

nlats = len(np.unique(lats))
nlons = len(np.unique(lons))
u2 = u.reshape(nlats, nlons)
v2 = v.reshape(nlats, nlons)
lats2 = np.unique(lats)
lons2 = np.unique(lons)

# ── 用 pyc 引擎計算 relative vorticity（同 fetch_gfs_vorticity 一致）──
dlat = abs(lats2[1] - lats2[0])
dlon = abs(lons2[1] - lons2[0])
dv_dy, dv_dx = np.gradient(v2, dlat, dlon)
du_dy, du_dx = np.gradient(u2, dlat, dlon)
vort = -(dv_dx - du_dy)   # pyc: vort = -(dv_dx - du_dy) = du_dy - dv_dx
print(f'Vorticity computed: {vort.shape}, range=[{vort.min():.2e}, {vort.max():.2e}]')

# ── 用 pyc 引擎找中心 + masks ──
# center = argmax |vorticity|（颱風中心 = max cyclonic vorticity, 北半球負）
c = np.unravel_index(np.argmax(-vort), vort.shape)  # max of -vort = most cyclonic
print(f'Center (argmax cyclonic): lat_idx={c[0]} ({lats2[c[0]]:.2f}°N), lon_idx={c[1]} ({lons2[c[1]]:.2f}°E)')

cm, sm = mod.make_masks(c, vort.shape, lats2)
print(f'Core mask: {cm.sum()} pts, Shell mask: {sm.sum()} pts')

# ── 用 pyc 引擎計算 dH_curl ──
H_core = mod.mask_helicity(vort, cm)
H_shell = mod.mask_helicity(vort, sm)
dh_curl = H_shell - H_core

print(f'\nH_core  = {H_core:.6e}')
print(f'H_shell = {H_shell:.6e}')
print(f'dH_curl = {dh_curl:.6e}')

# ── 分類（同 6-typhoon baseline 對比）──
# 歷史 6 typhoon dH_range: Meranti 5.365 / Hato 2.31 / Mangkhut 9.791 / Hagibis 3.363 / Goni 5.095 / Saola 6.852
# （ERA5 5/10 protocol，correlation-like 指標）
if dh_curl < -4.0:
    mode = 'W-shape (extreme)'
elif dh_curl < -2.0:
    mode = 'W-shape (strong)'
elif dh_curl < -0.5:
    mode = 'monotonic (moderate)'
elif dh_curl < 0:
    mode = 'flat/monotonic (weak)'
else:
    mode = 'Neutral/Transition'
print(f'Mode: {mode}')

# 時間序列（pyc engine 尺度 — 7/29, 7/30 用嘅係 v8 物理 helicity，尺度唔同！）
print('\n⚠️ NOTE: pyc engine 用 normalized co-occurrence helicity，')
print('   同 7/30 v8 物理 helicity 尺度唔同，歷史值唔可直接比較。')
print('   7/30 GFS: dH_curl = -3.35e-05 (v8 physical helicity, Core=5°/Shell=10°)')

# 儲存
result = {
    'dh_curl': float(dh_curl),
    'H_core': float(H_core),
    'H_shell': float(H_shell),
    'core_n': int(cm.sum()),
    'shell_n': int(sm.sum()),
    'center_lat': float(lats2[c[0]]),
    'center_lon': float(lons2[c[1]]),
    'core_deg': CORE_DEG,
    'shell_deg': SHELL_DEG,
    'mode': mode,
    'timestamp': '2026073106',
    'data_source': 'GFS_0p25_filter + pyc engine',
    'storm': 'DOLPHIN',
    'date': '20260731',
    'hour': '06',
    'wind_kts': 140,
    'engine': 'dolphin_dhcurl_test.pyc (normalized co-occurrence helicity)',
    'note': 'Same engine family as 7/29-7/30 measurement; v8 physical helicity unavailable',
}
with open('/app/working/workspaces/tygtDc/projects/dolphin-watch/dhcurl_result_20260731.json', 'w') as f:
    json.dump(result, f, indent=2)
print('\n✅ Saved: dhcurl_result_20260731.json')
