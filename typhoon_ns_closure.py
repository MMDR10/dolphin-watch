#!/usr/bin/env python3
"""
🧪 Phase 1 v2: Dolphin 2020 Ô-HAT 分辨率橋接 — 用 vorticity 場
================================================================
Path A: ERA5 降級到 0.5° → Ô-HAT: dH_curl (ζ shell-core diff) + θ₁ + singularity loc
Path B: ERA5 原 0.25° → native ζ max location + enstrophy (ground truth)
Compare: 空間重合 + 時間提前

Fix: 用 vorticity ζ = ∂v/∂x - ∂u/∂y 而唔係 wind curl
     0.5° degradation (step=2) 俾 core 有足夠 points
"""
import sys, json, math, os
import numpy as np
from scipy import stats
from pathlib import Path

OUT_DIR = Path('/tmp/typhoon_ns_closure/dolphin2020')
ERA5 = OUT_DIR / 'era5_hourly.nc'

TRACK = {
    '2020-09-19T00': (24.0, 133.0, 35), '2020-09-19T12': (24.5, 132.0, 45),
    '2020-09-20T00': (25.0, 131.0, 55), '2020-09-20T12': (25.5, 130.5, 65),
    '2020-09-21T00': (26.0, 130.0, 75), '2020-09-21T06': (26.2, 129.7, 82),
    '2020-09-21T12': (26.5, 129.5, 90), '2020-09-21T18': (26.7, 129.2, 98),
    '2020-09-22T00': (27.0, 129.0, 105),'2020-09-22T06': (27.2, 128.7, 115),
    '2020-09-22T12': (27.5, 128.5, 115),'2020-09-22T18': (27.7, 128.2, 110),
    '2020-09-23T00': (28.0, 128.0, 110),'2020-09-23T12': (28.5, 127.5, 100),
    '2020-09-24T00': (29.0, 127.0, 85), '2020-09-24T12': (30.0, 126.5, 65),
    '2020-09-25T00': (31.0, 126.0, 45),
}

def load_era5():
    import xarray as xr
    ds = xr.open_dataset(ERA5, engine='netcdf4')
    u=ds['u10'].values; v=ds['v10'].values
    lat=ds['latitude'].values; lon=ds['longitude'].values
    tv='valid_time' if 'valid_time' in ds else 'time'
    times=ds[tv].values; ds.close()
    return u,v,lat,lon,times

def vorticity(u,v,dx,dy):
    """ζ = ∂v/∂x - ∂u/∂y"""
    return np.gradient(v, dx, axis=1) - np.gradient(u, dy, axis=0)

def laplacian(f, dx, dy):
    lap=np.zeros_like(f)
    ny,nx=f.shape
    for j in range(1,ny-1):
        for k in range(nx):
            km=(k-1)%nx; kp=(k+1)%nx
            lap[j,k]=(f[j,km]-2*f[j,k]+f[j,kp])/dx**2+(f[j-1,k]-2*f[j,k]+f[j+1,k])/dy**2
    return lap

def mask_at(lat2d, lon2d, clat, clon, r):
    dw=(lon2d-clon+180)%360-180
    return np.sqrt((lat2d-clat)**2+dw**2)<=r

def get_track_center(time_str):
    clat,clon=27.0,129.0
    for tk,(tlat,tlon,_) in sorted(TRACK.items()):
        if tk<=time_str[:13]: clat,clon=tlat,tlon
    return clat,clon

