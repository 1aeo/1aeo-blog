#!/usr/bin/env python3
# Chart: "Two overload waves across the Tor network, June-July 2026"
# (blog image: circuit-building-dos-wave-june-2026-chart-network-overload-only.png)
#
# Fully reproducible from public data: streams Tor's signed server-descriptor
# archives from CollecTor and counts, per UTC day, the share of publishing
# relays whose descriptor carries an `overload-general` line.
# Every relay publishes a descriptor at least every 18h, so each UTC day
# covers effectively the whole live network.
#
# The signed *monthly* server-descriptor archive lags real time by a day or two,
# so it only fully covers days through ~Jul 12. To fill the final chart day
# (Jul 13) we ALSO parse CollecTor's *recent/* per-file server-descriptor
# documents (each covers a slice of the last few days) and union them into the
# final day only -- every earlier day comes wholly from the signed monthly
# archive, so Jul 11 stays 11.4% and Jul 12 stays 12.3% (settled monthly archive).
#
# The DENOMINATOR ("% of what?") is a config knob -- see below: "publishers"
# (default) or "consensus".
#
# Requires: python3 + matplotlib. Runtime: ~10-30 min (streams ~1-2 GB of archives).
# Usage: python3 chart-network-overload.py [output.png]
import sys, os, re, urllib.request, tarfile, json, datetime as dt
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
LAST_DAY = "2026-07-13"      # final chart day, filled from CollecTor recent/ per-file docs
OUT = sys.argv[1] if len(sys.argv) > 1 else "chart-network-overload-only.png"

# ---------------------------------------------------------------------------
# DENOMINATOR -- what the "% of the network" is measured against. Change freely.
#   "publishers" (default): relays that published a server descriptor that UTC
#       day. Every relay republishes at least every ~18h, so a day covers
#       effectively the whole live network. Uses only the descriptor archives
#       parsed below. This is what the published blog chart uses (wave-2 peak
#       12.3%, Jul 12).
#   "consensus": relays listed in that day's consensus (the 12:00 UTC one when
#       present). A slightly smaller, "official" denominator, so percentages come
#       out ~0.3-0.4 pp higher (wave-2 peak ~12.7%). This ALSO streams the
#       CollecTor consensus archives (a bit more to download).
# For any other denominator, edit denom_for_day() further down.
DENOMINATOR = "publishers"
# ---------------------------------------------------------------------------

# Stream a CollecTor monthly archive. Set CT_CACHE=/path to read a pre-downloaded
# *.tar.xz from disk (optional speedup; without it the archive is streamed straight
# from collector.torproject.org).
def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

# Yield the decoded text of each CollecTor recent/ per-file server-descriptors
# document. Public source: collector.torproject.org/recent/. Set CT_FRESH=/path
# to read a local directory of those files instead (fast offline verification).
def fresh_texts():
    local = os.environ.get("CT_FRESH")
    if local:
        for name in sorted(os.listdir(local)):
            p = os.path.join(local, name)
            if os.path.isfile(p):
                with open(p, encoding="ascii", errors="replace") as fh:
                    yield fh.read()
        return
    base = "https://collector.torproject.org/recent/relay-descriptors/server-descriptors/"
    idx = urllib.request.urlopen(base, timeout=300).read().decode("utf-8", "replace")
    for name in sorted(set(re.findall(r'href="([0-9-]+-server-descriptors)"', idx))):
        try:
            yield urllib.request.urlopen(base + name, timeout=300).read().decode("ascii", "replace")
        except Exception:
            continue

