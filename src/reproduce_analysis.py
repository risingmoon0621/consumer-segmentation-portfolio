"""Reproduce and audit the team report using a private survey workbook.
No participant-level data or assignments are exported; outputs are aggregate only.
Usage: python src/reproduce_analysis.py /private/path/to/anket_cevaplari_153.xlsx
"""
from pathlib import Path
import argparse, json, os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('MKL_NUM_THREADS','1')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.metrics import silhouette_score, adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.decomposition import PCA
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist
from scipy.stats import f_oneway

parser=argparse.ArgumentParser()
parser.add_argument('workbook',help='Private workbook with cleaned survey responses')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
data_dir=root/'data';fig_dir=root/'figures'
data_dir.mkdir(exist_ok=True);fig_dir.mkdir(exist_ok=True)
d=pd.read_excel(args.workbook)
items=[f'PSS_{i}' for i in range(1,11)]
reverse=['PSS_4','PSS_5','PSS_7','PSS_8']
req=items+['Vig_Days','Vig_Min','Mod_Days','Mod_Min','Walk_Days','Walk_Min','IPAQ_Score','PSS_Total','Snack_Freq','Snack_Portion','Snack_Score']
if d[req].isna().any().any():
    raise ValueError('Missing model inputs; inspect before fitting.')
r=d[items].copy();r[reverse]=4-r[reverse]
checks={'input_rows':len(d),'columns':len(d.columns),'missing_cells':int(d.isna().sum().sum()),
 'duplicate_excluding_ID_Puan':int(d.drop(columns=['ID','Puan'],errors='ignore').duplicated().sum()),
 'pss_formula_matches':int(np.isclose(r.sum(axis=1),d.PSS_Total).sum()),
 'ipaq_formula_matches':int(np.isclose(8*d.Vig_Days*d.Vig_Min+4*d.Mod_Days*d.Mod_Min+3.3*d.Walk_Days*d.Walk_Min,d.IPAQ_Score).sum()),
 'snack_formula_matches':int(np.isclose(d.Snack_Freq*d.Snack_Portion,d.Snack_Score).sum())}
assert checks['pss_formula_matches']==checks['ipaq_formula_matches']==checks['snack_formula_matches']==len(d)
q1,q3=d.IPAQ_Score.quantile([.25,.75]); upper=q3+3*(q3-q1)
a=d.loc[d.IPAQ_Score<=upper].copy()
r=a[items].copy();r[reverse]=4-r[reverse]
alpha=10/9*(1-r.var(ddof=1).sum()/r.sum(axis=1).var(ddof=1))
X=a[['PSS_Total','IPAQ_Score','Snack_Score']]
Z=((X-X.mean())/X.std(ddof=1)).to_numpy()
ref=pd.read_csv(data_dir/'segment_summary.csv')[['stress_z','activity_z','snack_z']].to_numpy()
checks.update({'upper_outer_fence':float(upper),'activity_outliers_removed':len(d)-len(a),
 'retained':len(a),'max_activity_retained':float(a.IPAQ_Score.max()),'cronbach_alpha':float(alpha)})
metrics=[];models={}
for k in range(1,9):
    m=KMeans(n_clusters=k,random_state=42,n_init=50).fit(Z)
    models[k]=m
    metrics.append({'k':k,'inertia':m.inertia_,'silhouette':silhouette_score(Z,m.labels_) if k>1 else np.nan,
                    'calinski_harabasz':calinski_harabasz_score(Z,m.labels_) if k>1 else np.nan,
                    'davies_bouldin':davies_bouldin_score(Z,m.labels_) if k>1 else np.nan})
metric=pd.DataFrame(metrics);metric.to_csv(data_dir/'model_metrics.csv',index=False,float_format='%.6f')
seeded=KMeans(n_clusters=3,init=ref,n_init=1,random_state=42).fit(Z)
ind=models[3];_,order=linear_sum_assignment(cdist(ref,ind.cluster_centers_))
counts_ref=np.bincount(seeded.labels_,minlength=3);counts_ind=np.bincount(ind.labels_,minlength=3)[order]
reference_rows=[]
for i in range(3):
    reference_rows.append({'segment':i+1,'reported_count':int(pd.read_csv(data_dir/'segment_summary.csv').iloc[i]['count']),
      'reference_initialized_count':int(counts_ref[i]),'independent_count':int(counts_ind[i]),
      **{f'reference_{name}_z':float(seeded.cluster_centers_[i,j]) for j,name in enumerate(['stress','activity','snack'])},
      **{f'independent_{name}_z':float(ind.cluster_centers_[order[i],j]) for j,name in enumerate(['stress','activity','snack'])}})
