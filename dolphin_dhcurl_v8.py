#!/usr/bin/env python3
"""
🐬 Dolphin dH_curl Real-time Test — v8 FINAL
==============================================
GFS 850hPa dH_curl core=5°/shell=8° 實時計算 — 完全本地物理算子

引擎（自動選擇按可用性）：
  [A] cfgrib + xarray   ✅ 最穩陣（conda install -c conda-forge cfgrib xarray）
  [B] Open-Meteo API     ✅ 零依賴，直接 HTTP JSON（免安裝）
  [C] eccodes            ✅ 次選

核心公式（與 ERA5 Backtest 一致）：
  dH_curl = H_shell(ζ) − H_core(ζ)
  🔴 負數 → 組織化結構（已發展颱風）
  🟢 正數 → 發散結構（genesis 中）

Usage:
  python dolphin_dhcurl_v8.py --date 20260729 --hour 00    # 自動下載 + 計算
  python dolphin_dhcurl_v8.py --mode openmeteo              # 用 Open-Meteo API
  python dolphin_dhcurl_v8.py --lat 15.4 --lon 166.6        # 指定中心位置
  python dolphin_dhcurl_v8.py --grib subset.grib2           # 用已下載檔案
"""

import sys, json, argparse, math, os, struct, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

CORE_DEG = 5.0
SHELL_DEG = 8.0
DOMAIN_PAD = 40.0  # 擴大到 40° 覆蓋成個西太平洋（108-188°E）


# ══════════════════════════════════════════════════════════════
# ENGINE A: cfgrib + xarray  (MOST ROBUST)
# ══════════════════════════════════════════════════════════════
def read_cfgrib(grib_path, level=850):
    try:
        import xarray as xr
        import cfgrib
    except ImportError:
        return None, "cfgrib/xarray 未安裝 — pip install cfgrib xarray"
    try:
        ds = xr.open_dataset(grib_path, engine='cfgrib',
            backend_kwargs={'filter_by_keys': {'typeOfLevel': 'isobaricInhPa', 'level': level}})
        u, v = ds['u'].values, ds['v'].values
        lat, lon = ds['latitude'].values, ds['longitude'].values
        grid = {
            'Ni': len(lon), 'Nj': len(lat),
            'lat1': float(lat[0]), 'lat2': float(lat[-1]),
            'lon1': float(lon[0]), 'lon2': float(lon[-1]),
            'di': float(abs(lon[1]-lon[0])), 'dj': float(abs(lat[1]-lat[0])),
        }
        if u.ndim == 3: u, v = u[0], v[0]
        ds.close()
        return {'u': u, 'v': v, 'grid': grid}, None
    except Exception as e:
        return None, f"cfgrib 錯誤: {e}"


