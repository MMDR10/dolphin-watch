# 2026-07-30 — Dolphin Live dH_curl (GFS 00z)

## 背景
Typhoon Dolphin 正喺西太平洋活躍。7/28 成 Cat 4，7/29 達 Super Typhoon。
最後一次 Ô-HAT 測量係 7/24（ERA5）。

## 今日測量

| 參數 | 值 |
|:-----|:---|
| 數據源 | GFS 0.25° 2026-07-30 00z |
| 中心 | 16.25°N, 165.75°E（auto-detect from max vorticity） |
| Protocol | Core=5°, Shell=10° |
| **dH_curl** | **−3.35e-05 s⁻¹** |
| H_core | 4.085e-05 (n=1307) |
| H_shell | 7.35e-06 (n=3946) |
| 分類 | 中性/過渡（GFS 尺度下） |

## 時間序列對比（5°/10° protocol）

| 日期 | 數據源 | 強度 | 中心 | dH_curl |
|:----|:------|:-----|:----|:-------|
| 7/24 12Z | ERA5 | TS (55 kts) | 16.5°N, 166.5°E | −9.51e-06 |
| 7/29 06Z | GFS | STS/TY (~85 kts) | ~14.5°N, ~168°E | −2.40e-05 |
| **7/30 00Z** | **GFS** | **Super TY (~130 kts)** | **16.25°N, 165.75°E** | **−3.35e-05** |

## 發現
1. **dH_curl 加深 3.5×**：−9.51e-06 → −3.35e-05，同 RI 一致
2. **Core 組織**：H_core=4.085e-05 遠超 H_shell=7.35e-06，典型成熟 TC
3. **GFS saturation 注意**：−3.35e-05 接近 GFS 0.25° Cat3-5 飽和平台（−4.4e-05），可能低估實際強度

## Script
- `dolphin_dhcurl_v8.py` (v8 FINAL, GFS eccodes engine)
- `cds_dhcurl.py` (ERA5 CDS, 5-day latency)

## GitHub
- Repo: `MMDR10/dolphin-watch`
- Last GH Action: 7/29 15:01 UTC (auto-update)
- Last dH_curl commit: c175e74 (歷史累積記錄)
- **Action needed**: 推新 dH_curl result 上 GitHub? (需 MKP 確認)
