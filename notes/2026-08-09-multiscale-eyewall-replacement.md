# Typhoon Dolphin: Multi-scale Structural Evolution Analysis

**Date:** 2026-08-09  
**Analysis Period:** 8/5-8/9, 2026  
**Method:** Multi-scale dH_curl at 4 radii (5°/10°/15°/20°)

---

## 📊 Key Findings

### Eyewall Replacement Cycle Detected

Multi-scale analysis reveals a classic **eyewall replacement cycle**:

| Phase | Time | Core (5°) | Shell (10°) | Outer (15°) | Physical Meaning |
|-------|------|-----------|-------------|-------------|------------------|
| **Dissolution** | 8/5-8/6 | **+2.1e-05 ~ +3.4e-05** | -2.0e-05 ~ -2.8e-05 | -1.0e-05 ~ -1.6e-05 | Core dissolves, outer intact |
| **Reorganization** | 8/7 | **-7.6e-05 ~ -7.9e-05** | -1.2e-05 ~ -1.5e-05 | -9.8e-06 ~ -1.5e-05 | New eyewall forms (44% stronger!) |
| **Weakening** | 8/8-8/9 | -6.7e-05 → -2.6e-05 | -6.5e-06 ~ -1.5e-05 | -1.2e-05 ~ -1.5e-05 | Gradual weakening |

---

## 🔍 Detailed Analysis

### Phase 1: Dissolution (8/5-8/6)

**Core (5°):** Positive dH_curl (+2.1e-05 to +3.4e-05)  
→ Eyewall structure breaking down (divergent flow)

**Shell/Outer (10°-15°):** Negative dH_curl (-2.0e-05 to -1.6e-05)  
→ Outer structure remains organized

**Environment (20°):** Negative dH_curl (-1.9e-06 to -7.5e-06)  
→ Environmental field remains supportive

**Interpretation:** Classic eyewall replacement onset. The inner core collapses while the outer structure maintains integrity, creating conditions for a new eyewall to form.

### Phase 2: Reorganization (8/7)

**Core (5°):** Strongly negative (-7.6e-05 to -7.9e-05)  
→ **New eyewall formed, 44% stronger than previous peak!**

**Shell (10°):** Weakly negative (-1.2e-05 to -1.5e-05)  
→ Old structure remnants

**Outer (15°):** Negative (-9.8e-06 to -1.5e-05)  
→ Outer structure still organized

**Environment (20°):** Negative (-3.5e-06 to -5.2e-06)  
→ Environmental field still supportive

**Interpretation:** New eyewall has fully formed and is now stronger than the original. The shell weakened as the old eyewall collapsed and was replaced.

### Phase 3: Weakening (8/8-8/9)

**Core (5°):** Gradually weakening (-6.7e-05 → -2.6e-05)  
→ Typhoon approaching land, losing energy

**All scales:** Remain negative but weakening  
→ Overall structure still organized but decaying

**Interpretation:** Gradual weakening as Dolphin approaches the Chinese coast.

---

## 🎯 Key Insights

### 1. Core-first Dissolution Pattern
- Core dissolves first (positive dH_curl)
- Outer structure remains intact (negative dH_curl)
- Creates "hollow" structure during transition

### 2. New Eyewall Stronger Than Old
- Old peak: -5.5e-05 (8/2)
- New peak: -7.9e-05 (8/7)
- **44% intensification** after replacement

### 3. Environmental Field Always Supportive
- Environment (20°) consistently negative throughout
- Suggests large-scale conditions favored typhoon maintenance
- Replacement driven by internal dynamics, not environmental degradation

---

## 📈 Visualization

See `dolphin_multiscale_evolution.png` for time series plot showing:
- Multi-scale dH_curl evolution
- Phase annotations (dissolution/reorganization/weakening)
- Clear transition from positive to negative core dH_curl

---

## 🧪 Methodology

**Multi-scale dH_curl:**
- Core: 5° radius (eyewall)
- Shell: 10° radius (inner core)
- Outer: 15° radius (outer core)
- Environment: 20° radius (environmental field)

**Data source:** GFS 0.25° 850hPa wind fields  
**Center tracking:** JTWC best track coordinates  
**Temporal resolution:** 12-hour intervals

---

## 📚 Physical Interpretation

This is a textbook **eyewall replacement cycle (ERC)**:

1. **Old eyewall weakens** (core dH_curl → positive)
2. **Outer eyewall contracts** (shell/outer remain negative)
3. **New eyewall forms** (core dH_curl → strongly negative)
4. **Typhoon reintensifies** (new peak stronger than old)
5. **Gradual weakening** (approaching land)

The multi-scale dH_curl analysis successfully captures this process, demonstrating its utility for tracking typhoon structural evolution.

---

## 🔬 Implications

1. **dH_curl sign change** (positive ↔ negative) = structural transition indicator
2. **Multi-scale analysis** reveals internal dynamics not visible at single scale
3. **Environmental field stability** suggests ERC was internally driven
4. **44% intensification** after replacement shows ERC can strengthen typhoons

---

## 📁 Files

- `multiscale_dhcurl_analysis.py` — Analysis script
- `dolphin_multiscale_analysis.json` — Raw results
- `plot_multiscale_evolution.py` — Visualization script
- `dolphin_multiscale_evolution.png` — Time series plot
- `notes/2026-08-09-multiscale-eyewall-replacement.md` — This document

---

**Status:** ✅ Complete  
**GitHub:** Committed to `MMDR10/dolphin-watch`
