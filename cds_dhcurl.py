#!/usr/bin/env python3
"""
🐬 CDS dH_curl Tracker — GitHub Actions 自動版
===============================================
從 ECMWF CDS API (ERA5 0.25°) 下載 U/V@850hPa，
計算洞度 ζ 及 dH_curl = H_shell − H_core 渦旋深度指標。

Output: dhcurl_result.json (for dashboard integration)

Usage:
  export CDSAPI_KEY=b82c5bd4-393c-4927-960d-dd6c8c966605
  python cds_dhcurl.py --date 20260729 --hour 06 --lat 14.5 --lon 168.4
  python cds_dhcurl.py --auto                  # 用目前時間最近嘅 synoptic hour
"""

import json, os, sys, time, argparse
from datetime import datetime, timezone, timedelta
import numpy as np

CORE_DEG = 5.0
SHELL_DEG = 10.0   # MKP 新協議 5/10
DOMAIN_HALF_DEG = 12.0
ERA5_LATENCY_DAYS = 5   # ERA5 reanalysis 約 5-7 日延遲


def fetch_cds_era5(clat, clon, date_str, hour_str):
    """Download ERA5 U/V@850hPa via CDS API, return (u, v, grid_dict) or raise."""
    import cdsapi
    import xarray as xr

    dt = datetime.strptime(f"{date_str} {hour_str}", "%Y%m%d %H")
    lat_max = min(90.0, clat + DOMAIN_HALF_DEG)
    lat_min = max(-90.0, clat - DOMAIN_HALF_DEG)
    lon_left = (clon - DOMAIN_HALF_DEG) % 360
    lon_right = (clon + DOMAIN_HALF_DEG) % 360
    if lon_right < lon_left:
        lon_left, lon_right = lon_right, lon_left

    outfile = f"/tmp/era5_cds_{date_str}_{hour_str}.nc"
    api_key = os.environ.get("CDSAPI_KEY", "")
    if not api_key:
        raise RuntimeError("CDSAPI_KEY env var not set")

    os.environ["CDSAPI_URL"] = "https://cds.climate.copernicus.eu/api"
    os.environ["CDSAPI_KEY"] = api_key

    c = cdsapi.Client()
    print(f"⬇️  CDS download: {date_str} {hour_str}z  ({lat_min:.1f}~{lat_max:.1f}°N, {lon_left:.1f}~{lon_right:.1f}°E)")
    t0 = time.time()

    c.retrieve("reanalysis-era5-pressure-levels", {
        "product_type": "reanalysis",
        "variable": ["u_component_of_wind", "v_component_of_wind"],
        "pressure_level": "850",
        "year": dt.strftime("%Y"),
        "month": dt.strftime("%m"),
        "day": dt.strftime("%d"),
        "time": [dt.strftime("%H:00")],
        "area": [lat_max, lon_left, lat_min, lon_right],
        "format": "netcdf",
    }, outfile)

    elapsed = time.time() - t0
    print(f"✅  Downloaded ({elapsed:.0f}s)")

    ds = xr.open_dataset(outfile)
    u = ds['u'].values.squeeze()
    v = ds['v'].values.squeeze()
    lats = ds['latitude'].values
    lons = ds['longitude'].values
    ds.close()
    try:
        os.remove(outfile)
    except OSError:
        pass

    grid = {
        'Ni': len(lons), 'Nj': len(lats),
        'lat1': float(lats[-1]), 'lat2': float(lats[0]),
        'lon1': float(lons[0]), 'lon2': float(lons[-1]),
        'di': float(abs(lons[1] - lons[0])),
        'dj': float(abs(lats[1] - lats[0])),
    }
    print(f"🌐  Grid: {grid['Nj']}×{grid['Ni']} @ {grid['di']:.2f}°"
          f"  |  {min(u.ravel()):.1f}~{max(u.ravel()):.1f} U  {min(v.ravel()):.1f}~{max(v.ravel()):.1f} V m/s")
    return u, v, grid


def compute_vorticity(u, v, g):
    """ζ = dv/dx − du/dy (s⁻¹)"""
    R = 6371000
    d2r = np.pi / 180
    nj, ni = u.shape
    lats = np.linspace(g['lat1'], g['lat2'], nj)
    lons = np.linspace(g['lon1'], g['lon2'], ni)
    dlat = abs(lats[1] - lats[0]) * d2r
    dlon = abs(lons[1] - lons[0]) * d2r
    cos_lat = np.cos(np.tile(lats.reshape(-1, 1), (1, ni)) * d2r)
    du_dy = np.zeros_like(u)
    du_dy[1:-1, :] = -(u[2:, :] - u[:-2, :]) / (2 * dlat * R)
    dv_dx = np.zeros_like(v)
    dv_dx[:, 1:-1] = (v[:, 2:] - v[:, :-2]) / (2 * dlon * R * cos_lat[:, 1:-1])
    return dv_dx - du_dy


def auto_find_center(zeta, g, lat_hint=None, lon_hint=None):
    """Find max |ζ| centre with optional hint window."""
    lats = np.linspace(g['lat1'], g['lat2'], zeta.shape[0])
    lons = np.linspace(g['lon1'], g['lon2'], zeta.shape[1])
    if lat_hint is not None and lon_hint is not None:
        mask = (lats >= lat_hint - 2) & (lats <= lat_hint + 2)
        mosk = (lons >= lon_hint - 2) & (lons <= lon_hint + 2)
        if mask.any() and mosk.any():
            zw = zeta[np.ix_(mask, mosk)]
            ci, cj = np.unravel_index(np.argmax(np.abs(zw)), zw.shape)
            return float(lats[np.where(mask)[0][ci]]), float(lons[np.where(mosk)[0][cj]])
    ci, cj = np.unravel_index(np.argmax(np.abs(zeta)), zeta.shape)
    return float(lats[ci]), float(lons[cj])


