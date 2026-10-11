#!/usr/bin/env python3
# Chart: "The flood overloaded 12% of the Tor network — the 1AEO fleet stayed near 0.3%"
# (blog image: circuit-building-dos-wave-june-2026-chart-network-overload.png)
#
# Two lines, Jun 10 -> Jul 13 (daily, UTC):
#   red   = rest of the Tor network — share of publishing relays signing overload-general
#   green = the 1AEO fleet         — same share, restricted to 1AEO's relays
#
# Fully reproducible from public data only:
#   1. Onionoo tells us which fingerprints are 1AEO's (contact=1aeo.com).
#   2. CollecTor's signed monthly server-descriptor archives give, per UTC day,
#      which relays published an `overload-general` line (authoritative through
#      the last complete archive day, 2026-07-12).
#   3. CollecTor's `recent/` server-descriptor directory fills the final day
#      (2026-07-13), whose descriptors have not yet rolled into the monthly archive.
#   Every relay publishes a descriptor at least every 18h, so each UTC day covers
#   effectively the whole live network.
#
# Requires: python3 + matplotlib. Runtime: ~10-30 min (streams ~1-2 GB of archives).
# Usage: python3 chart-network-overload-2line.py [output.png]
#
# Fast local verification (optional, not used by default):
#   CT_CACHE=/path/to/dir  -> read pre-downloaded monthly *.tar.xz from disk
#   CT_FRESH=/path/to/dir  -> read pre-downloaded recent single-file descriptors from disk
import sys, os, urllib.request, tarfile, json, re, datetime as dt
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS   = ["2026-06", "2026-07"]
START    = "2026-06-10"
LAST_DAY = "2026-07-13"   # monthly archive is authoritative through the day before; recent/ fills this day
OUT = sys.argv[1] if len(sys.argv) > 1 else \
    "chart-network-overload.png"

def get_json(url):
    r = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    return json.load(urllib.request.urlopen(r, timeout=180))

# Stream a CollecTor monthly archive. Set CT_CACHE=/dir to read a pre-downloaded
# *.tar.xz from disk (optional); otherwise it streams straight from collector.torproject.org.
def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

# Yield the text of each recent single-file server-descriptor document whose filename
# is dated on/after LAST_DAY. Set CT_FRESH=/dir to read pre-downloaded files from disk.
def iter_recent():
    local = os.environ.get("CT_FRESH")
    if local:
        for fn in sorted(os.listdir(local)):
            if fn[:10] >= LAST_DAY:
                yield open(os.path.join(local, fn), encoding="ascii", errors="replace").read()
        return
    base = "https://collector.torproject.org/recent/relay-descriptors/server-descriptors/"
    idx = urllib.request.urlopen(urllib.request.Request(base, headers={"User-Agent": "curl/8"}),
                                 timeout=180).read().decode("ascii", "replace")
    names = sorted(set(re.findall(r'href="(\d{4}-\d\d-\d\d-[^"]*-server-descriptors)"', idx)))
    for fn in names:
        if fn[:10] < LAST_DAY: continue
        yield urllib.request.urlopen(urllib.request.Request(base + fn, headers={"User-Agent": "curl/8"}),
                                     timeout=300).read().decode("ascii", "replace")

# ---- 1. which fingerprints are 1AEO's (public Onionoo) ----
d = get_json("https://onionoo.torproject.org/details?contact=1aeo.com&type=relay&last_seen_days=0-30&fields=fingerprint")
AEO = set(r["fingerprint"].upper() for r in d["relays"])
print("1AEO fingerprints:", len(AEO), flush=True)

# ---- 2. overload-general per UTC day, whole network + 1AEO subset ----
pub = defaultdict(set)   # day -> fps that published a descriptor
over = defaultdict(set)  # day -> fps whose descriptor carries overload-general

def finish(fp, day, ov, day_floor):
    # day_floor gates the recent/ pass so it only contributes the final day,
    # leaving days that the monthly archive already covers untouched.
    if fp and day and day >= day_floor:
        pub[day].add(fp)
        if ov: over[day].add(fp)

def scan(text, day_floor):
    fp = day = None; ov = False
    for line in text.split("\n"):
        if line.startswith("router "):
            finish(fp, day, ov, day_floor); fp = day = None; ov = False
        elif line.startswith("fingerprint "):
            fp = line[11:].replace(" ", "").strip().upper()
        elif line.startswith("published "):
            day = line.split()[1]
        elif line.startswith("overload-general"):
            ov = True
    finish(fp, day, ov, day_floor)

for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url); n = 0
    for mem in tf:
        if not mem.isfile(): continue
        try: text = tf.extractfile(mem).read().decode("ascii", "replace")
        except Exception: continue
        scan(text, "0000")          # monthly archive: keep every day it holds
        n += 1
        if n % 50000 == 0: print(f"  {month}: {n} descriptors", flush=True)
    print(f"  {month}: done, {n} descriptors", flush=True)