pd.DataFrame(reference_rows).to_csv(data_dir/'replication_comparison.csv',index=False,float_format='%.6f')
ward=AgglomerativeClustering(n_clusters=3,linkage='ward').fit(Z)
pca=PCA(n_components=2).fit(Z)
projected=pca.transform(seeded.cluster_centers_)
pss=seeded.labels_
tests=[]
for c in ['Age','Year_Study','Team_Freq','Gym_Freq','Budget','Snack_Freq']:
    if c in a:
        groups=[a.loc[pss==i,c].to_numpy() for i in range(3)]
        F,p=f_oneway(*groups)
        overall=a[c].mean()
        ss_between=sum(len(g)*(g.mean()-overall)**2 for g in groups); ss_total=((a[c]-overall)**2).sum()
        tests.append({'variable':c,'F':F,'p_raw':p,'eta_squared':ss_between/ss_total})
pd.DataFrame(tests).to_csv(data_dir/'profile_anova.csv',index=False,float_format='%.8g')
# Resample the observations, refit unsupervised K-means, predict all original points, compare with independent k=3.
rng=np.random.default_rng(42);aris=[]
for rep in range(60):
    sample=rng.choice(len(Z),len(Z),replace=True)
    boot=KMeans(n_clusters=3,n_init=15,random_state=rep).fit(Z[sample])
    aris.append(adjusted_rand_score(ind.labels_,boot.predict(Z)))
checks.update({'reference_count':counts_ref.tolist(),'independent_count':counts_ind.tolist(),
   'max_abs_reference_center_difference':float(abs(seeded.cluster_centers_-ref).max()),
   'reference_inertia':float(seeded.inertia_),'reference_silhouette':float(silhouette_score(Z,seeded.labels_)),
   'independent_inertia':float(ind.inertia_),'independent_silhouette':float(silhouette_score(Z,ind.labels_)),
   'ari_reference_vs_independent':float(adjusted_rand_score(seeded.labels_,ind.labels_)),
   'ari_ward_vs_independent':float(adjusted_rand_score(ward.labels_,ind.labels_)),
   'bootstrap_ari_median':float(np.median(aris)),'bootstrap_ari_p10':float(np.quantile(aris,.1)),
   'bootstrap_ari_p90':float(np.quantile(aris,.9)),
   'pca_explained_ratio':pca.explained_variance_ratio_.tolist()})
(data_dir/'validation_summary.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
# Visualizations, aggregate only.
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,
 'text.color':'#202B35','axes.labelcolor':'#202B35','xtick.color':'#52606C','ytick.color':'#52606C'})
fig,axs=plt.subplots(1,2,figsize=(9.2,3.5),dpi=220)
x=metric.k
axs[0].plot(x,metric.inertia,marker='o',color='#2F597B',linewidth=2)
axs[0].scatter([3],[ind.inertia_],s=80,facecolors='white',edgecolors='#298B85',linewidths=2,zorder=5)
axs[0].set(title='Elbow curve',xlabel='Number of clusters (k)',ylabel='Within-cluster sum of squares')
axs[0].set_xticks(x);axs[0].grid(alpha=.15)
axs[1].plot(x[1:],metric.silhouette[1:],marker='o',color='#2F597B',label='Independent fits',linewidth=2)
axs[1].scatter([3],[checks['reference_silhouette']],marker='D',s=55,color='#CC8E37',label='SPSS-center initialization',zorder=4)
axs[1].set(title='Silhouette comparison',xlabel='Number of clusters (k)',ylabel='Silhouette score',ylim=(0.26,.34))
axs[1].set_xticks(x[1:]);axs[1].grid(alpha=.15);axs[1].legend(fontsize=8,loc='lower right',frameon=False)
fig.tight_layout();fig.savefig(fig_dir/'model_selection.png',bbox_inches='tight',dpi=220);plt.close(fig)
fig,ax=plt.subplots(figsize=(6.8,3.5),dpi=220)
for i,(xy,c,n) in enumerate(zip(projected,['#2F597B','#298B85','#CC8E37'],counts_ref)):
    ax.scatter(*xy,s=30+5*n,c=c,alpha=.88,edgecolor='white',linewidth=1.4)
    ax.annotate(f'S{i+1} (n={n})',xy,xytext=(9,9),textcoords='offset points',fontweight='bold')
ax.axhline(0,color='#AAB4BD',linewidth=.8);ax.axvline(0,color='#AAB4BD',linewidth=.8)
ax.set(xlabel=f'PC1 ({pca.explained_variance_ratio_[0]*100:.1f}% variance)',ylabel=f'PC2 ({pca.explained_variance_ratio_[1]*100:.1f}% variance)')
ax.margins(.25);ax.grid(alpha=.16);fig.tight_layout()
fig.savefig(fig_dir/'pca_centers.png',bbox_inches='tight',dpi=220);plt.close(fig)
print(json.dumps(checks,indent=2))