# ═══ Path A: Ô-HAT on 0.5° ═══
def path_a():
    u,v,lat,lon,times=load_era5()
    
    # Degrade to 0.5° (every 2nd point)
    step=2
    u_d=u[:,::step,::step]; v_d=v[:,::step,::step]
    lat_d=lat[::step]; lon_d=lon[::step]
    dx_d=0.5*111320; dy_d=0.5*111320
    
    CORE_R=2.5; SHELL_R=6.0
    lat2d,lon2d=np.meshgrid(lat_d,lon_d,indexing='ij')
    
    print(f"   Path A degraded: {u_d.shape} (0.5°)")
    print(f"   lat range: {lat_d[0]:.1f} to {lat_d[-1]:.1f}")
    
    results=[]
    for t in range(u_d.shape[0]):
        ts=str(times[t])[:16]
        clat,clon=get_track_center(ts)
        
        # Vorticity at 0.5°
        zeta=vorticity(u_d[t],v_d[t],dx_d,dy_d)
        
        # Masks
        cm=mask_at(lat2d,lon2d,clat,clon,CORE_R)
        sm=mask_at(lat2d,lon2d,clat,clon,SHELL_R)&~cm
        
        # dH_curl: shell - core ζ (vorticity field difference, not ∇²)
        core_z=float(np.mean(zeta[cm])) if cm.sum()>0 else 0
        shell_z=float(np.mean(zeta[sm])) if sm.sum()>0 else 0
        dh=shell_z-core_z
        
        # Find max |ζ| location → Ô-HAT singularity
        max_idx=np.unravel_index(np.argmax(np.abs(zeta)),zeta.shape)
        sing_lat=float(lat_d[max_idx[0]])
        sing_lon=float(lon_d[max_idx[1]])
        
        # θ₁: PCA of (u, v) in core
        u_c=u_d[t][cm]; v_c=v_d[t][cm]
        if len(u_c)>8:
            X=np.column_stack([u_c,v_c]); X-=X.mean(axis=0)
            ev=np.linalg.eigvalsh(X.T@X)
            th=np.degrees(np.arctan(np.sqrt(max(ev.min(),0)/max(ev.max(),1e-30)))) if ev.max()>0 else 90
        else:
            th=float('nan')
        
        results.append({'time':ts,'lat':clat,'lon':clon,
                       'dH_curl':dh,'theta1':th,
                       'core_vort':core_z,'shell_vort':shell_z,
                       'sing_lat':sing_lat,'sing_lon':sing_lon,
                       'n_core':int(cm.sum()),'n_shell':int(sm.sum())})
    return results

# ═══ Path B: Native 0.25° ground truth ═══
def path_b():
    u,v,lat,lon,times=load_era5()
    dx=0.25*111320; dy=0.25*111320
    
    CORE_R=1.5
    lat2d,lon2d=np.meshgrid(lat,lon,indexing='ij')
    
    print(f"   Path B native: {u.shape} (0.25°)")
    
    results=[]
    for t in range(u.shape[0]):
        ts=str(times[t])[:16]
        clat,clon=get_track_center(ts)
        
        zeta=vorticity(u[t],v[t],dx,dy)
        
        # Masks at 0.25°
        cm=mask_at(lat2d,lon2d,clat,clon,CORE_R)
        sm=mask_at(lat2d,lon2d,clat,clon,4.0)&~cm
        
        # Max |ζ|
        max_idx=np.unravel_index(np.argmax(np.abs(zeta)),zeta.shape)
        
        # Enstrophy
        ens=0.5*zeta**2
        
        # ∇²ζ
        lap_zeta=laplacian(zeta, dx, dy)
        
        results.append({'time':ts,'lat':clat,'lon':clon,
                       'core_vort':float(np.mean(zeta[cm])),
                       'shell_vort':float(np.mean(zeta[sm])),
                       'core_enstrophy':float(np.mean(ens[cm])),
                       'core_lap':float(np.mean(lap_zeta[cm])),
                       'max_vort_lat':float(lat[max_idx[0]]),
                       'max_vort_lon':float(lon[max_idx[1]]),
                       'max_vort':float(zeta[max_idx]),
                       'n_core':int(cm.sum()),'n_shell':int(sm.sum())})
    return results

# ═══ Compare ═══
def compare(hat, native):
    hat_t={r['time'][:13]:r for r in hat}
    nat_t={r['time'][:13]:r for r in native}
    common=sorted(set(hat_t)&set(nat_t))
    
    comps=[]
    for t in common:
        h=hat_t[t]; n=nat_t[t]
        dlon=(n['max_vort_lon']-h['sing_lon']+180)%360-180
        serr=np.sqrt((n['max_vort_lat']-h['sing_lat'])**2+dlon**2)
        
        # Also track-center-based error
        dlon2=(n['max_vort_lon']-h['lon']+180)%360-180
        terr=np.sqrt((n['max_vort_lat']-h['lat'])**2+dlon2**2)
        
        comps.append({'time':t,
            'spatial_err_singularity':serr,
            'spatial_err_track':terr,
            'hat_dH':h['dH_curl'],'hat_theta1':h['theta1'],
            'hat_sing_lat':h['sing_lat'],'hat_sing_lon':h['sing_lon'],
            'nat_max_lat':n['max_vort_lat'],'nat_max_lon':n['max_vort_lon'],
            'nat_core_vort':n['core_vort'],'nat_core_lap':n['core_lap'],
            'nat_core_ens':n['core_enstrophy'],
            'hat_core_vort':h['core_vort'],
        })
    return comps

