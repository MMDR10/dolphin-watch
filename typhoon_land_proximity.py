#!/usr/bin/env python3
"""
🌀 近岸 vs 遠洋 — 颱風 6D 結構差異追蹤
==========================================
從 IBTrACS 抽 WPAC 強颱風（≥100kt），分近岸 (<300km) vs 遠洋 (>800km)，
下載 ERA5 跑 6D，測試 θ₁/H_core 同 land proximity 嘅關係。

Hypothesis: 近岸颱風 θ₁ 更低（陸地約束水平結構）但 H_core 更低（陸地破壞垂直耦合）
"""
import sys, json, os, math, time
from pathlib import Path
import numpy as np
import pandas as pd
import cdsapi
import xarray as xr

CORE_DEG = 5.0
SHELL_DEG = 10.0
DOMAIN_PAD = 15.0
OUT_DIR = Path('/tmp/typhoon_6d')
RESULTS_DIR = Path('/app/working/workspaces/tygtDc/projects/dolphin-watch/results')

# ── Step 1: Pull IBTrACS WPAC typhoons ──

def get_typhoons():
    """Get WPAC typhoons with peak >= 100kt, compute distance to land"""
    df = pd.read_csv('/app/working/workspaces/tygtDc/projects/cyclone/data/ibtracs_wp_2015_2025.csv')
    df['USA_WIND'] = pd.to_numeric(df['USA_WIND'].astype(str).str.strip(), errors='coerce')

    # Group by storm, get peak
    storms = []
    for name, grp in df.groupby('NAME'):
        grp = grp.dropna(subset=['USA_WIND'])
        if len(grp) == 0:
            continue
        peak = grp.loc[grp['USA_WIND'].idxmax()]
        if peak['USA_WIND'] < 100:
            continue
        storms.append({
            'name': name.strip().upper(),
            'date': str(peak['ISO_TIME'])[:10],
            'hour': int(str(peak['ISO_TIME'])[11:13]),
            'lat': float(peak['LAT']),
            'lon': float(peak['LON']),
            'wind': float(peak['USA_WIND']),
        })

    # Approximate distance to land (simple: use coastline boxes)
    # Major landmasses in WPAC: Asia coast ~105-125E, Philippines ~120-128E,
    # Japan ~130-146E, Taiwan ~120-122E, Vietnam ~105-110E
    # Simplified: nearest of these boxes
    def dist_to_land(lat, lon):
        coasts = [
            # (lat_range, lon_range, name)
            ((10, 45), (105, 122), 'Asia_mainland'),   # East Asia coast
            ((5, 19), (120, 128), 'Philippines'),
            ((30, 45), (130, 146), 'Japan'),
            ((21, 26), (120, 122), 'Taiwan'),
            ((8, 22), (105, 110), 'Vietnam'),
            ((1, 7), (95, 106), 'Malay_Peninsula'),
            ((-10, 5), (110, 142), 'Indonesia_PNG'),
        ]
        min_d = 9999
        nearest = 'none'
        for (lat_min, lat_max), (lon_min, lon_max), cname in coasts:
            if lat_min <= lat <= lat_max:
                d_lon = min(abs(lon - lon_min), abs(lon - lon_max))
            else:
                d_lat = min(abs(lat - lat_min), abs(lat - lat_max))
                d_lon = 0
                d = d_lat * 111  # deg→km
                if d < min_d:
                    min_d = d
                    nearest = cname
                continue

            if lon_min <= lon <= lon_max:
                d_lat = min(abs(lat - lat_min), abs(lat - lat_max))
                d = d_lat * 111
            else:
                d_lat = min(abs(lat - lat_min), abs(lat - lat_max))
                d_lon = min(abs(lon - lon_min), abs(lon - lon_max))
                d = np.sqrt((d_lat*111)**2 + (d_lon*111*np.cos(np.radians(lat)))**2)

            if d < min_d:
                min_d = d
                nearest = cname

        return min_d, nearest

    for s in storms:
        d, nearest = dist_to_land(s['lat'], s['lon'])
        s['dist_land_km'] = d
        s['nearest_land'] = nearest

    return storms


# ── Step 2: ERA5 download ──

def download_era5(t):
    nc_path = OUT_DIR / f"era5_{t['name'].lower()}_{t['date'].replace('-','')}_{t['hour']:02d}.nc"
    if nc_path.exists() and nc_path.stat().st_size > 1000:
        return nc_path

    area = [t['lat'] + DOMAIN_PAD, t['lon'] - DOMAIN_PAD,
            t['lat'] - DOMAIN_PAD, t['lon'] + DOMAIN_PAD]

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

    print(f"  🌐 {t['name']} {t['date']} {t['hour']:02d}z  dist_land={t['dist_land_km']:.0f}km ...", flush=True)
    client = cdsapi.Client(quiet=True)
    client.retrieve('reanalysis-era5-pressure-levels', request, str(nc_path))
    return nc_path


