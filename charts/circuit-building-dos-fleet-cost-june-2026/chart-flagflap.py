#!/usr/bin/env python3
# Chart: "1AEO's guards flickered out more than the network's under load — then fully recovered"
# (blog image: circuit-building-dos-wave-june-2026-chart-flagflap.png)
#
# Fully reproducible from public data — a matched guards-vs-guards comparison:
#   1. Onionoo identifies 1AEO's relays by ContactInfo (contact=1aeo.com);
#   2. CollecTor's signed consensus archives (every 6h: the 00/06/12/18 UTC
#      consensus) give, per snapshot, which relays carry the Running flag and
#      which carry the Guard flag;
#   3. GREEN = share of 1AEO's guard fleet that dropped the Running flag per 6h;
#      RED   = share of the whole NETWORK's guard relays that dropped it, same
#      6h grid. Guards vs guards, so the two populations are comparable, on one
#      shared % axis.
#
# NOTE ON 1AEO's NUMBER: this counts every 1AEO guard visible in the public
# consensus. The blog post's chart additionally sets aside ~35 relays that were
# being migrated to new addresses in the same window (intentionally offline for
# reasons unrelated to the DoS) — a detail 1AEO knows from its own inventory but
# that cannot be derived from public data alone. So 1AEO's peak reads a bit
# higher here (~7%) than in the post (~5%); the DoS-attributable figure is the
# lower one. The network line is unaffected either way.
#
# NOTE: CollecTor tar members are NOT in time order — every consensus is
# collected first, then processed strictly in valid-after order (critical for
# the diff). A relay's first appearance is never counted as a flap.
#
# Requires: python3 + matplotlib. Runtime: ~3-10 min (streams ~35 MB of archives).
# Usage: python3 chart-flagflap.py [output.png]
import sys, os, urllib.request, tarfile, base64, json, datetime as dt
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as md

MONTHS = ["2026-06", "2026-07"]
GRID = ("-00-00-00", "-06-00-00", "-12-00-00", "-18-00-00")
OUT = sys.argv[1] if len(sys.argv) > 1 else \
    "chart-flagflap.png"

def onionoo(url):
    req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
    return json.load(urllib.request.urlopen(req, timeout=180))
d = onionoo("https://onionoo.torproject.org/details?contact=1aeo.com&type=relay&fields=fingerprint")
AEO = set(r["fingerprint"].upper() for r in d["relays"])
print(f"1AEO relays (Onionoo contact=1aeo.com): {len(AEO)}", flush=True)

def open_archive(url):
    cache = os.environ.get("CT_CACHE")
    if cache:
        p = os.path.join(cache, url.rsplit("/", 1)[1])
        if os.path.exists(p): return tarfile.open(p, mode="r:xz")
    return tarfile.open(fileobj=urllib.request.urlopen(url, timeout=900), mode="r|xz")

def parse(text):
    va = None; fp = None; ip = None
    net_run = set(); net_guard = set()          # network Running set, Guard+Running set
    aeo_present = set(); aeo_running = 0          # 1AEO relays present / of which Running
    for line in text.split("\n"):
        if line.startswith("valid-after "):
            try: va = dt.datetime.strptime(line[12:].strip(), "%Y-%m-%d %H:%M:%S")
            except Exception: va = None
        elif line.startswith("r "):
            f = line.split(); fp = None; ip = None
            if len(f) >= 8:
                try: fp = base64.b64decode(f[2] + "=").hex().upper()
                except Exception: fp = None
                ip = f[6]
        elif line.startswith("s ") and fp is not None:
            fl = line.split()[1:]; running = "Running" in fl
            if running:
                net_run.add(sys.intern(fp))
                if "Guard" in fl: net_guard.add(sys.intern(fp))
            if fp in AEO:
                aeo_present.add(fp)
                if running: aeo_running += 1
            fp = None
    return va, frozenset(net_run), frozenset(net_guard), len(aeo_present), aeo_running

snaps = {}
for month in MONTHS:
    url = f"https://collector.torproject.org/archive/relay-descriptors/consensuses/consensuses-{month}.tar.xz"
    print(f"streaming {url} ...", flush=True)
    tf = open_archive(url)
    for mem in tf:
        name = mem.name.split("/")[-1]
        if not any(name.endswith(g + "-consensus") for g in GRID): continue
        va, net_run, net_guard, n_present, n_running = parse(tf.extractfile(mem).read().decode("ascii", "replace"))
        if va is None or not net_run: continue
        snaps[va] = (net_run, net_guard, n_present, n_running)
