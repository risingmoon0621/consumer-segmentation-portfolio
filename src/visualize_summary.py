"""Create charts from the published SPSS cluster summary, not respondent-level data.
This portfolio companion script does not reproduce clustering or the original Python analysis.
Run from the project root: python src/visualize_summary.py
"""
from pathlib import Path
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parents[1]
with (root / 'data/segment_summary.csv').open(newline='', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
counts = np.array([int(r['count']) for r in rows])
labels = [f"S{r['segment']}" for r in rows]
colors = ['#2F597B', '#298B85', '#CC8E37']
figures = root / 'figures'
figures.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'text.color':'#202B35','axes.labelcolor':'#202B35','axes.edgecolor':'#A2AAB2','xtick.color':'#52606C','ytick.color':'#202B35'})
fig,ax=plt.subplots(figsize=(7.0,2.6),dpi=210)
fig.subplots_adjust(left=.01,right=.99,top=.98,bottom=.03)
ax.pie(counts,colors=colors,startangle=90,counterclock=False,wedgeprops={'width':.30,'edgecolor':'white','linewidth':2})
ax.text(0,.06,f'{counts.sum()}',ha='center',va='center',fontsize=24,fontweight='bold',color='#202B35')
ax.text(0,-.17,'valid responses',ha='center',va='center',fontsize=9,color='#52606C')
ax.set_aspect('equal'); ax.set_xlim(-1.2,2.9); ax.set_ylim(-1.12,1.12)
descs=['Lower activity, lower snack score','Higher activity, lower snack score','Higher snack score']
for i,(c,n,desc) in enumerate(zip(colors,counts,descs)):
    y=.66-i*.66
    ax.scatter(1.18,y,s=75,c=c,marker='s',clip_on=False)
    ax.text(1.38,y+.11,f'S{i+1}  |  {n}  ({100*n/counts.sum():.1f}%)',va='center',fontweight='bold',fontsize=10)
    ax.text(1.38,y-.10,desc,va='center',fontsize=8.4)
fig.savefig(figures/'segment_distribution.png',bbox_inches='tight',pad_inches=.1,facecolor='white')
plt.close(fig)
fig,ax=plt.subplots(figsize=(7.3,3.25),dpi=210)
variables=['Perceived stress','Physical activity','Sweet snack score']
keys=['stress_z','activity_z','snack_z']
positions=np.arange(3)
for i,r in enumerate(rows):
    vals=[float(r[k]) for k in keys]
    y=positions+(i-1)*.24
    ax.barh(y, vals, height=.20, label=labels[i], color=colors[i])
    for v,yy in zip(vals,y):
        ax.text(v+(.045 if v>=0 else -.045), yy, f'{v:+.2f}',ha='left' if v>=0 else 'right',va='center',fontsize=8.5)
ax.axvline(0,color='#56616B',linewidth=.9)
ax.set_yticks(positions,variables)
ax.invert_yaxis()
ax.set_xlim(-1.04,2.20)
ax.set_xlabel('Standardized cluster center (z-score)')
ax.xaxis.grid(True,alpha=.16)
ax.set_axisbelow(True)
for spine in ('top','right','left'):ax.spines[spine].set_visible(False)
ax.tick_params(axis='y',length=0)
ax.legend(loc='lower center',bbox_to_anchor=(.5,1.00),ncol=3,frameon=False,fontsize=9)
fig.tight_layout(pad=.7)
fig.savefig(figures/'cluster_centers.png',bbox_inches='tight',pad_inches=.10,facecolor='white')
plt.close(fig)