# ═══ Phase coherence ═══
def coherence(hat):
    thetas=[r['theta1'] for r in hat]
    times=[r['time'] for r in hat]
    
    ri_idx=None
    for i,t in enumerate(times):
        if '2020-09-21T00'<=t[:13]<='2020-09-21T06': ri_idx=i; break
    
    win=4
    coh=[]
    for i in range(len(thetas)-win+1):
        w=[x for x in thetas[i:i+win] if not math.isnan(x)]
        if len(w)>=2:
            coh.append({'start':times[i],'end':times[i+win-1],
                       'theta_std':float(np.std(w)),'theta_mean':float(np.mean(w))})
    
    if coh and ri_idx:
        stds=[c['theta_std'] for c in coh]
        bl=np.median(stds[:max(1,ri_idx)])
        rupt=[(c['start'],c['theta_std']) for c in coh if c['theta_std']>3*bl]
        return {'coherence_windows':coh,'baseline_std':bl,'rupture_points':rupt}
    return None

# ═══ Main ═══
if __name__=='__main__':
    if not ERA5.exists():
        print("❌ No ERA5. Run download first.")
        sys.exit(1)
    
    print(f"{'═'*60}")
    print(f"  🧪 Phase 1 v2: Dolphin 2020 ζ-field 分辨率橋接")
    print(f"{'═'*60}")
    
    print("\n🔬 Path A: Ô-HAT on 0.5° vorticity...")
    hat=path_a()
    def clean(o):
        if isinstance(o, dict): return {k:clean(v) for k,v in o.items()}
        if isinstance(o, list): return [clean(v) for v in o]
        if isinstance(o, (np.floating, np.integer)): return o.item()
        if isinstance(o, np.bool_): return bool(o)
        return o
    json.dump(clean(hat),open(OUT_DIR/'hat_05deg.json','w'),indent=2)
    ths=[r['theta1'] for r in hat if not math.isnan(r['theta1'])]
    print(f"   {len(hat)} steps, θ₁: {np.mean(ths):.1f}°±{np.std(ths):.1f}° ({len(ths)} valid)")
    
    print("\n📐 Path B: Native 0.25° ground truth...")
    nat=path_b()
    json.dump(clean(nat),open(OUT_DIR/'native_025deg_v2.json','w'),indent=2)
    print(f"   {len(nat)} steps")
    
    print("\n🔄 Phase coherence...")
    pc=coherence(hat)
    if pc:
        json.dump(clean(pc),open(OUT_DIR/'phase_coherence_v2.json','w'),indent=2)
    
    print("\n📊 Compare...")
    comp=compare(hat,nat)
    json.dump(clean(comp),open(OUT_DIR/'comparisons_v2.json','w'),indent=2)
    
    # Metrics
    serr=[c['spatial_err_singularity'] for c in comp]
    terr=[c['spatial_err_track'] for c in comp]
    dh=[c['hat_dH'] for c in comp]
    ncv=[c['nat_core_vort'] for c in comp]
    ncd=[c['nat_core_lap'] for c in comp]
    nce=[c['nat_core_ens'] for c in comp]
    
    r_v,p_v=stats.pearsonr(dh,ncv)
    r_l,p_l=stats.pearsonr(dh,ncd)
    r_e,p_e=stats.pearsonr(dh,nce)
    
    # Cross-correlation lag
    if len(dh)>10:
        xc=np.correlate(dh-np.mean(dh),ncv-np.mean(ncv),mode='full')
        lags=np.arange(-len(dh)+1,len(dh))
        bl=lags[np.argmax(np.abs(xc))]
    else: bl=0
    
    print(f"\n{'═'*60}")
    print(f"  📊 結果")
    print(f"{'═'*60}")
    print(f"  空間誤差（singularity）: {np.mean(serr):.2f}° ± {np.std(serr):.2f}°")
    print(f"  空間誤差（track center）: {np.mean(terr):.2f}° ± {np.std(terr):.2f}°")
    print(f"  dH_curl × native core ζ:     r={r_v:.3f} p={p_v:.4f}")
    print(f"  dH_curl × native core ∇²ζ:   r={r_l:.3f} p={p_l:.4f}")
    print(f"  dH_curl × native enstrophy:  r={r_e:.3f} p={p_e:.4f}")
    print(f"  最優 lag: {bl} steps ({bl*3}h) {'← Ô-HAT leads' if bl<0 else '← native leads' if bl>0 else ''}")
    
    if pc and pc.get('rupture_points'):
        print(f"  Phase coherence 破裂: {len(pc['rupture_points'])} 點")
        for rp in pc['rupture_points'][:3]:
            print(f"    {rp[0]} std={rp[1]:.1f}°")
    
    print(f"\n💾 {OUT_DIR}")
    print(f"✅ Done")
