#!/usr/bin/env python3
"""Turn the cached hourly Tor consensuses into the two chart series.

Usage:  python3 series.py        (after python3 fetch.py)

Reads ./cache/consensuses-2026-{08,09,10}.tar.xz (and ./cache/recent/*-consensus,
if fetch.py needed any) without extracting them, keeps the hourly consensuses
from 2026-08-01 00:00 to 2026-10-10 03:00 UTC, and writes:

  out/hourly_exit_policies.csv  valid_after_utc, relays_on_policy_A,
                                relays_on_policy_B, total (= A + B)
  out/daily_ssh_openings.csv    date_utc, openings_total, openings_on_policies
                                (Aug 4 to Oct 9, 2026; see OPENING RULE below)
  out/facts.json                every number the charts print, derived here

Only counts are written. Relay fingerprints are used in memory to follow each
relay from hour to hour and are never saved.
"""
import csv
import datetime as dt
import glob
import json
import os
import sys
import tarfile
import time
from array import array
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache')
OUT = os.path.join(HERE, 'out')

FIRST = dt.datetime(2026, 8, 1, 0)
LAST = dt.datetime(2026, 10, 10, 3)
KNOWN_GAPS = {dt.datetime(2026, 10, 1, 19)}   # CollecTor has no consensus for this hour

# The two exit policies the intruders wrote, identified by the exact exit-policy
# summary each relay carries on its "p" line in the consensus (Tor dir-spec,
# "p" = the ports the relay's full exit policy accepts or rejects for most
# addresses). A relay counts as "on" a policy in a given hour when the text
# after "p " is exactly one of these strings. Both reject a short port list and
# allow everything else, including SSH (port 22).
POLICY_A = 'reject 25,110,135,137-139,143,445,465,587,993,995,3389'
#   first appears in the 2026-10-01 15:00 UTC consensus
POLICY_B = ('reject 25,119,135-139,445,465,563,587,993,995,1214,'
            '4661-4666,6346-6429,6699,6881-6999')
#   first appears in the 2026-10-02 10:00 UTC consensus

# OPENING RULE (port-22 openings, ssh-openings chart). For each relay, walk its
# hourly consensus entries in time order. A run of entries whose "p" summary
# does NOT allow port 22 (non-exits included) is a streak; a gap of more than
# STREAK_GAP hours between two consecutive entries starts a new streak. An
# "opening" is the first entry that allows port 22 right after a streak that
# spans at least MIN_STREAK hours (first to last entry, inclusive), provided it
# comes no more than MAX_GAP hours after the streak's last entry. It is dated by
# that entry's consensus hour (UTC) and counts as "on the policies" when that
# entry carries POLICY_A or POLICY_B.
MIN_STREAK = 72
STREAK_GAP = 6
MAX_GAP = 72

# Code bits stored per relay entry.
ALLOWS_22, ON_A, ON_B, BADEXIT = 1, 2, 4, 8
ON_POLICIES = ON_A | ON_B

CHART_DAYS = (dt.date(2026, 8, 4), dt.date(2026, 10, 9))
WORKERS_PER_ARCHIVE = 4


def allows_port(summary, port):
    """True when a consensus exit-policy summary ('accept 80,443' / 'reject 1-65535') permits port."""
    if not summary:
        return False                      # no "p" line: not an exit
    kind, _, spec = summary.partition(' ')
    hit = False
    for part in spec.split(','):
        lo, _, hi = part.partition('-')
        if int(lo) <= port <= int(hi or lo):
            hit = True
            break
    return hit if kind == 'accept' else not hit


def policy_code(summary):
    return (ALLOWS_22 if allows_port(summary, 22) else 0) | \
           (ON_A if summary == POLICY_A else 0) | (ON_B if summary == POLICY_B else 0)


def line_after(entry, key):
    i = entry.find(key)
    if i < 0:
        return b''
    i += len(key)
    j = entry.find(b'\n', i)
    return (entry[i:] if j < 0 else entry[i:j]).strip()


def parse_consensus(data, codes_cache):
    """Return (valid_after, [identity, ...], array of code bytes) for one consensus document."""
    head = b'\n' + data[:4096]
    if b'\nnetwork-status-version 3\n' not in head or b'\nvote-status consensus\n' not in head:
        raise ValueError('not an unflavored network-status consensus')
    va = line_after(head, b'\nvalid-after ').decode()
    end = data.find(b'\ndirectory-footer\n')
    start = data.find(b'\nr ')
    if end < 0 or start < 0 or start > end:
        raise ValueError('incomplete consensus (valid-after %s)' % va)
    ids, codes = [], array('B')
    for entry in data[start:end + 1].split(b'\nr ')[1:]:
        # "r nickname identity digest date time IP ORPort DirPort"
        sp1 = entry.index(b' ')
        ids.append(entry[sp1 + 1:entry.index(b' ', sp1 + 1)])
        pol = line_after(entry, b'\np ')
        c = codes_cache.get(pol)
        if c is None:
            c = codes_cache[pol] = policy_code(pol.decode())
        if b'BadExit' in line_after(entry, b'\ns '):
            c |= BADEXIT
        codes.append(c)
    return dt.datetime.strptime(va, '%Y-%m-%d %H:%M:%S'), ids, codes


