#!/usr/bin/env python3
"""WPAC 6 颱風 6D 跨驗證 — 統計整合"""
import json, numpy as np
from scipy import stats

d = json.load(open('/tmp/typhoon_6d/era5/wpac6_6d_results.json'))
storms = ['HATO','MANGKHUT','SAOLA','MERANTI','HAGIBIS','GONI']
rows = {s: d[s] for s in storms if 'error' not in d[s]}

print(f"{'颱風':<10}{'θ₁':>7}{'χ_eff':>8}{'H_core':>8}{'ΔH':>8}{'D₁':>7}")
for s in storms:
    r = rows[s]
    print(f"{s:<10}{r['theta1_deg']:>7.1f}{r['chi_eff_core']:>8.1f}{r['H_core']:>8.3f}{r['dH']:>8.3f}{r['D1']:>7.1f}")

t = np.array([rows[s]['theta1_deg'] for s in storms])
hc = np.array([rows[s]['H_core'] for s in storms])
dh = np.array([rows[s]['dH'] for s in storms])
d1 = np.array([rows[s]['D1'] for s in storms])

print(f"\n=== 統計 ===")
print(f"θ₁:   median={np.median(t):.1f}°  range=[{t.min():.1f}, {t.max():.1f}]")
print(f"H_core: median={np.median(hc):.3f}  range=[{hc.min():.3f}, {hc.max():.3f}]  (全部 >0: {np.all(hc>0)})")
print(f"ΔH:   median={np.median(dh):.3f}  (全部 >0: {np.all(dh>0)})  binomial p={(0.5)**6:.4f}")
print(f"D₁:   median={np.median(d1):.1f}  range=[{d1.min():.1f}, {d1.max():.1f}]")

# 同 Dolphin 強颱風期對比
dolphin_t = np.array([28.38, 27.70])
dolphin_hc = np.array([0.849, 0.793])
print(f"\n=== vs Dolphin 強颱風期 ===")
print(f"θ₁:   Dolphin median={np.median(dolphin_t):.1f}° vs WPAC6 median={np.median(t):.1f}°")
print(f"H_core: Dolphin median={np.median(dolphin_hc):.3f} vs WPAC6 median={np.median(hc):.3f}")

# 全部 8 個強颱風時點合併
all_t = np.concatenate([t, dolphin_t])
all_hc = np.concatenate([hc, dolphin_hc])
print(f"\n=== 合併 N=8 強颱風時點 ===")
print(f"θ₁:   median={np.median(all_t):.1f}°  CI95≈[{np.percentile(all_t,2.5):.1f}, {np.percentile(all_t,97.5):.1f}]")
print(f"H_core: median={np.median(all_hc):.3f}  (8/8 > 0: {np.all(all_hc>0)})  binomial p={(0.5)**8:.5f}")
