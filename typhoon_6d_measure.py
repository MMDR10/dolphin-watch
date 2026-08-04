#!/usr/bin/env python3
"""
🌀 Typhoon 6D Full-Vector Measurement — Dolphin
================================================
補齊颱風域 6D Ô-HAT 框架全向量測量（特別係 θ₁ 同 χ_eff 呢兩個未實測維度）

數據：GFS 0.25° 850+200 hPa（NOMADS subset 下載 / 或提供已下載 grib2）
中心：Dolphin 8/4 00z 位置（17.5N, 161.75E），可 override

6D 向量（定義依 6d-framework-algorithm.md v1.0）：
  1. dH_curl = H_shell(ζ) − H_core(ζ)          — 渦度核殼梯度
  2. θ₁      = arctan(PC₂/PC₁)                  — 耦合場空間 PCA 幾何角
  3. χ_eff   = Var(c)/Mean(c)                   — 耦合場壓縮率
  4. H       = Pearson r(z850, z200)            — 雙層螺旋度（+ ΔH 核殼分解）
  5. Ô       = pos/neg excursion 比             — 需時間序列（用歷史 dH_curl 補）
  6. D₁      = Var(c⁺)/Mean(c⁺)                 — 正耦合碎裂度（單快照值）

Usage:
  python typhoon_6d_measure.py --lat 17.5 --lon 161.75 --date 20260804 --hour 00
  python typhoon_6d_measure.py --grib /path/to/850_200.grib2 --lat 17.5 --lon 161.75
"""
import sys, json, argparse, math, os, urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np

CORE_DEG = 5.0
SHELL_DEG = 10.0
DOMAIN_PAD = 15.0


