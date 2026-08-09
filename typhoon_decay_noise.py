#!/usr/bin/env python3
"""
🌊 Decay Noise Topography — 雜訊散咗未？
===========================================
用現有 75 個 ERA5 nc，測 decay phase noise metrics
Test: noise disperses → wind drops → structure collapses?
"""
import json, math, os
from pathlib import Path
import numpy as np
import xarray as xr
from scipy.ndimage import gaussian_filter
from scipy import stats

CORE_DEG = 5.0
SHELL_DEG = 10.0
NC_DIR = Path('/tmp/typhoon_decay')
PROJ_DIR = Path('/app/working/workspaces/tygtDc/projects/dolphin-watch')

# Load existing decay results (has wind, θ₁, H_core, timestamps)
decay_data = json.load(open(PROJ_DIR / 'results/wpac_decay_collapse_6d.json'))


def dist_mask(lats, lons, lat_c, lon_c, r_deg):
    if lon_c < 0: lon_c += 360
    r_lat, r_lon = np.deg2rad(lats[:, None]), np.deg2rad(lons[None, :])
    rc_lat, rc_lon = np.deg2rad(lat_c), np.deg2rad(lon_c)
    a = np.sin((r_lat-rc_lat)/2)**2 + np.cos(rc_lat)*np.cos(r_lat)*np.sin((r_lon-rc_lon)/2)**2
    d = 2 * 6371 * np.arcsin(np.sqrt(a))
    return d <= r_deg * 111.32


def compute_noise_metrics(nc_label, lat_hint, lon_hint):
    """Compute noise topography in core region"""
    nc_path = NC_DIR / f"era5_decay_{nc_label}.nc"
    if not nc_path.exists():
        return None

    ds = xr.open_dataset(nc_path)
    u850 = ds['u'].sel(pressure_level=850).values[0]
    v850 = ds['v'].sel(pressure_level=850).values[0]
    u200 = ds['u'].sel(pressure_level=200).values[0]
    v200 = ds['v'].sel(pressure_level=200).values[0]
    lats = ds['latitude'].values[::-1]
    lons = ds['longitude'].values
    ds.close()

    u850, v850 = u850[::-1, :], v850[::-1, :]
    u200, v200 = u200[::-1, :], v200[::-1, :]

    g = {'lat1': float(lats[0]), 'lat2': float(lats[-1]),
         'lon1': float(lons[0]), 'lon2': float(lons[-1]),
         'di': float(lons[1] - lons[0]), 'dj': float(lats[1] - lats[0]),
         'Ni': len(lons), 'Nj': len(lats)}

    # Vorticity
    cos_lat = math.cos(math.radians((g['lat1']+g['lat2'])/2))
    dx = g['di'] * math.pi/180 * 6371000 * cos_lat
    dy = g['dj'] * math.pi/180 * 6371000

    z850 = np.gradient(v850, axis=1)/dx - np.gradient(u850, axis=0)/dy
    z200 = np.gradient(v200, axis=1)/dx - np.gradient(u200, axis=0)/dy

    # Standardize
    z850_s = (z850 - z850.mean()) / z850.std()
    z200_s = (z200 - z200.mean()) / z200.std()

    cm = dist_mask(lats, lons, lat_hint, lon_hint, CORE_DEG)
    sm = dist_mask(lats, lons, lat_hint, lon_hint, SHELL_DEG) & ~cm
    if cm.sum() < 10:
        return None

    # === Noise = deviation from smooth field ===
    sigma_px = CORE_DEG / g['di']  # ~20 pixels for 5° at 0.25°
    z850_smooth = gaussian_filter(z850_s, sigma=sigma_px)
    z200_smooth = gaussian_filter(z200_s, sigma=sigma_px)
    dH_850 = z850_s - z850_smooth
    dH_200 = z200_s - z200_smooth

    core_noise_850 = dH_850[cm]
    core_noise_200 = dH_200[cm]

    # Core z850 stats (raw, for variance/kurtosis)
    core_z850 = z850_s[cm]

    metrics = {}

    # 1. Noise magnitude (RMS of dH in core)
    metrics['noise_rms_850'] = float(np.sqrt(np.mean(core_noise_850**2)))
    metrics['noise_rms_200'] = float(np.sqrt(np.mean(core_noise_200**2)))

    # 2. Noise dispersion (std across core)
    metrics['noise_std_850'] = float(np.std(core_noise_850))
    metrics['noise_std_200'] = float(np.std(core_noise_200))

    # 3. Core vorticity variance (raw spread)
    metrics['core_var_850'] = float(np.var(core_z850))

    # 4. Excess kurtosis of core vorticity (peakedness)
    k = float(stats.kurtosis(core_z850))
    metrics['core_kurt_850'] = k  # excess kurtosis, normal=0

    # 5. Spatial roughness: mean |gradient| in core
    gz_y, gz_x = np.gradient(z850_s)
    roughness = np.sqrt(gz_x[cm]**2 + gz_y[cm]**2)
    metrics['roughness_850'] = float(np.mean(roughness))

    # 6. Coherent fraction: smooth energy / total energy in core
    total_E = float(np.sum(core_z850**2))
    smooth_E = float(np.sum(z850_smooth[cm]**2))
    metrics['coherent_frac_850'] = smooth_E / total_E if total_E > 0 else 1.0

    # 7. Noise × noise correlation: how structured is the noise?
    metrics['noise_corr_850_200'] = float(np.corrcoef(core_noise_850, core_noise_200)[0, 1])

    # 8. Shell noise for comparison
    if sm.sum() > 10:
        sm_z850 = z850_s[sm]
        sm_noise = dH_850[sm]
        metrics['shell_noise_rms_850'] = float(np.sqrt(np.mean(sm_noise**2)))
        metrics['shell_var_850'] = float(np.var(sm_z850))
        metrics['noise_ratio_core_shell'] = metrics['noise_rms_850'] / metrics['shell_noise_rms_850'] if metrics['shell_noise_rms_850'] > 0 else 1.0

    return metrics