# Relays in each day's consensus (used only when DENOMINATOR == "consensus").
# Public source: CollecTor consensus archives + recent/ for the final day or two.
# CT_CACHE reuses pre-downloaded consensuses-YYYY-MM.tar.xz; CT_FRESH_CONSENSUS
# points at a local dir of recent/ consensus files.
def consensus_counts():
    counts = {}
    def consider(name, data):
        base = name.rsplit("/", 1)[-1]
        if not base.endswith("-consensus"): return
        day = base[:10]
        noon = base[11:19] == "12-00-00"       # prefer the 12:00 UTC consensus per day
        if day in counts and not noon: return
        counts[day] = data.count(b"\nr ")       # each relay entry starts a line "r "
    for month in MONTHS:
        url = f"https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-{month}.tar.xz"
        print(f"streaming {url} (consensus denominator) ...", flush=True)
        try:
            tf = open_archive(url)
        except Exception as e:
            print("  (consensus archive unavailable:", e, ")", flush=True); continue
        for mem in tf:
            if mem.isfile() and mem.name.endswith("-consensus"):
                consider(mem.name, tf.extractfile(mem).read())
    # fill the final day(s) from CollecTor recent/ per-file consensuses
    localdir = os.environ.get("CT_FRESH_CONSENSUS")
    try:
        if localdir:
            for n in sorted(os.listdir(localdir)):
                p = os.path.join(localdir, n)
                if os.path.isfile(p): consider(n, open(p, "rb").read())
        else:
            rbase = "https://collector.torproject.org/recent/relay-descriptors/consensuses/"
            idx = urllib.request.urlopen(rbase, timeout=300).read().decode("utf-8", "replace")
            for n in sorted(set(re.findall(r'href="([0-9-]+-consensus)"', idx))):
                try: consider(n, urllib.request.urlopen(rbase + n, timeout=300).read())
                except Exception: continue
    except Exception as e:
        print("  (recent/ consensuses unavailable:", e, ")", flush=True)
    return counts

pub = defaultdict(set)   # day -> fps that published
over = defaultdict(set)  # day -> fps whose descriptor carries overload-general

def parse_descriptors(text, pubmap, overmap):
    fp = day = None; ov = False
    for line in text.split("\n"):
        if line.startswith("router "):
            if fp and day:
                pubmap[day].add(fp)
                if ov: overmap[day].add(fp)
            fp = day = None; ov = False
        elif line.startswith("fingerprint "):
            fp = line[11:].replace(" ", "").strip().upper()
        elif line.startswith("published "):
            day = line.split()[1]
        elif line.startswith("overload-general"):
            ov = True
    if fp and day:
        pubmap[day].add(fp)
        if ov: overmap[day].add(fp)

# ---- 1. signed monthly archives (whole series) ----
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/server-descriptors/server-descriptors-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    n = 0
    for mem in tf:
        if not mem.isfile(): continue
        try:
            text = tf.extractfile(mem).read().decode("ascii", "replace")
        except Exception:
            continue
        parse_descriptors(text, pub, over)
        n += 1
        if n % 50000 == 0: print(f"  {month}: {n} descriptors", flush=True)
    print(f"  {month}: done, {n} descriptors", flush=True)

# ---- 2. supplement ONLY the final day from CollecTor recent/ per-file docs ----
print("parsing CollecTor recent/ per-file server-descriptors for the final day ...", flush=True)
pub_f = defaultdict(set); over_f = defaultdict(set)
nf = 0
for text in fresh_texts():
    parse_descriptors(text, pub_f, over_f)
    nf += 1
print(f"  recent/: {nf} files; {LAST_DAY} adds pub {len(pub[LAST_DAY])}->{len(pub[LAST_DAY] | pub_f[LAST_DAY])}, "
      f"over {len(over[LAST_DAY])}->{len(over[LAST_DAY] | over_f[LAST_DAY])}", flush=True)
pub[LAST_DAY] |= pub_f[LAST_DAY]
over[LAST_DAY] |= over_f[LAST_DAY]

# ---- 3. denominator (config-selectable; edit denom_for_day for a custom one) ----
cons = consensus_counts() if DENOMINATOR == "consensus" else {}

def denom_for_day(d):
    if DENOMINATOR == "consensus":
        c = cons.get(d)
        if c: return c
        print(f"  [denominator] no consensus for {d}; falling back to publishers ({len(pub[d])})", flush=True)
    return len(pub[d])   # "publishers": relays that published a descriptor that day

