#!/usr/bin/env python3
"""Redraw the nine public-data figures from the accompanying frozen JSON.
Usage: python3 rebuild-dos-public-charts-2026-10-20.py [data.json] [output_dir]
Requires matplotlib. JSON describes fixed windows, cohorts, methods and archive hashes.
"""
from pathlib import Path
import json,sys,datetime as dt,statistics
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt,matplotlib.dates as md
here=Path(__file__).resolve().parent
source=Path(sys.argv[1]) if len(sys.argv)>1 else here/'dos-public-chart-data-2026-10-20.json'
out=Path(sys.argv[2]) if len(sys.argv)>2 else here.parent/'images';out.mkdir(parents=True,exist_ok=True)
d=json.loads(source.read_text());BG='#1e1e1e';FG='#e6e6e6';MUT='#b1b1b1';GREEN='#00ff7f';RED='#ff6b6b';BLUE='#66c9ff';AMBER='#ffb454';PURPLE='#b48cff'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':FG,'axes.labelcolor':MUT,'xtick.color':MUT,'ytick.color':MUT,'axes.edgecolor':'#555','axes.facecolor':BG,'figure.facecolor':BG,'savefig.facecolor':BG})
def date(s):return dt.datetime.fromisoformat(s)
def style(ax,timeaxis=True):
 ax.grid(True,color='#3a3a3a',lw=.65);ax.set_axisbelow(True)
 for side in ['top','right']:ax.spines[side].set_visible(False)
 if timeaxis:ax.xaxis.set_major_locator(md.AutoDateLocator(minticks=6,maxticks=9));ax.xaxis.set_major_formatter(md.DateFormatter('%b %d'))
def canvas(title,subtitle,notes,figsize=(11,6.4)):
 fig,ax=plt.subplots(figsize=figsize,dpi=160);fig.subplots_adjust(left=.10,right=.96,top=.76,bottom=.21)
 fig.text(.055,.945,title,fontsize=17,weight='bold',ha='left',va='top');fig.text(.055,.875,subtitle,fontsize=10.5,color=MUT,ha='left',va='top',linespacing=1.4)
 fig.text(.055,.105,notes,fontsize=9.4,color=MUT,ha='left',va='top',linespacing=1.4);fig.text(.96,.035,'Produced by 1AEO · UTC',fontsize=9,color=MUT,ha='right');style(ax);return fig,ax
def save(fig,name):
 for axis in fig.axes:
  if isinstance(axis.xaxis.get_major_formatter(),md.DateFormatter):axis.set_xlim(axis.dataLim.x0,axis.dataLim.x1)
 fig.savefig(out/name);plt.close(fig)
def mark(ax,t,y,label,offset=(0,15),color=FG):
 ax.scatter([t],[y],color=color,s=25,zorder=5);ax.annotate(label,(t,y),xytext=offset,textcoords='offset points',ha='center',va='bottom',fontsize=10,color=color,arrowprops={'arrowstyle':'-','color':color,'lw':.8})
