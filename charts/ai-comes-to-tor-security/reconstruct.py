#!/usr/bin/env python3
"""Reconstruct Tor Running-relay version-status counts and shares from CollecTor.

Applies Tor Onionoo's ``TorVersion.java`` comparison and classification rules to
archived hourly ``valid-after`` network-status consensuses (2017-01-01 00:00 UTC
through 2026-10-16 22:00 UTC) and reconciles against the audited annual and
2026 monthly relay-hour summaries used in:
https://1aeo.com/blog/ai-comes-to-tor-security.html

Usage:
  python3 reconstruct.py --test
  python3 reconstruct.py --recompute [--years 2026]
"""
from __future__ import annotations

import argparse
import calendar
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache, total_ordering
import math
import os
from pathlib import Path
import re
import tarfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

COLLECTOR_CONSENSUSES_URL = (
    "https://collector.torproject.org/archive/relay-descriptors/consensuses/"
)
CLASSIFIER_SOURCE = (
    "https://gitlab.torproject.org/tpo/network-health/metrics/onionoo/-/blob/"
    "master/src/main/java/org/torproject/metrics/onionoo/updater/TorVersion.java"
)
CUTOFF_UTC = datetime(2026, 10, 16, 22, 0, 0)
STATUS_COLUMNS = (
    "recommended",
    "obsolete",
    "unrecommended",
    "experimental",
    "new_in_series",
    "unknown",
)
STATUS_LABELS = {
    "recommended": "Recommended",
    "obsolete": "Obsolete",
    "unrecommended": "Unrecommended",
    "experimental": "Experimental",
    "new_in_series": "New in series",
    "unknown": "Unknown",
}

VERSIONS_RE = re.compile(rb"\nv ([^\n]*)")
RUNNING_RE = re.compile(rb"\ns [^\n]*\bRunning\b")
ENTRIES_RE = re.compile(rb"\ns ([^\n]*)\n(?:v ([^\n]*)\n)?")

