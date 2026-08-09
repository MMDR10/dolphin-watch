#!/usr/bin/env python3
"""
🌀 Life Cycle Evolution — θ₁ & H_core 隨 intensity 變化
========================================================
5 隻長 track WPAC 颱風 × 3 時間點 = 15 測量
每隻揀 early (CAT1-2) / peak / late (CAT1-2) → 追蹤結構演化
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
OUT_DIR = Path('/tmp/typhoon_lifecycle')
PROJ_DIR = Path('/app/working/workspaces/tygtDc/projects/dolphin-watch')

# ── Step 1: Pick 5 long-track typhoons with clear life cycle ──

def pick_targets():
    """Select 5 typhoons with long, well-documented tracks"""
    df = pd.read_csv('/app/working/workspaces/tygtDc/projects/cyclone/data/ibtracs_wp_2015_2025.csv')
    df['USA_WIND'] = pd.to_numeric(df['USA_WIND'].astype(str).str.strip(), errors='coerce')
    df['LAT'] = pd.to_numeric(df['LAT'].astype(str).str.strip(), errors='coerce')
    df['LON'] = pd.to_numeric(df['LON'].astype(str).str.strip(), errors='coerce')

    # Manually select 5 famous long-track typhoons
    names = ['MANGKHUT', 'HAGIBIS', 'MERANTI', 'GONI', 'HALONG']  # Halong had a very long life

    targets = []
    for name in names:
        grp = df[df['NAME'].str.strip().str.upper() == name].copy()
        grp = grp.dropna(subset=['USA_WIND'])
        if len(grp) == 0:
            continue

        grp = grp.sort_values('ISO_TIME')
        peak_idx = grp['USA_WIND'].idxmax()
        peak = grp.loc[peak_idx]

        # Early: first time reaches CAT1 (64kt) or first available >= 50kt
        early_mask = grp['USA_WIND'] >= 50
        if early_mask.any():
            early = grp[early_mask].iloc[0]
        else:
            early = grp.iloc[0]

        # Late: last time above CAT1, or last available >= 50kt
        if early_mask.any():
            late = grp[early_mask].iloc[-1]
        else:
            late = grp.iloc[-1]

        # Ensure 3 distinct points
        points = []
        for label, row in [('early', early), ('peak', peak), ('late', late)]:
            t = {
                'name': name.upper(),
                'label': label,
                'date': str(row['ISO_TIME'])[:10],
                'hour': int(str(row['ISO_TIME'])[11:13]),
                'lat': float(row['LAT']),
                'lon': float(row['LON']),
                'wind': float(row['USA_WIND']),
            }
            points.append(t)

        # Ensure points are ordered in time
        points.sort(key=lambda p: p['date'] + f"{p['hour']:02d}")
        points[0]['label'] = 'early'
        points[-1]['label'] = 'late'
        if len(points) > 2:
            points[1]['label'] = 'peak'

        targets.extend(points)
        print(f"  {name}: early={points[0]['date']}({points[0]['wind']:.0f}kt) peak={points[1]['date']}({points[1]['wind']:.0f}kt) late={points[-1]['date']}({points[-1]['wind']:.0f}kt)")

    return targets


# ── Step 2: Download & Measure (reuse from previous) ──

def download_era5(t):
    label = f"{t['name'].lower()}_{t['label']}_{t['date'].replace('-','')}_{t['hour']:02d}"
    nc_path = OUT_DIR / f"era5_{label}.nc"
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

    print(f"    🌐 {label} ...", end=' ', flush=True)
    client = cdsapi.Client(quiet=True)
    client.retrieve('reanalysis-era5-pressure-levels', request, str(nc_path))
    print(f"✅")
    return nc_path


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

    X = np.stack([z850[cm].ravel(), z200[cm].ravel()], axis=1)
    Xc = X - X.mean(axis=0)
    cov = np.cov(Xc.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    PC1 = evecs[:, order[0]]
    theta1 = math.degrees(math.atan2(abs(PC1[1]), abs(PC1[0])))
    # λ ratio
    lambda_ratio = evals[order[0]] / (evals[order[0]] + evals[order[1]] + 1e-12)

    H_global = float(np.corrcoef(z850.ravel(), z200.ravel())[0, 1])
    H_core = float(np.corrcoef(z850[cm].ravel(), z200[cm].ravel())[0, 1])
    H_shell = float(np.corrcoef(z850[sm].ravel(), z200[sm].ravel())[0, 1])

    return {
        'dH_curl': Hs - Hc,
        'theta1_deg': theta1,
        'lambda_ratio': lambda_ratio,
        'H_global': H_global,
        'H_core': H_core,
        'H_shell': H_shell,
        'dH': H_core - H_shell,
        'core_n': int(cm.sum()),
    }


# ── Main ──

def main():
    OUT_DIR.mkdir(exist_ok=True)

    print("🎯 Picking long-track targets...")
    targets = pick_targets()
    print(f"  Total: {len(targets)} measurements\n")

    results = []
    for t in targets:
        print(f"  {t['name']} [{t['label']}]", end='', flush=True)
        try:
            nc_path = download_era5(t)
            data = load_era5(nc_path)
            r = measure_6d(data, t['lat'], t['lon'])
            if r is None:
                print(" ❌ core too small")
                continue
            r['storm'] = t['name']
            r['label'] = t['label']
            r['wind_kt'] = t['wind']
            r['lat'] = t['lat']
            r['lon'] = t['lon']
            results.append(r)
            print(f"  θ₁={r['theta1_deg']:.1f}° H_core={r['H_core']:.3f} wind={t['wind']:.0f}kt")
            time.sleep(1)
        except Exception as e:
            print(f" ❌ {e}")

    # Analysis
    from scipy import stats
    print(f"\n{'═'*60}")
    print(f"  📊 LIFE CYCLE ANALYSIS (n={len(results)})")
    print(f"{'═'*60}")

    winds = np.array([r['wind_kt'] for r in results])
    theta1s = np.array([r['theta1_deg'] for r in results])
    hcores = np.array([r['H_core'] for r in results])

    # Per-storm trajectories  
    storms = sorted(set(r['storm'] for r in results))
    print(f"\n  Per-storm trajectories:")
    for s in storms:
        pts = [r for r in results if r['storm'] == s]
        pts.sort(key=lambda r: r['wind_kt'])
        traj = ' → '.join(f"{p['label'][0]}({p['wind_kt']:.0f}kt:θ₁={p['theta1_deg']:.0f}° H={p['H_core']:.3f})" for p in pts)
        print(f"    {s}: {traj}")

    # Within-storm wind→θ₁ correlation
    print(f"\n  Within-storm correlation (pooled):")
    all_winds, all_theta, all_hcore, all_labels = [], [], [], []
    for s in storms:
        pts = [r for r in results if r['storm'] == s]
        if len(pts) < 2:
            continue
        pts.sort(key=lambda r: r['wind_kt'])
        for p in pts:
            all_winds.append(p['wind_kt'])
            all_theta.append(p['theta1_deg'])
            all_hcore.append(p['H_core'])
            all_labels.append(p['storm'][:4])

    # Across all time points
    r_wt, p_wt = stats.pearsonr(all_winds, all_theta)
    r_wh, p_wh = stats.pearsonr(all_winds, all_hcore)
    print(f"  wind×θ₁:      r={r_wt:+.3f}  p={p_wt:.4f}")
    print(f"  wind×H_core:   r={r_wh:+.3f}  p={p_wh:.4f}")

    # Compare with cross-sectional (static peak) correlation from earlier
    print(f"\n  For comparison — cross-sectional peak-only (n=21):")
    print(f"  wind×θ₁:      r=+0.649  p=0.0015")
    print(f"  wind×H_core:   r=+0.397  p=0.0744")

    # Save
    out = PROJ_DIR / 'results' / 'wpac_lifecycle_6d.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n  💾 {out}")


if __name__ == '__main__':
    main()