# ── Step 3: Load & Measure ──

def load_era5(nc_path):
    ds = xr.open_dataset(nc_path)
    u850 = ds['u'].sel(pressure_level=850).values[0]
    v850 = ds['v'].sel(pressure_level=850).values[0]
    u200 = ds['u'].sel(pressure_level=200).values[0]
    v200 = ds['v'].sel(pressure_level=200).values[0]
    lats = ds['latitude'].values[::-1]
    lons = ds['longitude'].values
    u850, v850 = u850[::-1, :], v850[::-1, :]
    u200, v200 = u200[::-1, :], v200[::-1, :]
    grid = {
        'lat1': float(lats[0]), 'lat2': float(lats[-1]),
        'lon1': float(lons[0]), 'lon2': float(lons[-1]),
        'di': float(lons[1] - lons[0]), 'dj': float(lats[1] - lats[0]),
        'Ni': len(lons), 'Nj': len(lats),
    }
    ds.close()
    return {'u850': u850, 'v850': v850, 'u200': u200, 'v200': v200, 'grid': grid}


def dist_mask(grid, lat_c, lon_c, r_deg):
    nj, ni = grid['Nj'], grid['Ni']
    lats = np.linspace(grid['lat1'], grid['lat2'], nj)
    lons = np.linspace(grid['lon1'], grid['lon2'], ni)
    if lon_c < 0: lon_c += 360
    r = np.deg2rad(lats[:, None]), np.deg2rad(lons[None, :])
    rc = np.deg2rad(lat_c), np.deg2rad(lon_c)
    a = np.sin((r[0]-rc[0])/2)**2 + np.cos(rc[0])*np.cos(r[0])*np.sin((r[1]-rc[1])/2)**2
    d = 2 * 6371 * np.arcsin(np.sqrt(a))
    return d <= r_deg * 111.32