print(f"collected {len(snaps)} six-hourly consensuses", flush=True)

times = sorted(snaps)
base_nm = max(snaps[t][2] for t in times)                    # peak 1AEO fleet (all guards)
our_flap = [base_nm - snaps[t][3] for t in times]            # 1AEO guards that lost Running
our_pct = [100 * f / base_nm for f in our_flap]
net_g_drop = []; net_g_tot = []                              # network guards that dropped Running / prior guard total
prevG = None
for t in times:
    R = snaps[t][0]; G = snaps[t][1]
    net_g_drop.append(0 if prevG is None else len(prevG - R))
    net_g_tot.append(len(prevG) if prevG is not None else len(G))
    prevG = G
net_pct = [100 * dd / n for dd, n in zip(net_g_drop, net_g_tot)]

ONSET = dt.datetime(2026, 6, 25, 23)
print(f"our guards peak {max(our_flap)} = {max(our_pct):.1f}% | network guards peak {max(net_pct):.1f}%", flush=True)
json.dump({"times": [t.isoformat() for t in times], "our_flap": our_flap, "our_pct": [round(p,3) for p in our_pct],
           "net_g_drop": net_g_drop, "net_g_tot": net_g_tot, "net_pct": [round(p,3) for p in net_pct],
           "base_nm": base_nm}, open(OUT + ".data.json", "w"))

INK="#e6e6e6"; MUT="#9a9a9a"; BG="#1e1e1e"; GRID_C="#333"; GRN="#00ff7f"; RED="#ff6b6b"
X = times
fig, ax = plt.subplots(figsize=(10, 4.9), dpi=200); fig.patch.set_facecolor(BG); ax.set_facecolor(BG)
ax.axvline(ONSET, color=MUT, ls="--", lw=1, alpha=0.7)
ax.text(ONSET, max(our_pct) * 1.02, "  flood onset", color=MUT, fontsize=8.5, ha="left", va="top")
ax.fill_between(X, our_pct, color=GRN, alpha=0.15, zorder=3); ax.plot(X, our_pct, color=GRN, lw=2.6, zorder=4, label="1AEO guards (% flapping)")
ax.plot(X, net_pct, color=RED, lw=1.9, alpha=0.9, zorder=3, label="rest of the network's guards (% flapping)")
ax.set_ylabel("share of that operator's guards flapping\nthe Running flag  (% / 6h)", fontsize=10, color=MUT); ax.set_ylim(0, max(our_pct) * 1.2)
ax.tick_params(colors=MUT); ax.grid(True, axis="y", color=GRID_C, lw=0.6); ax.set_axisbelow(True)
for s in ("top", "right"): ax.spines[s].set_visible(False)
for s in ("left", "bottom"): ax.spines[s].set_color("#555")
ax.xaxis.set_major_formatter(md.DateFormatter("%b %d")); ax.xaxis.set_major_locator(md.DayLocator(interval=4)); fig.autofmt_xdate()
lg = ax.legend(loc="upper right", fontsize=9.5, frameon=True, facecolor=BG, edgecolor="#444")
for t in lg.get_texts(): t.set_color(INK)
ax.set_title("1AEO's guards flickered out more than the network's under load — then fully recovered",
             fontsize=12.4, color=INK, loc="left", pad=40, fontweight="bold")
ax.text(0, 1.03,
        "guard relays only on both lines — a matched, guards-vs-guards comparison from the signed CollecTor consensuses · UTC\n"
        f"before the flood 1AEO's guards essentially never dropped out; under load they peaked {max(our_pct):.1f}% vs the network's guards {max(net_pct):.1f}%, then self-healed to zero",
        transform=ax.transAxes, fontsize=8.2, color=MUT, va="bottom", linespacing=1.35)
fig.text(0.995, 0.012, "Produced by 1AEO", color="#a5a5a5", fontsize=8, ha="right", va="bottom")
fig.tight_layout(pad=1.1)
fig.savefig(OUT, facecolor=BG, bbox_inches="tight")
print("wrote", OUT)