# Exact integer relay-hour integrals from CollecTor consensuses, 2017-01-01 00:00 UTC
# through 2026-10-16 22:00 UTC (84,750 complete hourly consensuses).
ANNUAL_SUMMARY = (
    {
        "year": 2017,
        "label": "2017",
        "partial": False,
        "n_consensuses": 8756,
        "expected_hours": 8760,
        "period_end": "2017-12-31 23:00:00",
        "sums": {
            "recommended": 47851516,
            "obsolete": 3104380,
            "unrecommended": 10057481,
            "experimental": 115403,
            "new_in_series": 22180,
            "unknown": 485,
            "total": 61151445,
        },
    },
    {
        "year": 2018,
        "label": "2018",
        "partial": False,
        "n_consensuses": 8760,
        "expected_hours": 8760,
        "period_end": "2018-12-31 23:00:00",
        "sums": {
            "recommended": 42751236,
            "obsolete": 5472439,
            "unrecommended": 7124701,
            "experimental": 131458,
            "new_in_series": 64290,
            "unknown": 0,
            "total": 55544124,
        },
    },
    {
        "year": 2019,
        "label": "2019",
        "partial": False,
        "n_consensuses": 8754,
        "expected_hours": 8760,
        "period_end": "2019-12-31 23:00:00",
        "sums": {
            "recommended": 44547644,
            "obsolete": 3781800,
            "unrecommended": 7727996,
            "experimental": 160306,
            "new_in_series": 1643,
            "unknown": 405,
            "total": 56219794,
        },
    },
    {
        "year": 2020,
        "label": "2020",
        "partial": False,
        "n_consensuses": 8779,
        "expected_hours": 8784,
        "period_end": "2020-12-31 23:00:00",
        "sums": {
            "recommended": 49048931,
            "obsolete": 3672018,
            "unrecommended": 4759507,
            "experimental": 369006,
            "new_in_series": 4472,
            "unknown": 0,
            "total": 57853934,
        },
    },
    {
        "year": 2021,
        "label": "2021",
        "partial": False,
        "n_consensuses": 8721,
        "expected_hours": 8760,
        "period_end": "2021-12-31 23:00:00",
        "sums": {
            "recommended": 52733365,
            "obsolete": 724043,
            "unrecommended": 4619451,
            "experimental": 213395,
            "new_in_series": 25494,
            "unknown": 0,
            "total": 58315748,
        },
    },
    {
        "year": 2022,
        "label": "2022",
        "partial": False,
        "n_consensuses": 8721,
        "expected_hours": 8760,
        "period_end": "2022-12-31 23:00:00",
        "sums": {
            "recommended": 56556660,
            "obsolete": 579306,
            "unrecommended": 548544,
            "experimental": 471407,
            "new_in_series": 9173,
            "unknown": 0,
            "total": 58165090,
        },
    },
    {
        "year": 2023,
        "label": "2023",
        "partial": False,
        "n_consensuses": 8676,
        "expected_hours": 8760,
        "period_end": "2023-12-31 23:00:00",
        "sums": {
            "recommended": 59958067,
            "obsolete": 894400,
            "unrecommended": 433283,
            "experimental": 941839,
            "new_in_series": 5583,
            "unknown": 0,
            "total": 62233172,
        },
    },
    {
        "year": 2024,
        "label": "2024",
        "partial": False,
        "n_consensuses": 8632,
        "expected_hours": 8784,
        "period_end": "2024-12-31 23:00:00",
        "sums": {
            "recommended": 63362927,
            "obsolete": 1708548,
            "unrecommended": 183069,
            "experimental": 1070763,
            "new_in_series": 1,
            "unknown": 0,
            "total": 66325308,
        },
    },
    {
        "year": 2025,
        "label": "2025",
        "partial": False,
        "n_consensuses": 8616,
        "expected_hours": 8760,
        "period_end": "2025-12-31 23:00:00",
        "sums": {
            "recommended": 70310514,
            "obsolete": 4394715,
            "unrecommended": 282542,
            "experimental": 969478,
            "new_in_series": 3148,
            "unknown": 1564,
            "total": 75961961,
        },
    },
    {
        "year": 2026,
        "label": "2026 YTD",
        "partial": True,
        "n_consensuses": 6335,
        "expected_hours": 6935,
        "period_end": "2026-10-16 22:00:00",
        "sums": {
            "recommended": 51980979,
            "obsolete": 9281419,
            "unrecommended": 84058,
            "experimental": 608090,
            "new_in_series": 418,
            "unknown": 514,
            "total": 61955478,
        },
    },
)

