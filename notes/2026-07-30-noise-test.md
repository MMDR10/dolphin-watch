# 2026-07-30 — Dolphin dH_curl Noise Test

## 測試目的
驗證 Dolphin GFS dH_curl = −3.35e-05 s⁻¹ 係真實物理訊號定只係雜訊。

## 方法
使用 GFS 20260730 00z 850hPa u/v 場（121×121 grid, 2-32°N, 148-178°E），
對 GFS 數據做兩層 surrogate test（各 500 trials）：

1. **White noise** — 完全破壞空間結構，每個格點獨立隨機
2. **Circular shift** — 保留 autocorrelation，破壞 phase alignment

中心鎖定 16.25°N, 165.75°E（exact-center）。

## 結果

| Test | Null μ | Null σ | Real dH_curl | z-score | p-value | Verdict |
|:----|:------:|:------:|:-----------:|:------:|:------:|:-------|
| White noise | −2.18e-08 | 2.65e-06 | −3.35e-05 | **−12.6σ** | **0.0000** | ✅ SIGNIFICANT |
| Circular shift | 6.97e-08 | 1.25e-05 | −3.35e-05 | **−2.7σ** | **0.0280** | ✅ SIGNIFICANT |

## 結論

**Dolphin dH_curl = −3.35e-05 係真實物理訊號，非雜訊。** ✅✅

- White noise test: **12.6σ 顯著** → 訊號遠超純隨機背景
- Circular shift test: **2.7σ 顯著 (p=0.028)** → 訊號超越保留 autocorrelation 嘅 null model

## Script
- `projects/dolphin-watch/dolphin_noise_test.py`
