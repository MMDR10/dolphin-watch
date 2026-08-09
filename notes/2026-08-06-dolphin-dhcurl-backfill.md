# 🐬 Dolphin dH_curl Backfill — 2026-08-06

**事件：** MKP 問「今日上github收集颱風海豚數據測量記錄未？」

**操作：** git pull → 攞到 3 個新 dH_curl 自動 commit（8/5 07:48 → 8/6 07:48 UTC）→ backfill 入 `dhcurl_history.json`（15→**18 條**）→ push `2911548`

---

## 📊 新增 3 條記錄

| 時間 | dH_curl | 中心 | mode |
|------|---------|------|------|
| 8/5 00z | **−3.19e-05** | 18.0N 164.75E | ⚪ Neutral/Transitional |
| 8/5 12z | −1.08e-05 | 15.75N 162.25E | ⚪ Neutral/Transitional |
| 8/6 00z | −1.87e-05 | 14.75N 158.75E | ⚪ Neutral/Transitional |

---

## 🔍 完整趨勢（18 條，7/24 → 8/6）

| 階段 | 日期範圍 | dH_curl 範圍 | 特徵 |
|------|----------|-------------|------|
| ⬜ Pre-intensification | 7/24–7/26 | +8.5e-06 ~ −4.8e-06 | 接近零，未組織 |
| 🟡 Intensification | 7/29–7/31 | −2.4e-05 ~ −3.99e-05 | 4.2× 加深 |
| 🔴 PEAK | 8/1–8/2 00z | −4.52e-05 ~ **−5.49e-05** | 達飽和平台 +25%，11.4× vs 7/24 |
| 🟢 Decay | 8/2 06z–8/6 00z | −4.60e-06 ~ −3.19e-05 | 急跌後低位波動 |

---

## 🐬 Dolphin 現狀

- **JTWC Warning #41** (8/6 07:28 UTC)：Cat 1，80 kts，943 mb
- 位置：26.2N 133.5E，向 W (265°) 以 13 kts 移動
- dH_curl 已離開飽和平台（−4.4e-05），現於 −1~−2×10⁻⁵ 波動
- 中心路徑有回折跡象：21.5N peak → 14.75N now → 26.2N (JTWC)

---

## 🔧 操作備註

- `dhcurl_history.json` 仍靠**手動 backfill**，workflow 只更新 `dhcurl_result.json`
- 建議：加 auto-merge step 入 `dhcurl_track.yml` 免手動
- Commit `0081b31`（8/5 00z）嘅 commit message 寫 v8=−3.68e-05 但 `dhcurl_result.json` 係 −3.19e-05 — 可能係 message 手寫誤差或 6D vs v8 差異
