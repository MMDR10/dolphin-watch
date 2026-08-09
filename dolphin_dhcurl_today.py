#!/usr/bin/env python3
"""
🐬 Dolphin dH_curl — 2026-07-31 實測（恢復 GFS 引擎）
=====================================================
用 dolphin_dhcurl_test.pyc 恢復嘅 GFS 引擎函數，測今日最新 cycle。
Protocol: Core=5°, Shell=8°（pyc 內建值）
"""
import marshal, types, json, os, sys

# 載入 pyc module
pyc_path = '/app/working/workspaces/tygtDc/__pycache__/dolphin_dhcurl_test.cpython-311.pyc'
with open(pyc_path, 'rb') as f:
    f.read(16)
    code = marshal.load(f)

mod = types.ModuleType('dolphin_dhcurl_test')
mod.__dict__['__name__'] = 'dolphin_dhcurl_test'
exec(code, mod.__dict__)

print('=== Dolphin dH_curl — 2026-07-31 real-time measurement ===')
print(f'CORE_DEG={mod.CORE_DEG}, SHELL_DEG={mod.SHELL_DEG}, SIGMA={mod.SIGMA}, ROLL_WIN={mod.ROLL_WIN}')

# [1/4] Get latest position
print('\n[1/4] Getting Dolphin position...')
lat, lon, wind = mod.get_latest_dolphin_position()
print(f'  🐬 DOLPHIN @ {lat:.1f}°N, {lon:.1f}°E — {wind} kts')

# [2/4] Determine GFS cycle
print('\n[2/4] Determining GFS cycle...')
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)
h = now.hour
latest_cycle = (h // 6) * 6
if latest_cycle < 0:
    latest_cycle = 0
hour_str = f'{latest_cycle:02d}'
date_str = now.strftime('%Y%m%d')
if h < 3:
    yesterday = now - timedelta(days=1)
    date_str = yesterday.strftime('%Y%m%d')
    hour_str = '18'
print(f'  GFS cycle: {date_str} {hour_str}z')
print(f'  Center: {lat:.1f}°N, {lon:.1f}°E ±{mod.BOX_PAD}° box')

# [3/4] Fetch GFS vorticity
print('\n[3/4] Fetching GFS 0.25° 850hPa...')
try:
    u, v, grid = mod.fetch_gfs_vorticity(date_str, hour_str, lat, lon)
    print(f'  ✅ GFS data fetched: u={u.shape}, v={v.shape}')
    print(f'  grid: lats={grid.get("lats")[:3]}... lons={grid.get("lons")[:3]}...' if isinstance(grid, dict) else f'  grid: {type(grid)}')
except Exception as e:
    print(f'  ❌ GFS fetch failed: {e}')
    sys.exit(1)

# [4/4] Compute dH_curl series
print('\n[4/4] Computing dH_curl series...')
try:
    series = mod.compute_dhcurl_series(u, v, grid, lat, lon)
    print(f'  series type: {type(series)}')
    if isinstance(series, dict):
        for k, v in series.items():
            if isinstance(v, (int, float, str)):
                print(f'  {k}: {v}')
            elif hasattr(v, '__len__') and not isinstance(v, (str, bytes)):
                print(f'  {k}: {v}')
            else:
                print(f'  {k}: {v}')
    elif hasattr(series, 'to_dict'):
        print(json.dumps(series.to_dict() if hasattr(series, 'to_dict') else series, indent=1, default=str)[:2000])
    else:
        print(series)
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f'  ❌ compute failed: {e}')
