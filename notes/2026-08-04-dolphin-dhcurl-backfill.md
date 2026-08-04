# 2026-08-04 — Dolphin dH_curl 自動記錄收集 + History Backfill

## 背景
Typhoon Dolphin (12W) 由 7/31 起全自動測量（GitHub Actions `dhcurl_track.yml` 每 6h 跑，
GFS v8 優先）。本地 `dhcurl_history.json` 停喺 8/1（8 條）— workflow 只更新
`dhcurl_result.json` + `dashboard_data.json`，history 需手動 backfill（已知限制）。

## 今日操作（MKP「今日上GITHUB收集海豚資料測量記錄未」）

1. `git pull`（ab58f86..c64373a，8 個自動 commit，8/1 18:47 → 8/4 07:47 UTC）
2. 逐 commit 還原 `dhcurl_result.json` → 攞返 8/1 之後 **7 條新測量**
3. Backfill 入 `dhcurl_history.json`（8 → **15 條**，按 timestamp 排序）
4. Push（commit `903687b`）

## 完整時間序列（15 條，5°/10° protocol）

| 時間 | dH_curl | 中心 | 來源 | 階段 |
|:-----|:--------|:-----|:-----|:-----|
| 7/24 18z | −4.83e-06 | 15.75N 166.0E | ERA5/auto | TS |
| 7/25 06z | +8.47e-06 | 12.5N 168.75E | auto | 弱 |
| 7/26 06z | +4.22e-06 | 16.5N 166.5E | auto | 弱 |
| 7/29 00z | −2.56e-05 | 14.25N 168.75E | GFS | 增強 |
| 7/29 12z | −2.40e-05 | 14.75N 168.0E | GFS | 增強 |
| 7/30 06z | −3.35e-05 | 16.25N 165.75E | GFS | Super TY |
| 7/31 00z | −3.99e-05 | 18.25N 162.0E | GFS | Super TY |
| 8/1 00z | −4.52e-05 | 20.5N 159.0E | auto | Super TY Cat 5 |
| **8/1 12z** | **−5.23e-05** | 21.25N 156.0E | auto | **新深** |
| **8/2 00z** | **−5.49e-05** 🔴 | 21.25N 156.0E | auto | **史上最深** |
| 8/2 06z | −1.44e-05 | 22.0N 157.5E | auto | 急劇減弱 |
| 8/2 12z | −4.60e-06 | 18.5N 161.5E | auto | 回折 |
| 8/3 06z | −1.17e-05 | 19.0N 160.25E | auto | 弱 |
| 8/3 12z | −4.13e-06 | 20.0N 157.25E | auto | 最淺 |
| 8/4 00z | −2.04e-05 | 17.5N 161.75E | auto | 最新 |

## 發現

1. **峰值 8/2 00z −5.49e-05**：7/24→8/2 dH_curl 加深 **11.4×**（−4.83e-06 → −5.49e-05），
   超過 GFS Cat3-5 飽和平台（−4.4e-05）**25%** — 反映颱風喺 8/1-8/2 維持極強
   （JTWC 140 kts / 919 mb 後續）
2. **8/2 06z 起急劇減弱**：−5.49e-05 → −1.44e-05（−74% 喺 6 小時內）→ 回落至
   −4e-06 ~ −2e-05 量級；8/2 12z 中心由 22.0N 回折至 18.5N 161.5E
3. **中心路徑 8/2 後有回折跡象**：22.0N 157.5E → 18.5N 161.5E → 17.5N 161.75E，
   同 8/4 dashboard（Super TY Cat 5、warning 14）對照 — 颱風減弱/結構轉變階段
4. **8/4 00z 回升至 −2.04e-05**：仍屬負值（凝聚結構），但已離開飽和平台

## 操作教訓
- `dhcurl_history.json` 仍靠手動 backfill（workflow 只更新 `dhcurl_result.json`）
- 下次可考慮 workflow 加自動 merge history step（`merge_gfs_history.py` 已存在但未入 workflow）

## GitHub
- Repo: `MMDR10/dolphin-watch`
- Backfill commit: `903687b`（15 條完整序列已 push）
- 自動測量繼續（下次約 8/4 12z-18z UTC）
