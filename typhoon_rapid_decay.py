#!/usr/bin/env python3
"""Rapid decay validation — noise_corr lead wind?"""
import json, math, time
from pathlib import Path
import numpy as np, pandas as pd, xarray as xr
from scipy.ndimage import gaussian_filter
from scipy import stats
import cdsapi

CORE_DEG, SHELL_DEG, DOMAIN_PAD = 5.0, 10.0, 15.0
NC_DIR = Path('/tmp/typhoon_rapid')
PROJ_DIR = Path('/app/working/workspaces/tygtDc/projects/dolphin-watch')
NC_DIR.mkdir(exist_ok=True)

TARGETS = [('HIGOS','2015-02-10'),('MAN-YI','2024-11-17'),('YINXING','2024-11-07'),
           ('NORU','2022-09-25'),('USAGI','2024-11-13'),('GONI','2020-10-31')]

LAT, LON, WIND = 'LAT','LON','USA_WIND'

def get_decay(name):
    df = pd.read_csv(PROJ_DIR.parent/'cyclone'/'data'/'ibtracs_wp_2015_2025.csv')
    for col in [WIND, LAT, LON]:
        df[col] = pd.to_numeric(df[col].astype(str).str.strip(), errors='coerce')
    df['ISO_TIME'] = pd.to_datetime(df['ISO_TIME'])
    grp = df[(df['NAME'].str.strip().str.upper()==name)&(df[WIND]>=25)].copy()
    grp = grp.sort_values('ISO_TIME')
    peak_idx = grp[WIND].idxmax()
    peak_pos = grp.index.get_loc(peak_idx)
    dec = grp.iloc[peak_pos:].copy()
    if len(dec)>12: dec = dec.iloc[::len(dec)//12][:12]
    pts = []
    for _,r in dec.iterrows():
        pts.append({'name':name,'date':str(r['ISO_TIME'])[:10],
                    'hour':int(str(r['ISO_TIME'])[11:13]),
                    'lat':float(r[LAT]),'lon':float(r[LON]),
                    'wind':float(r[WIND]),'ts':str(r['ISO_TIME'])[:16]})
    return pts

def download(t):
    label = "rapid_{}_{}_{:02d}".format(t['name'].lower(),t['date'].replace('-',''),t['hour'])
    nc = NC_DIR / "era5_{}.nc".format(label)
    if nc.exists() and nc.stat().st_size>1000: return nc
    area = [t['lat']+DOMAIN_PAD,t['lon']-DOMAIN_PAD,t['lat']-DOMAIN_PAD,t['lon']+DOMAIN_PAD]
    cdsapi.Client(quiet=True).retrieve('reanalysis-era5-pressure-levels',{
        'product_type':'reanalysis','format':'netcdf',
        'variable':['u_component_of_wind','v_component_of_wind'],
        'pressure_level':['200','850'],'year':t['date'][:4],'month':t['date'][5:7],
        'day':t['date'][8:10],'time':["{:02d}:00".format(t['hour'])],'area':area,
    },str(nc))
    return nc

def measure(nc_path, lat_c, lon_c):
    ds = xr.open_dataset(nc_path)
    u850 = ds['u'].sel(pressure_level=850).values[0]
    v850 = ds['v'].sel(pressure_level=850).values[0]
    u200 = ds['u'].sel(pressure_level=200).values[0]
    v200 = ds['v'].sel(pressure_level=200).values[0]
    lat_arr = ds['latitude'].values[::-1]
    lon_arr = ds['longitude'].values
    ds.close()
    u850, v850 = u850[::-1,:], v850[::-1,:]
    u200, v200 = u200[::-1,:], v200[::-1,:]
    g = {'lat1':float(lat_arr[0]),'lat2':float(lat_arr[-1]),'lon1':float(lon_arr[0]),'lon2':float(lon_arr[-1]),
         'di':float(lon_arr[1]-lon_arr[0]),'dj':float(lat_arr[1]-lat_arr[0]),'Ni':len(lon_arr),'Nj':len(lat_arr)}
    cl = math.cos(math.radians((g['lat1']+g['lat2'])/2))
    dx = g['di']*math.pi/180*6371000*cl
    dy = g['dj']*math.pi/180*6371000
    z850 = np.gradient(v850,axis=1)/dx - np.gradient(u850,axis=0)/dy
    z200 = np.gradient(v200,axis=1)/dx - np.gradient(u200,axis=0)/dy
    z850s = (z850-z850.mean())/z850.std()
    z200s = (z200-z200.mean())/z200.std()
    # Distance mask
    rl = np.deg2rad(np.linspace(g['lat1'],g['lat2'],g['Nj'])[:,None])
    rn = np.deg2rad(np.linspace(g['lon1'],g['lon2'],g['Ni'])[None,:])
    rc_lat = np.deg2rad(lat_c)
    rc_lon = np.deg2rad(lon_c if lon_c>0 else lon_c+360)
    a = np.sin((rl-rc_lat)/2)**2+np.cos(rc_lat)*np.cos(rl)*np.sin((rn-rc_lon)/2)**2
    cm = (2*6371*np.arcsin(np.sqrt(a))) <= CORE_DEG*111.32
    if cm.sum()<10: return None
    sp = CORE_DEG/g['di']
    dH850 = z850s - gaussian_filter(z850s,sigma=sp)
    dH200 = z200s - gaussian_filter(z200s,sigma=sp)
    cn850 = dH850[cm]; cn200 = dH200[cm]
    X = np.stack([z850s[cm].ravel(),z200s[cm].ravel()],axis=1)
    Xc = X-X.mean(axis=0)
    ev,evc = np.linalg.eigh(np.cov(Xc.T))
    o = np.argsort(ev)[::-1]
    pc1 = evc[:,o[0]]
    theta1 = math.degrees(math.atan2(abs(pc1[1]),abs(pc1[0])))
    Hc = float(np.corrcoef(z850s[cm].ravel(),z200s[cm].ravel())[0,1])
    return {'theta1_deg':theta1,'H_core':Hc,
            'noise_rms':float(np.sqrt(np.mean(cn850**2))),
            'noise_corr':float(np.corrcoef(cn850,cn200)[0,1]),
            'core_var':float(np.var(z850s[cm]))}

all_r = []
for name, _ in TARGETS:
    pts = get_decay(name)
    w0 = pts[0]['wind']; w1 = pts[-1]['wind']
    print("{}: {} pts, {:.0f}→{:.0f}kt".format(name,len(pts),w0,w1))
    for t in pts:
        try:
            nc = download(t)
            r = measure(nc,t['lat'],t['lon'])
            if r:
                r['storm']=name; r['wind_kt']=t['wind']; r['timestamp']=t['ts']
                all_r.append(r)
            print('.',end='',flush=True)
            time.sleep(0.3)
        except Exception as e:
            print('!',end='',flush=True)
    own = sum(1 for x in all_r if x['storm']==name)
    print(" ({})".format(own))

print("\n"+"="*60)
print("  RAPID DECAY VALIDATION (n={})".format(len(all_r)))
print("="*60)

def drop_h(v): return np.argmax(v<v[0]*0.8)*6 if (v<v[0]*0.8).any() else 999

storms = sorted(set(r['storm'] for r in all_r))
leads = 0
for s in storms:
    pts = sorted([r for r in all_r if r['storm']==s], key=lambda r: r['wind_kt'], reverse=True)
    if len(pts)<4: continue
    w = np.array([p['wind_kt'] for p in pts])
    nc = np.array([p['noise_corr'] for p in pts])
    hc = np.array([p['H_core'] for p in pts])
    th = np.array([p['theta1_deg'] for p in pts])
    w80 = drop_h(w); nc80 = drop_h(nc); hc80 = drop_h(hc); th80 = drop_h(th)
    lead = ''
    if nc80 < w80-6: lead = 'NOISE LEADS'
    elif hc80 < w80-6: lead = 'H_core LEADS'
    elif nc80<=w80+6 and hc80<=w80+6: lead = 'sync'
    else: lead = 'wind leads'
    if 'LEAD' in lead: leads += 1
    r_nw,p_nw = stats.pearsonr(w,nc)
    r_hw,p_hw = stats.pearsonr(w,hc)
    print("{:<10} wind↓@{}h  ncorr↓@{}h  Hc↓@{}h  θ₁↓@{}h  {} | r_nc={:+.2f} r_hc={:+.2f}".format(
        s, str(w80).rjust(3), str(nc80).rjust(3), str(hc80).rjust(3), str(th80).rjust(3),
        lead, r_nw, r_hw))

print("\n  Noise/H_core leads wind: {}/{} rapid-decay storms".format(leads, len(storms)))

out = PROJ_DIR/'results'/'wpac_rapid_decay_noise.json'
with open(out,'w') as f: json.dump(all_r,f,indent=2)
print("  saved: {}".format(out))