MONTHLY_2026_SUMMARY = (
    {
        "month": "2026-01",
        "month_number": 1,
        "label": "Jan",
        "partial": False,
        "n_consensuses": 737,
        "expected_hours": 744,
        "period_end": "2026-01-31 23:00:00",
        "sums": {
            "recommended": 5487089,
            "obsolete": 1536314,
            "unrecommended": 20028,
            "experimental": 134534,
            "new_in_series": 0,
            "unknown": 0,
            "total": 7177965,
        },
    },
    {
        "month": "2026-02",
        "month_number": 2,
        "label": "Feb",
        "partial": False,
        "n_consensuses": 650,
        "expected_hours": 672,
        "period_end": "2026-02-28 23:00:00",
        "sums": {
            "recommended": 5258028,
            "obsolete": 1034558,
            "unrecommended": 39111,
            "experimental": 56605,
            "new_in_series": 344,
            "unknown": 0,
            "total": 6388646,
        },
    },
    {
        "month": "2026-03",
        "month_number": 3,
        "label": "Mar",
        "partial": False,
        "n_consensuses": 643,
        "expected_hours": 744,
        "period_end": "2026-03-31 23:00:00",
        "sums": {
            "recommended": 5350551,
            "obsolete": 812896,
            "unrecommended": 15139,
            "experimental": 44828,
            "new_in_series": 74,
            "unknown": 0,
            "total": 6223488,
        },
    },
    {
        "month": "2026-04",
        "month_number": 4,
        "label": "Apr*",
        "partial": False,
        "n_consensuses": 259,
        "expected_hours": 720,
        "period_end": "2026-04-30 23:00:00",
        "sums": {
            "recommended": 2349295,
            "obsolete": 253459,
            "unrecommended": 3019,
            "experimental": 16061,
            "new_in_series": 0,
            "unknown": 0,
            "total": 2621834,
        },
    },
    {
        "month": "2026-05",
        "month_number": 5,
        "label": "May",
        "partial": False,
        "n_consensuses": 742,
        "expected_hours": 744,
        "period_end": "2026-05-31 23:00:00",
        "sums": {
            "recommended": 6708581,
            "obsolete": 614581,
            "unrecommended": 6165,
            "experimental": 85118,
            "new_in_series": 0,
            "unknown": 0,
            "total": 7414445,
        },
    },
    {
        "month": "2026-06",
        "month_number": 6,
        "label": "Jun",
        "partial": False,
        "n_consensuses": 715,
        "expected_hours": 720,
        "period_end": "2026-06-30 23:00:00",
        "sums": {
            "recommended": 5903271,
            "obsolete": 973050,
            "unrecommended": 273,
            "experimental": 84527,
            "new_in_series": 0,
            "unknown": 0,
            "total": 6961121,
        },
    },
    {
        "month": "2026-07",
        "month_number": 7,
        "label": "Jul",
        "partial": False,
        "n_consensuses": 743,
        "expected_hours": 744,
        "period_end": "2026-07-31 23:00:00",
        "sums": {
            "recommended": 6546942,
            "obsolete": 715303,
            "unrecommended": 0,
            "experimental": 78748,
            "new_in_series": 0,
            "unknown": 0,
            "total": 7340993,
        },
    },
    {
        "month": "2026-08",
        "month_number": 8,
        "label": "Aug",
        "partial": False,
        "n_consensuses": 744,
        "expected_hours": 744,
        "period_end": "2026-08-31 23:00:00",
        "sums": {
            "recommended": 6946746,
            "obsolete": 517772,
            "unrecommended": 0,
            "experimental": 53690,
            "new_in_series": 0,
            "unknown": 151,
            "total": 7518359,
        },
    },
    {
        "month": "2026-09",
        "month_number": 9,
        "label": "Sep",
        "partial": False,
        "n_consensuses": 720,
        "expected_hours": 720,
        "period_end": "2026-09-30 23:00:00",
        "sums": {
            "recommended": 4781826,
            "obsolete": 1972359,
            "unrecommended": 323,
            "experimental": 35924,
            "new_in_series": 0,
            "unknown": 363,
            "total": 6790795,
        },
    },
    {
        "month": "2026-10",
        "month_number": 10,
        "label": "Oct MTD",
        "partial": True,
        "n_consensuses": 382,
        "expected_hours": 383,
        "period_end": "2026-10-16 22:00:00",
        "sums": {
            "recommended": 2648650,
            "obsolete": 851127,
            "unrecommended": 0,
            "experimental": 18055,
            "new_in_series": 0,
            "unknown": 0,
            "total": 3517832,
        },
    },
)


@total_ordering
@dataclass(frozen=True)
class TorVersion:
    """Port Onionoo's TorVersion.java ordering, including pre-release tag order."""

    numbers: tuple[int, ...]
    tag: str | None = None

    @property
    def series(self):
        return self.numbers[:3] if len(self.numbers) >= 3 else None

    @property
    def sort_key(self):
        return self.numbers, self.tag is not None, self.tag or ""

    def __lt__(self, other):
        if not isinstance(other, TorVersion):
            return NotImplemented
        return self.sort_key < other.sort_key