def parse_task(task):
    """Parse one share of an archive (every n-th consensus) or one loose file.

    Returns (identity table, [(valid_after, local id bytes, code bytes), ...])."""
    kind, path, part, nparts = task
    table, rows, codes_cache = {}, [], {}

    def add(data):
        va, ids, codes = parse_consensus(data, codes_cache)
        if FIRST <= va <= LAST:
            loc = array('i', [table.setdefault(x, len(table)) for x in ids])
            rows.append((va, loc.tobytes(), codes.tobytes()))

    if kind == 'tar':
        k = 0
        with tarfile.open(path, 'r|xz') as tf:
            for m in tf:
                if not (m.isfile() and m.name.endswith('-consensus')):
                    continue
                if k % nparts == part:
                    add(tf.extractfile(m).read())
                k += 1
    else:
        with open(path, 'rb') as fh:
            add(fh.read())
    return list(table), rows


def load():
    archives = sorted(glob.glob(os.path.join(CACHE, 'consensuses-2026-*.tar.xz')))
    loose = sorted(glob.glob(os.path.join(CACHE, 'recent', '*-consensus')))
    if len(archives) < 3:
        raise SystemExit('cache/ is missing archives; run python3 fetch.py first')
    tasks = [('tar', a, i, WORKERS_PER_ARCHIVE) for a in archives for i in range(WORKERS_PER_ARCHIVE)]
    tasks += [('file', f, 0, 1) for f in loose]
    gid = {}
    by_hour = {}
    with ProcessPoolExecutor(max_workers=min(len(tasks), os.cpu_count() or 4)) as ex:
        for table, rows in ex.map(parse_task, tasks):
            remap = np.array([gid.setdefault(x, len(gid)) for x in table], dtype=np.int32)
            for va, loc, codes in rows:
                if va not in by_hour:          # archive copy wins over a recent/ duplicate
                    by_hour[va] = (remap[np.frombuffer(loc, dtype=np.int32)],
                                   np.frombuffer(codes, dtype=np.uint8))
    hours = sorted(by_hour)
    want, t = [], FIRST
    while t <= LAST:
        want.append(t)
        t += dt.timedelta(hours=1)
    missing = [x for x in want if x not in by_hour]
    if set(missing) - KNOWN_GAPS:
        raise SystemExit('unexpected consensus coverage; missing %s. Run python3 fetch.py'
                         % [x.strftime('%Y-%m-%d %H:%M') for x in missing[:10]])
    return hours, by_hour, len(gid)


def hstr(t):
    return t.strftime('%Y-%m-%d %H:%M')


