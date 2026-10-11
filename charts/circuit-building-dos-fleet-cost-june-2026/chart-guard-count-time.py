#!/usr/bin/env python3
# Chart: "Overloaded guard relays over time, top-10 guard operators — 1AEO holds near zero throughout"
# (blog image: circuit-building-dos-wave-june-2026-chart-guard-count-time.png)
#
# For each of the ten Tor operators that run the most GUARD relays, this plots the daily
# NUMBER of that operator's guard-position relays flagged overloaded during the June-2026
# circuit-building flood. 1AEO (bold green) holds near zero the whole time; nothingtohide.nl
# spikes to ~53 around Jun 28; the rest oscillate between 0 and ~20.
#
# Fully reproducible from public data — NO first-party / Prometheus / localhost inputs:
#   1. Onionoo /details (contact=<operator>) gives each operator's relay fingerprint set;
#   2. CollecTor's signed consensus archives (the daily 12:00 consensus) classify every
#      relay's role per day, so we know which of an operator's relays sit in the guard
#      position (Guard flag, i.e. role guard-only or guard+exit) on each day;
#   3. CollecTor's signed server-descriptor archives tell us, per day, which relays
#      published an `overload-general` line;
#   join by fingerprint+day and count, per operator per day, the guard-position relays overloaded.
#
# Requires: python3 + matplotlib. Runtime: ~15-40 min (streams ~1-2 GB of archives).
# Usage: python3 chart-guard-count-time.py [output.png]
import sys, os, urllib.request, tarfile, base64, gzip, json, datetime as dt
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
START, END = "2026-06-01", "2026-07-11"   # published window: first flood month through the last complete archive day
OUT = sys.argv[1] if len(sys.argv) > 1 else \
    "chart-guard-count-time.png"

# The ten Tor operators running the most guard relays (AROI, metrics.1aeo.com), each identified
# publicly by a substring of its Onionoo `contact` line. Display name -> contact substring.
OPS = [("1AEO", "1aeo.com"), ("prsv.ch", "prsv.ch"), ("nothingtohide.nl", "nothingtohide.nl"),
       ("for-privacy.net", "for-privacy.net"), ("alpenwall", "alpenwall"), ("tuxli.org", "tuxli.org"),
       ("c3w.at", "c3w.at"), ("fluffypancakes", "fluffypancakes"), ("arbitrary.ch", "arbitrary.ch"),
       ("doedelkiste.de", "doedelkiste.de")]
order = [nm for nm, _ in OPS]

# ---- Onionoo: each operator's relay fingerprint set (public, no auth) ----
def onionoo(contact):
    url = "https://onionoo.torproject.org/details?contact=" + urllib.request.quote(contact) + \
          "&type=relay&fields=fingerprint"
    req = urllib.request.Request(url, headers={"Accept-Encoding": "gzip", "User-Agent": "curl/8"})
    raw = urllib.request.urlopen(req, timeout=180).read()
    try: raw = gzip.decompress(raw)
    except Exception: pass
    return json.loads(raw)["relays"]

opsets = {}
for nm, contact in OPS:
    rs = onionoo(contact)
    opsets[nm] = set(r["fingerprint"].upper() for r in rs)
    print(f"Onionoo {nm:18s} contact={contact:18s} relays={len(opsets[nm])}", flush=True)

# Stream a CollecTor archive. Set CT_CACHE=/path to read pre-downloaded *.tar.xz from disk
# (optional; without it the archive is streamed straight from collector.torproject.org).
def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

# ---- 1. roles from the daily noon consensus ----
def classify(flags):
    g = "Guard" in flags; e = "Exit" in flags
    return "both" if (g and e) else "guard" if g else "exit" if e else "middle"

role_of = defaultdict(dict)
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    for mem in tf:
        if not mem.name.endswith("-12-00-00-consensus"): continue
        day = mem.name.split("/")[-1][:10]
        if not (START <= day <= END): continue
        fp = None
        for line in tf.extractfile(mem).read().decode("ascii", "replace").split("\n"):
            if line.startswith("r "):
                f = line.split(); fp = None
                if len(f) >= 3:
                    try: fp = base64.b64decode(f[2] + "=").hex().upper()
                    except Exception: fp = None
            elif line.startswith("s ") and fp is not None:
                role_of[day][fp] = classify(set(line[2:].split())); fp = None
        print(f"  {day}: {len(role_of[day])} relays classified", flush=True)

