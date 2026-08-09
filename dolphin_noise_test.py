#!/usr/bin/env python3
"""
🐬 Dolphin Noise Test — dH_curl surrogates
============================================
對 Dolphin GFS 數據做兩層雜訊測試：
  1. White noise surrogate — 完全破壞空間結構
  2. Circular shift surrogate — 保留 autocorrelation，破壞 phase alignment

Output: 比較真實 dH_curl 與 surrogate distribution
"""

import json, sys, os
import numpy as np

sys.path.insert(0, '/app/working/workspaces/tygtDc')
from importlib import import_module

# ── 直接 import compute_vorticity 同 compute_dh_curl ──
# 因為 script 係直接 run 嘅，用 exec 方法
exec(open('/app/working/workspaces/tygtDc/dolphin_dhcurl_v8.py').read().split("if __name__")[0])

# ── 設定 ──
GRIB_FILE = "/app/working/workspaces/tygtDc/gfs_20260730_00_u850_v850.grib2"
CORE_DEG = 5.0
SHELL_DEG = 10.0
N_SURROGATES = 500
CENTER_LAT = 16.25
CENTER_LON = 165.75
SEED = 42

np.random.seed(SEED)

# ── Load data ──
print("📂 Loading GFS data...")
data, err = read_eccodes(GRIB_FILE)
if data is None:
    print(f"❌ eccodes: {err}")
    sys.exit(1)

u = data['u']
v = data['v']
g = data['grid']
print(f"  Grid: {g['Ni']}×{g['Nj']}")
print(f"  U: {u.min():.1f}~{u.max():.1f}  V: {v.min():.1f}~{v.max():.1f} m/s")

# ── Real dH_curl ──
print("\n🔵 Computing real dH_curl...")
z_real = compute_vorticity(u, v, g)
r_real = compute_dh_curl(z_real, g, CORE_DEG, SHELL_DEG,
                          lat_hint=CENTER_LAT, lon_hint=CENTER_LON,
                          exact_center=True)
dh_real = r_real['dh_curl']
print(f"  Real dH_curl = {dh_real:.6e} s⁻¹")

# ── 1. White noise surrogate ──
print(f"\n⚪ White noise surrogate ({N_SURROGATES} trials)...")
dh_white = []
for i in range(N_SURROGATES):
    u_surr = np.random.normal(u.mean(), u.std(), u.shape)
    v_surr = np.random.normal(v.mean(), v.std(), v.shape)
    z_surr = compute_vorticity(u_surr, v_surr, g)
    r_surr = compute_dh_curl(z_surr, g, CORE_DEG, SHELL_DEG,
                              lat_hint=CENTER_LAT, lon_hint=CENTER_LON,
                              exact_center=True)
    dh_white.append(r_surr['dh_curl'])
    if (i+1) % 100 == 0:
        print(f"    {i+1}/{N_SURROGATES}")

dh_white = np.array(dh_white)
p_white = np.mean(np.abs(dh_white) >= np.abs(dh_real))
print(f"  White noise: mean={dh_white.mean():.3e}, std={dh_white.std():.3e}")
print(f"  p-value (two-tailed) = {p_white:.4f}")
print(f"  z-score = {(dh_real - dh_white.mean()) / dh_white.std():.1f}σ")

# ── 2. Circular shift surrogate (保留 autocorrelation) ──
print(f"\n🔄 Circular shift surrogate ({N_SURROGATES} trials)...")
dh_shift = []
ny, nx = u.shape
for i in range(N_SURROGATES):
    dx = np.random.randint(0, nx)
    dy = np.random.randint(0, ny)
    u_surr = np.roll(np.roll(u, dx, axis=1), dy, axis=0)
    v_surr = np.roll(np.roll(v, dx, axis=1), dy, axis=0)
    z_surr = compute_vorticity(u_surr, v_surr, g)
    r_surr = compute_dh_curl(z_surr, g, CORE_DEG, SHELL_DEG,
                              lat_hint=CENTER_LAT, lon_hint=CENTER_LON,
                              exact_center=True)
    dh_shift.append(r_surr['dh_curl'])
    if (i+1) % 100 == 0:
        print(f"    {i+1}/{N_SURROGATES}")

dh_shift = np.array(dh_shift)
p_shift = np.mean(np.abs(dh_shift) >= np.abs(dh_real))
print(f"  Circular shift: mean={dh_shift.mean():.3e}, std={dh_shift.std():.3e}")
print(f"  p-value (two-tailed) = {p_shift:.4f}")
print(f"  z-score = {(dh_real - dh_shift.mean()) / dh_shift.std():.1f}σ")

# ── Result ──
print(f"\n{'═'*55}")
print(f"  🐬 DOLPHIN NOISE TEST RESULTS")
print(f"{'═'*55}")
print(f"  Real dH_curl:     {dh_real:.6e} s⁻¹")
print(f"  White noise:      μ={dh_white.mean():.6e}  σ={dh_white.std():.6e}  p={p_white:.4f}")
print(f"  Circular shift:   μ={dh_shift.mean():.6e}  σ={dh_shift.std():.6e}  p={p_shift:.4f}")
print(f"{'═'*55}")

if p_white < 0.05:
    print(f"  ✅ White noise: SIGNIFICANT (signal > white noise)")
else:
    print(f"  ❌ White noise: NOT significant")

if p_shift < 0.05:
    print(f"  ✅ Circular shift: SIGNIFICANT (signal > null model)")
else:
    print(f"  ❌ Circular shift: NOT significant")

print(f"{'═'*55}")
