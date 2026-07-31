import json

with open('dhcurl_history.json') as f:
    h = json.load(f)

existing_ts = {r['timestamp'] for r in h['records']}

gfs_records = [
    {"dh_curl": -2.5597897547413595e-05, "H_core": 3.504855703795329e-05, "H_shell": 9.450659490539692e-06,
     "center_lat": 14.25, "center_lon": 168.75, "core_n": 1295, "shell_n": 2032,
     "timestamp": "202607290000", "storm": "DOLPHIN", "mode": "Neutral/Transition",
     "core_deg": 5.0, "shell_deg": 8.0, "data_source": "GFS"},
    {"dh_curl": -2.395124283793848e-05, "H_core": 3.467825808911584e-05, "H_shell": 1.0727015251177363e-05,
     "center_lat": 14.75, "center_lon": 168.0, "core_n": 1295, "shell_n": 2042,
     "timestamp": "202607291200", "storm": "DOLPHIN", "mode": "Neutral/Transition",
     "core_deg": 5.0, "shell_deg": 8.0, "data_source": "GFS"},
    {"dh_curl": -3.349970620547538e-05, "H_core": 4.08535088354256e-05, "H_shell": 7.3538026299502235e-06,
     "center_lat": 16.25, "center_lon": 165.75, "core_n": 1307, "shell_n": 3946,
     "timestamp": "202607300600", "storm": "DOLPHIN", "mode": "Neutral/Transition",
     "core_deg": 5.0, "shell_deg": 10.0, "data_source": "GFS"},
    {"dh_curl": -3.990871255155071e-05, "H_core": 4.505702236201614e-05, "H_shell": 5.1483098104654346e-06,
     "center_lat": 18.25, "center_lon": 162.0, "core_n": 1327, "shell_n": 3988,
     "timestamp": "202607310000", "storm": "DOLPHIN", "mode": "Neutral/Transition",
     "core_deg": 5.0, "shell_deg": 10.0, "data_source": "GFS"},
]

added = 0
for r in gfs_records:
    if r['timestamp'] not in existing_ts:
        h['records'].append(r)
        added += 1

h['records'].sort(key=lambda x: x['timestamp'])
with open('dhcurl_history.json', 'w') as f:
    json.dump(h, f, indent=2, ensure_ascii=False)

latest = h['records'][-1]
with open('dhcurl_result.json', 'w') as f:
    json.dump(latest, f, indent=2, ensure_ascii=False)

print(f"added {added} GFS records")
print(f"total {len(h['records'])} records")
print(f"latest: {latest['timestamp']} dH_curl={latest['dh_curl']:.4e}")
