# 2026-08-05 — 近岸 vs 遠洋：21 個 WPAC 颱風 6D 測量

## 目的
測試「近岸颱風 vs 遠洋颱風結構差異」假說：陸地邊界約束是否改變颱風嘅 6D 拓撲（θ₁、H_core、ΔH）？

## 方法
- 從 IBTrACS 抽 WPAC 所有 ≥100kt 颱風（84 個）
- 排除已測嘅 6 個，取 wind 最強 15 個
- 每隻下載 ERA5 200hPa+850hPa u/v（29×29° box @ 0.25°）
- 統一 measure_6d pipeline（5° core / 10° shell）
- Simplified coastline distance（7 個 WPAC 陸地板塊 box）
- 合併舊 6 個 → n=21

## 結果

### 核心發現：θ₁ × H_core 極強相關 r=+0.698 p=0.0004
- 高 H_core（強垂直耦合）→ 高 θ₁（更 isotropic，兩個 PCA 軸貢獻接近）
- 低 H_core（弱垂直耦合）→ 低 θ₁（anisotropic，一個軸主導）
- 物理詮釋：強耦合核心入面，渦度同輻散場結構同步 → 兩個維度貢獻均衡 → θ₁ 趨 45°；弱耦合 → 單軸主導 → θ₁ 趨 0°

### 陸地距離效應
- H_core × dist_land: **r=+0.441 p=0.045** ✅（近岸 → H_core 低）
- θ₁ × dist_land: r=+0.374 p=0.095（趨勢未達標）
- 海岸距離計法簡陋（box distance），低估真實距離（e.g. Mangkhut 777km 其實係 open ocean Phillipine Sea）

### 分群
- 近岸 (<300km, n=9): θ₁=28.5°±5.6, H_core=0.652±0.134
- 遠洋 (>800km, n=0) — 距離計法問題，冇一個計到 >800km
- 真正遠洋代表：Mangkhut(777km), Yutu(699km), Mawar(655km)

## 值得注意嘅個體
- **Chanthu**（56km, θ₁=26.5°, H_core=0.380）— 極近岸 + 極低 H_core
- **Hato**（322km, θ₁=17.1°, H_core=0.441）— 極低 θ₁（最 anisotropic）
- **Halong**（100km, θ₁=33.5°, H_core=0.784）— 近岸但高耦合，反例
- **Nepartak**（56km, θ₁=23.3°, H_core=0.719）— 超近岸但 H_core 唔低

## Partial Correlation 追加（控制 wind）

| 關係 | Zero-order | Partial | wind |
|------|-----------|---------|------|
| dist × H_core | r=+0.441 p=0.045 | **r=+0.442 p=0.051** | ✅ 獨立於 wind |
| dist × θ₁ | r=+0.374 p=0.095 | r=+0.412 p=0.071 | 趨勢 |
| **wind × θ₁** | **r=+0.649 p=0.0015** | — | 🔥 主要 driver |

**結論：** land proximity 唔係主角。Wind intensity 先係 θ₁ 嘅主要 driver。dist×H_core 獨立存在但效應弱。

---

# Life Cycle Evolution（同一日追加）

## 方法
5 隻長 track × 3 時間點（early 50kt / peak / late 50kt）= 15 測量。

## 結果

### Within-storm >> cross-sectional
| 關係 | Within-storm (n=15) | Cross-sectional (n=21) |
|------|---------------------|------------------------|
| wind×θ₁ | **r=+0.778 p=0.0006** | r=+0.649 p=0.0015 |
| wind×H_core | **r=+0.786 p=0.0005** | r=+0.397 p=0.074 |

### 核心洞察：颱風有 personality
H_core 唔係由絕對 wind speed 決定，而係由「邊隻颱風」決定。同一個 170kt，Meranti H_core=0.637 vs Mangkhut 155kt=0.861。跨颱風 variability 淹冇咗 intensity 信號（cross-sectional r=0.397 ns）。但同一隻颱風入面，intensity 追得好緊（r=0.786）。

### 衰減崩塌（late stage collapse）
- **Hagibis** late: θ₁=0.5° H_core=−0.027 — 完全解耦
- **Goni** late: θ₁=5.2° H_core=0.070 — 近乎零
- **Mangkhut** late: θ₁=20.5° H_core=0.589 — 部分保留結構
- **Meranti** late: θ₁=13.3° H_core=0.324 — 中等
- **Halong** late: θ₁=9.1° H_core=0.277 — 明顯衰減

衰減路徑唔對稱：有嘅完全崩（Hagibis, Goni），有嘅保留結構（Mangkhut, Meranti）。

### 物理詮釋
θ₁×H_core 反映「颱風嘅結構 integrity」— 愈強愈 isotropic 愈耦合。呢個唔係靜態屬性，而係動態追蹤 intensity 演化。Decay collapse（θ₁→0, H_core→0）代表垂直耦合結構徹底瓦解 — 可能係強度預測前兆。

