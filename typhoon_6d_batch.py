#!/usr/bin/env python3
"""
🌀 Typhoon 6D Cross-Validation — WPAC 6 Typhoons via ERA5
==========================================================
逐個颱風從 CDS ERA5 下載 850+200 hPa U/V，跑 6D 全向量測量。

Typhoons:
  MERANTI   2016-09-13 12z  20.4N 122.9E  170kt
  HATO      2017-08-23 03z  21.9N 113.7E  100kt
  MANGKHUT  2018-09-12 06z  14.0N 135.2E  155kt
  HAGIBIS   2019-10-07 10z  15.9N 147.1E  160kt
  GONI      2020-10-31 18z  13.7N 125.0E  170kt
  SAOLA     2023-08-29 18z  19.9N 121.9E  140kt

Usage: python typhoon_6d_batch.py
"""
import sys, json, os, math, time
from pathlib import Path
import numpy as np
import cdsapi

CORE_DEG = 5.0
SHELL_DEG = 10.0
DOMAIN_PAD = 15.0
OUT_DIR = Path('/tmp/typhoon_6d')
RESULTS_DIR = Path('/app/working/workspaces/tygtDc/projects/dolphin-watch/results')

TYPHOONS = [
    {'name': 'MERANTI',  'date': '2016-09-13', 'hour': 12, 'lat': 20.4, 'lon': 122.9, 'wind': 170},
    {'name': 'HATO',     'date': '2017-08-23', 'hour': 3,  'lat': 21.9, 'lon': 113.7, 'wind': 100},
    {'name': 'MANGKHUT', 'date': '2018-09-12', 'hour': 6,  'lat': 14.0, 'lon': 135.2, 'wind': 155},
    {'name': 'HAGIBIS',  'date': '2019-10-07', 'hour': 10, 'lat': 15.9, 'lon': 147.1, 'wind': 160},
    {'name': 'GONI',     'date': '2020-10-31', 'hour': 18, 'lat': 13.7, 'lon': 125.0, 'wind': 170},
    {'name': 'SAOLA',    'date': '2023-08-29', 'hour': 18, 'lat': 19.9, 'lon': 121.9, 'wind': 140},
]


def download_era5(t):
    """Download ERA5 u/v 850+200 hPa for typhoon peak time"""
    nc_path = OUT_DIR / f"era5_{t['name'].lower()}_{t['date'].replace('-','')}_{t['hour']:02d}.nc"
    if nc_path.exists() and nc_path.stat().st_size > 1000:
        print(f"  📂 already cached: {nc_path.name} ({nc_path.stat().st_size/1024:.0f} KB)")
        return nc_path

    area = [t['lat'] + DOMAIN_PAD, t['lon'] - DOMAIN_PAD,
            t['lat'] - DOMAIN_PAD, t['lon'] + DOMAIN_PAD]  # N,W,S,E

    request = {
        'product_type': 'reanalysis',
        'format': 'netcdf',
        'variable': ['u_component_of_wind', 'v_component_of_wind'],
        'pressure_level': ['200', '850'],
        'year': t['date'][:4],
        'month': t['date'][5:7],
        'day': t['date'][8:10],
        'time': [f"{t['hour']:02d}:00"],
        'area': area,
    }

    print(f"  🌐 CDS download {t['name']} {t['date']} {t['hour']:02d}z (area={area}) ...", flush=True)
    client = cdsapi.Client()
    client.retrieve('reanalysis-era5-pressure-levels', request, str(nc_path))
    print(f"    ✅ {nc_path.stat().st_size/1024:.0f} KB")
    return nc_path


