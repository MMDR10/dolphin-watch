#!/usr/bin/env python3
"""Update dhcurl_history.json with corrected measurements"""
import json

# Load existing history
with open("dhcurl_history.json", "r") as f:
    history = json.load(f)

# Load new corrected measurements
with open("dolphin_rebackfill_results.json", "r") as f:
    corrected = json.load(f)

# Remove old incorrect records (8/5 onwards)
old_count = len(history["records"])
history["records"] = [r for r in history["records"] if r["timestamp"] < "202608050000"]
removed = old_count - len(history["records"])

# Add corrected records
for rec in corrected:
    history["records"].append({
        "dh_curl": rec["dh_curl"],
        "H_core": 0,  # Placeholder
        "H_shell": 0,  # Placeholder
        "core_n": 0,
        "shell_n": 0,
        "center_lat": rec["center_lat"],
        "center_lon": rec["center_lon"],
        "core_deg": 5.0,
        "shell_deg": 8.0,
        "mode": "Neutral/Transitional",
        "timestamp": rec["timestamp"],
        "data_source": "GFS_corrected",
        "storm": "DOLPHIN"
    })

# Save updated history
with open("dhcurl_history.json", "w") as f:
    json.dump(history, f, indent=2)

print(f"Updated dhcurl_history.json: {len(history['records'])} records")
print(f"Removed {removed} incorrect records")
print(f"Added {len(corrected)} corrected records")