# Daily publishing set, explicit denominator and historical endpoint.
fig,ax=canvas('Two early peaks in daily overload reports','Daily unique relays publishing an overload report / all relays publishing that UTC day\nJune 15–July 13, 2026 · finalized June and July archives','A report can remain in descriptors for 72 hours after its last trigger.\nThis counts report publication, not simultaneous overload or confirmed attack victims.')
rows=list(d['daily'].items());X=[date(k) for k,v in rows];Y=[v['pct'] for k,v in rows];ax.plot(X,Y,color=RED,lw=2.5);ax.fill_between(X,Y,color=RED,alpha=.13);ax.set_ylabel('Daily publishers with an overload report (%)');ax.set_ylim(0,15)
for day,label,off in [('2026-06-28','Jun 28 · 8.19%\n814 relays',(0,13)),('2026-07-12','Jul 12 · 12.31%\n1,265 relays',(-60,16))]:mark(ax,date(day),d['daily'][day]['pct'],label,off,RED)
ax.text(.98,.42,'Jul 13: 11.77%\n1,200 / 10,194',transform=ax.transAxes,ha='right',color=MUT,fontsize=10);save(fig,'circuit-building-dos-wave-june-2026-chart-network-overload-only.png')
# Flag eligibility groups, not circuit roles.
fig,ax=canvas('Overload reports were most common among Guard-flagged relays','Daily reports joined to each day’s 12:00 UTC consensus · June 1–July 12, 2026','Denominator: relays in each noon flag group. HSDir without Guard overlaps other groups.\nConsensus flags describe eligibility; these curves do not identify a circuit’s hop or traffic type.')
stylelist=[('Guard_without_Exit','Guard, no Exit',RED),('Guard_with_Exit','Guard + Exit',AMBER),('Exit_without_Guard','Exit, no Guard',GREEN),('neither','Neither Guard nor Exit',PURPLE),('HSDir_without_Guard','HSDir, no Guard',BLUE)]
X=[date(k) for k in d['flag_daily']]
for key,label,col in stylelist:ax.plot(X,[v[key]['pct'] for v in d['flag_daily'].values()],color=col,lw=2,ls='--' if key.startswith('HSDir') else '-',label=label)
ax.set_ylabel('Flag group publishing an overload report (%)');ax.set_ylim(0,21);ax.legend(fontsize=9.3,loc='upper left',facecolor=BG,edgecolor='#555',labelcolor=FG,ncol=2);save(fig,'circuit-building-dos-wave-june-2026-chart-guards-vs-exits.png')
# Six-hour endpoint departures; missing comparisons deliberately omitted.
fig,ax=canvas('More relays were absent at the next six-hour snapshot','Previous Running set absent from the next Running set / previous Running set\nJune 1–July 13, 2026 · 00:00 / 06:00 / 12:00 / 18:00 UTC consensuses','Only endpoints exactly six hours apart are compared; missing snapshots leave a gap.\nA departure does not reveal its cause; a departure and return between endpoints are not counted.')
rows=d['departures'];X=[date(r['time']) for r in rows];Y=[r['network_pct'] if r['interval_hours']==6 else float('nan') for r in rows];ax.plot(X,Y,color=RED,lw=2);ax.fill_between(X,Y,color=RED,alpha=.13);ax.set_ylabel('Prior Running set absent six hours later (%)');save(fig,'circuit-building-dos-wave-june-2026-chart-netflap-rate.png')
# Hourly churn and counts.
fig,axs=plt.subplots(2,1,figsize=(11,8.5),dpi=160,sharex=True);fig.subplots_adjust(left=.10,right=.96,top=.79,bottom=.17,hspace=.25)
fig.text(.055,.956,'Running-set membership changed more often during the event',fontsize=16.5,weight='bold',va='top');fig.text(.055,.902,'Hourly consensuses · June 15–July 12, 2026\nMembership changes include entries and departures; they do not measure circuit availability.',fontsize=10.5,color=MUT,va='top',linespacing=1.5)
h=d['hourly'];X=[date(r[0]) for r in h['hourly']];on=[r[2] for r in h['hourly']];ch=[r[1] for r in h['hourly']]
for ax in axs:style(ax)
axs[0].plot(X,on,color=BLUE,lw=1.4);axs[0].axhline(h['base_online'],color=MUT,ls='--',lw=1);axs[0].set_ylabel('Running relays');axs[0].text(.02,.10,'June 15–21 mean: 9,802\nMinimum: 9,333 (June 30)',transform=axs[0].transAxes,color=MUT,fontsize=10)
axs[1].plot(X,ch,color=RED,lw=1.1);axs[1].axhline(h['base_churn'],color=MUT,ls='--',lw=1);axs[1].set_ylabel('Entries + departures / hour');axs[1].text(.02,.93,'June 26–July 2: 3.2× baseline\nJuly 6–12: 2.8× baseline',transform=axs[1].transAxes,ha='left',va='top',fontsize=10)
fig.text(.055,.105,'Relays with at least two observed membership transitions: 2,036 → 5,925 (2.9×).\nEqual 16-day windows: June 9–24 and June 25–July 10. First observed appearances excluded from this count.',fontsize=9.6,color=MUT,va='top',linespacing=1.4);fig.text(.96,.035,'Produced by 1AEO · UTC',fontsize=9,color=MUT,ha='right');save(fig,'circuit-building-dos-wave-june-2026-chart-network-flap.png')
# Cumulative distinct and daily report counts.
fig,ax=canvas('The cumulative report count reached 4,574 relay identities','June 24–July 27, 2026 · daily publication counts and cumulative in-window trigger timestamps','4,271 of the 9,961 July 8 reference relays reported an in-window trigger (42.9%).\nAnother 303 reporting identities were outside that reference cohort. Neither curve identifies attack victims.')
rows=d['cumulative'];X=[date(r['date']) for r in rows];ax.plot(X,[r['cumulative'] for r in rows],color=GREEN,lw=2.8,label='Cumulative identities with in-window trigger timestamp');ax.plot(X,[r['daily'] for r in rows],color=RED,lw=2.2,label='Daily publishers carrying an overload report');ax.set_ylabel('Distinct relay identities');ax.set_ylim(0,5400);ax.legend(fontsize=9.8,loc='upper left',facecolor=BG,edgecolor='#555',labelcolor=FG)
mark(ax,X[-1],rows[-1]['cumulative'],'4,574',(-5,10),GREEN);mark(ax,date('2026-07-21'),1330,'Daily peak: 1,330',(0,18),RED)
ax.text(.03,.45,'First 20 days: 3,353 identities\nPre-event 20-day windows: 695–762',transform=ax.transAxes,color=MUT,fontsize=10);save(fig,'circuit-building-dos-wave-june-2026-chart-blastradius.png')
# Explicit equal-count deciles.
fig,ax=canvas('Overload reports appeared across consensus-weight deciles','July 8 reference cohort: 4,113 relays with Guard and without Exit\nShare with a reported trigger timestamp during June 24–July 27, 2026','Equal-count groups sorted by consensus weight; fingerprint breaks ties.\nAn “any report” indicator does not measure attack intensity, CPU work or equal exposure.')
rows=d['deciles'];vals=[r['pct'] for r in rows];ax.bar(range(1,11),vals,color=GREEN,alpha=.8,width=.72)
for i,v in enumerate(vals,1):ax.text(i,v+1.3,f'{v:.1f}%',ha='center',fontsize=10)
ax.set_xticks(range(1,11),[str(i) for i in range(1,11)]);ax.set_xlabel('Consensus-weight decile (lowest → highest)');ax.set_ylabel('Relays with an in-window report (%)');ax.set_ylim(0,82);ax.grid(False,axis='x');save(fig,'circuit-building-dos-wave-june-2026-chart-weightdeciles.png')
# HSDir population counts; exact contemporaneous ContactInfo classification.
fig,ax=canvas('The HSDir population remained below its June plateau','Hourly HSDir-flagged relay counts · June 14–July 27, 2026','July 27 at noon: 3,640 relays, 62.9% of the June 15–21 noon mean (5,787).\nCounts measure flag eligibility, not bandwidth capacity. 1AEO includes its planned July 11 restart.')
rows=d['hsdir'];X=[date(r['time']) for r in rows];ax.plot(X,[r['hsdir'] for r in rows],color=GREEN,lw=2.1,label='All HSDir-flagged relays');ax.plot(X,[r['non_aeo_hsdir'] if not r['unknown_hsdir'] else float('nan') for r in rows],color=BLUE,lw=1.5,label='Excluding historical 1AEO ContactInfo');ax.set_ylabel('HSDir-flagged relay count');ax.set_ylim(0,6600);ax.legend(fontsize=10,loc='upper right',facecolor=BG,edgecolor='#555',labelcolor=FG)
mark(ax,date('2026-07-22 09:00:00'),917,'917 · July 22',(40,18),RED);save(fig,'onion-service-directory-chart-hsdir-population.png')
# Plain ratio of counts, not traffic or assignment estimates.
base=d['hsdir_baseline'];fig,ax=canvas('The non-1AEO HSDir count fell sharply, then partly recovered',f'Baseline count ÷ current count · baseline = {base:,.1f} (June 17–24 hourly median)\nJune 17–July 27, 2026 · historical ContactInfo classification','A value of 2 means half as many non-1AEO HSDir-flagged relays as at baseline.\nThis ratio does not measure descriptor requests, each relay’s responsibility or traffic load.')
rows=[r for r in d['hsdir'] if r['time']>='2026-06-17'];X=[date(r['time']) for r in rows];Y=[base/r['non_aeo_hsdir'] if not r['unknown_hsdir'] and r['non_aeo_hsdir'] else float('nan') for r in rows];ax.plot(X,Y,color=GREEN,lw=2.2);ax.fill_between(X,1,Y,color=GREEN,alpha=.12);ax.axhline(1,color=MUT,ls='--',lw=1);ax.set_ylabel('Baseline count / current count');ax.set_ylim(0,max(x for x in Y if x==x)*1.2);i=max(range(len(Y)),key=lambda i:Y[i] if Y[i]==Y[i] else -1);mark(ax,X[i],Y[i],f'{Y[i]:.2f}×',(-15,12),GREEN);save(fig,'onion-service-directory-chart-hsdir-load.png')
# Truly matched six-hour Guard-without-Exit departures; all maintenance included.
fig,ax=canvas('A matched comparison of six-hour Running-set departures','Guard-flagged relays without Exit in the prior snapshot · June 15–July 13, 2026\nHistorical descriptor ContactInfo identifies 1AEO; the rest-of-network line excludes 1AEO.','Both lines: prior cohort absent from next Running set ÷ prior cohort. All maintenance included.\nThis is not a count of attack-caused outages; departures returning between snapshots are missed.')
rows=[r for r in d['departures'] if r['time']>='2026-06-15'];X=[date(r['time']) for r in rows]
for field,label,col in [('aeo_pct','1AEO (historical ContactInfo)',GREEN),('rest_pct','Rest of network',RED)]:ax.plot(X,[r[field] if r['interval_hours']==6 else float('nan') for r in rows],color=col,lw=2,label=label)
ax.set_ylabel('Prior cohort absent six hours later (%)');ax.legend(fontsize=10,loc='upper right',facecolor=BG,edgecolor='#555',labelcolor=FG);save(fig,'circuit-building-dos-wave-june-2026-chart-flagflap.png')
print('Wrote nine figures to',out)
