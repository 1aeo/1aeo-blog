# Reproduce the public-data charts from the June–July 2026 circuit-building DoS series

Every chart below is built **entirely from Tor's public data** — the signed
[CollecTor](https://collector.torproject.org/) archives and/or the
[Onionoo](https://onionoo.torproject.org/) API. No relay access, no private
telemetry. Each script is self-contained: it fetches the data, recomputes the
numbers from scratch, and renders the chart published in the post.

## The series

The charts belong to a four-part series on the June–July 2026 circuit-building
DoS wave. Script directories are named after the post they reproduce:

| # | post | scripts |
|---|---|---|
| 1 | [The Tor Network Is Under a Circuit-Building DoS Wave](https://1aeo.com/blog/tor-network-dos-wave-june-2026.html) | **`tor-network-dos-wave-june-2026/`** — every chart in the post |
| 2 | [Anatomy of a Circuit-Building DoS: Three Waves on a Guard Fleet](https://1aeo.com/blog/circuit-building-dos-anatomy-june-2026.html) | none — its charts are built from 1AEO's first-party MetricsPort telemetry, not reproducible without relay access |
| 3 | [What a Circuit-Building DoS Actually Costs: How 1AEO's Guard Fleet Held](https://1aeo.com/blog/circuit-building-dos-fleet-cost-june-2026.html) | **`circuit-building-dos-fleet-cost-june-2026/`** — the post's public-data charts (its first-party charts are not reproducible) |
| 4 | [Defending Against Circuit-Building DoS: Better Metrics, and What Tor Could Fix](https://1aeo.com/blog/defending-against-circuit-dos-june-2026.html) | none — no charts |

## Charts in the network-view post ("The Tor Network Is Under a Circuit-Building DoS Wave")

| script | chart | data source | runtime |
|---|---|---|---|
| `tor-network-dos-wave-june-2026/chart-network-overload.py` | Two overload waves across the Tor network | CollecTor server descriptors (`overload-general`) | 10–30 min |
| `tor-network-dos-wave-june-2026/chart-guards-vs-exits.py` | The flood hits the guard position hardest | CollecTor consensuses (flags) × server descriptors | 15–40 min |
| `tor-network-dos-wave-june-2026/chart-network-flap.py` | The flood shook the Running flag network-wide | CollecTor hourly consensuses (`Running` diffs) | 5–15 min |
| `tor-network-dos-wave-june-2026/chart-netflap-rate.py` | Running-flag flicker rate (% of the network) | CollecTor 6h consensuses (`Running` diffs) | 3–10 min |

## Public-data charts in the fleet-cost post ("What a Circuit-Building DoS Actually Costs")

| script | chart | data source | runtime |
|---|---|---|---|
| `circuit-building-dos-fleet-cost-june-2026/chart-network-overload-2line.py` | Network overload vs the 1AEO fleet | CollecTor server descriptors + Onionoo (1AEO fingerprint set) | 10–30 min |
| `circuit-building-dos-fleet-cost-june-2026/chart-guard-count-time.py` | Overloaded guards over time, top-10 operators | CollecTor consensuses × server descriptors + Onionoo (operator sets) | 15–40 min |
| `circuit-building-dos-fleet-cost-june-2026/chart-flagflap.py` | 1AEO guards' Running-flag flapping vs the network's guards (matched %) | CollecTor 6h consensuses + Onionoo (1AEO fingerprint set) | 5–15 min |
| `circuit-building-dos-fleet-cost-june-2026/chart-guard-bubble.py` | Scale vs. overload — top-10 guard operators | Onionoo `/details` (snapshot) | seconds |
| `circuit-building-dos-fleet-cost-june-2026/chart-entryload.py` | Per-guard entry load vs overload | Onionoo `/details` + `/weights` (snapshot) | seconds |

## Requirements

- Python 3.9+ and `matplotlib` (`pip install matplotlib`). No other third-party packages.
- Network access to `collector.torproject.org` and `onionoo.torproject.org`.
- The CollecTor scripts stream the June + July 2026 monthly archives (several
  hundred MB to ~2 GB per run). Only the chart and a small `.data.json` are written.

## Usage

```
python3 <post-directory>/<script>.py [output.png]
```

**Optional speed-ups (CollecTor scripts):** pre-download the monthly `.tar.xz`
archives once and point the scripts at them, avoiding re-downloads:

```
export CT_CACHE=/path/to/archives      # dir holding consensuses-2026-06.tar.xz, server-descriptors-2026-06.tar.xz, ...
export CT_FRESH=/path/to/recent-files  # (overload scripts only) dir of CollecTor recent/ per-file server-descriptors for the final day
export CT_FRESH_CONSENSUS=/path/to/dir # (chart-network-overload.py with DENOMINATOR="consensus" only) dir of recent/ per-file consensuses for the final day
```

Without them, everything is fetched live from CollecTor. (Note: the scripts use
Python's built-in `lzma`/`tarfile`, so no `xz` binary is required.)

## Method notes (the details that matter)

- **Overload:** a relay signs `overload-general` into its server descriptor when
  it crosses Tor's internal overload thresholds. Relays publish at least every
  18 h, so each UTC day effectively covers the whole live network; we count
  distinct fingerprints per day.
- **Denominator (configurable):** `chart-network-overload.py` has a `DENOMINATOR`
  knob at the top — `"publishers"` (default: relays that published a descriptor
  that day) or `"consensus"` (relays in that day's consensus, a slightly smaller
  denominator → percentages ~0.3–0.4 pp higher, e.g. the Jul-12 peak reads 12.7%
  instead of 12.3%). The per-day stdout prints which denominator was used.
- **Final day (Jul 13):** CollecTor's signed *monthly* archive lags real time by
  a day or two (it fully covers days through ~Jul 12). The overload scripts fill
  the final chart day (Jul 13) by unioning CollecTor's *recent/* per-file
  server-descriptor documents into **that day only** — every earlier day comes
  wholly from the signed monthly archive, so Jul 11 stays 11.4% and Jul 12 stays
  12.3%. Overload peaked Jul 12 (12.3%, 1,265 relays) and eased to ~11.7% on Jul 13
  (publishers denominator; the `"consensus"` denominator gives ~12.7% at the peak).
- **Roles:** each relay's role (guard-only / guard+exit / exit-only / middle) is
  read from the flags in the daily 12:00 UTC consensus and joined to that day's
  overload set by fingerprint.
- **Running-flag flap:** the `Running` set is diffed between consecutive hourly
  consensuses. ⚠️ CollecTor tar archives are **not** in time order — consensuses
  are collected first, then processed strictly in `valid-after` order (processing
  in tar order silently corrupts the diffs). A relay's first appearance is never
  counted as a flap, so relay onboarding cannot inflate the counts.
- **Operator grouping (AROI):** operators are grouped by the operator domain
  proven in ContactInfo (queried via Onionoo `contact=<domain>`), and 1AEO's own
  relays are identified publicly via `contact=1aeo.com` — never from any private
  list.
- **`chart-flagflap.py`:** a matched guards-vs-guards comparison — the % of 1AEO's
  guard fleet that dropped the `Running` flag per 6h (green) vs the % of the whole
  network's guard relays that did (red), on one shared axis. Guard-only on both
  sides so the populations are comparable; 1AEO relays are identified via Onionoo
  `contact=1aeo.com`. The script counts every 1AEO guard visible in the public
  consensus: essentially zero flapping pre-flood, a peak of **~7.4%** under load
  (vs the network's guards ~2.1%), then self-healing back to zero — the relays
  stayed up, losing only the flag. The blog post's chart reads a bit lower at the
  peak (**~4.6%**) because it additionally sets aside ~35 relays that were being
  migrated to new addresses in the same window — intentionally offline for
  reasons unrelated to the DoS, known from 1AEO's own inventory and not derivable
  from public data — so the DoS-attributable figure is the lower one. The network
  line is identical either way.

## Onionoo snapshots (`chart-guard-bubble.py`, `chart-entryload.py`)

Onionoo serves only the **current** network state — it has no historical archive —
so these two snapshot charts cannot be reproduced from a past date the way the
CollecTor time-series can. Each script embeds the plotted values from its
documented Onionoo query (snapshot **2026-07-13**, all Guard-flag relays per
operator) and renders deterministically from them. `chart-guard-bubble.py
--verify` re-runs the live Onionoo query and prints the current numbers so you
can compare against the embedded snapshot.

## A note on drift

CollecTor archives are immutable, so the CollecTor time-series reproduce
bit-for-bit. The pieces that touch Onionoo (the 1AEO fingerprint set, operator
counts) move slightly day to day as the live network changes; re-running a day
later shifts those by a relay or two without changing any headline figure.

Produced by [1AEO](https://1aeo.com).
