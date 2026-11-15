# Tor relay version-status trends (`2017–2026`): chart and reproduction code

These scripts rebuild both charts in [AI Helps Secure Tor: Obsolete Relay Average Hits a Ten-Year High](https://1aeo.com/blog/ai-comes-to-tor-security.html) from public [CollecTor](https://collector.torproject.org/) hourly network-status consensuses and Tor [Onionoo](https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/blob/master/src/main/java/org/torproject/metrics/onionoo/updater/TorVersion.java) version-classification rules.

| Chart | Published outputs | Scope |
|---|---|---|
| Yearly status shares (`2017–2026 YTD`) | `site/blog/images/ai-tor-security-yearly-version-status-2017-2026.{svg,-mobile.svg,.png}` | Annual shares of observed Running relay-hours (`84,750` consensuses) |
| Monthly status shares (`2026`) | `site/blog/images/ai-tor-security-monthly-version-status-2026.{svg,-mobile.svg,.png}` | Monthly shares of observed Running relay-hours in 2026 through `Oct 16, 22:00 UTC` (`6,335` consensuses) |

## Definitions

- **Time basis & cutoff:** All timestamps are `UTC` consensus `valid-after` hours from `2017-01-01 00:00 UTC` through `2026-10-16 22:00 UTC` (`84,750` complete archived consensuses).
- **Population:** Relays listed in each archived consensus carrying the `Running` flag. Bridges and non-`Running` relays are excluded.
- **Version classification:** Each relay's `v` line token after `Tor ` is compared against that consensus's contemporaneous `server-versions` line using Onionoo's `TorVersion` comparator (`recommended`, `obsolete`, `unrecommended`, `experimental`, `new_in_series`, and `unknown` for missing/non-`Tor ` version lines or missing `server-versions`). Pre-release suffixes such as `-alpha`, `-rc` and `-dev` are preserved; commit metadata is ignored.
- **Relay-hour shares & mean counts:** Annual and monthly status shares divide status relay-hours by total observed `Running` relay-hours in the period (`100 × sum(status) / sum(total)`), matching the ratio of unweighted arithmetic hourly means. Missing CollecTor consensus hours (including `461` missing hours in April 2026) are omitted rather than interpolated.

## How to run

Requirements: Python 3.9+ with `matplotlib` and `numpy` (and `reconstruct.py --test` uses stdlib only). Run from this directory:

```sh
python3 reconstruct.py --test
python3 render_charts.py
```

- `reconstruct.py --test`: Runs unit tests against Onionoo's official `TorVersion` test cases and verifies the exact integer relay-hour integrals in `ANNUAL_SUMMARY` and `MONTHLY_2026_SUMMARY`.
- `render_charts.py`: Uses `../shared/blog_chart_style.py` and `../shared/blog_display_numbers.py` to generate deterministic `800px` desktop SVGs, `360px` mobile SVGs (`-mobile.svg`), and `2400 × 1620` PNG exports under `../../site/blog/images/`, asserting zero clipped or overlapping labels before writing.
- `reconstruct.py --recompute [--years 2026 ...]`: Optional end-to-end verification against CollecTor `consensuses-YYYY-MM.tar.xz` archives (set `CT_CACHE` to reuse previously downloaded `.tar.xz` archives; otherwise archives are fetched into git-ignored `cache/`). Recomputing all ten years (`2017–2026`) downloads and streams roughly `118` monthly archives.

## Sources

- CollecTor network-status consensus archives: <https://collector.torproject.org/archive/relay-descriptors/consensuses/>
- Onionoo `TorVersion` classifier: <https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/blob/master/src/main/java/org/torproject/metrics/onionoo/updater/TorVersion.java>
- Tor 0.4.9.14 changelog citing LLM security reports: <https://gitlab.torproject.org/tpo/core/tor/-/blob/tor-0.4.9.14/ChangeLog#L134>
