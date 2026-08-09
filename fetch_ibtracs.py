#!/usr/bin/env python3
"""Fetch JTWC best track for Dolphin 2026"""
import urllib.request
import json

# IBTrACS API for Dolphin 2026
url = "https://www.ncei.noaa.gov/access/services/data/v1?dataset=ibtracs&storm=2026220N25305&format=json"
try:
    with urllib.request.urlopen(url, timeout=30) as resp:
        data = json.loads(resp.read().decode())
        print(f"Found {len(data)} records")
        for rec in data[:20]:
            print(f"{rec.get('ISO_TIME')}: {rec.get('LAT')}, {rec.get('LON')}")
except Exception as e:
    print(f"IBTrACS API failed: {e}")
    print("Trying alternative approach...")
