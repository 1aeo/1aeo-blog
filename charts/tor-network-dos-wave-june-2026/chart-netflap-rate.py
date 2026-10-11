#!/usr/bin/env python3
# Chart: "The flood shook the Running flag network-wide — a 6h flicker rate, not an outage"
# (blog image: circuit-building-dos-wave-june-2026-chart-netflap-rate.png)
#
# Fully reproducible from public data: streams CollecTor's signed consensus archives,
# takes the four daily 6h consensuses (00/06/12/18 UTC), and — strictly in valid-after
# order — counts, per snapshot, how many relays that carried the Running flag in the
# PREVIOUS consensus have dropped it. Plots that flicker rate two ways on one line:
#   left axis  = share of the network (% of the Running set) that flapped that 6h;
#   right axis = the same rate as a multiple of its pre-flood (Jun 15-22) baseline.
#
# NOTE: CollecTor tar members are NOT in time order — every consensus is collected
# first, then processed strictly in valid-after order (critical for the diff).
#
# Requires: python3 + matplotlib. Runtime: ~3-10 min (streams ~35 MB of archives).
# Usage: python3 chart-netflap-rate.py [output.png]
import sys, os, urllib.request, tarfile, base64, json, datetime as dt, statistics as st
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
GRID = ("-00-00-00", "-06-00-00", "-12-00-00", "-18-00-00")
OUT = sys.argv[1] if len(sys.argv) > 1 else "chart-netflap-rate.png"

def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

def parse(text):
    va = None; fp = None; run = set()
    for line in text.split("\n"):
        if line.startswith("valid-after "):
            try: va = dt.datetime.strptime(line[12:].strip(), "%Y-%m-%d %H:%M:%S")
            except Exception: va = None
        elif line.startswith("r "):
            f = line.split(); fp = None
            if len(f) >= 3:
                try: fp = base64.b64decode(f[2] + "=").hex().upper()
                except Exception: fp = None
        elif line.startswith("s ") and fp is not None:
            if "Running" in line.split()[1:]: run.add(sys.intern(fp))
            fp = None
    return va, frozenset(run)

snaps = {}
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    for mem in tf:
        name = mem.name.split("/")[-1]
        if not any(name.endswith(g + "-consensus") for g in GRID): continue
        va, run = parse(tf.extractfile(mem).read().decode("ascii", "replace"))
        if va is not None and run: snaps[va] = run
print(f"collected {len(snaps)} six-hourly consensuses", flush=True)

times = sorted(snaps)
net_drop = []; net_size = []
prev = None
for t in times:
    R = snaps[t]
    net_drop.append(0 if prev is None else len(prev - R))
    net_size.append(len(R)); prev = R

ONSET = dt.datetime(2026, 6, 25, 23)
BA, BB = dt.datetime(2026, 6, 15), dt.datetime(2026, 6, 22)
base = st.mean(d for d, t in zip(net_drop, times) if BA <= t < BB)
pct = [100 * d / n for d, n in zip(net_drop, net_size)]
xb = [d / base for d in net_drop]
print(f"baseline (Jun 15-22): {base:.0f} drops/6h | peak {max(pct):.1f}% of network = x{max(xb):.1f}")
json.dump({"times": [t.isoformat() for t in times], "net_drop": net_drop, "net_size": net_size,
           "pct": [round(p, 3) for p in pct], "xbaseline": [round(x, 3) for x in xb], "base": round(base, 1)},
          open(OUT + ".data.json", "w"))

INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID_C="#333"; RED="#ff6b6b"; AMB="#ffb454"
X = times
fig, ax = plt.subplots(figsize=(10, 4.7), dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.axvline(ONSET, color=MUT, ls="--", lw=1, alpha=0.7)
ax.text(ONSET, max(pct) * 1.02, "  flood onset Jun 25", color=MUT, fontsize=8.5, ha="left", va="top")
ax.fill_between(X, pct, color=RED, alpha=0.15, zorder=2); ax.plot(X, pct, color=RED, lw=2.4, zorder=3)
ax.set_ylabel("network relays flapping the\nRunning flag  (% of network / 6h)", fontsize=10, color=RED); ax.set_ylim(0, max(pct) * 1.18)
ax.tick_params(axis='y', colors=RED); ax.tick_params(axis='x', colors=MUT)
ax.grid(True, axis="y", color=GRID_C, lw=0.6); ax.set_axisbelow(True)
for _sp in ("top","right"): ax.spines[_sp].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#555")
ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=4)); fig.autofmt_xdate()
ax.set_title("The flood shook the Running flag network-wide — a 6h flicker rate, not an outage",
             fontsize=12.2, color=INK, loc="left", pad=26, fontweight="bold")
ax.text(0, 1.03, f"share of all Tor relays that dropped the Running flag in each 6-hour window · from the signed CollecTor consensuses · peaks {max(pct):.1f}% of the network · UTC",
        transform=ax.transAxes, fontsize=8.2, color=MUT, va="bottom")
fig.text(0.995, 0.012, "Produced by 1AEO", color="#a5a5a5", fontsize=8, ha="right", va="bottom")
fig.tight_layout(pad=1.1)
fig.savefig(OUT, facecolor=BG, bbox_inches="tight"); print("wrote", OUT)