@lru_cache(maxsize=None)
def parse_version(version: str | None) -> TorVersion | None:
    """Parse up to four dotted ASCII digits plus an optional status tag."""
    if version is None:
        return None
    components = version.split("-", 1)[0].split(".")
    numbers = []
    for position, component in enumerate(components[:4]):
        if component:
            if not re.fullmatch(r"[+]?\d+", component, re.ASCII):
                return None
            value = int(component)
            if not -2147483648 <= value <= 2147483647:
                return None
            numbers.append(value)
        elif position == 0 or position < len(components) - 1:
            return None
    tag = version.split("-", 1)[1].split(" ")[0] if "-" in version else None
    return TorVersion(tuple(numbers), tag)


@lru_cache(maxsize=None)
def recommendation_versions(recommended: tuple[str, ...]):
    return tuple(
        sorted(
            {
                parsed
                for value in recommended
                if (parsed := parse_version(value)) is not None
            }
        )
    )


@lru_cache(maxsize=None)
def classify_version(version: str | None, recommended: tuple[str, ...]) -> str:
    """Classify one relay version against contemporaneous consensus recommendations."""
    recs = recommendation_versions(recommended)
    if version is None or not recs:
        return "unknown"
    parsed = parse_version(version)
    if parsed is None or parsed.series is None:
        return "unrecommended"
    if parsed in recs:
        return "recommended"
    if parsed > recs[-1]:
        return "experimental"
    if parsed < recs[0]:
        return "obsolete"
    same_series = [other for other in recs if other.series == parsed.series]
    if same_series and all(parsed > other for other in same_series):
        return "new_in_series"
    return "unrecommended"


def normalize_consensus_version(value: str) -> str | None:
    """Extract the first whitespace token after 'Tor ', matching Onionoo."""
    return value.split(" ")[1] if value.startswith("Tor ") else None


def classify_counts(version_counts, recommended):
    rec = tuple(recommended)
    counts = Counter({name: 0 for name in STATUS_COLUMNS})
    for version, count in version_counts.items():
        counts[classify_version(normalize_consensus_version(version), rec)] += count
    return {**counts, "total": sum(version_counts.values())}


def parse_consensus(raw: bytes, source: str = ""):
    """Parse one archived consensus document into Running relay version counts."""
    if b"\ndirectory-footer\n" not in raw or b"-----END SIGNATURE-----" not in raw:
        return None, "incomplete_footer_or_signature"
    stamp_match = re.search(rb"\nvalid-after ([^\n]*)", raw)
    if not stamp_match:
        return None, "missing_timestamp"
    stamp = stamp_match.group(1).decode("ascii")
    ts = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    if not datetime(2017, 1, 1) <= ts <= CUTOFF_UTC:
        return None, "outside_period"
    entry_count = raw.count(b"\nr ")
    if not entry_count or entry_count != raw.count(b"\ns "):
        return None, "mismatched_entry_flags"
    all_versions = Counter(VERSIONS_RE.findall(raw))
    if sum(all_versions.values()) > entry_count:
        return None, "too_many_version_lines"
    n_running = len(RUNNING_RE.findall(raw))
    if n_running == entry_count:
        running = all_versions
        if sum(running.values()) < entry_count:
            running[b"(missing)"] = entry_count - sum(running.values())
    else:
        entries = ENTRIES_RE.findall(raw)
        if len(entries) != entry_count:
            return None, "malformed_entry_order"
        running = Counter(
            v or b"(missing)" for flags, v in entries if b"Running" in flags.split()
        )
        if sum(running.values()) != n_running:
            return None, "running_count_mismatch"
    rec = re.search(rb"\nserver-versions ([^\n]*)", raw)
    return {
        "timestamp": stamp,
        "recommended": rec.group(1).decode("ascii").split(",") if rec else [],
        "running": {v.decode("utf-8", errors="replace"): c for v, c in running.items()},
        "source": source,
    }, None


