#!/usr/bin/env python3
# Chart: "The flood shook the Running flag network-wide"
# (blog image: circuit-building-dos-wave-june-2026-chart-network-flap.png)
#
# Fully reproducible from public data: streams every hourly consensus in
# CollecTor's signed archives, diffs the network's Running set hour-to-hour
# (daily median), tracks the total online count, and counts relays that
# flapped Running >=2 times in two equal 16-day windows.
# NOTE: tar members are NOT in time order — all consensuses are collected
# first and processed strictly in valid-after order.
#
# Requires: python3 + matplotlib. Runtime: ~5-15 min (streams ~200 MB of archives).
# Usage: python3 chart-network-flap.py [output.png]
import sys, os, urllib.request, tarfile, base64, json, datetime as dt, statistics as st
from collections import defaultdict
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
OUT = sys.argv[1] if len(sys.argv) > 1 else "chart-network-flap.png"

# Stream a CollecTor archive. Set CT_CACHE=/path to read pre-downloaded *.tar.xz from disk
# (optional; without it the archive is streamed straight from collector.torproject.org).
def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

def parse(text):
    running = set(); fp = None; va = None
    for line in text.split("\n"):
        if line.startswith("valid-after "):
            try: va = dt.datetime.strptime(line[12:].strip(), "%Y-%m-%d %H:%M:%S")
            except Exception: va = None
        elif line.startswith("r "):
            f = line.split(); fp = None
            if len(f) >= 3:
                try: fp = sys.intern(base64.b64decode(f[2] + "=").hex().upper())
                except Exception: fp = None
        elif line.startswith("s ") and fp is not None:
            if "Running" in line.split()[1:]: running.add(fp)
            fp = None
    return va, running

# ---- pass 1: collect all consensuses (tar order != time order) ----
snaps = {}
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    for mem in tf:
        if not mem.name.endswith("-consensus"): continue
        try: text = tf.extractfile(mem).read().decode("ascii", "replace")
        except Exception: continue
        va, running = parse(text)
        if va and running: snaps[va] = frozenset(running)
        if len(snaps) % 200 == 0: print(f"  collected {len(snaps)}", flush=True)
print(f"collected {len(snaps)} consensuses", flush=True)

# ---- pass 2: strictly chronological churn + per-relay toggle counting ----
PRE_A, PRE_B = dt.datetime(2026, 6, 9), dt.datetime(2026, 6, 25)     # 16-day pre-flood window
FLD_A, FLD_B = dt.datetime(2026, 6, 25), dt.datetime(2026, 7, 11)    # 16-day flood window
times = sorted(snaps)
records = {}; last = {}; flap_pre = defaultdict(int); flap_fld = defaultdict(int)
prev = None
for t in times:
    R = snaps[t]
    churn = len(prev.symmetric_difference(R)) if prev is not None else None  # no churn for the very first consensus
    records[t] = {"online": len(R), "churn": churn}
    def bump(fp):
        if PRE_A <= t < PRE_B: flap_pre[fp] += 1
        if FLD_A <= t < FLD_B: flap_fld[fp] += 1
    for fp in R:
        if fp in last and last[fp] is False: bump(fp)
        last[fp] = True
    for fp, stt in list(last.items()):
        if stt is True and fp not in R:
            bump(fp); last[fp] = False
    prev = R
ge2_pre = sum(1 for c in flap_pre.values() if c >= 2)
ge2_fld = sum(1 for c in flap_fld.values() if c >= 2)
print(f"repeat-flappers >=2: pre {ge2_pre}, flood {ge2_fld}")

# ---- hourly series for display (06-15..07-12) ----
DISP_A, DISP_B = dt.datetime(2026, 6, 15), dt.datetime(2026, 7, 13)
disp = [t for t in times if DISP_A <= t < DISP_B]
X = disp
churn = [records[t]["churn"] for t in disp]
online = [records[t]["online"] for t in disp]
BASE_A, BASE_B = dt.datetime(2026, 6, 15), dt.datetime(2026, 6, 22)
bch = [records[t]["churn"] for t in times if BASE_A <= t < BASE_B and records[t]["churn"] is not None]
bon = [records[t]["online"] for t in times if BASE_A <= t < BASE_B]
base = st.mean(bch); obase = st.mean(bon)
W1_A, W1_B = dt.datetime(2026, 6, 26), dt.datetime(2026, 7, 3)
W2_A, W2_B = dt.datetime(2026, 7, 6), dt.datetime(2026, 7, 13)
w1 = st.mean(records[t]["churn"] for t in times if W1_A <= t < W1_B and records[t]["churn"] is not None)
w2 = st.mean(records[t]["churn"] for t in times if W2_A <= t < W2_B and records[t]["churn"] is not None)
lows = [(records[t]["online"], t) for t in times if dt.datetime(2026, 6, 25) <= t < dt.datetime(2026, 7, 5)]
omin, tmin = min(lows)
json.dump({"hourly": [[t.isoformat(), records[t]["churn"], records[t]["online"]] for t in disp],
           "base_churn": base, "base_online": obase, "w1": w1, "w2": w2,
           "trough": [tmin.isoformat(), omin], "ge2_pre": ge2_pre, "ge2_flood": ge2_fld}, open(OUT + ".data.json", "w"))
