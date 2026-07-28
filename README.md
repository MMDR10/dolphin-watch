# 🐬 Dolphin Watch — Noise Topography 實時驗證

**Typhoon Dolphin (12W)** 的 Noise Topography 預測 vs JTWC 實況自動追蹤儀表板。

## 🌐 一鍵直達

👉 **[mmdr10.github.io/dolphin-watch](https://mmdr10.github.io/dolphin-watch)**

## 🔬 Noise Topography 預測

| 層級 | 狀態 | 意義 |
|------|------|------|
| Z1 阻尼 | 蒸發 | 無阻尼 → RI 無阻 |
| Z2 蛇形 | 鎖定 | 路徑幾何鎖死 → 穩定增強 |
| Z3 脆性 | 脆性 | 結構脆化 → 爆發式重組 |
| **三層疊加** | **極端風險區** | Z1∩Z2∩Z3 重疊 |
| **預測巔峰** | **≥280 km/h** | 可能超越 Cat 5 |
| **0-Lag RI** | **Active** | 快速增強進行中 |

## 🛰️ 數據來源

- **JTWC** 公告（WTPN31）經由 [cyclocane.com](https://www.cyclocane.com/dolphin-storm-tracker)
- 每 6 小時自動更新（GitHub Actions cron @ 0330/0930/1530/2130 UTC）

## 📊 Dashboard 內容

- 💨 實時風速 + 級別
- 🔬 NT 預測 vs JTWC 偏差（Δ km/h）
- 📈 強度預測走勢圖
- 🕐 JTWC 預測路徑時間線
- 📋 完整 Advisory 記錄

## 🐙 GitHub

- **Repo**: [MMDR10/dolphin-watch](https://github.com/MMDR10/dolphin-watch)
- **Actions**: [自動更新運行狀態](https://github.com/MMDR10/dolphin-watch/actions)
- **Pages**: [mmdr10.github.io/dolphin-watch](https://mmdr10.github.io/dolphin-watch)

---

*Noise Topography 方法：Ô-HAT Core-Shell Helicity Decomposition + Multi-Scale Δ²H + dH_curl U-Shape Detection*
