"""Reproduce figures from original uploaded CSVs; no synthetic measurements."""
from pathlib import Path
import csv, json, math
from collections import Counter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
FIG=ROOT/'figures'; DER=ROOT/'derived'
FIG.mkdir(exist_ok=True); DER.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
def read(rel):
 with (ROOT/rel).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def number(s):
 try:return float(s)
 except (ValueError,TypeError):return math.nan
def save(fig,name):
 fig.savefig(FIG/(name+'.png'),dpi=220,bbox_inches='tight')
 fig.savefig(FIG/(name+'.svg'),bbox_inches='tight');plt.close(fig)
summary={'source':'Original uploaded CSVs. Frame/sample proportions are not independent accuracy estimates.','uwb':[]}
fig,axs=plt.subplots(2,1,figsize=(11,7),layout='constrained')
for n,ax in enumerate(axs,1):
 rel=f'raw/uwb_20261016/session_{n:02}/telemetry.csv';rows=read(rel)
 t0=float(rows[0]['monotonic_s']);t=[float(r['monotonic_s'])-t0 for r in rows]
 for field,label,color in [('raw_distance_m','Raw range','#b8c2d1'),('filtered_distance_m','Filtered range','#007c91')]:
  ax.plot(t,[number(r[field]) for r in rows],label=label,color=color,lw=1.3)
 ax.set(title=f'UWB session {n} | 2026-10-16 | {len(rows):,} records',xlabel='Elapsed time (s)',ylabel='Distance (m)');ax.grid(alpha=.2);ax.legend(loc='upper right')
 summary['uwb'].append({'source':rel,'records':len(rows),'elapsed_s':round(t[-1],3),'valid_records':sum(r['valid'].lower()=='true' for r in rows),'status_counts':dict(Counter(r['status'] for r in rows))})
fig.suptitle('Measured UWB range — reference distance not supplied',fontsize=15)
save(fig,'uwb_sessions')
base='raw/block_b_20261027/reply3/1_radar_test3/'
rows=read(base+'test3_radar.csv');actions=read(base+'test3_action_times.csv');cam=read(base+'test3_cam.csv')
t0=float(next(r for r in actions if r['event']=='start_empty')['안내_pi_time'])
t=[float(r['wall_time'])-t0 for r in rows]
positive=[int(number(r['num_tracks'])>0 or number(r['presence'])==1) for r in rows]
fig,axs=plt.subplots(3,1,figsize=(12,8),sharex=True,layout='constrained')
axs[0].step(t,[number(r['num_tracks']) for r in rows],where='post',color='#007c91',label='Tracked targets');axs[0].set_ylabel('Tracks')
axs[1].step(t,positive,where='post',color='#b65336');axs[1].set(ylabel='Presence evidence',yticks=[0,1])
axs[2].plot([float(r['wall_time'])-t0 for r in cam],[number(r['ratio']) for r in cam],color='#506bb2',lw=1);axs[2].set(ylabel='Camera motion ratio',xlabel='Seconds from empty-seat cue')
intervals=[(0,170,'Initial empty','#e4f2ed'),(180,300,'Seated still','#dbe9fa'),(315,375,'Empty after departure','#f7d8cf')]
summary['radar_test3']={'source':base+'test3_radar.csv','records':len(rows),'bad_frames':sum(number(r['bad_frame'])!=0 for r in rows),'intervals':[]}
for a,b,label,color in intervals:
 ids=[i for i,x in enumerate(t) if a<=x<b]
 pos=sum(positive[i] for i in ids)
 summary['radar_test3']['intervals'].append({'label':label,'start_s_inclusive':a,'end_s_exclusive':b,'frames':len(ids),'positive_frames':pos,'positive_percent':100*pos/len(ids) if ids else None})
 for ax in axs:ax.axvspan(a,b,color=color,alpha=.65,zorder=-1)
 axs[0].text((a+b)/2,1.02,label,ha='center',va='bottom',transform=axs[0].get_xaxis_transform(),fontsize=10)
for ax in axs:
 ax.grid(alpha=.2)
 for r in actions:
  x=number(r.get('실제_상대초'))
  if math.isfinite(x):ax.axvline(x,color='#555',ls=':',lw=.8)
axs[0].legend(loc='upper left');fig.suptitle('Radar test 3 — departure does not immediately clear tracks',fontsize=15)
save(fig,'radar_test3_timeline')
base='raw/block_b_20261027/reply3/2_camera/'
rows=read(base+'cam_light.csv');cues=read(base+'cam_light_cues.csv')
t0=float(next(r for r in cues if r['event']=='start_empty')['pi_time'])
t=[float(r['wall_time'])-t0 for r in rows]
fig,axs=plt.subplots(2,1,figsize=(12,6),sharex=True,layout='constrained')
axs[0].plot(t,[number(r['ratio']) for r in rows],color='#506bb2',lw=1);axs[0].set_ylabel('Changed-pixel ratio')
axs[1].step(t,[number(r['motion_active']) for r in rows],where='post',color='#007c91');axs[1].set(ylabel='Motion active',yticks=[0,1],xlabel='Seconds from empty-screen cue')
for ax in axs:
 ax.grid(alpha=.2)
 for r in cues:ax.axvline(float(r['pi_time'])-t0,color='#aaa',lw=.7,ls=':')
summary['camera_light']={'source':base+'cam_light.csv','records':len(rows),'kind_counts':dict(Counter(r['kind'] for r in rows)),'motion_active_records':sum(number(r['motion_active'])==1 for r in rows),'cue_source':base+'cam_light_cues.csv'}
fig.suptitle('Camera motion / lighting experiment — motion is not occupancy',fontsize=15)
save(fig,'camera_light_timeline')
(DER/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
with (DER/'radar_interval_summary.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(summary['radar_test3']['intervals'][0]));w.writeheader();w.writerows(summary['radar_test3']['intervals'])
print(json.dumps(summary,ensure_ascii=False,indent=2))