def main():
    t0 = time.time()
    hours, by_hour, nrelays = load()
    print('parsed %d consensuses (%s to %s UTC), %d relays, in %.0f s'
          % (len(hours), hstr(hours[0]), hstr(hours[-1]), nrelays, time.time() - t0))
    os.makedirs(OUT, exist_ok=True)

    # ---- hourly counts on the two policies (exit-policies chart) -------------
    rows = []
    for t in hours:
        c = by_hour[t][1]
        a, b = int(((c & ON_A) > 0).sum()), int(((c & ON_B) > 0).sum())
        rows.append((t, a, b, a + b))
    with open(os.path.join(OUT, 'hourly_exit_policies.csv'), 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['valid_after_utc', 'relays_on_policy_A', 'relays_on_policy_B', 'total'])
        for t, a, b, n in rows:
            w.writerow([hstr(t), a, b, n])

    # ---- per-relay timelines --------------------------------------------------
    hoff = {t: int((t - FIRST).total_seconds()) // 3600 for t in hours}
    H = np.concatenate([np.full(len(by_hour[t][0]), hoff[t], dtype=np.int32) for t in hours])
    R = np.concatenate([by_hour[t][0] for t in hours])
    C = np.concatenate([by_hour[t][1] for t in hours])
    order = np.lexsort((H, R))
    H, R, C = H[order], R[order], C[order]
    starts = np.concatenate([[0], np.flatnonzero(np.diff(R)) + 1])
    ends = np.append(starts[1:], len(R))
    a22 = (C & ALLOWS_22) > 0
    some22 = np.maximum.reduceat(a22, starts)
    all22 = np.minimum.reduceat(a22, starts)
    anypol = np.maximum.reduceat((C & ON_POLICIES) > 0, starts)

    openings = []          # (hour offset, on_policies)
    new_badexit = []       # hour offsets at which a relay on A/B newly carries BadExit
    for k in np.flatnonzero((some22 & ~all22) | anypol):
        s, e = int(starts[k]), int(ends[k])
        ho = H[s:e].tolist()
        cd = C[s:e].tolist()
        st = None
        for i, c in enumerate(cd):
            if not c & ALLOWS_22:
                if st is None or cd[i - 1] & ALLOWS_22 or ho[i] - ho[i - 1] > STREAK_GAP:
                    st = ho[i]
                continue
            if st is not None and i > 0 and not cd[i - 1] & ALLOWS_22:
                if ho[i - 1] - st + 1 >= MIN_STREAK and ho[i] - ho[i - 1] <= MAX_GAP:
                    openings.append((ho[i], bool(c & ON_POLICIES)))
            st = None
        # BadExit assigned by the directory authorities to a relay while it was
        # on policy A or B: BadExit now, and not in the relay's previous entry
        # (or a relay first seen after the opening hour of the data, already flagged).
        for i, c in enumerate(cd):
            if c & ON_POLICIES and c & BADEXIT and ((i > 0 and not cd[i - 1] & BADEXIT) or (i == 0 and ho[0] > 0)):
                new_badexit.append(ho[i])

    def to_time(o):
        return FIRST + dt.timedelta(hours=o)

    daily, daily_pol, hourly_open = {}, {}, {}
    for o, onp in openings:
        d = to_time(o).date()
        daily[d] = daily.get(d, 0) + 1
        daily_pol[d] = daily_pol.get(d, 0) + onp
        hourly_open[o] = hourly_open.get(o, 0) + 1
    days = [CHART_DAYS[0] + dt.timedelta(days=i) for i in range((CHART_DAYS[1] - CHART_DAYS[0]).days + 1)]
    # Aug 1-3 cannot hold an opening (72 h of history needed); Oct 10 has only 4 hours of data.
    assert not any(d < CHART_DAYS[0] for d in daily)
    with open(os.path.join(OUT, 'daily_ssh_openings.csv'), 'w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['date_utc', 'openings_total', 'openings_on_policies'])
        for d in days:
            w.writerow([d.isoformat(), daily.get(d, 0), daily_pol.get(d, 0)])

    # ---- facts -----------------------------------------------------------------
    tot = np.array([r[3] for r in rows])
    nz = np.flatnonzero(tot)
    ipk = int(np.argmax(tot))
    first_a = next(r[0] for r in rows if r[1])
    first_b = next(r[0] for r in rows if r[2])
    after_last = next(r[0] for r in rows if r[0] > rows[nz[-1]][0])

    def span(a, b):
        return [d for d in days if a <= d <= b]

    base = span(dt.date(2026, 8, 4), dt.date(2026, 9, 30))
    wave = span(dt.date(2026, 10, 1), dt.date(2026, 10, 4))
    rest = span(dt.date(2026, 10, 5), dt.date(2026, 10, 9))
    busiest = max(hourly_open, key=lambda o: (hourly_open[o], -o))
    flag = min(new_badexit)
    facts = dict(
        data=dict(source='Tor CollecTor hourly network-status consensuses',
                  first_consensus_utc=hstr(hours[0]), last_consensus_utc=hstr(hours[-1]),
                  consensuses=len(hours), hours_without_a_consensus=sorted(hstr(t) for t in KNOWN_GAPS)),
        policies=dict(policy_A=POLICY_A, policy_B=POLICY_B,
                      policy_A_first_utc=hstr(first_a), policy_B_first_utc=hstr(first_b)),
        exit_policies_chart=dict(
            peak_relays=int(tot[ipk]), peak_utc=hstr(rows[ipk][0]),
            first_nonzero_utc=hstr(rows[nz[0]][0]), last_nonzero_utc=hstr(rows[nz[-1]][0]),
            first_zero_after_utc=hstr(after_last),
            nonzero_outside_first_to_last=int((tot[:nz[0]] > 0).sum() + (tot[nz[-1] + 1:] > 0).sum())),
        ssh_openings_chart=dict(
            opening_rule=dict(min_streak_hours=MIN_STREAK, streak_gap_hours=STREAK_GAP, max_gap_hours=MAX_GAP),
            days=len(days), first_day=days[0].isoformat(), last_day=days[-1].isoformat(),
            baseline_days=len(base), baseline_openings=sum(daily.get(d, 0) for d in base),
            baseline_openings_on_policies=sum(daily_pol.get(d, 0) for d in base),
            oct1_4_openings=sum(daily.get(d, 0) for d in wave),
            oct1_4_openings_on_policies=sum(daily_pol.get(d, 0) for d in wave),
            oct2_openings=daily.get(dt.date(2026, 10, 2), 0),
            oct5_9_openings=sum(daily.get(d, 0) for d in rest),
            busiest_hour_utc=hstr(to_time(busiest)), busiest_hour_openings=hourly_open[busiest],
            first_badexit_on_policies_utc=hstr(to_time(flag)),
            hours_from_policy_B_to_first_badexit=int((to_time(flag) - first_b).total_seconds() // 3600)),
    )
    with open(os.path.join(OUT, 'facts.json'), 'w') as fh:
        json.dump(facts, fh, indent=2)
        fh.write('\n')
    print(json.dumps(facts, indent=2))
    print('wrote out/hourly_exit_policies.csv, out/daily_ssh_openings.csv, out/facts.json in %.0f s'
          % (time.time() - t0))


if __name__ == '__main__':
    sys.exit(main())
