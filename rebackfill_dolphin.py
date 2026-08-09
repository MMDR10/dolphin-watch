#!/usr/bin/env python3
"""Re-backfill Dolphin dH_curl with corrected grid and fixed-center"""
import subprocess
import json
from pathlib import Path

# Estimated JTWC best track coordinates for Dolphin 2026
JTWC_TRACKS = {
    "20260805_00": (20.0, 140.0),
    "20260805_12": (19.0, 138.0),
    "20260806_00": (18.0, 135.0),
    "20260807_00": (27.0, 128.0),
    "20260808_00": (27.0, 127.0),
    "20260809_00": (27.0, 128.0),
}

results = []

for timestamp, (lat, lon) in JTWC_TRACKS.items():
    date_str = timestamp.split("_")[0]
    hour_str = timestamp.split("_")[1]
    
    print(f"\n{'='*60}")
    print(f"Measuring {date_str} {hour_str}z at {lat}°N, {lon}°E")
    print('='*60)
    
    # Remove old GRIB file
    grib_file = Path(f"gfs_{date_str}_{hour_str}_u850_v850.grib2")
    if grib_file.exists():
        grib_file.unlink()
    
    # Run measurement
    cmd = [
        "python3", "dolphin_dhcurl_v8.py",
        "--date", date_str,
        "--hour", hour_str,
        "--mode", "auto",
        "--lat", str(lat),
        "--lon", str(lon),
        "--exact-center"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        output = result.stdout + result.stderr
        
        # Extract dH_curl from output
        for line in output.split('\n'):
            if 'dH_curl:' in line and 's⁻¹' in line:
                dh_curl_str = line.split('dH_curl:')[1].strip().split('s⁻¹')[0].strip()
                dh_curl = float(dh_curl_str)
                
                record = {
                    "timestamp": timestamp.replace("_", ""),
                    "center_lat": lat,
                    "center_lon": lon,
                    "dh_curl": dh_curl,
                    "data_source": "GFS_corrected",
                    "storm": "DOLPHIN"
                }
                results.append(record)
                print(f"✅ dH_curl = {dh_curl:.6e}")
                break
        else:
            print(f"❌ Could not extract dH_curl")
            
    except Exception as e:
        print(f"❌ Error: {e}")

# Save results
with open("dolphin_rebackfill_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n{'='*60}")
print(f"Re-backfill complete: {len(results)} records")
print(f"Saved to dolphin_rebackfill_results.json")
print('='*60)
