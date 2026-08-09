#!/usr/bin/env python3
"""
🌀 Decay Collapse Prediction — θ₁ & H_core lead wind decline?
==================================================================
5 typhoons × 6-hourly intervals from peak to dissipation
Test: does structural collapse (θ₁→0, H_core→0) precede wind drop?
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
OUT_DIR = Path('/tmp/typhoon_decay')
PROJ_DIR = Path('/app/working/workspaces/tygtDc/projects/dolphin-watch')

# ── Step 1: Pull decay-phase time series from IBTrACS ──

def get_decay_series():
    df = pd.read_csv('/app/working/workspaces/tygtDc/projects/cyclone/data/ibtracs_wp_2015_2025.csv')
    df['USA_WIND'] = pd.to_numeric(df['USA_WIND'].astype(str).str.strip(), errors='coerce')
    df['LAT'] = pd.to_numeric(df['LAT'].astype(str).str.strip(), errors='coerce')
    df['LON'] = pd.to_numeric(df['LON'].astype(str).str.strip(), errors='coerce')
    df['ISO_TIME'] = pd.to_datetime(df['ISO_TIME'])

    # 5 typhoons with clear decay profiles
    names = ['MANGKHUT', 'HAGIBIS', 'GONI', 'HALONG', 'MERANTI']

    all_series = []
    for name in names:
        grp = df[df['NAME'].str.strip().str.upper() == name].copy()
        grp = grp.dropna(subset=['USA_WIND'])
        grp = grp.sort_values('ISO_TIME')

        if len(grp) < 8:
            continue

        # Find peak
        peak_idx = grp['USA_WIND'].idxmax()
        peak_pos = grp.index.get_loc(peak_idx)

        # Take from peak to end (decay only)
        decay = grp.iloc[peak_pos:].copy()

        # Sample at 6-hourly resolution (IBTrACS already is, but skip missing)
        # Take max 15 points per storm to keep CDS downloads reasonable
        if len(decay) > 15:
            decay = decay.iloc[::len(decay)//15][:15]

        pts = []
        for _, row in decay.iterrows():
            pts.append({
                'name': name.upper(),
                'date': str(row['ISO_TIME'])[:10],
                'hour': int(str(row['ISO_TIME'])[11:13]),
                'lat': float(row['LAT']),
                'lon': float(row['LON']),
                'wind': float(row['USA_WIND']),
                'timestamp': str(row['ISO_TIME'])[:16],
            })

        all_series.append(pts)
        print(f"  {name}: {len(pts)} decay points, {pts[0]['wind']:.0f}kt → {pts[-1]['wind']:.0f}kt")

    return all_series


# ── Step 2-3: Download & Measure ──

def download_era5(t):
    label = f"decay_{t['name'].lower()}_{t['date'].replace('-','')}_{t['hour']:02d}"
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

    client = cdsapi.Client(quiet=True)
    client.retrieve('reanalysis-era5-pressure-levels', request, str(nc_path))
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

    X = np.stack([z850[cm].ravel(), z200[cm].ravel()], axis=1)
    Xc = X - X.mean(axis=0)
    cov = np.cov(Xc.T)
    evals, evecs = np.linalg.eigh(cov)
    order = np.argsort(evals)[::-1]
    PC1 = evecs[:, order[0]]
    theta1 = math.degrees(math.atan2(abs(PC1[1]), abs(PC1[0])))

    H_global = float(np.corrcoef(z850.ravel(), z200.ravel())[0, 1])
    H_core = float(np.corrcoef(z850[cm].ravel(), z200[cm].ravel())[0, 1])

    return {
        'theta1_deg': theta1,
        'H_global': H_global,
        'H_core': H_core,
        'core_n': int(cm.sum()),
    }


# ── Main ──

def main():
    OUT_DIR.mkdir(exist_ok=True)

    print("📡 Pulling decay-phase time series...")
    all_series = get_decay_series()
    total = sum(len(s) for s in all_series)
    print(f"  Total: {total} measurements\n")

    all_results = []
    for series in all_series:
        name = series[0]['name']
        print(f"  {name}: ", end='', flush=True)
        storm_results = []
        for t in series:
            try:
                nc_path = download_era5(t)
                data = load_era5(nc_path)
                r = measure_6d(data, t['lat'], t['lon'])
                if r is None:
                    print('x', end='', flush=True)
                    continue
                r['storm'] = name
                r['wind_kt'] = t['wind']
                r['timestamp'] = t['timestamp']
                r['lat'] = t['lat']
                r['lon'] = t['lon']
                storm_results.append(r)
                print('·', end='', flush=True)
                time.sleep(0.5)
            except Exception as e:
                print(f'!', end='', flush=True)
        print(f" ({len(storm_results)} points)")
        all_results.extend(storm_results)

    # ── Analysis: Lead/Lag ──
    from scipy import stats
    from scipy.signal import correlate, correlation_lags

    print(f"\n{'═'*60}")
    print(f"  📊 DECAY COLLAPSE LEAD/LAG ANALYSIS (n={len(all_results)} total)")
    print(f"{'═'*60}")

    storms = sorted(set(r['storm'] for r in all_results))
    results_by_storm = {s: sorted([r for r in all_results if r['storm'] == s],
                                  key=lambda r: r['wind_kt'], reverse=True) for s in storms}

    # Per-storm: cross-correlation between wind and θ₁/H_core over decay
    for s in storms:
        pts = results_by_storm[s]
        if len(pts) < 5:
            continue
        winds = np.array([p['wind_kt'] for p in pts])
        theta1s = np.array([p['theta1_deg'] for p in pts])
        hcores = np.array([p['H_core'] for p in pts])
        timestamps = [p['timestamp'] for p in pts]

        print(f"\n  ── {s} ({len(pts)} points, {winds[0]:.0f}→{winds[-1]:.0f}kt) ──")

        # Compute derivatives
        dw = np.diff(winds)
        dt = np.diff(theta1s)
        dh = np.diff(hcores)

        # Simple test: does θ₁ or H_core drop BEFORE wind drops?
        # Find first significant drop in each
        for signal, label in [(theta1s, 'θ₁'), (hcores, 'H_core'), (winds, 'wind')]:
            # 20% drop from peak
            peak_val = signal[0]
            drop20 = peak_val * 0.8
            drop_idx = np.argmax(signal < drop20) if (signal < drop20).any() else -1
            if drop_idx > 0:
                print(f"    {label} 80% @ t+{drop_idx*6}h: {signal[drop_idx]:.1f} (from {peak_val:.1f})  [{timestamps[drop_idx]}]")

        # Cross-correlation: wind vs θ₁
        if len(winds) >= 6:
            # Detrend
            w_det = winds - np.polyval(np.polyfit(np.arange(len(winds)), winds, 1), np.arange(len(winds)))
            t_det = theta1s - np.polyval(np.polyfit(np.arange(len(theta1s)), theta1s, 1), np.arange(len(theta1s)))
            h_det = hcores - np.polyval(np.polyfit(np.arange(len(hcores)), hcores, 1), np.arange(len(hcores)))

            # Zero-lag correlation
            r_wt, p_wt = stats.pearsonr(winds, theta1s)
            r_wh, p_wh = stats.pearsonr(winds, hcores)
            print(f"    wind×θ₁ @ lag=0: r={r_wt:+.3f} p={p_wt:.3f}")
            print(f"    wind×H_core @ lag=0: r={r_wh:+.3f} p={p_wh:.3f}")

        # Simple statistic: slope of θ₁/wind across decay (pooled)
        dtheta_dwind = (theta1s[-1] - theta1s[0]) / (winds[-1] - winds[0]) if winds[-1] != winds[0] else 0
        dhcore_dwind = (hcores[-1] - hcores[0]) / (winds[-1] - winds[0]) if winds[-1] != winds[0] else 0
        print(f"    dθ₁/dwind = {dtheta_dwind:+.3f}°/kt")
        print(f"    dH_core/dwind = {dhcore_dwind:+.4f}/kt")

    # Pooled statistics
    all_winds_pooled = np.array([r['wind_kt'] for r in all_results])
    all_theta_pooled = np.array([r['theta1_deg'] for r in all_results])
    all_hcore_pooled = np.array([r['H_core'] for r in all_results])

    r_wt, p_wt = stats.pearsonr(all_winds_pooled, all_theta_pooled)
    r_wh, p_wh = stats.pearsonr(all_winds_pooled, all_hcore_pooled)

    print(f"\n  Pooled decay phase (n={len(all_results)}):")
    print(f"  wind×θ₁:      r={r_wt:+.3f}  p={p_wt:.4f}")
    print(f"  wind×H_core:   r={r_wh:+.3f}  p={p_wh:.4f}")

    # Save
    out = PROJ_DIR / 'results' / 'wpac_decay_collapse_6d.json'
    with open(out, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  💾 {out}")


if __name__ == '__main__':
    main()