def compute_dh_curl(zeta, g, lat_c, lon_c):
    """dH_curl = mean(ζ_shell) − mean(ζ_core)"""
    lats = np.linspace(g['lat1'], g['lat2'], zeta.shape[0])
    lons = np.linspace(g['lon1'], g['lon2'], zeta.shape[1])
    r_lat = np.deg2rad(lats[:, None])
    r_lon = np.deg2rad(lons[None, :])
    rc = (np.deg2rad(lat_c), np.deg2rad(lon_c))
    a = np.sin((r_lat - rc[0]) / 2)**2 + np.cos(rc[0]) * np.cos(r_lat) * np.sin((r_lon - rc[1]) / 2)**2
    d = 2 * 6371 * np.arcsin(np.sqrt(a))
    core_mask = d <= CORE_DEG * 111.32
    shell_mask = (d > CORE_DEG * 111.32) & (d <= SHELL_DEG * 111.32)
    if not core_mask.any() or not shell_mask.any():
        raise RuntimeError("No grid points in core/shell region")
    Hc = float(np.mean(zeta[core_mask]))
    Hs = float(np.mean(zeta[shell_mask]))
    return {
        "dh_curl": Hs - Hc,
        "H_core": Hc, "H_shell": Hs,
        "core_n": int(core_mask.sum()), "shell_n": int(shell_mask.sum()),
        "center_lat": lat_c, "center_lon": lon_c,
        "core_deg": CORE_DEG, "shell_deg": SHELL_DEG,
    }


def classify_mode(dh):
    if dh < -0.3: return "Monotonic (Deep)"
    if dh > 0.3: return "W-shape (Genesis/Spread)"
    return "Neutral/Transition"


# ════════════════════ MAIN ════════════════════

def main():
    ap = argparse.ArgumentParser(description="🐬 CDS dH_curl Tracker")
    ap.add_argument("--date", help="YYYYMMDD")
    ap.add_argument("--hour", help="00/06/12/18")
    ap.add_argument("--lat", type=float, help="Center latitude hint")
    ap.add_argument("--lon", type=float, help="Center longitude hint")
    ap.add_argument("--storm", default="DOLPHIN", help="Storm name")
    ap.add_argument("--output", default="dhcurl_result.json", help="Output JSON")
    ap.add_argument("--auto", action="store_true", help="Use latest synoptic time")
    ap.add_argument("--era5-latest", action="store_true",
                    help="Use LATEST AVAILABLE ERA5 date (now - {}d latency)".format(ERA5_LATENCY_DAYS))
    args = ap.parse_args()

    if args.era5_latest:
        # ERA5 has ~5d latency → query latest available
        latest = datetime.now(timezone.utc) - timedelta(days=ERA5_LATENCY_DAYS)
        args.date = latest.strftime("%Y%m%d")
        args.hour = f"{(latest.hour // 6) * 6:02d}"
        print(f"  ⚠️  ERA5 latency ~{ERA5_LATENCY_DAYS}d → using {args.date} {args.hour}z")
    elif args.auto or not (args.date and args.hour):
        now = datetime.now(timezone.utc)
        args.date = now.strftime("%Y%m%d")
        args.hour = f"{(now.hour // 6) * 6:02d}"

    lat_hint = args.lat or 14.5
    lon_hint = args.lon or 168.0

    print(f"\n{'='*50}")
    print(f"  🐬 {args.storm} dH_curl  —  {args.date} {args.hour}z")
    print(f"  Core={CORE_DEG}°  Shell={SHELL_DEG}°  Domain=±{DOMAIN_HALF_DEG}°")
    print(f"{'='*50}")

    # Fetch
    u, v, grid = fetch_cds_era5(lat_hint, lon_hint, args.date, args.hour)

    # Compute ζ
    zeta = compute_vorticity(u, v, grid)
    print(f"🌀  ζ range: [{zeta.min():.5e}, {zeta.max():.5e}] s⁻¹")

    # Locate centre
    lat_c, lon_c = auto_find_center(zeta, grid, lat_hint, lon_hint)
    print(f"📍  Centre: {lat_c:.2f}°N {lon_c:.2f}°E (hint: {lat_hint}°N {lon_hint}°E)")

    # dH_curl
    result = compute_dh_curl(zeta, grid, lat_c, lon_c)
    result["mode"] = classify_mode(result["dh_curl"])
    result["timestamp"] = f"{args.date}{args.hour}00"
    result["data_source"] = "ERA5_CDS"
    result["storm"] = args.storm
    result["date"] = args.date
    result["hour"] = args.hour

    print(f"\n  📊  dH_curl:  {result['dh_curl']:.6e}  s⁻¹")
    print(f"      Core ζ:  {result['H_core']:.6e}  (n={result['core_n']})")
    print(f"      Shell ζ: {result['H_shell']:.6e}  (n={result['shell_n']})")
    print(f"      Mode:    {result['mode']}")
    print()

    if result["dh_curl"] < -0.3:
        print("  🔴  Monotonic — mature TC, deep organised vortex")
    elif result["dh_curl"] < -0.1:
        print("  🟠  Organising — strengthening TC")
    elif result["dh_curl"] > 0.3:
        print("  🟢  W-shape — genesis / divergent structure")
    else:
        print("  ⚪  Neutral — transitional regime")
    print()

    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"💾  Saved {args.output}")


if __name__ == "__main__":
    main()
