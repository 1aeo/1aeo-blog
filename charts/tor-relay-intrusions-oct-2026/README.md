# Tor relay intrusions, October 2026: chart code

These scripts rebuild 1AEO charts from public Tor network data: the hourly
network-status consensuses archived by the Tor Project's
[CollecTor](https://collector.torproject.org/). Anyone can rerun them and get the
same numbers. Only counts are written; relay fingerprints are used in memory to
follow each relay from hour to hour and are never saved.

| Chart | Output file | Published in |
|---|---|---|
| Exit policies | `png/tor-relay-intrusions-oct-2026-chart-exit-policies.png` | [Securing a Fresh Ubuntu VM for a Tor Relay: A Beginner's Checklist](https://1aeo.com/blog/securing-fresh-ubuntu-vm-tor-relay-checklist.html) |

## What each chart shows

**Exit policies** (Sep 30 to Oct 10, 2026, hourly). For each hourly consensus, the
number of relays advertising either of the two exit policies the intruders wrote
(policy A or B below). The count is zero in every consensus before
2026-10-01 15:00 UTC, peaks at **353 relays at 2026-10-04 04:00 UTC**, and is zero
again from **2026-10-05 17:00 UTC** onward. The dashed line marks the Tor Project's
[warning on the Tor forum](https://forum.torproject.org/t/tor-relays-security-incident-affecting-some-relay-operators/22231),
posted 2026-10-05 17:50 UTC.

Each chart script asserts the numbers it prints against the data before it draws
anything, and checks that no label is clipped or overlaps another.

## Definitions

All times are UTC and refer to a consensus's `valid-after` hour. The data runs
from 2026-08-01 00:00 to 2026-10-10 03:00, 1,683 hourly consensuses. CollecTor has
no consensus for 2026-10-01 19:00, so that hour is simply absent.

**Policy A and policy B.** Each relay entry in a consensus has a `p` line, the
summary of its exit policy (the ports it accepts or rejects for most addresses;
see the [directory protocol spec](https://spec.torproject.org/dir-spec/consensus-formats.html)).
A relay is "on" a policy in a given hour when the text after `p ` is exactly:

```
A: reject 25,110,135,137-139,143,445,465,587,993,995,3389
B: reject 25,119,135-139,445,465,563,587,993,995,1214,4661-4666,6346-6429,6699,6881-6999
```

Policy A first appears at 2026-10-01 15:00 and policy B at 2026-10-02 10:00. Both
reject a short port list and allow every other port, including 22.

**Opening of port 22.** For each relay, take its consensus entries in time order.
A run of entries whose `p` summary does not allow port 22 (non-exits included) is
a streak; a gap of more than 6 hours between two consecutive entries starts a new
streak. An opening is the first entry that allows port 22 right after a streak
spanning at least 72 hours (first to last entry, inclusive), provided it comes no
more than 72 hours after the streak's last entry. It is dated by that entry's
consensus hour, and counts toward the red bars when that entry is on policy A or
B. Because 72 hours of history are needed, openings can be counted from Aug 4 on.

**First BadExit flag on these relays.** The first consensus in which the
directory authorities newly gave the `BadExit` flag to a relay while it was on
policy A or B (the relay carries `BadExit` in that consensus but not in its
previous one). A relay that already carried `BadExit` before it switched to
policy A or B, and kept it throughout, does not count.

## How to run

Requirements: Python 3.9 or newer with `numpy` and `matplotlib`
(`python3 -m pip install numpy matplotlib`). Run from this folder:

```sh
python3 fetch.py && python3 series.py && python3 chart-exit-policies.py
```

| Step | What it does | Measured time |
|---|---|---|
| `fetch.py` | Downloads `consensuses-2026-08/09/10.tar.xz` (about 64 MB, growing to about 85 MB once October is complete) into `cache/`, checks each file's size and SHA-256 against CollecTor's published index, reads every archive end to end, and confirms that every hour in the window is present (apart from the one hour CollecTor lacks). If the October archive does not reach 2026-10-10 03:00 yet, it fetches the missing hours from CollecTor's `recent/` folder. Files already in `cache/` that match the index are skipped. | 15 s from scratch, 1 s when cached |
| `series.py` | Streams the consensuses out of the archives (about 6.5 GB of text, never extracted to disk) and writes `out/hourly_exit_policies.csv`, `out/daily_ssh_openings.csv` and `out/facts.json`. | 14 s on a 32-thread machine (about 110 CPU-seconds, about 3.5 GB RAM in total across 12 worker processes; fewer cores use proportionally less) |
| `chart-exit-policies.py` | Reads `out/`, assert the published numbers, write `png/`. | under 1 s each |

To redraw the chart without downloading anything, run only the chart script:
`out/` is committed.

## Outputs

- `out/hourly_exit_policies.csv`: `valid_after_utc, relays_on_policy_A, relays_on_policy_B, total`
  for every consensus in the window; `total` is A + B and is what the exit-policies chart plots.
- `out/daily_ssh_openings.csv`: `date_utc, openings_total, openings_on_policies`
  for Aug 4 to Oct 9.
- `out/facts.json`: the chart's numbers and the derived counts behind them.
- `png/`: the chart, 2080 x 1120 px (not committed; the published copies ship
  with the posts).

## Reproducibility notes

- CollecTor rebuilds the archive for the current month as new hours arrive, so the
  October file you download will differ from ours. `series.py` only uses consensuses
  up to 2026-10-10 03:00, so the outputs do not change.
- With Python 3.9.6, numpy 2.0.2 and matplotlib 3.9.4 the PNG is byte-identical
  to the published chart. Other matplotlib or FreeType versions can
  shift anti-aliasing slightly; the numbers are the same.
- `cache/` is git-ignored.

## Sources

- Tor Project CollecTor, network-status consensus archives:
  `https://collector.torproject.org/archive/relay-descriptors/consensuses/`
  (`recent/relay-descriptors/consensuses/` for the newest hours) and the file index
  `https://collector.torproject.org/index/index.json.xz`.
- Consensus format: [Tor directory protocol, consensus formats](https://spec.torproject.org/dir-spec/consensus-formats.html).
- Tor Project warning, 2026-10-05 17:50 UTC:
  [Security incident affecting some relay operators](https://forum.torproject.org/t/tor-relays-security-incident-affecting-some-relay-operators/22231).