print("filling final day from CollecTor recent/ ...", flush=True)
for text in iter_recent():
    scan(text, LAST_DAY)            # recent pass: only descriptors published on the final day

# ---- 3. build the daily curve ----
roll = {d: {"pub": len(pub[d]), "over": len(over[d]),
            "over_aeo": len(over[d] & AEO), "pub_aeo": len(pub[d] & AEO)}
        for d in sorted(pub) if START <= d <= LAST_DAY and len(pub[d]) > 5000}
days = sorted(roll)
x = [dt.datetime.strptime(dd, "%Y-%m-%d") for dd in days]
net = [roll[dd]["over"] / roll[dd]["pub"] * 100 for dd in days]
aeo = [roll[dd]["over_aeo"] / max(roll[dd].get("pub_aeo", 1009), 1) * 100 for dd in days]
for dd in days:
    r = roll[dd]
    print(dd, f"net {100*r['over']/r['pub']:.1f}% ({r['over']}/{r['pub']})  "
              f"1AEO {100*r['over_aeo']/max(r['pub_aeo'],1):.2f}% ({r['over_aeo']}/{r['pub_aeo']})", flush=True)

# ---- 4. figure (styling ported verbatim from the blog generator) ----
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"
GRN="#00ff7f"; RED="#ff6b6b"; AMB="#ffb454"
fig,ax=plt.subplots(figsize=(10,4.9),dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)

# onset marker
onset=dt.datetime(2026,6,25)
ax.axvline(onset,color=RED,ls="--",lw=1,alpha=0.6)
ax.text(onset,12.15,"flood onset\nJun 25",color=RED,fontsize=8,ha="center",va="bottom")

# network line (the rest of the Tor network)
ax.fill_between(x,net,color=RED,alpha=0.13,zorder=2)
ax.plot(x,net,color=RED,lw=2.6,zorder=4,label="rest of the Tor network")
# 1AEO line
ax.fill_between(x,aeo,color=GRN,alpha=0.25,zorder=3)
ax.plot(x,aeo,color=GRN,lw=2.8,zorder=5,label="1AEO fleet")

# annotate the two waves on the network curve
def note(ds,txt,dy,col):
    di=days.index(ds); ax.annotate(txt,(x[di],net[di]),xytext=(0,dy),textcoords="offset points",
        ha="center",fontsize=9,color=col,fontweight="bold",
        arrowprops=dict(arrowstyle="-",color=MUT,lw=0.8))
note("2026-06-28","wave 1 peak\n8.2% of the network",22,AMB)
dpk=days.index("2026-07-12")
ax.annotate("wave 2 peak · 12.2% (1,254) · Jul 12",(x[dpk],net[dpk]),xytext=(-150,6),textcoords="offset points",
    ha="left",va="center",fontsize=9,color=RED,fontweight="bold",
    arrowprops=dict(arrowstyle="-",color=MUT,lw=0.8))

# label 1AEO's flat floor
di=days.index("2026-07-13")
ax.scatter([x[di]],[net[di]],s=22,color=RED,zorder=6,edgecolor=BG,lw=1)
ax.annotate("eased to\n11.3% · Jul 13",(x[di],net[di]),xytext=(8,-2),textcoords="offset points",
    ha="left",va="center",fontsize=8.4,color=MUT,fontweight="bold",arrowprops=dict(arrowstyle="-",color=MUT,lw=0.7))
ax.annotate("1AEO: 0.3–0.6% overloaded — flat through both waves",
    (x[days.index("2026-07-04")],aeo[days.index("2026-07-04")]),
    xytext=(0,34),textcoords="offset points",ha="center",fontsize=9.5,color=GRN,fontweight="bold",
    arrowprops=dict(arrowstyle="-",color=GRN,lw=0.9))

ax.set_ylim(0,13); ax.set_ylabel("relays reporting overload  (% of operator's relays)",fontsize=10.5,color=MUT)
ax.grid(True,color=GRID,lw=0.7); ax.set_axisbelow(True)
for s in ("top","right"): ax.spines[s].set_visible(False)
for s in ("left","bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT)
ax.margins(x=0.06)
ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=3))
fig.autofmt_xdate()
lg=ax.legend(loc="upper left",fontsize=10,frameon=True,facecolor=BG,edgecolor="#444")
for t in lg.get_texts(): t.set_color(INK)
ax.set_title("The flood overloaded 12% of the Tor network — the 1AEO fleet stayed near 0.3%",
    fontsize=12.5,color=INK,loc="left",pad=26,fontweight="bold")
ax.text(0,1.045,"share of each operator's relays signing an overload-general line, from Tor's own signed CollecTor archives · daily · UTC",
    transform=ax.transAxes,fontsize=8.7,color=MUT,va="bottom")
fig.tight_layout(pad=1.1)
fig.savefig(OUT,facecolor=BG,bbox_inches="tight"); print("wrote",OUT)
print("network peak %.1f%% on %s ; 1AEO range %.2f-%.2f%%"%(max(net),days[net.index(max(net))],min(aeo),max(aeo)))