def read_eccodes_dual(grib_path):
    """讀 GRIB2 入面 850 + 200 hPa 嘅 U/V（eccodes）"""
    import eccodes as ec
    fields = {}
    with open(grib_path, 'rb') as f:
        while True:
            try:
                iid = ec.codes_grib_new_from_file(f)
                if iid is None:
                    break
                sn = ec.codes_get(iid, 'shortName')
                lvl = ec.codes_get(iid, 'level')
                if sn in ('u', 'v') and lvl in (850, 200):
                    key = (lvl, sn)
                    ni = ec.codes_get(iid, 'Ni')
                    nj = ec.codes_get(iid, 'Nj')
                    vals = ec.codes_get_values(iid)
                    fields[key] = {
                        'values': np.array(vals, dtype=np.float64).reshape((nj, ni)),
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
    need = [(850,'u'),(850,'v'),(200,'u'),(200,'v')]
    if not all(k in fields for k in need):
        missing = [k for k in need if k not in fields]
        return None, f"缺少欄位: {missing}"
    g = fields[(850,'u')]
    return {
        'u850': fields[(850,'u')]['values'], 'v850': fields[(850,'v')]['values'],
        'u200': fields[(200,'u')]['values'], 'v200': fields[(200,'v')]['values'],
        'grid': g,
    }, None


def download_gfs_dual(date_str, hour_str, clat, clon, out_path):
    lat_min = clat - DOMAIN_PAD
    lat_max = clat + DOMAIN_PAD
    lon_min = clon - DOMAIN_PAD
    lon_max = clon + DOMAIN_PAD
    url = (
        f"https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
        f"?dir=%2Fgfs.{date_str}%2F{hour_str}%2Fatmos"
        f"&file=gfs.t{hour_str}z.pgrb2.0p25.f000"
        f"&var_UGRD&var_VGRD&lev_850_mb&lev_200_mb"
        f"&subregion=&toplat={lat_max:.1f}&leftlon={lon_min:.1f}"
        f"&rightlon={lon_max:.1f}&bottomlat={lat_min:.1f}"
    )
    print(f"  🌐 下載 {date_str} {hour_str}z (850+200 hPa) ...", end=' ', flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            with open(out_path, 'wb') as f:
                while True:
                    c = resp.read(65536)
                    if not c:
                        break
                    f.write(c)
        sz = os.path.getsize(out_path)
        if sz < 500:
            with open(out_path) as f:
                t = f.read(200)
            os.remove(out_path)
            return False, f"Server: {t[:80]}"
        print(f"✅ {sz/1024:.0f} KB")
        return True, None
    except Exception as e:
        return False, str(e)[:80]


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


def dist_mask(grid, lat_c, lon_c, r_deg):
    nj, ni = grid['Nj'], grid['Ni']
    lats = np.linspace(grid['lat1'], grid['lat2'], nj)
    lons = np.linspace(grid['lon1'], grid['lon2'], ni)
    r = np.deg2rad(lats[:, None]), np.deg2rad(lons[None, :])
    rc = np.deg2rad(lat_c), np.deg2rad(lon_c)
    a = np.sin((r[0]-rc[0])/2)**2 + np.cos(rc[0])*np.cos(r[0])*np.sin((r[1]-rc[1])/2)**2
    d = 2 * 6371 * np.arcsin(np.sqrt(a))
    return d <= r_deg * 111.32


def measure_6d(data, lat_hint, lon_hint, core_deg=CORE_DEG, shell_deg=SHELL_DEG,
               exact_center=False):
    g = data['grid']
    u850, v850 = data['u850'], data['v850']
    u200, v200 = data['u200'], data['v200']

    # ── vorticity（原始 + 標準化）──
    z850_raw = compute_vorticity(u850, v850, g)
    z200_raw = compute_vorticity(u200, v200, g)
    z850 = (z850_raw - z850_raw.mean()) / z850_raw.std()
    z200 = (z200_raw - z200_raw.mean()) / z200_raw.std()

    # 中心（exact 用 hint；否則用 850 ζ max |ζ|）
    if exact_center and lat_hint is not None and lon_hint is not None:
        lat_c, lon_c = lat_hint, lon_hint
    else:
        lat_c, lon_c = find_center(z850_raw, g, lat_hint, lon_hint)

    cm = dist_mask(g, lat_c, lon_c, core_deg)
    sm = dist_mask(g, lat_c, lon_c, shell_deg) & ~cm

    # ── 維度 1：dH_curl = H_shell(ζ) − H_core(ζ)，用原始 vorticity（同 v8 一致）──
    Hc = float(z850_raw[cm].mean())
    Hs = float(z850_raw[sm].mean())
    dh_curl = Hs - Hc

    # ── 耦合場 c = z850 · z200（標準化）──
    c = z850 * z200

    # ── 維度 2：θ₁ = arctan(PC₂/PC₁)，核心區 PCA（避免全域無相關 45° 偽影）──
    X = np.stack([z850[cm].ravel(), z200[cm].ravel()], axis=1)
    Xc = X - X.mean(axis=0)
    cov = np.cov(Xc.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    PC1, PC2 = evecs[:, order[0]], evecs[:, order[1]]
    # θ₁ = 主軸與水平軸嘅夾角（0° = 完全對齊 / 45° = 無相關對角）
    theta1_deg = math.degrees(math.atan2(abs(PC1[1]), abs(PC1[0])))

    # ── 維度 3：χ_eff = Var(c)/Mean(c)，核心區 + 正耦合版本 ──
    c_core = c[cm]
    chi_eff_core = float(np.var(c_core) / np.mean(c_core))
    cpos = c[c > 0]
    chi_eff_pos = float(np.var(cpos) / np.mean(cpos)) if len(cpos) > 0 and cpos.mean() > 0 else None

    # ── 維度 4：H = Pearson r(z850, z200)（全域 + 核殼分解）──
    H_global = float(np.corrcoef(z850.ravel(), z200.ravel())[0, 1])
    H_core = float(np.corrcoef(z850[cm].ravel(), z200[cm].ravel())[0, 1])
    H_shell = float(np.corrcoef(z850[sm].ravel(), z200[sm].ravel())[0, 1])
    dH = H_core - H_shell

    # ── 維度 6：D₁ = Var(c⁺)/Mean(c⁺) ──
    if len(cpos) > 0 and cpos.mean() > 0:
        D1 = float(np.var(cpos) / np.mean(cpos))
    else:
        D1 = None

    return {
        'center_lat': lat_c, 'center_lon': lon_c,
        'dH_curl': dh_curl, 'H_core_zeta': Hc, 'H_shell_zeta': Hs,
        'theta1_deg': theta1_deg,
        'chi_eff_core': chi_eff_core, 'chi_eff_pos': chi_eff_pos,
        'H_global': H_global, 'H_core': H_core, 'H_shell': H_shell, 'dH': dH,
        'D1': D1,
        'core_n': int(cm.sum()), 'shell_n': int(sm.sum()),
        'core_deg': core_deg, 'shell_deg': shell_deg,
    }


def main():
    ap = argparse.ArgumentParser(description='🌀 Typhoon 6D Full-Vector Measurement')
    ap.add_argument('--lat', type=float, default=17.5, help='Center lat hint')
    ap.add_argument('--lon', type=float, default=161.75, help='Center lon hint')
    ap.add_argument('--date', default='20260804')
    ap.add_argument('--hour', default='00')
    ap.add_argument('--grib', help='Existing dual-level grib2 file')
    ap.add_argument('--core', type=float, default=CORE_DEG)
    ap.add_argument('--shell', type=float, default=SHELL_DEG)
    ap.add_argument('--exact-center', action='store_true', help='用 --lat/--lon 做精確中心')
    ap.add_argument('--output', default=None)
    args = ap.parse_args()

    out_dir = Path('/tmp/typhoon_6d')
    out_dir.mkdir(exist_ok=True)

    if args.grib and os.path.exists(args.grib):
        print(f"📂 使用 grib: {args.grib}")
        data, err = read_eccodes_dual(args.grib)
        if data is None:
            print(f"❌ {err}")
            sys.exit(1)
        src = args.grib
    else:
        grib_path = out_dir / f"gfs_{args.date}_{args.hour}_850_200.grib2"
        if not grib_path.exists():
            ok, err = download_gfs_dual(args.date, args.hour, args.lat, args.lon, str(grib_path))
            if not ok:
                print(f"❌ 下載失敗: {err}")
                sys.exit(1)
        data, err = read_eccodes_dual(str(grib_path))
        if data is None:
            print(f"❌ {err}")
            sys.exit(1)
        src = str(grib_path)

    print(f"  網格: {data['grid']['Ni']}×{data['grid']['Nj']}")
    r = measure_6d(data, args.lat, args.lon, args.core, args.shell,
                   exact_center=args.exact_center)
    r['timestamp'] = f"{args.date}{args.hour}00"
    r['data_source'] = src
    r['storm'] = 'DOLPHIN'

    print(f"\n{'═'*56}")
    print(f"  🌀 DOLPHIN 6D FULL VECTOR — {args.date} {args.hour}z")
    print(f"{'═'*56}")
    print(f"  中心:    {r['center_lat']:.2f}°N  {r['center_lon']:.2f}°E")
    print(f"  1. dH_curl: {r['dH_curl']:.6e}  (Core {r['H_core_zeta']:.3e} / Shell {r['H_shell_zeta']:.3e})")
    print(f"  2. θ₁:      {r['theta1_deg']:.2f}°  (核心區 PCA)")
    print(f"  3. χ_eff:   core {r['chi_eff_core']:.3f} / pos-coupling {r['chi_eff_pos'] if r['chi_eff_pos'] is not None else 'N/A'}")
    print(f"  4. H:       global {r['H_global']:.4f} / core {r['H_core']:.4f} / shell {r['H_shell']:.4f} / ΔH {r['dH']:.4f}")
    print(f"  5. Ô:       (需時間序列 — 用歷史 dH_curl 補，見報告)")
    print(f"  6. D₁:      {r['D1'] if r['D1'] is not None else 'N/A'}")
    print(f"{'═'*56}")

    op = args.output or str(out_dir / f"dolphin_6d_{args.date}_{args.hour}.json")
    with open(op, 'w') as f:
        json.dump(r, f, indent=2, ensure_ascii=False)
    print(f"\n  💾 {op}")


if __name__ == '__main__':
    main()
