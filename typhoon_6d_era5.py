#!/usr/bin/env python3
"""
🌀 WPAC 6 颱風 6D 跨驗證 — ERA5 下載 + 測量
============================================
用 CDS ERA5 下載 6 颱風峰值時點嘅 850+200 hPa U/V，然後用 6D 框架測量。

峰值時點（IBTrACS WMO_WIND max）：
  HATO     2017-08-23 00:00  21.5N 114.5E
  MANGKHUT 2018-09-11 12:00  13.7N 138.7E
  SAOLA    2023-08-30 00:00  20.1N 121.0E
  MERANTI  2016-09-13 12:00  20.4N 122.9E
  HAGIBIS  2019-10-07 12:00  16.1N 146.6E
  GONI     2020-10-31 18:00  13.7N 125.0E

Usage:
  python typhoon_6d_era5.py --all            # 全部 6 個
  python typhoon_6d_era5.py --storm MANGKHUT # 單個
"""
import sys, json, os, math
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from typhoon_6d_measure import measure_6d, CORE_DEG, SHELL_DEG

STORMS = {
    'HATO':     dict(date='2017-08-23', hour=0,  lat=21.5, lon=114.5),
    'MANGKHUT': dict(date='2018-09-11', hour=12, lat=13.7, lon=138.7),
    'SAOLA':    dict(date='2023-08-30', hour=0,  lat=20.1, lon=121.0),
    'MERANTI':  dict(date='2016-09-13', hour=12, lat=20.4, lon=122.9),
    'HAGIBIS':  dict(date='2019-10-07', hour=12, lat=16.1, lon=146.6),
    'GONI':     dict(date='2020-10-31', hour=18, lat=13.7, lon=125.0),
}

OUT_DIR = Path('/tmp/typhoon_6d/era5')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def download_era5_dual(storm, cfg):
    """CDS ERA5 下載 850+200 hPa u/v，單一時點"""
    import cdsapi
    out = OUT_DIR / f'{storm.lower()}_{cfg["date"].replace("-","")}_era5.nc'
    if out.exists():
        return str(out), None
    c = cdsapi.Client()
    yr = int(cfg['date'][:4])
    mo = int(cfg['date'][5:7])
    dy = int(cfg['date'][8:10])
    hh = cfg['hour']
    # 0.25° 窗口：中心 ±15°
    try:
        c.retrieve(
            'reanalysis-era5-single-levels',
            {
                'product_type': 'reanalysis',
                'variable': ['10m_u_component_of_wind', '10m_v_component_of_wind'],
                'year': str(yr), 'month': f'{mo:02d}', 'day': f'{dy:02d}',
                'time': f'{hh:02d}:00',
                'area': [cfg['lat']+15, cfg['lon']-15, cfg['lat']-15, cfg['lon']+15],
                'format': 'netcdf',
            },
            str(out))
    except Exception as e:
        return None, f'ERA5 single-levels 失敗: {e}'
    return str(out), None


def download_era5_pressure(storm, cfg):
    """CDS ERA5 壓力層（850/200 hPa）u/v"""
    import cdsapi
    out = OUT_DIR / f'{storm.lower()}_{cfg["date"].replace("-","")}_pl.nc'
    if out.exists():
        return str(out), None
    c = cdsapi.Client()
    yr = int(cfg['date'][:4])
    mo = int(cfg['date'][5:7])
    dy = int(cfg['date'][8:10])
    hh = cfg['hour']
    try:
        c.retrieve(
            'reanalysis-era5-pressure-levels',
            {
                'product_type': 'reanalysis',
                'variable': ['u_component_of_wind', 'v_component_of_wind'],
                'pressure_level': ['850', '200'],
                'year': str(yr), 'month': f'{mo:02d}', 'day': f'{dy:02d}',
                'time': f'{hh:02d}:00',
                'area': [cfg['lat']+15, cfg['lon']-15, cfg['lat']-15, cfg['lon']+15],
                'format': 'netcdf',
            },
            str(out))
    except Exception as e:
        return None, f'ERA5 pressure-levels 失敗: {e}'
    return str(out), None


def load_era5_dual(nc_path):
    """讀 ERA5 pressure-levels netCDF → measure_6d 格式"""
    import xarray as xr
    ds = xr.open_dataset(nc_path)
    # 維度名可能係 pressure_level 或 level
    lvl_dim = 'pressure_level' if 'pressure_level' in ds.dims else 'level'
    u850 = ds['u'].sel({lvl_dim: 850}).values.squeeze()
    v850 = ds['v'].sel({lvl_dim: 850}).values.squeeze()
    u200 = ds['u'].sel({lvl_dim: 200}).values.squeeze()
    v200 = ds['v'].sel({lvl_dim: 200}).values.squeeze()
    lat = ds['latitude'].values
    lon = ds['longitude'].values
    grid = {
        'Ni': len(lon), 'Nj': len(lat),
        'lat1': float(lat[0]), 'lat2': float(lat[-1]),
        'lon1': float(lon[0]), 'lon2': float(lon[-1]),
        'di': float(abs(lon[1]-lon[0])), 'dj': float(abs(lat[1]-lat[0])),
    }
    ds.close()
    return {'u850': u850, 'v850': v850, 'u200': u200, 'v200': v200, 'grid': grid}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--storm', default=None)
    args = ap.parse_args()

    if args.storm:
        targets = {args.storm.upper(): STORMS[args.storm.upper()]}
    else:
        targets = STORMS

    results = {}
    for storm, cfg in targets.items():
        print(f"\n{'═'*50}\n  🌀 {storm} ({cfg['date']} {cfg['hour']:02d}z @ {cfg['lat']}N {cfg['lon']}E)\n{'═'*50}")
        nc_path, err = download_era5_pressure(storm, cfg)
        if err or not nc_path:
            print(f"  ❌ 下載失敗: {err}")
            results[storm] = {'error': err}
            continue
        print(f"  📂 {nc_path}")
        try:
            data = load_era5_dual(nc_path)
            print(f"  網格: {data['grid']['Ni']}×{data['grid']['Nj']}")
            r = measure_6d(data, cfg['lat'], cfg['lon'], CORE_DEG, SHELL_DEG,
                           exact_center=True)
            r['storm'] = storm
            r['peak_time'] = f"{cfg['date']} {cfg['hour']:02d}:00"
            results[storm] = r
            print(f"  dH_curl={r['dH_curl']:.3e}  θ₁={r['theta1_deg']:.2f}°  "
                  f"χ_eff_core={r['chi_eff_core']:.1f}  H_core={r['H_core']:.3f}  "
                  f"ΔH={r['dH']:.3f}  D₁={r['D1']:.1f}")
        except Exception as e:
            print(f"  ❌ 測量失敗: {e}")
            results[storm] = {'error': str(e)}

    out = OUT_DIR / 'wpac6_6d_results.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 {out}")


if __name__ == '__main__':
    main()