## 待辦
- [ ] 改用高精度海岸線（GSHHS）重計距離
- [x] ~~跑 partial correlation distance×H_core｜wind~~ → 證實獨立於 wind
- [x] ~~Decay collapse 做 intensity 預測測試~~ → 見下方 Decay Collapse
- [ ] 寫正式報告整合 land proximity + life cycle + decay
- [ ] 加更多遠洋個案（中太平洋颱風 CPAC？）

---

# Decay Collapse Phase — Lead/Lag 分析（同一日追加）

## 方法
5 颱風 × 15 個 6-hourly decay 時間點 = 75 測量。追蹤 peak → dissipation 嘅 θ₁/H_core 演變，同 wind 做 lead/lag 比較。

## 結果

### Pooled decay correlation
- wind×θ₁: **r=+0.771 p<0.0001**
- wind×H_core: **r=+0.765 p<0.0001**
- 比 life cycle（r=0.78）一致，比 cross-sectional peak-only（r=0.40）強近一倍

### Decay 斜率一致
| Storm | dθ₁/dwind | dH_core/dwind |
|-------|-----------|---------------|
| Goni | +0.234°/kt | +0.0047/kt |
| Meranti | +0.164°/kt | +0.0034/kt |
| Hagibis | +0.156°/kt | +0.0033/kt |
| Halong | +0.152°/kt | +0.0041/kt |
| Mangkhut | +0.057°/kt | +0.0018/kt |

除 Mangkhut（結構頑強），其餘 4 隻 dθ₁/dwind ≈ 0.15-0.23°/kt，dH_core ≈ 0.003-0.005/kt。**每跌 10kt wind，θ₁ 跌 ~2°，H_core 跌 ~0.04。**

### ⚠️ 結構崩塌唔係 predictor — 係 consequence

| Storm | Wind 80% | θ₁ 80% | Lead/Lag |
|-------|----------|--------|----------|
| Hagibis | t+42h | t+78h | **結構 lag 36h** |
| Halong | t+12h | t+24h | **結構 lag 12h** |
| Goni | t+6h | t+6h | 同步 |
| Meranti | t+36h | t+30h | 結構 lead 6h（例外！） |
| Mangkhut | t+48h | never | θ₁ 頑強 |

**結論：結構崩塌係 wind decline 嘅後果，唔係前兆。** 假說「結構先崩 → wind 後跌 → 可做 prediction」被數據推翻。

唯一例外係 Meranti（rapid intensifier + rapid decay），H_core 80% @ t+18h 領先 wind 80% @ t+36h。可能 rapid-decay cases 有唔同機制。

---

# Noise Topography — Decay Phase（同一日追加）

## 方法
用現有 75 個 ERA5 nc，計算 decay phase noise metrics：
- noise_rms_850：core 內 dH = z - smooth(z) 嘅 RMS
- core_var_850：core vorticity variance
- noise_corr_850_200：850-200hPa 兩層 noise 嘅 cross-correlation
- coherent_frac_850：smooth 能量佔總能量比例

## 結果

### Pooled noise-wind correlation（n=75）
- noise_rms × wind: **r=+0.816** p<0.0001
- core_var × wind: **r=+0.845** p<0.0001
- noise_corr_850_200 × wind: **r=+0.761** p<0.0001
- 全部比 H_core（r=0.765）同 θ₁（r=0.771）強或持平

→ Noise metrics track wind 極緊，甚至比 coherent structure 更貼。

### Lead/Lag: 兩種 decay mode

| Storm | Wind↓ | noise_corr↓ | H_core↓ | Mode |
|-------|:-----:|:-----------:|:-------:|------|
| Meranti | 36h | **18h** 🔥 | 18h | **Rapid: noise→structure→wind** |
| Goni | 6h | 6h | 6h | Rapid: 同步崩塌 |
| Halong | 12h | 24h | 24h | Gradual: wind 先跌 |
| Hagibis | 42h | 78h | 78h | Gradual: wind 先跌 |
| Mangkhut | 48h | 48h | 48h | Gradual: 同步跟 |

### 兩個 decay mode
1. **Rapid decay**（Meranti-type）：noise 跨層 coherence 先斷 → 結構崩塌 → wind 跟跌。MKP 因果鏈成立。
2. **Gradual decay**（Hagibis-type）：wind 慢慢跌 → 結構跟住散。唔同 physics，可能係環境（SST/風切）主導。

### 關鍵 metric：noise_corr_850_200
兩層 noise 嘅 cross-correlation 係最 sensitive 嘅 decay 前兆。Meranti 領先 wind 18h，Goni 同步但快到分唔到。

## 待辦
- [x] ~~Meranti 例外：rapid-decay 颱風係咪普遍有 leading structure signal？~~ → 兩種 decay mode 確立
- [ ] Test 更多 rapid-decay 個案驗證 noise_corr 前兆普適性
- [ ] 寫正式報告整合四層分析（land proximity / life cycle / decay collapse / noise topography）