def measure_6d(data, lat_hint, lon_hint):
    g = data['grid']
    z850_raw = np.gradient(data['v850'], axis=1) / (g['di']*math.pi/180*6371000*math.cos(math.radians((g['lat1']+g['lat2'])/2))) \
               - np.gradient(data['u850'], axis=0) / (g['dj']*math.pi/180*6371000)
    z200_raw = np.gradient(data['v200'], axis=1) / (g['di']*math.pi/180*6371000*math.cos(math.radians((g['lat1']+g['lat2'])/2))) \
               - np.gradient(data['u200'], axis=0) / (g['dj']*math.pi/180*6371000)
    z850 = (z850_raw - z850_raw.mean()) / z850_raw.std()
    z200 = (z200_raw - z200_raw.mean()) / z200_raw.std()

    cm = dist_mask(g, lat_hint, lon_hint, CORE_DEG)
    sm = dist_mask(g, lat_hint, lon_hint, SHELL_DEG) & ~cm
    if cm.sum() < 10:
        return None

    Hc = float(z850_raw[cm].mean())
    Hs = float(z850_raw[sm].mean())
    dh_curl = Hs - Hc

    c = z850 * z200
    X = np.stack([z850[cm].ravel(), z200[cm].ravel()], axis=1)
    Xc = X - X.mean(axis=0)
    cov = np.cov(Xc.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    PC1 = evecs[:, order[0]]
    theta1 = math.degrees(math.atan2(abs(PC1[1]), abs(PC1[0])))

    H_global = float(np.corrcoef(z850.ravel(), z200.ravel())[0, 1])
    H_core = float(np.corrcoef(z850[cm].ravel(), z200[cm].ravel())[0, 1])
    H_shell = float(np.corrcoef(z850[sm].ravel(), z200[sm].ravel())[0, 1])

    return {
        'storm': 'UNKNOWN', 'dH_curl': dh_curl, 'theta1_deg': theta1,
        'H_global': H_global, 'H_core': H_core, 'H_shell': H_shell,
        'dH': H_core - H_shell, 'core_n': int(cm.sum()), 'shell_n': int(sm.sum()),
    }


# ── Main ──

def main():
    OUT_DIR.mkdir(exist_ok=True)
    RESULTS_DIR.mkdir(exist_ok=True)

    print("📡 Pulling IBTrACS WPAC typhoons (≥100kt)...")
    all_typhoons = get_typhoons()
    print(f"  Found {len(all_typhoons)} typhoons ≥100kt")

    # Filter: skip already-measured 6
    measured = {'MERANTI','HATO','MANGKHUT','HAGIBIS','GONI','SAOLA'}
    new = [t for t in all_typhoons if t['name'] not in measured]
    print(f"  New: {len(new)} (excluding 6 already measured)")

    # Pick a diverse set: sort by wind, pick top 15
    new.sort(key=lambda x: x['wind'], reverse=True)
    targets = new[:15]

    print(f"\n  Targeting top {len(targets)} by wind:")
    for t in targets:
        print(f"    {t['name']:<12} {t['wind']:.0f}kt  dist_land={t['dist_land_km']:.0f}km  {t['nearest_land']}")

    results = []
    for t in targets:
        try:
            nc_path = download_era5(t)
            data = load_era5(nc_path)
            r = measure_6d(data, t['lat'], t['lon'])
            if r is None:
                print(f"    ❌ core too small")
                continue
            r['storm'] = t['name']
            r['wind_kt'] = t['wind']
            r['dist_land_km'] = t['dist_land_km']
            r['nearest_land'] = t['nearest_land']
            r['lat'] = t['lat']
            r['lon'] = t['lon']
            results.append(r)
            print(f"    ✅ θ₁={r['theta1_deg']:.1f}° H_core={r['H_core']:.3f} ΔH={r['dH']:+.3f}")
            time.sleep(1)
        except Exception as e:
            print(f"    ❌ {e}")

    # Merge with existing 6
    existing = json.load(open(RESULTS_DIR / 'wpac6_6d_summary.json'))
    for e in existing:
        # find dist_land from typhoons list
        match = [t for t in all_typhoons if t['name'] == e['storm']]
        if match:
            e['dist_land_km'] = match[0]['dist_land_km']
            e['nearest_land'] = match[0]['nearest_land']
            e['wind_kt'] = match[0]['wind']

    all_r = existing + results

    # Analysis
    from scipy import stats
    print(f"\n{'═'*60}")
    print(f"  📊 ANALYSIS (n={len(all_r)} typhoons)")
    print(f"{'═'*60}")

    dists = np.array([r['dist_land_km'] for r in all_r])
    theta1s = np.array([r['theta1_deg'] for r in all_r])
    hcores = np.array([r['H_core'] for r in all_r])

    r_t, p_t = stats.pearsonr(dists, theta1s)
    r_h, p_h = stats.pearsonr(dists, hcores)
    r_th, p_th = stats.pearsonr(theta1s, hcores)

    print(f"\n  Distance to land × θ₁:       r={r_t:+.3f}  p={p_t:.3f} {'🔥' if p_t<0.05 else ''}")
    print(f"  Distance to land × H_core:   r={r_h:+.3f}  p={p_h:.3f} {'🔥' if p_h<0.05 else ''}")
    print(f"  θ₁ × H_core:                 r={r_th:+.3f}  p={p_th:.3f} {'🔥' if p_th<0.05 else ''}")

    # Near vs Far split
    near = [r for r in all_r if r['dist_land_km'] < 300]
    far = [r for r in all_r if r['dist_land_km'] > 800]
    print(f"\n  Near-shore (<300km): n={len(near)}")
    if near:
        print(f"    θ₁ = {np.mean([r['theta1_deg'] for r in near]):.1f}° ± {np.std([r['theta1_deg'] for r in near]):.1f}")
        print(f"    H_core = {np.mean([r['H_core'] for r in near]):.3f} ± {np.std([r['H_core'] for r in near]):.3f}")
    print(f"  Open-ocean (>800km): n={len(far)}")
    if far:
        print(f"    θ₁ = {np.mean([r['theta1_deg'] for r in far]):.1f}° ± {np.std([r['theta1_deg'] for r in far]):.1f}")
        print(f"    H_core = {np.mean([r['H_core'] for r in far]):.3f} ± {np.std([r['H_core'] for r in far]):.3f}")

    # Save
    out = RESULTS_DIR / "wpac_land_proximity_6d.json"
    with open(out, 'w') as f:
        json.dump(all_r, f, indent=2)
    print(f"\n  💾 {out}")

    # Full table
    print(f"\n  {'Storm':<12} {'Wind':>5} {'Dist':>6} {'θ₁':>6} {'H_core':>7} {'H_glob':>7} {'ΔH':>7} {'Land'}")
    print(f"  {'─'*12} {'─'*5} {'─'*6} {'─'*6} {'─'*7} {'─'*7} {'─'*7} {'─'*15}")
    for r in sorted(all_r, key=lambda x: x['dist_land_km']):
        print(f"  {r['storm']:<12} {r.get('wind_kt',r.get('peak_wind_kt',0)):>5.0f} {r['dist_land_km']:>6.0f} {r['theta1_deg']:>5.1f}° {r['H_core']:>7.3f} {r['H_global']:>7.3f} {r.get('dH', r.get('dH',0)):>+.3f} {r.get('nearest_land','?')}")


if __name__ == '__main__':
    main()
