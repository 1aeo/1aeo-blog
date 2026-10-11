#!/usr/bin/env python3
# Chart: "Scale vs. overload — 1AEO owns the top-left corner (most guards, least overloaded)"
# (blog image: circuit-building-dos-wave-june-2026-chart-guard-bubble.png)
#
# DATA PROVENANCE (fully public, Onionoo — the same source Tor Metrics uses):
#   For each of the top-10 guard operators (by guard count, grouped by AROI operator domain proven in
#   ContactInfo), we count its Guard-flag relays and the share of them currently signalling overload.
#     guards   = relays returned by  https://onionoo.torproject.org/details?contact=<domain>&type=relay
#                that carry the "Guard" flag.
#     overload = of those, the share whose `overload_general_timestamp` is set (an active overload signal).
#   This uses the DEFAULT Onionoo query (all Guard-flag relays, no running filter), so re-running the
#   documented query reproduces these counts directly.
#
# SNAPSHOT: 2026-07-13 (Onionoo serves only current data; the values below are the immutable record of
#   that snapshot and are what the chart plots). Run with `--verify` to fetch Onionoo now and print the
#   current numbers for comparison.
#
# Requires: python3 + matplotlib.  Usage: python3 chart-guard-bubble.py [output.png] [--verify]
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = next((a for a in sys.argv[1:] if not a.startswith("--")),
           "chart-guard-bubble.png")

# top-10 guard operators by guard count (Onionoo snapshot 2026-07-13): (AROI domain, guards, overload %)
D=[("1AEO",739,0.3),("prsv.ch",282,0.4),("nothingtohide.nl",154,53.9),("for-privacy.net",74,0.0),
   ("alpenwall.codeberg.page",49,8.2),("tuxli.org",53,3.8),("c3w.at",32,0.0),
   ("fluffypancakes.dev",19,42.1),("arbitrary.ch",14,7.1),("doedelkiste.de",15,13.3)]

def verify():
    import urllib.request, json
    det=json.load(urllib.request.urlopen("https://onionoo.torproject.org/details?type=relay&fields=fingerprint,contact,flags,overload_general_timestamp",timeout=120))["relays"]
    SUB={"1AEO":"1aeo.com","prsv.ch":"prsv.ch","nothingtohide.nl":"nothingtohide","for-privacy.net":"for-privacy.net",
         "alpenwall.codeberg.page":"alpenwall","tuxli.org":"tuxli.org","c3w.at":"c3w.at","fluffypancakes.dev":"fluffypancakes",
         "arbitrary.ch":"arbitrary.ch","doedelkiste.de":"doedelkiste"}
    print("LIVE Onionoo (all Guard-flag relays):")
    for name,_,_ in D:
        G=[r for r in det if SUB[name] in (r.get("contact") or "").lower() and "Guard" in r.get("flags",[])]
        ov=sum(1 for r in G if r.get("overload_general_timestamp"))
        print(f"  {name:26} {len(G):>4} guards  {100*ov/len(G) if G else 0:5.1f}% overloaded")

if "--verify" in sys.argv:
    verify(); sys.exit(0)

SNAPSHOT = "2026-07-13"   # Onionoo snapshot date these values were pulled on (pinned for reproducibility)
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"; GRN="#00ff7f"; RED="#ff6b6b"; AMB="#ff8c42"; CYA="#66d9ff"
def col(nm,ov): return GRN if nm=="1AEO" else (RED if ov>10 else (AMB if ov>=1 else CYA))
XT=10
S_1AEO=560; S_OTHER=190
FS_LEAD=13.0; FS_1AEO=15.0; FS_PRSV=13.5
fig,ax=plt.subplots(figsize=(11.4,6.9),dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.add_patch(Rectangle((-2,10),XT+2,795,color=GRN,alpha=0.09,zorder=0))
ax.axvline(XT,color=MUT,ls=":",lw=1,alpha=0.6)
ax.text(5,585,"OPTIMAL",color=GRN,fontsize=12.5,fontweight="bold",ha="center",va="center",alpha=0.95)
ax.text(5,530,"≤ 10% overloaded\n↑ more guards is better",color="#7fdca8",fontsize=8.6,ha="center",va="center",style="italic",linespacing=1.25)
INLINE={"1AEO":(13,0,"left"),"prsv.ch":(13,0,"left")}
FULL={"1AEO":"1AEO  ·  739 guards · 0.3%","prsv.ch":"prsv.ch  ·  282 guards · 0.4%",
      "nothingtohide.nl":"nothingtohide.nl · 154 guards · 53.9%"}
LEADER={"for-privacy.net":(14,690,"left"),"c3w.at":(14,578,"left"),"tuxli.org":(14,466,"left"),"arbitrary.ch":(14,396,"left"),
        "alpenwall.codeberg.page":(34,650,"left"),"doedelkiste.de":(34,538,"left"),"fluffypancakes.dev":(46,495,"left"),
        "nothingtohide.nl":(51,196,"right")}
for nm,g,ov in D:
    c=col(nm,ov)
    ax.scatter([ov],[g],s=(S_1AEO if nm=="1AEO" else S_OTHER),color=c,alpha=0.9,edgecolor="#0a0a0a",lw=1.4,zorder=5)
    if nm in INLINE:
        dx,dy,ha=INLINE[nm]
        ax.annotate(FULL[nm],xy=(ov,g),xytext=(dx,dy),textcoords="offset points",ha=ha,va="center",
                    color=(GRN if nm=="1AEO" else INK),fontsize=FS_1AEO if nm=="1AEO" else FS_PRSV,
                    fontweight="bold" if nm=="1AEO" else "normal",zorder=6)
    else:
        lx,ly,lha=LEADER[nm]
        txt=FULL.get(nm, f"{nm}  ·  {g}g · {ov:.1f}%")
        ax.annotate(txt,xy=(ov,g),xytext=(lx,ly),textcoords="data",ha=lha,va="center",
                    fontsize=FS_LEAD,color=INK,zorder=6,
                    arrowprops=dict(arrowstyle="-",color="#8a8a8a",lw=0.7,alpha=0.65,shrinkA=3,shrinkB=5))
ax.set_xlim(-2,64); ax.set_ylim(0,800)
ax.set_xlabel("guard relays overloaded now  (%)      ←  lower is better",fontsize=10.5,color=MUT)
ax.set_ylabel("guard relays run  (count)      ↑  more = larger share of the guard position",fontsize=10.2,color=MUT)
ax.grid(True,color=GRID,lw=0.6); ax.set_axisbelow(True)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT)
ax.set_title("Scale vs. overload — 1AEO owns the top-left corner (most guards, least overloaded)",fontsize=12.6,color=INK,loc="left",pad=42,fontweight="bold")
ax.text(0,1.015,"top-10 Tor operators by guard count (AROI) · x = share of the operator's guards overloaded now, y = number of guards it runs · Onionoo "+SNAPSHOT+"\nup-and-to-the-left is best; green = ≤10% of guards overloaded. Only 1AEO and prsv.ch pair many guards with low overload — 1AEO runs 2.6x more than prsv.",
        transform=ax.transAxes,fontsize=7.9,color=MUT,va="bottom",linespacing=1.3)
fig.tight_layout(pad=1.1)
fig.savefig(OUT,facecolor=BG,bbox_inches="tight"); print("wrote",OUT)
