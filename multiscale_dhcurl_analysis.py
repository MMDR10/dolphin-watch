#!/usr/bin/env python3
"""
Multi-scale dH_curl analysis for Typhoon Dolphin (8/5-8/9, 2026)
Track dissolution → reorganization process
"""

import subprocess
import json
import os
from datetime import datetime, timedelta
import numpy as np

# Dolphin track (JTWC best track coordinates)
DOLPHIN_TRACK = {
    "20260805_00": (20.0, 140.0),
    "20260805_12": (19.0, 138.0),
    "20260806_00": (18.0, 135.0),
    "20260806_12": (20.0, 132.0),
    "20260807_00": (27.0, 128.0),
    "20260807_12": (27.0, 127.0),
    "20260808_00": (27.0, 127.0),
    "20260808_12": (26.0, 126.0),
    "20260809_00": (27.0, 128.0),
}

# Multi-scale radii
SCALES = {
    "core": 5.0,
    "shell": 10.0,
    "outer": 15.0,
    "environment": 20.0,
}

def run_multiscale_measurement(timestamp, lat, lon):
    """Run dH_curl at multiple scales for a single timestamp"""
    date_str = timestamp.split("_")[0]
    hour_str = timestamp.split("_")[1]
    
    results = {
        "timestamp": timestamp,
        "center_lat": lat,
        "center_lon": lon,
        "scales": {}
    }
    
    for scale_name, radius in SCALES.items():
        # Remove old GRIB file
        grib_file = f"gfs_{date_str}_{hour_str}_u850_v850.grib2"
        if os.path.exists(grib_file):
            os.remove(grib_file)
        
        # Run measurement
        cmd = [
            "python3", "dolphin_dhcurl_v8.py",
            "--date", date_str,
            "--hour", hour_str,
            "--mode", "auto",
            "--lat", str(lat),
            "--lon", str(lon),
            "--exact-center",
            "--core", str(radius),
            "--shell", str(radius + 3.0)  # shell = core + 3°
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            output = result.stdout + result.stderr
            
            # Extract dH_curl
            for line in output.split('\n'):
                if 'dH_curl:' in line and 's⁻¹' in line:
                    dh_curl_str = line.split('dH_curl:')[1].strip().split('s⁻¹')[0].strip()
                    dh_curl = float(dh_curl_str)
                    
                    # Extract H_core and H_shell
                    h_core = 0.0
                    h_shell = 0.0
                    for h_line in output.split('\n'):
                        if 'Core:' in h_line:
                            h_core_str = h_line.split('Core:')[1].strip().split('(')[0].strip()
                            h_core = float(h_core_str)
                        if 'Shell:' in h_line:
                            h_shell_str = h_line.split('Shell:')[1].strip().split('(')[0].strip()
                            h_shell = float(h_shell_str)
                    
                    results["scales"][scale_name] = {
                        "radius": radius,
                        "dH_curl": dh_curl,
                        "H_core": h_core,
                        "H_shell": h_shell
                    }
                    break
            else:
                results["scales"][scale_name] = None
                
        except Exception as e:
            print(f"  Error at {scale_name}: {e}")
            results["scales"][scale_name] = None
    
    return results

def main():
    print("=" * 70)
    print("Multi-scale dH_curl Analysis: Typhoon Dolphin (8/5-8/9)")
    print("Track dissolution → reorganization process")
    print("=" * 70)
    
    all_results = []
    
    for timestamp, (lat, lon) in DOLPHIN_TRACK.items():
        print(f"\n[{timestamp}] Center: {lat}°N, {lon}°E")
        print("-" * 70)
        
        result = run_multiscale_measurement(timestamp, lat, lon)
        all_results.append(result)
        
        # Print summary
        for scale_name in SCALES.keys():
            if result["scales"].get(scale_name):
                scale_data = result["scales"][scale_name]
                print(f"  {scale_name:12s} (r={scale_data['radius']:.0f}°): "
                      f"dH_curl = {scale_data['dH_curl']:+.3e}, "
                      f"H_core = {scale_data['H_core']:.3e}, "
                      f"H_shell = {scale_data['H_shell']:.3e}")
            else:
                print(f"  {scale_name:12s}: FAILED")
    
    # Save results
    output_file = "dolphin_multiscale_analysis.json"
    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'=' * 70}")
    print(f"Analysis complete. Results saved to {output_file}")
    print("=" * 70)
    
    # Generate summary
    print("\n📊 Summary: Multi-scale structural evolution")
    print("-" * 70)
    print(f"{'Timestamp':<15} {'Core(5°)':<12} {'Shell(10°)':<12} {'Outer(15°)':<12} {'Env(20°)':<12}")
    print("-" * 70)
    
    for result in all_results:
        ts = result["timestamp"]
        core = result["scales"].get("core", {}).get("dH_curl", 0) if result["scales"].get("core") else 0
        shell = result["scales"].get("shell", {}).get("dH_curl", 0) if result["scales"].get("shell") else 0
        outer = result["scales"].get("outer", {}).get("dH_curl", 0) if result["scales"].get("outer") else 0
        env = result["scales"].get("environment", {}).get("dH_curl", 0) if result["scales"].get("environment") else 0
        
        print(f"{ts:<15} {core:+.3e}  {shell:+.3e}  {outer:+.3e}  {env:+.3e}")

if __name__ == "__main__":
    main()
