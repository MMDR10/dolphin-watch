# WPAC 6 Typhoons — 6D Full-Vector Cross-Validation

**日期：** 2026-08-05
**狀態：** ✅ 6/6 完成
**Script：** `projects/dolphin-watch/typhoon_6d_batch.py`
**數據源：** CDS ERA5 reanalysis, 0.25° pressure-level (850+200 hPa U/V)
**Output：** `projects/dolphin-watch/results/wpac6_6d_summary.json`

---

## 背景

Dolphin (2026) 單颱風 6D pilot 完成後（8/4），跨颱風驗證 WPAC 6 颱風峰值時刻，將 θ₁/H_core 由「單一信源」升格做「跨颱風通則」。

## 方法

- 每個颱風取 IBTrACS 峰值風速時刻（USA_WIND max）
- CDS ERA5 下載 850+200 hPa U/V，30°×30° domain（~120×120 格點，0.25°）
- 6D 測量：dH_curl / θ₁ / χ_eff / H_global + H_core + H_shell + ΔH / D₁
- Core=5°, Shell=10°, 中心用 IBTrACS 位置

## 颱風峰值資訊

| Storm | Peak Time | Lat | Lon | Wind | Basin Position |
|-------|-----------|----:|----:|:----:|:---|
| MERANTI | 2016-09-13 12z | 20.4°N | 122.9°E | 170kt | Luzon Strait |
| HATO | 2017-08-23 03z | 21.9°N | 113.7°E | 100kt | South China coast |
| MANGKHUT | 2018-09-12 06z | 14.0°N | 135.2°E | 155kt | Philippine Sea (open) |
| HAGIBIS | 2019-10-07 10z | 15.9°N | 147.1°E | 160kt | NW Pacific (open) |
| GONI | 2020-10-31 18z | 13.7°N | 125.0°E | 170kt | Philippine Sea |
| SAOLA | 2023-08-29 18z | 19.9°N | 121.9°E | 140kt | Luzon Strait |

## 結果

### 6D 全向量表

| Storm | dH_curl | θ₁ | H_core | H_global | ΔH | D₁ | Wind |
|-------|:-------:|:--:|:------:|:--------:|:--:|:--:|:----:|
| DOLPHIN* | −5.50e-05 | 27.7° | 0.793 | — | +0.629 | 178.8 | (Cat5) |
| MERANTI | −4.30e-05 | 29.2° | 0.637 | 0.269 | +0.562 | 43.9 | 170kt |
| HATO | −3.55e-05 | **17.1°** | 0.441 | 0.165 | +0.404 | 14.4 | 100kt |
| MANGKHUT | −4.52e-05 | 34.1° | **0.861** | **0.496** | +0.697 | **184.1** | 155kt |
| HAGIBIS | −5.55e-05 | 28.8° | 0.655 | 0.361 | +0.687 | 45.5 | 160kt |
| GONI | −2.21e-05 | **36.6°** | 0.738 | 0.304 | +0.728 | 84.4 | 170kt |
| SAOLA | −2.84e-05 | **17.1°** | 0.541 | 0.159 | +0.525 | 29.0 | 140kt |

*Dolphin 用 GFS NOMADS（非 ERA5），只列作參考

### 核心發現

#### 1. θ₁：17.1°–36.6°，全部部分有序 ✅ NEW

- 全部 6 颱風 θ₁ 遠低於 random 55°，確認颱風係**部分有序結構**
- ENSO θ₁=9.8°（高度有序）> 颱風 ~17-37°（中等有序）> random 55°
- **Hato/Saola 最低 ~17°**，Goni 最高 36.6°
- Hato/Saola 兩個近岸颱風 θ₁ 最低 → 可能反映 land interaction 令結構更有序（非隨機）

#### 2. H_core：全部正、0.44–0.86 ✅ NEW 跨颱風通則

- 全部 6 颱風 H_core > 0.4，確認 850/200 核心垂直耦合係強颱風通用特徵
- Mangkhut 最高 0.86，Hato 最低 0.44
- ΔH 全部正（0.40–0.73）：全部 Core-organized
- H_core 同峰值風速**非簡單線性**：Mangkhut 155kt H_core=0.86 > Goni 170kt H_core=0.74