# ── Main ──

print("🌊 Computing noise topography for decay phase...")
print(f"  Loading {len(decay_data)} existing measurements\n")

results = []
for i, d in enumerate(decay_data):
    storm = d['storm']
    ts = d['timestamp']  # "2020-10-31 18:00"
    date_part = ts[:10].replace('-', '')
    hour_part = ts[11:13]
    label = f"{storm.lower()}_{date_part}_{hour_part}"
    # Match the download naming convention
    try:
        metrics = compute_noise_metrics(label, d['lat'], d['lon'])
    except Exception as e:
        print(f"  ❌ {storm} [{d['timestamp']}] {e}")
        continue

    if metrics is None:
        continue

    r = {
        'storm': storm,
        'timestamp': d['timestamp'],
        'wind_kt': d['wind_kt'],
        'theta1_deg': d['theta1_deg'],
        'H_core': d['H_core'],
    }
    r.update(metrics)
    results.append(r)
    if (i+1) % 15 == 0:
        print(f"  ... {i+1}/{len(decay_data)}")

print(f"\n  Total: {len(results)} with noise metrics")

# ── Analysis: Lead/Lag ──
storms = sorted(set(r['storm'] for r in results))
noise_keys = ['noise_rms_850', 'noise_std_850', 'core_var_850', 'core_kurt_850',
             'roughness_850', 'coherent_frac_850', 'noise_corr_850_200']

print(f"\n{'═'*70}")
print(f"  📊 NOISE LEAD/LAG ANALYSIS")
print(f"{'═'*70}")

for s in storms:
    pts = sorted([r for r in results if r['storm'] == s], key=lambda r: r['wind_kt'], reverse=True)
    if len(pts) < 5:
        continue

    winds = np.array([p['wind_kt'] for p in pts])
    times = [p['timestamp'] for p in pts]

    print(f"\n  ── {s} ({len(pts)} points, {winds[0]:.0f}→{winds[-1]:.0f}kt) ──")

    # For each noise metric: when does it first cross 80% of peak?
    # Compute 80% threshold crossings
    wind_80_idx = np.argmax(winds < winds[0]*0.8) if (winds < winds[0]*0.8).any() else -1

    for key in noise_keys:
        vals = np.array([p[key] for p in pts])
        if np.std(vals) < 1e-10:
            continue

        # For metrics where LOWER = more dispersed (coherent_frac) or HIGHER = more noise
        if key in ['coherent_frac_850']:
            # LOW = structure breaking down; use 80% of peak (drop TO 80%)
            threshold = vals[0] * 0.8
            cross_idx = np.argmax(vals < threshold) if (vals < threshold).any() else -1
            direction = '↓'
        else:
            # HIGH = more noise; use 120% of initial (rise TO 120%)
            threshold = abs(vals[0]) * 1.2 if vals[0] != 0 else 1.0
            cross_idx = np.argmax(vals > threshold) if (vals > threshold).any() else -1
            direction = '↑'

        if cross_idx > 0:
            lead_lag = (wind_80_idx - cross_idx) * 6 if wind_80_idx > 0 else '?'
            lead_str = f"lead wind {abs(lead_lag)}h" if isinstance(lead_lag, int) and lead_lag > 0 else \
                       f"lag wind {abs(lead_lag)}h" if isinstance(lead_lag, int) and lead_lag < 0 else 'same'
            # Only print if it's an interesting lead
            if isinstance(lead_lag, int) and lead_lag > 0:
                print(f"    {key:<25} {direction} @ t+{cross_idx*6}h  {'🔥 LEAD' if lead_lag >= 6 else ''}")

    # Pooled correlations: noise metrics vs wind
    print(f"    --- pooled correlations ---")
    for key in noise_keys:
        vals = np.array([p[key] for p in pts])
        if np.std(vals) < 1e-10:
            continue
        r_v, p_v = stats.pearsonr(winds, vals)
        label = '🔥' if p_v < 0.05 else ''
        print(f"    wind×{key:<22} r={r_v:+.3f} p={p_v:.3f} {label}")

    # Key test: noise_rms vs H_core correlation (should be negative)
    noise_rms = np.array([p['noise_rms_850'] for p in pts])
    hcores = np.array([p['H_core'] for p in pts])
    r_nh, p_nh = stats.pearsonr(noise_rms, hcores)
    print(f"    noise_rms×H_core: r={r_nh:+.3f} p={p_nh:.3f}")


# Pooled across all storms
print(f"\n{'═'*70}")
print(f"  POOLED ALL STORMS (n={len(results)})")
print(f"{'═'*70}")
all_winds = np.array([r['wind_kt'] for r in results])
for key in noise_keys + ['theta1_deg', 'H_core']:
    vals = np.array([r[key] for r in results])
    r_v, p_v = stats.pearsonr(all_winds, vals)
    label = '🔥' if p_v < 0.01 else ''
    print(f"  wind×{key:<22} r={r_v:+.3f} p={p_v:.4f} {label}")

# Save
out = PROJ_DIR / 'results' / 'wpac_decay_noise_topography.json'
with open(out, 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n  💾 {out}")