days = sorted(d for d in pub if "2026-06-15" <= d <= LAST_DAY and len(pub[d]) > 5000)  # wave 1 peaked Jun 28 (8.2%), wave 2 peaked Jul 12 (12.3%), eased to ~11.7% on Jul 13
X = [dt.datetime.strptime(d, "%Y-%m-%d") for d in days]
denom = {d: denom_for_day(d) for d in days}
net = [100 * len(over[d]) / denom[d] for d in days]
for d, v in zip(days, net):
    print(f"{d}  overloaded={len(over[d]):5d}  denom[{DENOMINATOR}]={denom[d]:5d}  {v:.1f}%")
json.dump({"denominator": DENOMINATOR,
           "days": {d: {"over": len(over[d]), "denom": denom[d]} for d in days}},
          open(OUT + ".data.json", "w"))

# ---- figure ----
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"; RED="#ff6b6b"; AMB="#ffb454"
fig, ax = plt.subplots(figsize=(10, 4.7), dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.fill_between(X, net, color=RED, alpha=0.16, zorder=2); ax.plot(X, net, color=RED, lw=2.6, zorder=3)
onset = dt.datetime(2026, 6, 25); ax.axvline(onset, color=MUT, ls="--", lw=1, alpha=0.7)
ax.text(onset, 12.2, "onset ~Jun 25", color=MUT, fontsize=8.5, ha="center", va="bottom")

# data-driven wave annotations
i1 = max((i for i, d in enumerate(days) if "2026-06-26" <= d <= "2026-07-02"), key=lambda i: net[i])
i2 = max((i for i, d in enumerate(days) if d >= "2026-07-08"), key=lambda i: net[i])
ax.annotate(f"wave 1\n{net[i1]:.1f}% ({len(over[days[i1]]):,} relays)", (X[i1], net[i1]), xytext=(0, 20),
            textcoords="offset points", ha="center", fontsize=9.5, color=AMB, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
ax.annotate(f"wave 2 peak\n{net[i2]:.1f}% ({len(over[days[i2]]):,}) · {X[i2]:%b %d}", (X[i2], net[i2]), xytext=(-150, 8),
            textcoords="offset points", ha="left", va="center", fontsize=9.5, color=RED, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
# mark the final day easing off the peak
ax.scatter([X[-1]], [net[-1]], s=22, color=RED, zorder=6, edgecolor=BG, lw=1)
ax.annotate(f"eased to {net[-1]:.1f}%\n{X[-1]:%b %d}", (X[-1], net[-1]), xytext=(10, 26),
            textcoords="offset points", ha="left", va="center", fontsize=9.0, color=INK, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=MUT, lw=0.8))
# data-driven baseline label (pre-onset days) -- correct for either denominator
base_i = [i for i, d in enumerate(days) if d <= "2026-06-25"]
if base_i:
    blo, bhi = min(net[i] for i in base_i), max(net[i] for i in base_i)
    ax.text(X[3], 2.0, f"baseline {blo:.1f}-{bhi:.1f}%", color=MUT, fontsize=8.5)
ax.set_ylim(0, 13); ax.set_ylabel("Tor relays reporting overload  (% of network)", fontsize=10.5, color=MUT)
ax.grid(True, color=GRID, lw=0.7); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#555")
ax.tick_params(colors=MUT); ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=3)); fig.autofmt_xdate()
ax.set_title("Two overload waves across the Tor network, June–July 2026", fontsize=13, color=INK, loc="left", pad=26, fontweight="bold")
ax.text(0, 1.045, "share of all Tor relays signing an overload-general line, from Tor's signed CollecTor archives · daily · UTC",
        transform=ax.transAxes, fontsize=8.6, color=MUT, va="bottom")
fig.text(0.995, 0.012, "Produced by 1AEO", color="#a5a5a5", fontsize=8, ha="right", va="bottom")
fig.tight_layout(pad=1.1); fig.savefig(OUT, facecolor=BG, bbox_inches="tight")
print("wrote", OUT)