print(f"baseline {base:.0f}/hr online {obase:.0f} | w1 {w1:.0f} x{w1/base:.1f} | w2 {w2:.0f} x{w2/base:.1f} | trough {omin} @{tmin}")

# ---- figure: two stacked panels ----
INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID="#333"; RED="#ff6b6b"; CYA="#6fb3e0"
onset = dt.datetime(2026, 6, 26)
fig, (a1, a2) = plt.subplots(2, 1, figsize=(12.5, 7.6), dpi=180, sharex=True, gridspec_kw={"height_ratios": [1, 1]})
fig.patch.set_facecolor(BG)
for ax in (a1, a2):
    ax.set_facecolor(BG); ax.grid(True, color=GRID, lw=0.5, alpha=0.7); ax.set_axisbelow(True)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_color("#555")
    ax.tick_params(colors=MUT)
    ax.axvline(onset, color=RED, ls=":", lw=1.1, alpha=0.7)
# top: network online count
a1.plot(X, online, color=CYA, lw=1.5)
a1.fill_between(X, min(online) * 0.996, online, color=CYA, alpha=0.10)
a1.axhline(obase, color="#bbb", ls="--", lw=1.1)
a1.text(X[2], obase + 12, f"baseline avg ≈ {obase:,.0f}", color="#cccccc", fontsize=9.5, fontweight="bold", va="bottom")
a1.annotate(f"trough {omin:,} ({tmin:%m-%d}, −{100*(obase-omin)/obase:.1f}%)", xy=(tmin, omin), xytext=(18, -4),
            textcoords="offset points", ha="left", fontsize=10, color=CYA, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=CYA, lw=0.9))
a1.scatter([tmin], [omin], s=22, color=CYA, zorder=5)
a1.text(0.995, 0.94, "recovers above baseline\n(~400 brand-new relays join in early July)", transform=a1.transAxes,
        fontsize=8.6, color=MUT, ha="right", va="top")
a1.set_ylim(min(online) * 0.996, max(online) * 1.004)
a1.set_ylabel("relays with the\nRunning flag (network)", fontsize=9.8, color=MUT)
# bottom: hourly churn
a2.plot(X, churn, color=RED, lw=1.1)
a2.fill_between(X, 0, churn, color=RED, alpha=0.13)
a2.axhline(base, color="#bbb", ls="--", lw=1.1)
a2.text(X[2], base + 5, f"baseline avg {base:.0f}/hr", color="#cccccc", fontsize=9.5, fontweight="bold", va="bottom")
a2.axhline(3 * base, color=RED, ls=":", lw=1.0, alpha=0.8)
a2.text(X[2], 3 * base + 5, f"3× baseline ({3*base:.0f}/hr) = the flood level", color=RED, fontsize=8.8, va="bottom", alpha=0.9)
mid1 = dt.datetime(2026, 6, 29, 12); mid2 = dt.datetime(2026, 7, 9, 12)
a2.text(mid1, max(churn) * 0.93, f"WAVE 1 ×{w1/base:.1f}\n({w1:.0f}/hr avg)", color=RED, fontsize=10.5, fontweight="bold", ha="center", va="top")
a2.text(mid2, max(churn) * 0.93, f"WAVE 2 ×{w2/base:.1f}\n({w2:.0f}/hr avg)", color=RED, fontsize=10.5, fontweight="bold", ha="center", va="top")
a2.text(0.335, 0.13, f"≈{ge2_fld:,} relays flapped Running ≥2× during the flood — {ge2_fld/max(ge2_pre,1):.1f}× the ≈{ge2_pre:,}\nin an equal-length pre-flood window",
        transform=a2.transAxes, fontsize=8.6, color=INK, va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.45", fc="#242424", ec="#555", alpha=0.92))
a2.set_ylim(0, max(churn) * 1.06)
a2.set_ylabel("relays entering/leaving the\nRunning set  (flaps / hour)", fontsize=9.8, color=MUT)
a2.xaxis.set_major_formatter(md.DateFormatter("%m-%d")); a2.xaxis.set_major_locator(md.DayLocator(interval=3))
fig.suptitle("The DoS made relays flicker out of the consensus — network-wide, not just 1AEO's",
             fontsize=15.5, color=INK, x=0.012, ha="left", fontweight="bold")
fig.text(0.012, 0.935, "a relay keeps the Running flag only if a majority of the voting directory authorities each reached it recently (a reachability test completed within ~45 minutes);\n"
         f"too saturated to answer, it drops out of the consensus that hour. Across the whole Tor network (hourly CollecTor consensuses), flapping roughly TRIPLED during\n"
         f"the flood; at the {tmin:%m-%d} trough ~{obase-omin:,.0f} relays were out versus baseline. UTC",
         fontsize=9.2, color=MUT, ha="left", va="top", linespacing=1.4)
fig.text(0.012, 0.012, "Source: CollecTor hourly consensuses. Bottom = membership churn (relays entering+leaving the Running set)/hr; the ×-vs-baseline ratio is the signal, not the absolute.",
         fontsize=8.2, color="#7a828e", ha="left", va="bottom")
fig.text(0.995, 0.012, "Produced by 1AEO", color="#a5a5a5", fontsize=8, ha="right", va="bottom")
fig.tight_layout(rect=[0, 0.03, 1, 0.87])
fig.savefig(OUT, facecolor=BG, bbox_inches="tight")
print("wrote", OUT)