# ---- 2. overload-general per day from server descriptors ----
over = defaultdict(set)
def finish(fp, day, ov):
    if fp and day and ov: over[day].add(fp)
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    n = 0
    for mem in tf:
        if not mem.isfile(): continue
        try: text = tf.extractfile(mem).read().decode("ascii", "replace")
        except Exception: continue
        fp = day = None; ov = False
        for line in text.split("\n"):
            if line.startswith("router "):
                finish(fp, day, ov); fp = day = None; ov = False
            elif line.startswith("fingerprint "): fp = line[11:].replace(" ", "").strip().upper()
            elif line.startswith("published "): day = line.split()[1]
            elif line.startswith("overload-general"): ov = True
        finish(fp, day, ov)
        n += 1
        if n % 50000 == 0: print(f"  {month}: {n} descriptors", flush=True)

# ---- 3. join: per operator per day, count guard-position relays overloaded ----
days = sorted(d for d in role_of if START <= d <= END)
X = [dt.datetime.strptime(d, "%Y-%m-%d") for d in days]
cnt = {op: [] for op in order}
for d in days:
    ro = role_of[d]; ofps = over.get(d, set())
    for op in order:
        guards = [fp for fp in opsets[op] if ro.get(fp) in ("guard", "both")]
        cnt[op].append(sum(1 for fp in guards if fp in ofps))

# ---- printed numbers ----
aeo = cnt["1AEO"]; nth = cnt["nothingtohide.nl"]
print("days", days[0], "->", days[-1], "n=", len(days))
print("final counts:", {op: cnt[op][-1] for op in order})
print(f"1AEO flat range (raw): {min(aeo)}-{max(aeo)} of {len(opsets['1AEO'])} relays")
print(f"nothingtohide.nl peak (raw): {max(nth)} on {days[nth.index(max(nth))]}")

# ---- figure (styling ported verbatim from the blog's chart) ----
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"; GRN="#00ff7f"; RED="#ff6b6b"
FIELD=["#ff8c42","#ffb454","#b48cff","#66d9ff","#ff6b6b","#c98cff","#8ab4ff","#ffa0c0","#9ad19a"]
def smooth(y):
    return [sum(y[max(0,i-1):i+2])/len(y[max(0,i-1):i+2]) for i in range(len(y))]
fig,ax=plt.subplots(figsize=(11,5.2),dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
onset=dt.datetime(2026,6,25); ax.axvspan(onset,X[-1],color=RED,alpha=0.06,zorder=0)
ax.axvline(onset,color=MUT,ls="--",lw=1,alpha=0.7)
ax.text(onset,1,"  flood onset Jun 25",color=MUT,fontsize=8.5,ha="left",va="bottom",rotation=90)
others=[op for op in order if op!="1AEO"]
for i,op in enumerate(others):
    ax.plot(X,smooth(cnt[op]),color=FIELD[i%len(FIELD)],lw=1.4,alpha=0.8,zorder=3,label=op)
ax.plot(X,smooth(cnt["1AEO"]),color=GRN,lw=3.4,zorder=6,label="1AEO",solid_capstyle="round")
ax.set_ylim(bottom=0); ax.set_ylabel("guard relays overloaded  (count)",fontsize=10.5,color=MUT)
ax.grid(True,color=GRID,lw=0.7); ax.set_axisbelow(True)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT); ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=4)); fig.autofmt_xdate()
lg=ax.legend(loc="upper left",fontsize=8.3,frameon=True,facecolor=BG,edgecolor="#444",ncol=2)
for t in lg.get_texts(): t.set_color(INK)
lg.get_texts()[-1].set_color(GRN); lg.get_texts()[-1].set_fontweight("bold")
ax.annotate("1AEO: near 0 throughout\n(0–3 of 739 guards)",xy=(X[-1],smooth(cnt["1AEO"])[-1]),xytext=(-12,34),textcoords="offset points",color=GRN,fontsize=9,ha="right",va="bottom",fontweight="bold",arrowprops=dict(arrowstyle="->",color=GRN,lw=1.2))
ax.set_title("Overloaded guard relays over time, top-10 guard operators — 1AEO holds near zero throughout",fontsize=11.8,color=INK,loc="left",pad=40,fontweight="bold")
ax.text(0,1.015,"number of each operator's guard-position relays flagged overloaded, daily · CollecTor consensus flags × overload-general · UTC\nexit-only operators excluded (0 guards, not in the flood's path)",transform=ax.transAxes,fontsize=7.9,color=MUT,va="bottom",linespacing=1.3)
fig.text(0.995,0.012,"Produced by 1AEO",color="#a5a5a5",fontsize=8,ha="right",va="bottom")
fig.tight_layout(pad=1.1)
fig.savefig(OUT,facecolor=BG,bbox_inches="tight"); print("wrote",OUT)