# ══════════════════════════════════════════════════════════════
# ENGINE B: Open-Meteo Historical Weather API  (NO GRIB2!)
# ══════════════════════════════════════════════════════════════
def fetch_openmeteo(center_lat, center_lon, date_str, hour_str):
    """
    用 Open-Meteo API 直接拎 850hPa 風場數據。
    回傳 JSON，唔使同 GRIB2 糾纏。
    """
    # Open-Meteo 用 0.25° 網格，同 GFS 一樣
    lat_min = center_lat - DOMAIN_PAD
    lat_max = center_lat + DOMAIN_PAD
    lon_min = center_lon - DOMAIN_PAD
    lon_max = center_lon + DOMAIN_PAD

    # 構建時間範圍：用指定日期嘅前後1日
    dt = datetime.strptime(f"{date_str} {hour_str}", "%Y%m%d %H")
    start = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
    end = (dt + timedelta(days=1)).strftime("%Y-%m-%d")

    # Open-Meteo API 要點：每 0.25° 格點逐個查太慢
    # 改用 ERA5 0.25° 格點數據，單點下載成個區域
    # 但 Open-Meteo 免費 API 有限制，每次最多 1000 點

    # Open-Meteo 嘅 Gridded ERA5 API
    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={center_lat}&longitude={center_lon}"
        f"&start_date={start}&end_date={end}"
        f"&hourly=u_component_of_wind_850hPa,v_component_of_wind_850hPa"
        f"&timezone=UTC"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "dolphin-dhcurl/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return None, f"Open-Meteo API 失敗: {e}"

    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    u_arr = hourly.get('u_component_of_wind_850hPa', [])
    v_arr = hourly.get('v_component_of_wind_850hPa', [])

    if not times or not u_arr:
        return None, "Open-Meteo 回傳空數據"

    # 只拎單點——對颱風中心做 volumetric 分析係唔夠嘅
    # 但可以粗略睇下 helicity 趨勢
    target = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{hour_str}:00"
    try:
        idx = times.index(target)
    except ValueError:
        idx = len(times) // 2  # fallback 去中間點

    u, v = u_arr[idx], v_arr[idx]
    if u is None or v is None:
        return None, f"無數據 for {target}"

    print(f"  Open-Meteo: 單點 ({center_lat}, {center_lon}) U={u:.2f} V={v:.2f}")

    # Open-Meteo 單點只夠做 scalar analysis，做唔到 dH_curl
    # 回傳單點數據，主程式會提示改用 cfgrib
    return {
        'u': np.array([[u]]),
        'v': np.array([[v]]),
        'grid': {
            'Ni': 1, 'Nj': 1,
            'lat1': center_lat, 'lat2': center_lat,
            'lon1': center_lon, 'lon2': center_lon,
            'di': 0.25, 'dj': 0.25,
        },
        '_openmeteo_single_point': True,
    }, None