def load_era5(nc_path):
    """Load u/v at 850/200 from ERA5 netcdf"""
    import xarray as xr
    ds = xr.open_dataset(nc_path)

    # ERA5 lat goes N→S, lon 0→360; CDS new API uses 'pressure_level' not 'level'
    u850 = ds['u'].sel(pressure_level=850).values[0]  # [time, level, lat, lon]
    v850 = ds['v'].sel(pressure_level=850).values[0]
    u200 = ds['u'].sel(pressure_level=200).values[0]
    v200 = ds['v'].sel(pressure_level=200).values[0]
    lats = ds['latitude'].values  # descending (N→S)
    lons = ds['longitude'].values

    # Flip lats to ascending
    u850 = u850[::-1, :]
    v850 = v850[::-1, :]
    u200 = u200[::-1, :]
    v200 = v200[::-1, :]
    lats = lats[::-1]

    grid = {
        'lat1': float(lats[0]), 'lat2': float(lats[-1]),
        'lon1': float(lons[0]), 'lon2': float(lons[-1]),
        'di': float(lons[1] - lons[0]),
        'dj': float(lats[1] - lats[0]),
        'Ni': len(lons), 'Nj': len(lats),
    }
    ds.close()
    return {'u850': u850, 'v850': v850, 'u200': u200, 'v200': v200, 'grid': grid}


def dist_mask(grid, lat_c, lon_c, r_deg):
    nj, ni = grid['Nj'], grid['Ni']
    lats = np.linspace(grid['lat1'], grid['lat2'], nj)
    lons = np.linspace(grid['lon1'], grid['lon2'], ni)
    # Handle 0→360 lon for WPAC
    if lon_c < 0:
        lon_c += 360
    r = np.deg2rad(lats[:, None]), np.deg2rad(lons[None, :])
    rc = np.deg2rad(lat_c), np.deg2rad(lon_c)
    a = np.sin((r[0]-rc[0])/2)**2 + np.cos(rc[0])*np.cos(r[0])*np.sin((r[1]-rc[1])/2)**2
    d = 2 * 6371 * np.arcsin(np.sqrt(a))
    return d <= r_deg * 111.32


def compute_vorticity(u, v, grid):
    R = 6371000
    mid = math.radians((grid['lat1'] + grid['lat2']) / 2)
    dlon_m = grid['di'] * math.pi / 180 * R * math.cos(mid)
    dlat_m = grid['dj'] * math.pi / 180 * R
    return np.gradient(v, axis=1) / dlon_m - np.gradient(u, axis=0) / dlat_m


