"""Offline literature screening. No hardware, deployment, or calibrated=true writes.
Data: McLaren et al (2005), Fig.3; visual reads rounded to nearest 1 F.
Approximate digitization, NOT original data; assumed reading sensitivity +/-1 F.
LOCO = leave one published curve out, SAME study/vehicle, not independent vehicle validation.
"""
import json, math, hashlib
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
P=Path(__file__).parent
minutes=np.arange(0,61,5,dtype=float)
curves_f={
 'ambient_73F':[73,83,90,95,99,102,104,106,108,109,111,112,113],
 'ambient_74F':[74,86,95,100,104,107,110,112,114,115,116,117,117],
 'ambient_77F':[77,94,100,104,106,109,110,112,114,114,116,118,118],
 'ambient_78F':[78,89,95,99,102,105,106,107,109,110,111,112,112],
 'ambient_84F':[84,97,103,108,111,114,116,118,120,122,123,124,125],
 'ambient_88F':[88,96,105,112,117,122,125,127,130,132,133,135,137],
 'ambient_93F':[93,100,106,110,114,117,119,122,124,125,127,129,130],
}
(P/'digitized_fig3.json').write_text(json.dumps({'source_doi':'10.1542/peds.2004-2368','figure':3,'minutes':minutes.tolist(),'temperature_F':curves_f,'method':'Visual reading from original embedded raster; integer F; approximate, not original observations.','reading_sensitivity_F':1.0},indent=2))
curves={k:(np.array(v)-32)*5/9 for k,v in curves_f.items()}
def fit(values):
 def residual(x):
  a,tau=x
  return np.concatenate([a*(-np.expm1(-minutes[1:]/tau))-(v[1:]-v[0]) for v in values])
 r=least_squares(residual,[25,22],bounds=([0.01,0.1],[200,1000]),xtol=1e-12,ftol=1e-12,gtol=1e-12)
 return r.x

def first_cross(t,y,threshold=35):
 if y[0]>=threshold:return float(t[0])
 for i in range(1,len(y)):
  if y[i]>=threshold:return float(t[i-1]+(threshold-y[i-1])/(y[i]-y[i-1])*(t[i]-t[i-1]))
 return None

def rc_eta(t0,ta,R,C,Q,risk=35):
 if t0>=risk:return 0.0
 eq=ta+R*Q
 if eq<=risk:return None
 return -R*C*math.log((eq-risk)/(eq-t0))/60

def summary(err):
 a=np.array(err);return {'mae_C':float(np.mean(abs(a))),'rmse_C':float(np.sqrt(np.mean(a*a))),'max_abs_C':float(max(abs(a)))}
A,tau=fit(list(curves.values()))
folds=[];all_err=[];rolling={h:{k:[] for k in ['persistence','linear','adaptive_rc']} for h in [5,10]}
for key,values in curves.items():
 a,tt=fit([v for k,v in curves.items() if k!=key])
 pred=values[0]+a*(-np.expm1(-minutes/tt))
 err=pred[1:]-values[1:];all_err.extend(err)
 obs=first_cross(minutes,values)
 eta=-tt*math.log(1-(35-values[0])/a) if values[0]<35<values[0]+a else (0 if values[0]>=35 else None)
 folds.append({'case':key,'fit_other_curves_A_C':float(a),'fit_other_curves_tau_min':float(tt),**summary(err),'observed35_graph_interpolated_min':obs,'predicted35_min':eta,'eta_error_min':None if eta is None or obs is None else eta-obs})
 for h in [5,10]:
  steps=h//5
  for i in range(2,len(minutes)-steps):
   slope=np.polyfit(minutes[i-2:i+1]-minutes[i],values[i-2:i+1],1)[0]
   target=values[i+steps]
   predictions={'persistence':values[i],'linear':values[i]+slope*h,'adaptive_rc':values[i]+slope*tt*(-math.expm1(-h/tt))}
   for name,prediction in predictions.items():rolling[h][name].append(float(prediction-target))
# Reading sensitivity only; not a statistical prediction interval.
rng=np.random.default_rng(20261028)
sensitivity=[]
for _ in range(200):
 perturbed=[v+rng.uniform(-5/9,5/9,len(v)) for v in curves.values()]
 sensitivity.append(fit(perturbed).tolist())
sens=np.array(sensitivity)
# Exact-vs-Euler numerical correctness, separate from empirical prediction accuracy.
R=1/60;C=125*3600;Q=1800;ta=t0=20
num=t0;max_error=0.0
for t in range(1,3601):
 num+=((ta-num)/R+Q)/C
 exact=ta+R*Q+(t0-ta-R*Q)*math.exp(-t/(R*C))
 max_error=max(max_error,abs(num-exact))
results={
 'source_equation':'C*dT/dt=(Ta-T)/R+Q; R=1/H; C=3600*mC(Wh/K)',
 'gaspar2024_table1':{'R_K_W':R,'C_J_K':C,'Q_W':Q,'tau_min':R*C/60,'rise30_C':R*Q*(-math.expm1(-1800/(R*C))),'rise60_C':R*Q*(-math.expm1(-3600/(R*C))),'t35_from20_min':rc_eta(20,20,R,C,Q),'euler1s_max_error_1h_C':max_error},
 'existing_placeholder':{'R_K_W':0.2,'C_J_K':1000,'Q_W':80,'tau_min':.2*1000/60,'equilibrium_at_Ta5_C':5+.2*80,'t35_from20_min':rc_eta(20,20,.2,1000,80)},
 'mclaren_published_summary':{'rise60_mean_C':41*5/9,'rise60_range_C':[28*5/9,49*5/9],'fraction_30_over60':.8},
 'mclaren_fig3_common_fit':{'A_C':float(A),'tau_min':float(tau),'note':'Fit to all 7 approximate graph curves; this is calibration, not validation.'},
 'loco':{'metrics':summary(all_err),'folds':folds,'note':'Same-study graph-held-out curves; no independent vehicle/environment validation; no irradiance control.'},
 'rolling_forecast':{str(h):{name:{**summary(e),'n':len(e)} for name,e in models.items()} for h,models in rolling.items()},
 'digitization_sensitivity':{'replicates':200,'seed':20261028,'A_C_minmax':[float(sens[:,0].min()),float(sens[:,0].max())],'tau_min_minmax':[float(sens[:,1].min()),float(sens[:,1].max())],'note':'Uniform independent +/-1 F perturbations; reading sensitivity only, NOT confidence or prediction interval.'}}
(P/'results.json').write_text(json.dumps(results,indent=2))
warmup_cases=[k for k,v in curves.items() if v[2]>=35]
results['cold_start_screen']={'history_minutes':10,'threshold_C':35,'cases_at_or_above_threshold_when_history_ready':warmup_cases,'count':len(warmup_cases),'total':len(curves),'note':'Approximate graph readings. A history-only forecast cannot provide a pre-threshold warning in these cases.'}
results['digitization_quality_check']='Compared color-trace pixel positions against axes; corrected six one-F visual readings. Overlapping curves remain approximate. Not raw instrument measurements.'
assert rc_eta(35,20,R,C,Q)==0
assert rc_eta(20,5,.2,1000,80) is None
assert max_error<.001
assert abs(rc_eta(20,20,R,C,Q)*60-R*C*math.log(2))<1e-8
(P/'results.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