def fetch_openmeteo_grid(center_lat, center_lon, date_str, hour_str, grid_size=7):
    """
    Open-Meteo batch API：用單一 request 拎晒成個 grid 嘅 850hPa wind。
    因為 API 唔直接提供 U/V components 850hPa，改用 wind_speed + wind_direction
    然後轉換為 U/V 分量。

    Open-Meteo 支援 lat/lon arrays → 一次性 batch 所有格點。
    """
    dt = datetime.strptime(f"{date_str} {hour_str}", "%Y%m%d %H")
    target = dt.strftime("%Y-%m-%dT%H:00")
    half = (grid_size - 1) // 2

    # 構建 grid：先固定 lat，變換 lon（row-major order）
    lats = []
    lons = []
    for i in range(-half, half + 1):
        for j in range(-half, half + 1):
            lats.append(center_lat + i * 0.25)
            lons.append(center_lon + j * 0.25)

    lat_str = ",".join(f"{l:.4f}" for l in lats)
    lon_str = ",".join(f"{l:.4f}" for l in lons)

    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat_str}&longitude={lon_str}"
        f"&start_date={dt.strftime('%Y-%m-%d')}&end_date={dt.strftime('%Y-%m-%d')}"
        f"&hourly=wind_speed_850hPa,wind_direction_850hPa"
        f"&timezone=UTC"
    )

    req = urllib.request.Request(url, headers={"User-Agent": "dolphin-dhcurl/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        return None, f"Open-Meteo batch API 失敗: {e}"

    if 'error' in data:
        return None, f"Open-Meteo error: {data.get('reason','')}"

    hourly = data.get('hourly', {})
    times = hourly.get('time', [])
    speeds = hourly.get('wind_speed_850hPa', [])
    dirs = hourly.get('wind_direction_850hPa', [])

    if not speeds or not dirs:
        return None, "Open-Meteo 回傳空數據"

    # Find target time index
    try:
        idx = times.index(target)
    except ValueError:
        idx = len(times) // 2

    n_pts = len(speeds)
    if n_pts < 4:
        return None, f"太少格點: {n_pts}"

    # Convert speed (km/h) + direction (°met) → U/V (m/s)
    # Wind direction: meteorological convention (0°=from N, 90°=from E)
    # u = -speed * sin(dir_rad), v = -speed * cos(dir_rad)
    u_1d = np.zeros(n_pts)
    v_1d = np.zeros(n_pts)
    valid_mask = np.ones(n_pts, dtype=bool)

    for i in range(n_pts):
        spd = speeds[i][idx] if isinstance(speeds[i], list) else speeds[i]
        d = dirs[i][idx] if isinstance(dirs[i], list) else dirs[i]
        if spd is None or d is None:
            valid_mask[i] = False
            continue
        spd_ms = spd / 3.6  # km/h → m/s
        d_rad = math.radians(d)
        u_1d[i] = -spd_ms * math.sin(d_rad)
        v_1d[i] = -spd_ms * math.cos(d_rad)

    if not valid_mask.any():
        return None, "所有格點無效"

    # Reshape to 2D grid (row-major: lat fixed, lon varies)
    u_grid = u_1d.reshape(grid_size, grid_size)
    v_grid = v_1d.reshape(grid_size, grid_size)

    lat_vals = np.array([center_lat + i * 0.25 for i in range(-half, half + 1)])
    lon_vals = np.array([center_lon + j * 0.25 for j in range(-half, half + 1)])

    return {
        'u': u_grid, 'v': v_grid,
        'grid': {
            'Ni': grid_size, 'Nj': grid_size,
            'lat1': float(lat_vals[0]), 'lat2': float(lat_vals[-1]),
            'lon1': float(lon_vals[0]), 'lon2': float(lon_vals[-1]),
            'di': 0.25, 'dj': 0.25,
        },
    }, None

    print(f"  Open-Meteo grid: {grid_size}×{grid_size} points @ 0.25°")

    return {
        'u': u_grid,
        'v': v_grid,
        'grid': {
            'Ni': len(lons), 'Nj': len(lats),
            'lat1': lats[0], 'lat2': lats[-1],
            'lon1': lons[0], 'lon2': lons[-1],
            'di': 0.25, 'dj': 0.25,
        },
    }, None


# ══════════════════════════════════════════════════════════════
# ENGINE C: eccodes Python bindings
# ══════════════════════════════════════════════════════════════
def read_eccodes(grib_path, level=850):
    try:
        import eccodes as ec
    except ImportError:
        return None, "eccodes 未安裝 — pip install eccodes"

    fields = {}
    try:
        with open(grib_path, 'rb') as f:
            while True:
                try:
                    iid = ec.codes_grib_new_from_file(f)
                    if iid is None: break
                    sn = ec.codes_get(iid, 'shortName')
                    if sn in ('u', 'v') and ec.codes_get(iid, 'level') == level:
                        ni = ec.codes_get(iid, 'Ni')
                        nj = ec.codes_get(iid, 'Nj')
                        vals = ec.codes_get_values(iid)
                        if sn not in fields:
                            fields[sn] = {
                                'values': np.array(vals, dtype=np.float32).reshape((nj, ni)),
                                'Ni': ni, 'Nj': nj,
                                'lat1': ec.codes_get(iid, 'latitudeOfFirstGridPointInDegrees'),
                                'lat2': ec.codes_get(iid, 'latitudeOfLastGridPointInDegrees'),
                                'lon1': ec.codes_get(iid, 'longitudeOfFirstGridPointInDegrees'),
                                'lon2': ec.codes_get(iid, 'longitudeOfLastGridPointInDegrees'),
                                'di': ec.codes_get(iid, 'iDirectionIncrementInDegrees'),
                                'dj': ec.codes_get(iid, 'jDirectionIncrementInDegrees'),
                            }
                    ec.codes_release(iid)
                except ec.NoMoreCodes:
                    break
    except Exception as e:
        return None, f"eccodes 錯誤: {e}"

    if 'u' not in fields or 'v' not in fields:
        return None, f"U/V@{level} 未找到"
    return {'u': fields['u']['values'], 'v': fields['v']['values'], 'grid': fields['u']}, None


# ══════════════════════════════════════════════════════════════
# COMPUTATION — 全部本地物理，唔需要任何 API
# ══════════════════════════════════════════════════════════════
def compute_vorticity(u, v, grid):
    """ζ = dv/dx − du/dy (s⁻¹)"""
    R = 6371000
    mid = math.radians((grid['lat1'] + grid['lat2']) / 2)
    dlon_m = grid['di'] * math.pi / 180 * R * math.cos(mid)
    dlat_m = grid['dj'] * math.pi / 180 * R
    return np.gradient(v, axis=1) / dlon_m - np.gradient(u, axis=0) / dlat_m


def find_center(zeta, grid, lat_hint=None, lon_hint=None):
    nj, ni = zeta.shape
    lats = np.linspace(grid['lat1'], grid['lat2'], nj)
    lons = np.linspace(grid['lon1'], grid['lon2'], ni)
    if lat_hint is not None and lon_hint is not None:
        lm = (lats >= lat_hint - 3) & (lats <= lat_hint + 3)
        lom = (lons >= lon_hint - 3) & (lons <= lon_hint + 3)
        if lm.any() and lom.any():
            zw = zeta[np.ix_(lm, lom)]
            ci, cj = np.unravel_index(np.argmax(np.abs(zw)), zw.shape)
            return float(lats[np.where(lm)[0][ci]]), float(lons[np.where(lom)[0][cj]])
    ci, cj = np.unravel_index(np.argmax(np.abs(zeta)), zeta.shape)
    return float(lats[ci]), float(lons[cj])


def compute_dh_curl(zeta, grid, core_deg=CORE_DEG, shell_deg=SHELL_DEG,
                    lat_hint=None, lon_hint=None, exact_center=False):
    """
    dH_curl = H_shell(ζ) − H_core(ζ)
    負值 → core 組織 > shell → 已發展颱風
    正值 → shell 組織 > core → genesis/發散

    exact_center=True → 直接用 lat_hint/lon_hint 做中心（跳過自動偵測）
    """
    nj, ni = zeta.shape
    lats = np.linspace(grid['lat1'], grid['lat2'], nj)
    lons = np.linspace(grid['lon1'], grid['lon2'], ni)
    if nj == 1 or ni == 1:
        return None  # need 2D grid

    if exact_center:
        lat_c, lon_c = lat_hint, lon_hint
        print(f"  中心: 使用 --lat/--lon 指定 ({lat_c:.2f}°N, {lon_c:.2f}°E)")
    else:
        lat_c, lon_c = find_center(zeta, grid, lat_hint, lon_hint)
        if lat_hint is not None:
            print(f"  中心: 自動偵測 @ {lat_c:.2f}°N, {lon_c:.2f}°E (hint: {lat_hint}°N, {lon_hint}°E)")
        else:
            print(f"  中心: 自動偵測 @ {lat_c:.2f}°N, {lon_c:.2f}°E")

    # Haversine distance
    r = np.deg2rad(lats[:, None]), np.deg2rad(lons[None, :])
    rc = np.deg2rad(lat_c), np.deg2rad(lon_c)
    a = np.sin((r[0]-rc[0])/2)**2 + np.cos(rc[0])*np.cos(r[0])*np.sin((r[1]-rc[1])/2)**2
    d = 2 * 6371 * np.arcsin(np.sqrt(a))

    cm = d <= core_deg * 111.32
    sm = (d > core_deg * 111.32) & (d <= shell_deg * 111.32)
    if not cm.any() or not sm.any():
        return None

    Hc, Hs = float(np.mean(zeta[cm])), float(np.mean(zeta[sm]))
    return {
        'dh_curl': Hs - Hc,
        'H_core': Hc, 'H_shell': Hs,
        'core_n': int(cm.sum()), 'shell_n': int(sm.sum()),
        'center_lat': lat_c, 'center_lon': lon_c,
        'core_deg': core_deg, 'shell_deg': shell_deg,
    }


def classify_mode(dh):
    if dh < -0.3: return "🟠 Monotonic (持續增強)"
    if dh > 0.3: return "🟢 W-shape (genesis)"
    return "⚪ Neutral/Transitional"


# ══════════════════════════════════════════════════════════════
# GFS DOWNLOAD via NOMADS HTTP (NO OPeNDAP SSL)
# ══════════════════════════════════════════════════════════════
def download_gfs_subset(date_str, hour_str, center_lat, center_lon, out_path):
    lat_min = center_lat - DOMAIN_PAD
    lat_max = center_lat + DOMAIN_PAD
    lon_min = center_lon - DOMAIN_PAD
    lon_max = center_lon + DOMAIN_PAD

    url = (
        f"https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
        f"?dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
        f"&file=gfs.t{hour_str}z.pgrb2.0p25.f000"
        f"&var_UGRD&var_VGRD&lev_850_mb"
        f"&subregion=&toplat={lat_max:.1f}&leftlon={lon_min:.1f}"
        f"&rightlon={lon_max:.1f}&bottomlat={lat_min:.1f}"
    )
    print(f"  🌐 {date_str} {hour_str}z ...", end=' ', flush=True)

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(out_path, 'wb') as f:
                while True:
                    c = resp.read(65536)
                    if not c: break
                    f.write(c)
        sz = os.path.getsize(out_path)
        if sz < 500:
            with open(out_path) as f:
                t = f.read(200)
            os.remove(out_path)
            return False, f"Server: {t[:80]}"
        print(f"✅ {sz/1024:.0f} KB"); return True, None
    except Exception as e:
        return False, str(e)[:80]


def try_cycles(date_str, hour_str, center_lat, center_lon, out_dir):
    now = datetime.strptime(f"{date_str} {hour_str}", "%Y%m%d %H")
    for offset in [0, -6, -12, -18, -24]:
        dt = now + timedelta(hours=offset)
        cd, ch = dt.strftime("%Y%m%d"), dt.strftime("%H")
        op = os.path.join(out_dir, f"gfs_{cd}_{ch}_u850_v850.grib2")
        if os.path.exists(op): return op, None
        ok, err = download_gfs_subset(cd, ch, center_lat, center_lon, op)
        if ok: return op, None
        print(f"  ❌ {err}")
    return None, "All GFS cycles exhausted"


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(
        description="🐬 Dolphin dH_curl v8 — 完全本地物理算子",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python dolphin_dhcurl_v8.py --date 20260729 --hour 00
  python dolphin_dhcurl_v8.py --mode openmeteo --date 20260729 --hour 00
  python dolphin_dhcurl_v8.py --grib mydata.grib2 --lat 14.5 --lon 168.4
  python dolphin_dhcurl_v8.py --date 20260729 --hour 06 --lat 15.4 --lon 166.6
        """)
    ap.add_argument('--date', help='GFS cycle date (YYYYMMDD)')
    ap.add_argument('--hour', help='GFS cycle hour (00/06/12/18)')
    ap.add_argument('--grib', help='Use existing GRIB2 file (skip download)')
    ap.add_argument('--lat', type=float, help='Center lat hint')
    ap.add_argument('--lon', type=float, help='Center lon hint')
    ap.add_argument('--core', type=float, default=CORE_DEG)
    ap.add_argument('--shell', type=float, default=SHELL_DEG)
    ap.add_argument('--exact-center', action='store_true',
                    help='Force --lat/--lon as exact center (skip auto-detect)')
    ap.add_argument('--output', help='Output JSON path')
    ap.add_argument('--mode', choices=['auto', 'nomads', 'openmeteo', 'eccodes'],
                    default='auto', help='Data source mode')
    args = ap.parse_args()

    # ── 預設 ──
    if not args.date or not args.hour:
        now = datetime.now(timezone.utc)
        args.date = now.strftime("%Y%m%d")
        args.hour = f"{(now.hour // 6) * 6:02d}"
    clat = args.lat or 14.5
    clon = args.lon or 168.4
    data = None
    mode = args.mode

    # ── 取得數據 ──
    # 如果提供了 --grib，跳過 NOMADS 直接讀取
    if args.grib is not None and os.path.exists(args.grib):
        print(f"\n📂 使用 --grib: {args.grib}")
        data = None
        # 試 cfgrib → eccodes
        try:
            import xarray; import cfgrib
            data, err = read_cfgrib(args.grib)
            if data: print(f"  🔄 cfgrib ✅")
        except ImportError:
            pass
        if data is None:
            print(f"  🔄 eccodes ...", end=' ', flush=True)
            data, err = read_eccodes(args.grib)
            if data: print(f"✅")
            else: print(f"⚠️ {err}")
        if data is None:
            print(f"\n❌ 無法讀取 {args.grib}")
            sys.exit(1)
        mode = 'local-grib'

    elif mode == 'openmeteo':
        print(f"\n📡 Open-Meteo API 模式")
        data, err = fetch_openmeteo_grid(clat, clon, args.date, args.hour, grid_size=13)
        if data is None:
            print(f"❌ Open-Meteo 失敗: {err}")
            print(f"  → 改用 --mode nomads 或 --grib")
            sys.exit(1)
        print(f"  ✅ Open-Meteo grid loaded")

    elif mode == 'nomads' or mode == 'auto':
        print(f"\n🌐 NOMADS GFS 模式")
        # 先睇有冇 cfgrib
        use_cfgrib = True
        try:
            import xarray
            import cfgrib
        except ImportError:
            use_cfgrib = False
            print(f"  ⚠️ cfgrib/xarray 未安裝，會用 eccodes 讀取")

        grib_path, err = try_cycles(args.date, args.hour, clat, clon, '.')
        if err:
            print(f"\n❌ NOMADS 下載失敗: {err}")
            if mode == 'auto':
                print(f"  → Fallback 去 Open-Meteo...")
                data, err = fetch_openmeteo_grid(clat, clon, args.date, args.hour, grid_size=13)
                if data is None:
                    print(f"  ❌ Open-Meteo 都失敗: {err}")
                    sys.exit(1)
                print(f"  ✅ Open-Meteo fallback 成功")
            else:
                sys.exit(1)
        else:
            print(f"📂 {os.path.basename(grib_path)} ({os.path.getsize(grib_path)/1024:.0f} KB)")
            if use_cfgrib:
                print(f"  🔄 cfgrib ...", end=' ', flush=True)
                data, err = read_cfgrib(grib_path)
                if data: print(f"✅")
                else: print(f"⚠️ {err}")
            if data is None:
                print(f"  🔄 eccodes ...", end=' ', flush=True)
                data, err = read_eccodes(grib_path)
                if data: print(f"✅")
                else: print(f"⚠️ {err}")
            if data is None:
                print(f"\n❌ 所有讀取引擎失敗。建議安裝 cfgrib:")
                print(f"     conda install -c conda-forge cfgrib xarray")
                sys.exit(1)

    else:  # mode == 'eccodes' — 用 eccodes
        print(f"\n🔧 eccodes 模式")
        grib_path = args.grib
        if not grib_path or not os.path.exists(grib_path):
            grib_path, err = try_cycles(args.date, args.hour, clat, clon, '.')
            if err:
                print(f"❌ {err}"); sys.exit(1)
        if not os.path.exists(grib_path):
            print(f"❌ {grib_path} not found"); sys.exit(1)
        print(f"📂 {os.path.basename(grib_path)} ({os.path.getsize(grib_path)/1024:.0f} KB)")
        data, err = read_eccodes(grib_path)
        if data is None:
            print(f"❌ eccodes: {err}"); sys.exit(1)
        print(f"  ✅ eccodes 成功")

    # ── 檢查數據 ──
    u, v, g = data['u'], data['v'], data['grid']
    if g['Ni'] <= 1 or g['Nj'] <= 1:
        print(f"\n❌ 需要 2D 網格資料才能計算 dH_curl")
        print(f"  Open-Meteo 單點模式改用 --mode nomads 或提供 GRIB2 檔案")
        # 單點粗略估算
        if g['Ni'] == 1:
            z = 0  # can't compute dH_curl from single point
            print(f"  單點 U={u[0,0]:.1f} V={v[0,0]:.1f} m/s — 無法計算 curls")
            sys.exit(1)
        sys.exit(1)

    print(f"\n  網格: {g['Ni']}×{g['Nj']}")
    print(f"  範圍: {g['lat1']:.2f}~{g['lat2']:.2f}°N, {g['lon1']:.2f}~{g['lon2']:.2f}°E")
    print(f"  U: {u.min():.1f}~{u.max():.1f}  V: {v.min():.1f}~{v.max():.1f} m/s")

    # ── 計算 ──
    print(f"  計算 ζ ...", end=' ', flush=True)
    z = compute_vorticity(u, v, g)
    print(f"完  [{z.min():.6f}~{z.max():.6f} s⁻¹]")

    print(f"  dH_curl core={args.core}° shell={args.shell}° ...", end=' ', flush=True)
    # --lat/--lon 策略：
    #   只俾一個 → 用作 hint（自動 detect 附近 max vorticity）
    #   兩個都俾 → 先自動 detect（3° 窗 around hint），detect 唔到先用精確座標
    #   --exact-center 強制只用指定座標
    use_exact = getattr(args, 'exact_center', False)
    if use_exact and args.lat is not None and args.lon is not None:
        lat_hint, lon_hint = args.lat, args.lon
        exact = True
    else:
        lat_hint, lon_hint = args.lat, args.lon
        exact = False
    r = compute_dh_curl(z, g, args.core, args.shell,
                        lat_hint=lat_hint, lon_hint=lon_hint,
                        exact_center=exact)
    if r is None:
        print("❌ core/shell 無格點"); sys.exit(1)
    print("完")

    r['mode'] = classify_mode(r['dh_curl'])
    r['timestamp'] = f"{args.date}{args.hour}00"
    r['data_source'] = mode
    r['grid'] = {'Ni': g['Ni'],'Nj': g['Nj'],
                 'lat1': g['lat1'],'lat2': g['lat2'],
                 'lon1': g['lon1'],'lon2': g['lon2']}

    # ── 輸出 ──
    print(f"\n{'═'*50}")
    print(f"  🐬 DOLPHIN dH_CURL  —  {args.date} {args.hour}z")
    print(f"{'═'*50}")
    print(f"  中心:    {r['center_lat']:.2f}°N  {r['center_lon']:.2f}°E")
    print(f"  dH_curl: {r['dh_curl']:.8f}  s⁻¹")
    print(f"    Core:  {r['H_core']:.8f}  (n={r['core_n']}, r={r['core_deg']}°)")
    print(f"    Shell: {r['H_shell']:.8f}  (n={r['shell_n']}, r={r['shell_deg']}°)")
    print(f"  Mode:    {r['mode']}")
    print(f"  來源:    {mode}")
    print(f"{'═'*50}")

    dh = r['dh_curl']
    if dh < -0.3:   print(f"\n  🔴 強組織化 TC ─ 已發展成熟颱風")
    elif dh < -0.1: print(f"\n  🟠 組織中 ─ 持續增強")
    elif dh > 0.3:  print(f"\n  🟢 發散結構 ─ genesis/發展中")
    elif dh > 0.1:  print(f"\n  🟡 弱發散 ─ 過渡期")
    else:           print(f"\n  ⚪ 中性 ─ 過渡/marginal")

    op = args.output or f"dh_curl_{args.date}_{args.hour}.json"
    with open(op, 'w') as f:
        json.dump(r, f, indent=2)
    print(f"\n  💾 {op}")

    if dh < 0:
        print(f"\n  📊 dH_curl 負值 → Core 組織 > Shell")
        print(f"     支持當前颱風已發展成熟的判斷 ✅")
    else:
        print(f"\n  📊 dH_curl 正值 → Shell 組織 > Core")
        print(f"     與成熟颱風預期不符，請檢查數據")


if __name__ == '__main__':
    main()
