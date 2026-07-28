#!/usr/bin/env python3
"""
🐬 Dolphin Watch Auto-Update — GitHub Actions cron job
=======================================================
Fetches JTWC advisory from cyclocane, parses position/wind/forecast,
computes Noise Topography verification metrics,
outputs dashboard_data.json for the HTML dashboard.

Dependencies: none (stdlib only)
"""

import json, urllib.request, re, sys, os
from datetime import datetime, timezone, timedelta

# ─── Config ───
CYCLOCANE_URL = "https://www.cyclocane.com/dolphin-storm-tracker"
OUTPUT_JSON = "dashboard_data.json"
HISTORY_JSON = "history.json"

# Noise Topography baseline prediction (from Z1-Z3 analysis)
NT_PREDICTION = {
    "peak_intensity_kmh": 280,        # ≥280 km/h predicted
    "peak_intensity_kts": 151,         # ~151 kts
    "0lag_active": True,               # 0-Lag RI active
    "z1_damping_zone": "dissipated",   # Z1 damping evaporated
    "z2_snake_lock": "locked",         # Z2 serpentine locked
    "z3_brittle": "brittle",           # Z3 geometric brittleness
    "forecast_date": "2026-07-27",
    "confidence": "high",
    "three_layer_overlap": True,       # Z1+Z2+Z3 extreme risk overlap
}

# ─── Parse JTWC Advisory ───
def parse_jtwc_advisory(text):
    """Parse the JTWC WTPN31 advisory text into structured data."""
    data = {
        "warning_nr": None,
        "storm_name": "DOLPHIN",
        "storm_id": "12W",
        "issued_time": None,
        "position": {"lat": None, "lon": None},
        "movement": {"direction": None, "speed_kts": None},
        "max_wind_kts": None,
        "gust_kts": None,
        "min_pressure_mb": None,
        "max_wave_height_ft": None,
        "forecasts": [],
        "next_warnings": [],
        "raw_text": text,
    }
    
    # Warning number
    m = re.search(r'WARNING NR\s*(\d+)', text)
    if m: data["warning_nr"] = int(m.group(1))
    
    # Storm name + ID
    m = re.search(r'(?:TYPHOON|TROPICAL STORM|TROPICAL DEPRESSION|SUPER TYPHOON)\s+(\d+W)\s*\((\w+)\)', text, re.IGNORECASE)
    if m:
        data["storm_id"] = m.group(1)
        data["storm_name"] = m.group(2)
    
    # Storm type
    m = re.search(r'UPGRADED FROM (\w+(?:\s+\w+)?)', text)
    if m:
        data["upgraded_from"] = m.group(1)
    
    # Position (from WARNING POSITION: block or REPEAT POSIT:)
    m = re.search(r'NEAR\s+(\d+\.?\d*)\s*([NS])\s+(\d+\.?\d*)\s*([EW])', text)
    if m:
        lat = float(m.group(1)) * (1 if m.group(2) == "N" else -1)
        lon = float(m.group(3)) * (1 if m.group(4) == "E" else -1)
        data["position"] = {"lat": lat, "lon": lon}
    
    # Issued time (from WARNING POSITION: block)
    m = re.search(r'(\d{2})(\d{2})(\d{2})Z\s*---\s*NEAR', text)
    if m:
        day, hour, minute = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # Assume current month/year
        now = datetime.now(timezone.utc)
        data["issued_time"] = f"{now.year}-{now.month:02d}-{day:02d}T{hour:02d}:{minute:02d}Z"
    
    # Movement
    m = re.search(r'MOVEMENT PAST SIX HOURS\s*-\s*(\d+)\s*DEGREES AT\s*(\d+)\s*KTS', text)
    if m:
        data["movement"]["direction"] = int(m.group(1))
        data["movement"]["speed_kts"] = int(m.group(2))
    
    # Max sustained winds
    m = re.search(r'MAX SUSTAINED WINDS\s*-\s*(\d+)\s*KT,\s*GUSTS\s*(\d+)\s*KT', text)
    if m:
        data["max_wind_kts"] = int(m.group(1))
        data["gust_kts"] = int(m.group(2))
    
    # Central pressure
    m = re.search(r'MINIMUM CENTRAL PRESSURE\s*(?:AT\s*\d+Z\s*IS|AT\s*\d+Z)\s*(\d+)\s*MB', text)
    if not m:
        m = re.search(r'MINIMUM CENTRAL PRESSURE.*?(\d{3,4})\s*MB', text)
    if m:
        data["min_pressure_mb"] = int(m.group(1))
    
    # Max wave height
    m = re.search(r'MAXIMUM SIGNIFICANT WAVE HEIGHT.*?(\d+)\s*FEET', text)
    if m:
        data["max_wave_height_ft"] = int(m.group(1))
    
    # Forecasts — parse each forecast block
    forecast_pattern = re.finditer(
        r'(\d+)\s*HRS,\s*VALID AT:\s*\n\s*(\d{6})Z\s*---\s*(\d+\.?\d*)([NS])\s+(\d+\.?\d*)([EW])\s*\n\s*MAX SUSTAINED WINDS\s*-\s*(\d+)\s*KT,\s*GUSTS\s*(\d+)\s*KT',
        text
    )
    for m in forecast_pattern:
        hrs = int(m.group(1))
        valid_time = m.group(2)  # DDHHMM
        lat = float(m.group(3)) * (1 if m.group(4) == "N" else -1)
        lon = float(m.group(5)) * (1 if m.group(6) == "E" else -1)
        wind_kts = int(m.group(7))
        gust_kts = int(m.group(8))
        data["forecasts"].append({
            "hours": hrs,
            "valid_time": valid_time,
            "position": {"lat": lat, "lon": lon},
            "wind_kts": wind_kts,
            "gust_kts": gust_kts,
        })
    
    # Next warnings
    m = re.search(r'NEXT WARNINGS AT\s*(.*?)//', text)
    if m:
        times = m.group(1).strip()
        data["next_warnings"] = [t.strip() for t in times.split(',')]
    
    return data