#### 3. dH_curl：全部負（−2.2 ~ −5.5e-05）

- 全部 6 颱風 dH_curl < 0，同 Dolphin v8 一致（強颱風 Shell > Core 渦度）
- Hagibis −5.55e-05 最強，Goni −2.21e-05 最弱
- Goni dH_curl 弱可能反映快速移動（or 峰值位置非最大渦度梯度點）

#### 4. 近岸 vs 遠洋 pattern

| Group | θ₁ | H_core | H_global | Members |
|-------|:--:|:------:|:--------:|---------|
| 近岸 (<125°E) | **17.1°** | **0.44–0.54** | **0.16–0.27** | Hato, Saola, (Meranti) |
| 遠洋 (>130°E) | 28.8–36.6° | 0.66–0.86 | 0.30–0.50 | Mangkhut, Hagibis |
| Meranti (mixed) | 29.2° | 0.64 | 0.27 | Luzon Strait |

近岸颱風 θ₁ 低（更有序？）、H_core 低（垂直耦合弱）→ 可能陸地干擾破壞垂直結構但同時約束水平結構。樣本太少（n=2–3），未達統計顯著。

#### 5. D₁ 單快照：14–184，wide spread

- D₁ = Var(c⁺)/Mean(c⁺)，反映正耦合區碎裂度
- Mangkhut 184（爆炸性碎裂），Hato 15（compact）
- **注意**：呢個係單快照 D₁，唔係文檔 Cascade Ratio；跨颱風比較時 H_core 更可靠

---

## 討論

- **H_core 已升格為跨颱風通則** ✅：6/6 WPAC 颱風峰值 H_core > 0.4，ΔH 全部正 → Core-organized 係強颱風通用結構
- **θ₁ ~17-37° 確認颱風域定位**：介乎 ENSO (9.8°) 同 random (55°) 之間，符合物理（颱風 = 局部組織 vs ENSO = basin-scale 有序）
- **近岸 vs 遠洋差異**值得追：Hato/Saola 兩個近岸颱風 θ₁ 最低（17°），但 H_core 亦最低（0.44-0.54）。可能係陸地同時破壞垂直耦合（H_core↓）但約束水平結構（θ₁↓）
- χ_eff 跨颱風仍然唔穩定（36–217），確認 Dolphin pilot 結論：颱風域 χ_eff 定義需重新設計
- 限制：ERA5 vs GFS 產品差異（Dolphin 用 GFS），每個颱風只用一個時次（峰值），Core=5° 固定半徑未做敏感度

---

## 結論

> **H_core 跨颱風通則成立：6/6 WPAC 颱風峰值 H_core > 0.4，全部 Core-organized (ΔH>0)。θ₁ ~17-37° 確認颱風域定位為「中等有序結構」。H_core 係強颱風垂直耦合嘅清晰 discriminator。**

---

## 證據等級

| 結論 | 證據等級 | 說明 |
|------|:--:|------|
| H_core > 0.4 跨颱風通則 | ✅ 已交叉驗證 | 6/6 WPAC 颱風一致（+ Dolphin 7/7） |
| ΔH 全部正 (Core-organized) | ✅ 已交叉驗證 | 6/6 + Dolphin |
| θ₁ ~17-37° 颱風域定位 | ✅ 已交叉驗證 | 6 颱風覆蓋 17-37° range |
| 近岸 vs 遠洋 pattern | ⚠️ 單一信源 | n=2-3，未達統計顯著 |
| χ_eff 跨颱風不穩定 | ✅ 已交叉驗證 | 同 Dolphin pilot 一致 |
| D₁ 單快照 | ⚠️ 單一信源 | 非 Cascade Ratio，比較需謹慎 |

---

## 檔案

- Script: `projects/dolphin-watch/typhoon_6d_batch.py`
- 數據: `/tmp/typhoon_6d/era5_*.nc`（6 files, ~150-160KB each）
- 個別結果: `projects/dolphin-watch/results/*_6d_*.json`（6 files）
- 彙總: `projects/dolphin-watch/results/wpac6_6d_summary.json`
