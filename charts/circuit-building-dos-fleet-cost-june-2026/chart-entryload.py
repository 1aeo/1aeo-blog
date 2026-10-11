#!/usr/bin/env python3
# Chart: "Why 1AEO's guards held: it carries Tor's largest guard-entry load — spread thinnest"
# (blog image: circuit-building-dos-wave-june-2026-chart-entryload.png)
#
# DATA PROVENANCE (fully public, Onionoo):
#   Pure-guard operators = operators whose relays hold the Guard flag but NOT the Exit flag.
#   Per-guard entry load = median of each operator's guards' `guard_probability`
#     from  https://onionoo.torproject.org/weights?type=relay&fields=fingerprint,guard_probability
#     scaled x1e6 (guard_probability is a fraction of all guard selections; x1e6 gives readable integers).
#   Overload %          = share of the operator's guards whose most recent server descriptor carries an
#                         `overload-general` line, from  https://onionoo.torproject.org/details
#                         (field `overload_general_timestamp`, non-null within the measurement window).
#   Total entry share % = sum of the operator's guards' guard_probability (its share of ALL Tor guard entries).
#   Operator grouping   = AROI (Authenticated Relay Operator Identifier), the operator domain proven in the
#                         relay ContactInfo — the same grouping the 1AEO AROI validator uses.
#
# SNAPSHOT: 2026-07-13 (guard counts + overload); guard_probability + entry-share are the Onionoo /weights
# medians/sums as of the same window. Onionoo serves only the CURRENT network state (it has no historical
# archive), so the values below are embedded as the immutable record of that snapshot and the chart is
# reproduced deterministically from them. Re-run the queries above to compare against the live network.
# Guards = all Guard-flag relays for the operator (the default Onionoo query, no running filter).
#
# Requires: python3 + matplotlib.  Usage: python3 chart-entryload.py [output.png]
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
OUT = sys.argv[1] if len(sys.argv) > 1 else "chart-entryload.png"

SNAPSHOT = "2026-07-13"   # Onionoo snapshot date these values were pulled on (pinned for reproducibility)
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"; GRN="#00ff7f"; RED="#ff6b6b"; CYA="#66d9ff"; AMB="#ff8c42"
# pure-guard operators among the majors (Onionoo snapshot 2026-07-13):
# (name, per-guard entry load [median guard_probability x1e-6], overload%, total entry share%, guards, color)
D=[("1AEO",92,0.3,12.2,739,GRN),
   ("prsv.ch",224,0.4,6.90,282,CYA),
   ("nothingtohide.nl",395,53.9,6.63,154,RED)]

fig,ax=plt.subplots(figsize=(10.4,5.4),dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
# overload "wall": per-guard load high enough to saturate CPU (between prsv 224 coping and nothingtohide 404 overloaded)
ax.axvline(320,color="#ff9a9a",ls=":",lw=1,alpha=0.5,zorder=0)
ax.text(360,52,"per-guard load high enough\nto saturate CPU → overload",color="#ff9a9a",fontsize=8.5,ha="center",va="top",style="italic")
LBL={"1AEO":(0,26,"center","bottom"),"prsv.ch":(0,26,"center","bottom"),"nothingtohide.nl":(-20,0,"right","center")}
for nm,x,ov,share,g,c in D:
    ax.scatter([x],[ov],s=share*95,color=c,alpha=0.85,edgecolor="#0a0a0a",lw=1.5,zorder=4)
    dx,dy,ha,va=LBL[nm]
    ax.annotate(f"{nm} — {ov:.1f}% overload\n{g} guards · {share:.1f}% of Tor's guard entries",
                xy=(x,ov),xytext=(dx,dy),textcoords="offset points",ha=ha,va=va,linespacing=1.3,
                color=(GRN if nm=="1AEO" else INK),fontsize=9,fontweight="bold" if nm=="1AEO" else "normal")
ax.set_xlim(55,475); ax.set_ylim(-4,66)
ax.set_xlabel("per-guard entry load  (median guard_probability, ×10⁻⁶)  — lower = load spread thinner",fontsize=10,color=MUT)
ax.set_ylabel("guard relays overloaded  (%)",fontsize=10.5,color=MUT)
ax.grid(True,color=GRID,lw=0.7); ax.set_axisbelow(True)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT)
ax.text(0.99,0.02,"bubble = share of ALL Tor guard entries the operator carries",transform=ax.transAxes,ha="right",va="bottom",color=MUT,fontsize=7.8,style="italic")
ax.set_title("Why 1AEO's guards held: it carries Tor's largest guard-entry load — spread thinnest",fontsize=12.6,color=INK,loc="left",pad=44,fontweight="bold")
ax.text(0,1.015,"pure-guard operators · per-guard entry load (Onionoo guard_probability) vs overload · 1AEO carries 12.2% of all Tor guard selections\n(the most of any operator) across 739 guards → 92 per guard (lowest) → under the overload wall; nothingtohide packs 6.6% into 154 → 395 → over it · Onionoo "+SNAPSHOT,
        transform=ax.transAxes,fontsize=7.9,color=MUT,va="bottom",linespacing=1.3)
fig.tight_layout(pad=1.1)
fig.savefig(OUT,facecolor=BG,bbox_inches="tight"); print("wrote",OUT)