# ─── Fetch + Parse ───
def fetch_advisory():
    """Fetch cyclocane page and extract JTWC advisory."""
    req = urllib.request.Request(CYCLOCANE_URL, headers={
        "User-Agent": "Dolphin-Watch/1.0 (research dashboard)"
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        html = resp.read().decode("utf-8")
    
    # Find JTWC advisory block — WTPN31
    start = html.find("WTPN31")
    if start < 0:
        return None, "No JTWC advisory found on cyclocane"
    
    # Extract from WTPN31 to NNNN
    end = html.find("NNNN", start)
    if end < 0:
        end = start + 5000  # fallback
    
    advisory_text = html[start:end+4]
    
    # Clean up
    advisory_text = advisory_text.replace("<br>", "\n").replace("<br/>", "\n")
    advisory_text = re.sub(r'<[^>]+>', '', advisory_text)
    # Decode HTML entities (&#x000A; → newline, etc.)
    advisory_text = advisory_text.replace("&#x000A;", "\n").replace("&#x000D;", "")
    advisory_text = advisory_text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    advisory_text = advisory_text.replace("&quot;", '"').replace("&#x27;", "'")
    # Collapse multiple blank lines
    advisory_text = re.sub(r'\n{3,}', '\n\n', advisory_text)
    
    return parse_jtwc_advisory(advisory_text), None

# ─── Noise Topography Verification ───
def verify_noise_topography(advisory_data):
    """Compare JTWC actual/forecast with Noise Topography prediction."""
    result = {
        "prediction": NT_PREDICTION,
        "verification": {},
        "status": "pending",
        "remarks": [],
    }
    
    # 1. Peak intensity comparison
    jtwc_peak = None
    for fc in advisory_data["forecasts"]:
        if jtwc_peak is None or fc["wind_kts"] > jtwc_peak:
            jtwc_peak = fc["wind_kts"]
    
    if jtwc_peak:
        jtwc_peak_kmh = round(jtwc_peak * 1.852)
        nt_peak_kmh = NT_PREDICTION["peak_intensity_kmh"]
        diff = jtwc_peak_kmh - nt_peak_kmh
        result["verification"]["peak_intensity"] = {
            "nt_predicted_kmh": nt_peak_kmh,
            "jtwc_forecast_kmh": jtwc_peak_kmh,
            "jtwc_forecast_kts": jtwc_peak,
            "difference_kmh": diff,
            "difference_pct": round(abs(diff)/nt_peak_kmh * 100, 1) if nt_peak_kmh else 0,
            "within_tolerance": abs(diff) <= 10,
            "remark": f"NT≥{nt_peak_kmh} vs JTWC={jtwc_peak_kmh} km/h (Δ={diff} km/h)"
            if abs(diff) > 10 else
            f"NT≥{nt_peak_kmh} vs JTWC={jtwc_peak_kmh} km/h — within tolerance (±10 km/h)"
        }
    
    # 2. Current intensity vs 0-Lag RI
    current_kts = advisory_data.get("max_wind_kts", 0)
    if current_kts:
        ri_status = "Active" if current_kts >= 75 else "Not yet"
        result["verification"]["0lag_ri"] = {
            "nt_status": "0-Lag RI Active",
            "current_kts": current_kts,
            "current_kmh": round(current_kts * 1.852),
            "category": get_category(current_kts),
            "status": "✅ Confirmed" if current_kts >= 75 else "⏳ Building",
        }
    
    # 3. Overall status
    checks = [result["verification"]["peak_intensity"]["within_tolerance"]]
    if "0lag_ri" in result["verification"]:
        checks.append(result["verification"]["0lag_ri"]["status"] == "✅ Confirmed")
    
    if all(checks):
        result["status"] = "✅ NT verified"
        result["remarks"].append("Noise Topography prediction confirmed")
    elif any(checks):
        result["status"] = "🟡 NT partially verified"
        result["remarks"].append("Partial verification — monitoring")
    else:
        result["status"] = "⏳ Awaiting data"
    
    return result

# ─── Category ───
def get_category(kts):
    if kts >= 137: return "Super Typhoon (Cat 5)"
    if kts >= 113: return "Typhoon (Cat 4)"
    if kts >= 96: return "Typhoon (Cat 3)"
    if kts >= 83: return "Typhoon (Cat 2)"
    if kts >= 64: return "Typhoon (Cat 1)"
    if kts >= 34: return "Tropical Storm"
    return "Tropical Depression"

# ─── Load/Save History ───
def load_history():
    if os.path.exists(HISTORY_JSON):
        with open(HISTORY_JSON, "r") as f:
            return json.load(f)
    return {"advisories": [], "storm_name": "DOLPHIN", "storm_id": "12W"}

def save_history(history):
    with open(HISTORY_JSON, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

# ═══════════════ MAIN ═══════════════

def main():
    now = datetime.now(timezone.utc)
    print("="*60)
    print("🐬 Dolphin Watch Auto-Update")
    print(f"  {now.strftime('%Y-%m-%d %H:%M UTC')}")
    print("="*60)
    
    # 1. Fetch advisory
    print("\n[1/4] Fetching JTWC advisory from cyclocane...")
    advisory, error = fetch_advisory()
    if error:
        print(f"  ❌ {error}")
        # Try to load last known data
        if os.path.exists(OUTPUT_JSON):
            with open(OUTPUT_JSON) as f:
                data = json.load(f)
            data["generated"] = now.strftime("%Y-%m-%d %H:%M UTC")
            data["_error"] = error
            with open(OUTPUT_JSON, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("  ⚠️  Using cached data")
        return
    
    print(f"  ✅ Warning NR {advisory['warning_nr']}: {advisory['storm_name']} ({advisory['storm_id']})")
    print(f"  📍 {advisory['position']['lat']}°{',' if advisory['position']['lat']>0 else ''}N {advisory['position']['lon']}°E")
    print(f"  💨 {advisory['max_wind_kts']} kts ({get_category(advisory['max_wind_kts'])})")
    print(f"  🧭 Moving {advisory['movement']['direction']}° at {advisory['movement']['speed_kts']} kts")
    if advisory['min_pressure_mb']:
        print(f"  🌡️  {advisory['min_pressure_mb']} mb")
    
    # 2. Noise Topography verification
    print("\n[2/4] Noise Topography verification...")
    nt_result = verify_noise_topography(advisory)
    print(f"  {nt_result['status']}")
    for r in nt_result['remarks']:
        print(f"  └─ {r}")
    
    # 3. Update history
    print("\n[3/4] Updating history...")
    history = load_history()
    
    # Check if this advisory is already recorded
    existing = any(a.get("warning_nr") == advisory["warning_nr"] for a in history["advisories"])
    
    if not existing:
        entry = {
            "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"),
            "warning_nr": advisory["warning_nr"],
            "position": advisory["position"],
            "max_wind_kts": advisory["max_wind_kts"],
            "category": get_category(advisory["max_wind_kts"]),
            "movement": advisory["movement"],
            "min_pressure_mb": advisory["min_pressure_mb"],
            "peak_forecast_kts": max(
                (f["wind_kts"] for f in advisory["forecasts"]), default=0
            ),
            "peak_forecast_time": advisory["forecasts"][0]["valid_time"] if advisory["forecasts"] else "",
            "nt_status": nt_result["status"],
        }
        history["advisories"].append(entry)
        history["advisories"].sort(key=lambda x: x["warning_nr"])
        save_history(history)
        print(f"  ✅ Warning NR {advisory['warning_nr']} added to history ({len(history['advisories'])} total)")
    else:
        print(f"  ℹ️  Warning NR {advisory['warning_nr']} already in history")
    
    # 4. Build dashboard data
    print("\n[4/4] Writing dashboard_data.json...")
    
    peak_forecast = max(
        (f["wind_kts"] for f in advisory["forecasts"]), default=0
    )
    peak_forecast_kmh = round(peak_forecast * 1.852)
    
    data = {
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "source": f"JTWC via cyclocane (WTPN31)",
        "_storm_active": True,
        "current": {
            "warning_nr": advisory["warning_nr"],
            "storm_name": advisory["storm_name"],
            "storm_id": advisory["storm_id"],
            "category": get_category(advisory["max_wind_kts"]),
            "position": advisory["position"],
            "max_wind_kts": advisory["max_wind_kts"],
            "max_wind_kmh": round(advisory["max_wind_kts"] * 1.852),
            "gust_kts": advisory["gust_kts"],
            "movement_direction": advisory["movement"]["direction"],
            "movement_speed_kts": advisory["movement"]["speed_kts"],
            "min_pressure_mb": advisory["min_pressure_mb"],
            "max_wave_height_ft": advisory["max_wave_height_ft"],
            "issued_time": advisory["issued_time"],
            "next_warnings": advisory["next_warnings"],
        },
        "forecast": advisory["forecasts"],
        "peak_forecast": {
            "kts": peak_forecast,
            "kmh": peak_forecast_kmh,
            "category": get_category(peak_forecast),
        },
        "noise_topography": nt_result,
        "history": history["advisories"],
        "summary": {
            "current_speed": f"{advisory['max_wind_kts']} kts ({round(advisory['max_wind_kts']*1.852)} km/h)",
            "peak_predicted": f"{peak_forecast} kts ({peak_forecast_kmh} km/h) — {get_category(peak_forecast)}",
            "nt_vs_jtwc": f"NT≥280 km/h → JTWC max={peak_forecast_kmh} km/h" if peak_forecast_kmh else "",
            "movement": f"{advisory['movement']['direction']}° at {advisory['movement']['speed_kts']} kts",
            "advisory_count": len(history["advisories"]),
        },
    }
    
    with open(OUTPUT_JSON, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"  ✅ {OUTPUT_JSON} ({os.path.getsize(OUTPUT_JSON)} bytes)")
    print(f"  ─────────────────────────────")
    print(f"  🐬 {advisory['storm_name']} | {advisory['max_wind_kts']} kts | {get_category(advisory['max_wind_kts'])}")
    print(f"  📍 {advisory['position']['lat']}N {advisory['position']['lon']}E")
    print(f"  📈 Peak forecast: {peak_forecast} kts ({peak_forecast_kmh} km/h)")
    print(f"  🔬 NT verification: {nt_result['status']}")
    print("="*60)

if __name__ == "__main__":
    main()