def download_archive(url: str, target: Path) -> Path:
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(".part")
    for attempt in range(3):
        try:
            req = Request(url, headers={"User-Agent": "1aeo-version-reconstruct/1.0"})
            with urlopen(req, timeout=120) as response, part.open("wb") as out:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
            part.replace(target)
            return target
        except (HTTPError, URLError, TimeoutError, OSError):
            if part.exists():
                part.unlink()
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    return target


def recompute_from_collector(years: list[int], cache_dir: Path) -> None:
    """Stream CollecTor monthly archives and assert exact match to embedded sums."""
    expected_by_year = {row["year"]: row for row in ANNUAL_SUMMARY}
    expected_by_month = {row["month"]: row for row in MONTHLY_2026_SUMMARY}
    for year in years:
        if year not in expected_by_year:
            raise ValueError(f"Unsupported year {year}; expected 2017..2026")
        max_month = 10 if year == 2026 else 12
        year_sums = Counter({k: 0 for k in (*STATUS_COLUMNS, "total")})
        year_consensuses = 0
        for month_num in range(1, max_month + 1):
            key = f"{year}-{month_num:02d}"
            archive_name = f"consensuses-{key}.tar.xz"
            url = COLLECTOR_CONSENSUSES_URL + archive_name
            archive_path = download_archive(url, cache_dir / archive_name)
            rows = {}
            with tarfile.open(archive_path, "r|xz") as archive:
                for member in archive:
                    if not member.isfile() or not member.name.endswith("-consensus"):
                        continue
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        continue
                    parsed, _ = parse_consensus(extracted.read(), url + "#" + member.name)
                    if parsed:
                        rows[parsed["timestamp"]] = parsed
            month_sums = Counter({k: 0 for k in (*STATUS_COLUMNS, "total")})
            for stamp, raw in sorted(rows.items()):
                counts = classify_counts(raw["running"], raw["recommended"])
                month_sums.update(counts)
            n_obs = len(rows)
            year_sums.update(month_sums)
            year_consensuses += n_obs
            if key in expected_by_month:
                ref = expected_by_month[key]
                assert n_obs == ref["n_consensuses"], (key, n_obs, ref["n_consensuses"])
                assert dict(month_sums) == ref["sums"], (key, dict(month_sums), ref["sums"])
            print(f"{key}: {n_obs} consensuses, obsolete={month_sums['obsolete']:,}, total={month_sums['total']:,}")
        ref_year = expected_by_year[year]
        assert year_consensuses == ref_year["n_consensuses"], (year, year_consensuses, ref_year["n_consensuses"])
        assert dict(year_sums) == ref_year["sums"], (year, dict(year_sums), ref_year["sums"])
        print(f"VERIFIED {year}: {year_consensuses} consensuses match ANNUAL_SUMMARY exactly.")


