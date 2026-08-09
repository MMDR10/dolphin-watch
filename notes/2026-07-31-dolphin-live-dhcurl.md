# 2026-07-31 — Dolphin Live dH_curl (GFS 00z)

## 背景
Typhoon Dolphin 持續為 Super Typhoon（~140 kts）。上次測量 7/30 00z 得 −3.35e-05。
今日用返 **v8 物理 helicity 引擎**（`dolphin_dhcurl_v8.py`，git d5f4e0af 恢復）測量。

> ⚠️ 早前誤用 pyc engine（normalized co-occurrence helicity）測出 0 值 — 尺度同 v8 唔可比，
> 已棄用該結果（dhcurl_result_20260731.json 為 pyc 假結果，勿用）。

## 今日測量

| 參數 | 值 |
|:-----|:---|
| 數據源 | GFS 0.25° 2026-07-31 00z |
| 中心 | 18.25°N, 162.00°E（auto-detect from max vorticity） |
| Protocol | Core=5°, Shell=10° |
| **dH_curl** | **−3.99e-05 s⁻¹** |
| H_core | 4.506e-05 (n=1327) |
| H_shell | 5.15e-06 (n=3988) |
| 分類 | 中性/過渡（GFS 尺度下） |

## 時間序列對比（5°/10° protocol）

| 日期 | 數據源 | 強度 | 中心 | dH_curl |
|:----|:------|:-----|:----|:-------|
| 7/24 12Z | ERA5 | TS (55 kts) | 16.5°N, 166.5°E | −9.51e-06 |
| 7/29 06Z | GFS | STS/TY (~85 kts) | ~14.5°N, ~168°E | −2.40e-05 |
| 7/30 00Z | GFS | Super TY (~130 kts) | 16.25°N, 165.75°E | −3.35e-05 |
| 7/31 00Z | GFS | Super TY (~140 kts) | 18.25°N, 162.00°E | −3.99e-05 |
| **7/31 06Z** | **GFS (自動)** | **Super TY (~140 kts)** | **18.75°N, 161.00°E** | **−4.49e-05** |

## 發現
1. **dH_curl 持續加深 4.7×**：−9.51e-06 → −4.49e-05（7/24→7/31 06z），每日穩步加深
2. **7/31 06z 已達 GFS 飽和平台**：−4.49e-05 已超過之前標定嘅 Cat3-5 飽和平台（−4.4e-05），GFS 可能已無法分辨實際強度提升
3. **中心持續西北移動**：16.25°N → 18.75°N, 165.75°E → 161.00°E，符合颱風路徑

## 🤖 自動化升級（2026-07-31 10:07 UTC 生效）
- **v8 GFS 引擎入 repo**：`dolphin_dhcurl_v8.py` 已 commit（由 git d5f4e0af 恢復）
- **Workflow 升級**：`dhcurl_track.yml` 每 6h 自動跑，**GFS v8 優先**（即時），失敗 fallback ERA5 CDS（5-day latency）
- 自動中心 hint：從 `dhcurl_history.json` 最新 record 攞
- **Push retry**：5 次 retry（處理多 workflow 同時 push 嘅 non-fast-forward 衝突）
- 7/31 06z 係第一個全自動 GFS 結果（commit 34005a5）✅
- **歷史 backfill**：7/29-7/31 共 4 條 GFS 記錄已入 `dhcurl_history.json`（commit f816eea）

## Script
- `dolphin_dhcurl_v8.py` (v8 FINAL, GFS eccodes engine) — git d5f4e0af 恢復 + 已入 GitHub repo
- Output: `dhcurl_result_20260731_v8.json`（手動 00z）、`dhcurl_result.json`（自動 06z）

## GitHub
- Repo: `MMDR10/dolphin-watch`
- **Action needed**: 推 7/31 dH_curl result 上 GitHub? (需 MKP 確認)