def measure_6d(data, lat_hint, lon_hint, core_deg=CORE_DEG, shell_deg=SHELL_DEG):
    g = data['grid']
    z850_raw = compute_vorticity(data['u850'], data['v850'], g)
    z200_raw = compute_vorticity(data['u200'], data['v200'], g)
    z850 = (z850_raw - z850_raw.mean()) / z850_raw.std()
    z200 = (z200_raw - z200_raw.mean()) / z200_raw.std()

    # Center: hint position
    lat_c, lon_c = lat_hint, lon_hint

    cm = dist_mask(g, lat_c, lon_c, core_deg)
    sm = dist_mask(g, lat_c, lon_c, shell_deg) & ~cm

    if cm.sum() < 10:
        return {'error': f'core too small: {cm.sum()} cells', 'data': data}

    # dH_curl
    Hc = float(z850_raw[cm].mean())
    Hs = float(z850_raw[sm].mean())
    dh_curl = Hs - Hc

    # Coupling field
    c = z850 * z200

    # θ₁
    X = np.stack([z850[cm].ravel(), z200[cm].ravel()], axis=1)
    Xc = X - X.mean(axis=0)
    cov = np.cov(Xc.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    PC1 = evecs[:, order[0]]
    theta1_deg = math.degrees(math.atan2(abs(PC1[1]), abs(PC1[0])))

    # χ_eff
    c_core = c[cm]
    chi_eff_core = float(np.var(c_core) / np.mean(c_core)) if np.mean(c_core) != 0 else None

    # H
    H_global = float(np.corrcoef(z850.ravel(), z200.ravel())[0, 1])
    H_core = float(np.corrcoef(z850[cm].ravel(), z200[cm].ravel())[0, 1])
    H_shell = float(np.corrcoef(z850[sm].ravel(), z200[sm].ravel())[0, 1])
    dH = H_core - H_shell

    # D₁
    cpos = c[c > 0]
    D1 = float(np.var(cpos) / np.mean(cpos)) if len(cpos) > 0 and cpos.mean() > 0 else None

    return {
        'center_lat': lat_c, 'center_lon': lon_c,
        'dH_curl': dh_curl, 'H_core_zeta': Hc, 'H_shell_zeta': Hs,
        'theta1_deg': theta1_deg,
        'chi_eff_core': chi_eff_core,
        'H_global': H_global, 'H_core': H_core, 'H_shell': H_shell, 'dH': dH,
        'D1': D1,
        'core_n': int(cm.sum()), 'shell_n': int(sm.sum()),
    }


def main():
    OUT_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    all_results = []
    errors = []

    for t in TYPHOONS:
        name = t['name']
        print(f"\n{'═'*56}")
        print(f"  🌀 {name}  peak {t['date']} {t['hour']:02d}z  {t['lat']}N {t['lon']}E  {t['wind']}kt")
        print(f"{'═'*56}")

        try:
            nc_path = download_era5(t)
            data = load_era5(nc_path)
            print(f"  網格: {data['grid']['Ni']}×{data['grid']['Nj']}")

            r = measure_6d(data, t['lat'], t['lon'])
            if 'error' in r:
                print(f"  ❌ {r['error']}")
                errors.append({'name': name, 'error': r['error']})
                continue

            r['storm'] = name
            r['peak_wind_kt'] = t['wind']
            r['timestamp'] = f"{t['date'].replace('-','')}{t['hour']:02d}00"
            r['source'] = 'ERA5'

            print(f"  dH_curl: {r['dH_curl']:.6e}")
            print(f"  θ₁:      {r['theta1_deg']:.2f}°")
            print(f"  χ_eff:   {r['chi_eff_core']}")

            print(f"  H_global: {r['H_global']:.4f}  H_core: {r['H_core']:.4f}  H_shell: {r['H_shell']:.4f}  ΔH: {r['dH']:.4f}")
            print(f"  D₁:      {r['D1']}")
            print(f"  core_n: {r['core_n']}  shell_n: {r['shell_n']}")

            all_results.append(r)

            # Save individual
            out_json = RESULTS_DIR / f"{name.lower()}_6d_{t['date'].replace('-','')}.json"
            with open(out_json, 'w') as f:
                json.dump(r, f, indent=2)
            print(f"  💾 {out_json}")

        except Exception as e:
            print(f"  ❌ Exception: {e}")
            errors.append({'name': name, 'error': str(e)})
            import traceback
            traceback.print_exc()

        # Small pause between CDS requests
        time.sleep(1)

    # Summary
    print(f"\n\n{'═'*56}")
    print(f"  📊 SUMMARY")
    print(f"{'═'*56}")
    print(f"  Completed: {len(all_results)}/{len(TYPHOONS)}")
    if errors:
        print(f"  Errors: {len(errors)}")
        for e in errors:
            print(f"    {e['name']}: {e['error']}")

    if all_results:
        print(f"\n  {'Storm':<12} {'dH_curl':>12} {'θ₁':>7} {'H_core':>7} {'H_global':>8} {'ΔH':>7} {'D₁':>8}")
        print(f"  {'─'*12} {'─'*12} {'─'*7} {'─'*7} {'─'*8} {'─'*7} {'─'*8}")
        for r in all_results:
            print(f"  {r['storm']:<12} {r['dH_curl']:>12.2e} {r['theta1_deg']:>6.1f}° {r['H_core']:>7.4f} {r['H_global']:>8.4f} {r['dH']:>+.4f} {r['D1']:>8.1f}")

        # Save full
        full_out = RESULTS_DIR / "wpac6_6d_summary.json"
        with open(full_out, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\n  💾 Full summary: {full_out}")

    return all_results, errors


if __name__ == '__main__':
    main()