class ReconstructTests(unittest.TestCase):
    recommended = (
        "0.2.5.16",
        "0.2.5.17",
        "0.2.9.14",
        "0.2.9.15",
        "0.3.1.9",
        "0.3.1.10",
        "0.3.2.8-rc",
        "0.3.2.9",
        "0.3.3.1-alpha",
        "0.3.3.2-alpha",
    )

    def test_official_onionoo_status_cases(self):
        cases = {
            "0.2.5.16": "recommended",
            "0.3.2.8-rc": "recommended",
            "0.3.3.2-alpha": "recommended",
            "0.3.3.2-alpha-dev": "experimental",
            "0.3.3.3-alpha": "experimental",
            "0.3.4.0-alpha-dev": "experimental",
            "0.2.5.15": "obsolete",
            "0.1.0.1-rc": "obsolete",
            "0.2.5.18": "new_in_series",
            "0.3.2.9-dev": "new_in_series",
            "0.3.2.10": "new_in_series",
            "0.2.9.13": "unrecommended",
            "0.3.1.8-dev": "unrecommended",
            "0.3.3.0-alpha-dev": "unrecommended",
            "1.0-final": "unrecommended",
            "0.0.2pre13": "unrecommended",
        }
        for version, expected in cases.items():
            with self.subTest(version=version):
                self.assertEqual(classify_version(version, self.recommended), expected)

    def test_official_comparator_cases(self):
        cases = [
            ("0.2.5.16", "0.2.5.16", 0),
            ("0.2.5.16", "0.2.5.17", -1),
            ("0.3.3.1-alpha", "0.3.3.1-alpha", 0),
            ("0.1.2.3", "00.01.02.03", 0),
            ("0.1.2.3-alpha", "00.01.02.03-aallpphhaa", 1),
            *[(value, "0.1.2.3", -1) for value in ("0", "0.", "0.1", "0.1.", "0.1.2", "0.1.2.")],
            ("0.2", "0.1.2.3", 1),
        ]
        for first, second, expected in cases:
            with self.subTest(first=first, second=second):
                a, b = parse_version(first), parse_version(second)
                self.assertEqual((a > b) - (a < b), expected)

    def test_consensus_version_normalization_and_conservation(self):
        self.assertIsNone(normalize_consensus_version("Arti 2.0.0"))
        self.assertEqual(normalize_consensus_version("Tor 0.4.9.14 (git-1234)"), "0.4.9.14")
        counts = classify_counts(
            {"Tor 0.2.5.15": 3, "Tor 0.2.5.16": 5, "Tor badver": 2, "(missing)": 7},
            self.recommended,
        )
        self.assertEqual(counts["obsolete"], 3)
        self.assertEqual(counts["recommended"], 5)
        self.assertEqual(counts["unrecommended"], 2)
        self.assertEqual(counts["unknown"], 7)
        self.assertEqual(counts["total"], 17)

    def test_summary_integrals_and_reconciliation(self):
        self.assertEqual([r["year"] for r in ANNUAL_SUMMARY], list(range(2017, 2027)))
        self.assertEqual(sum(r["n_consensuses"] for r in ANNUAL_SUMMARY), 84750)
        for row in (*ANNUAL_SUMMARY, *MONTHLY_2026_SUMMARY):
            sums = row["sums"]
            self.assertEqual(sum(sums[k] for k in STATUS_COLUMNS), sums["total"])
            self.assertGreater(row["n_consensuses"], 0)
            self.assertLessEqual(row["n_consensuses"], row["expected_hours"])
        ytd_2026 = ANNUAL_SUMMARY[-1]
        self.assertEqual(sum(r["n_consensuses"] for r in MONTHLY_2026_SUMMARY), ytd_2026["n_consensuses"])
        for key in (*STATUS_COLUMNS, "total"):
            self.assertEqual(sum(r["sums"][key] for r in MONTHLY_2026_SUMMARY), ytd_2026["sums"][key])
        self.assertTrue(math.isclose(100 * ytd_2026["sums"]["obsolete"] / ytd_2026["sums"]["total"], 14.980788300915053))


def run_tests() -> None:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ReconstructTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", action="store_true", help="Run Onionoo classifier and data consistency tests")
    parser.add_argument("--recompute", action="store_true", help="Stream CollecTor tar.xz archives and verify sums")
    parser.add_argument("--years", nargs="+", type=int, default=list(range(2017, 2027)), help="Years for --recompute")
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(os.environ.get("CT_CACHE") or Path(__file__).resolve().parent / "cache"),
        help="Directory holding consensuses-YYYY-MM.tar.xz archives",
    )
    args = parser.parse_args()
    if args.test or not args.recompute:
        run_tests()
    if args.recompute:
        recompute_from_collector(args.years, args.cache_dir)


if __name__ == "__main__":
    main()
