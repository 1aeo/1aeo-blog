#!/usr/bin/env python3
"""Download the Tor consensus archives behind both charts into ./cache/.

Usage:  python3 fetch.py

Source: Tor Project CollecTor, https://collector.torproject.org/
  archive/relay-descriptors/consensuses/consensuses-2026-{08,09,10}.tar.xz
  recent/relay-descriptors/consensuses/<hour>-consensus (only for hours the
  October archive does not contain yet)

Every file is checked against the size and SHA-256 digest that CollecTor
publishes in its index (index/index.json.xz). Each archive is then read end to
end, which also checks the xz integrity checks, to confirm it holds every hourly
consensus from 2026-08-01 00:00 to 2026-10-10 03:00 UTC. Files already in
./cache/ that match the index are not downloaded again. CollecTor rebuilds the
archive for the current month as new hours arrive, so an older cached copy of
that archive is replaced. Standard library only.
"""
import base64
import datetime as dt
import hashlib
import json
import lzma
import os
import sys
import tarfile
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, 'cache')
RECENT = os.path.join(CACHE, 'recent')
MANIFEST = os.path.join(CACHE, 'manifest.json')

BASE = 'https://collector.torproject.org'
INDEX_URL = BASE + '/index/index.json.xz'
ARCHIVE_PATH = 'archive/relay-descriptors/consensuses'
RECENT_PATH = 'recent/relay-descriptors/consensuses'
ARCHIVES = ['consensuses-2026-08.tar.xz', 'consensuses-2026-09.tar.xz', 'consensuses-2026-10.tar.xz']

FIRST = dt.datetime(2026, 8, 1, 0)    # first consensus used (UTC valid-after hour)
LAST = dt.datetime(2026, 10, 10, 3)   # last consensus used
# CollecTor has no consensus for this hour (the Tor network did not publish one
# that it archived); both charts are built without it.
KNOWN_GAPS = {dt.datetime(2026, 10, 1, 19)}

USER_AGENT = 'tor-relay-intrusions-oct-2026-charts/1.0 (python urllib)'


def needed_hours():
    hours, t = [], FIRST
    while t <= LAST:
        if t not in KNOWN_GAPS:
            hours.append(t)
        t += dt.timedelta(hours=1)
    return hours


def hour_from_name(name):
    """'.../2026-10-04-04-00-00-consensus' -> datetime, or None."""
    base = os.path.basename(name)
    if not base.endswith('-consensus'):
        return None
    try:
        return dt.datetime.strptime(base[:19], '%Y-%m-%d-%H-%M-%S')
    except ValueError:
        return None


def sha256_b64(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return base64.b64encode(h.digest()).decode()


def download(url, dest, expect_size=None, expect_sha=None, tries=3):
    """Stream url to dest via a .part file; replace dest only after all checks pass."""
    part = dest + '.part'
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp, open(part, 'wb') as out:
                length = resp.headers.get('Content-Length')
                got = 0
                for chunk in iter(lambda: resp.read(1 << 20), b''):
                    out.write(chunk)
                    got += len(chunk)
            if length is not None and got != int(length):
                raise IOError('truncated: got %d of %s bytes' % (got, length))
            if expect_size is not None and got != expect_size:
                raise IOError('size %d does not match the CollecTor index (%d)' % (got, expect_size))
            if expect_sha is not None and sha256_b64(part) != expect_sha:
                raise IOError('SHA-256 does not match the CollecTor index')
            os.replace(part, dest)
            return got
        except Exception as exc:  # network errors, truncation, digest mismatch
            if os.path.exists(part):
                os.remove(part)
            if attempt == tries:
                raise SystemExit('download failed: %s (%s)' % (url, exc))
            print('  retrying %s after error: %s' % (os.path.basename(url), exc))
            time.sleep(5 * attempt)


def load_index():
    path = os.path.join(CACHE, 'index.json.xz')
    try:
        download(INDEX_URL, path)
    except SystemExit as exc:
        if not os.path.exists(path):
            raise
        print('warning: could not refresh the CollecTor index (%s); using the cached copy' % exc)
    index = json.loads(lzma.decompress(open(path, 'rb').read()))

    def listing(path):
        node = index
        for part in path.split('/'):
            node = next((d for d in node.get('directories', []) if d['path'] == part), None)
            if node is None:
                return {}
        return {f['path']: f for f in node.get('files', [])}

    return listing(ARCHIVE_PATH), listing(RECENT_PATH), index.get('index_created', '?')


def scan_archive(path):
    """Read a .tar.xz end to end; return the consensus hours it contains."""
    hours = []
    with tarfile.open(path, 'r|xz') as tf:
        for m in tf:
            if m.isfile():
                t = hour_from_name(m.name)
                data = tf.extractfile(m).read()
                if t is not None:
                    if b'\ndirectory-footer\n' not in data:
                        raise IOError('%s: incomplete consensus %s' % (path, m.name))
                    hours.append(t.strftime('%Y-%m-%d %H:%M'))
    return sorted(hours)


def main():
    t0 = time.time()
    os.makedirs(CACHE, exist_ok=True)
    archives, recent, created = load_index()
    print('CollecTor index created %s UTC' % created)

    # 1. monthly archives
    for name in ARCHIVES:
        dest = os.path.join(CACHE, name)
        entry = archives.get(name)
        if entry is None:
            raise SystemExit('%s is not listed in the CollecTor index' % name)
        if os.path.exists(dest):
            if os.path.getsize(dest) == entry['size'] and sha256_b64(dest) == entry['sha256']:
                print('%-28s present, matches index (%.1f MB)' % (name, entry['size'] / 1e6))
                continue
            print('%-28s cached copy differs from the index (changed on CollecTor or incomplete locally); downloading again' % name)
        else:
            print('%-28s downloading %.1f MB ...' % (name, entry['size'] / 1e6))
        download('%s/%s/%s' % (BASE, ARCHIVE_PATH, name), dest, entry['size'], entry['sha256'])
        print('%-28s ok, size and SHA-256 match index' % name)

    # 2. read every archive end to end and list the hours it holds (cached by digest)
    try:
        manifest = json.load(open(MANIFEST))
    except (OSError, ValueError):
        manifest = {}
    todo = [n for n in ARCHIVES if manifest.get(n, {}).get('sha256') != archives[n]['sha256']]
    if todo:
        print('reading %d archive(s) end to end ...' % len(todo))
        with ProcessPoolExecutor(max_workers=len(todo)) as ex:
            for n, hours in zip(todo, ex.map(scan_archive, [os.path.join(CACHE, n) for n in todo])):
                manifest[n] = dict(sha256=archives[n]['sha256'], size=archives[n]['size'], hours=hours)
    have = set()
    for n in ARCHIVES:
        have.update(manifest[n]['hours'])

    # 3. hours the archives do not hold yet: fetch them from CollecTor's recent/ folder
    missing = [t for t in needed_hours() if t.strftime('%Y-%m-%d %H:%M') not in have]
    if missing:
        os.makedirs(RECENT, exist_ok=True)
    for t in missing:
        name = t.strftime('%Y-%m-%d-%H-%M-%S') + '-consensus'
        dest = os.path.join(RECENT, name)
        entry = recent.get(name)
        if os.path.exists(dest) and (entry is None or sha256_b64(dest) == entry['sha256']):
            data = open(dest, 'rb').read()
        elif entry is not None:
            print('%-28s downloading from recent/ ...' % name)
            download('%s/%s/%s' % (BASE, RECENT_PATH, name), dest, entry['size'], entry['sha256'])
            data = open(dest, 'rb').read()
        else:
            continue
        if b'\ndirectory-footer\n' not in data:
            raise SystemExit('%s is incomplete' % dest)
        have.add(t.strftime('%Y-%m-%d %H:%M'))
    manifest['recent'] = sorted(h for h in have if not any(h in manifest[n]['hours'] for n in ARCHIVES))
    with open(MANIFEST, 'w') as fh:
        json.dump(manifest, fh, indent=1)

    # 4. coverage report
    still = [t for t in needed_hours() if t.strftime('%Y-%m-%d %H:%M') not in have]
    extra = [t for t in KNOWN_GAPS if t.strftime('%Y-%m-%d %H:%M') in have]
    print('hourly consensuses %s to %s UTC: %d of %d present (CollecTor has no consensus for %s)'
          % (FIRST.strftime('%Y-%m-%d %H:%M'), LAST.strftime('%Y-%m-%d %H:%M'),
             len(needed_hours()) - len(still), len(needed_hours()),
             ', '.join(sorted(t.strftime('%Y-%m-%d %H:%M') for t in KNOWN_GAPS))))
    if extra:
        print('note: CollecTor now has a consensus for an hour that was missing when the charts were made; '
              'series.py will include it and the published numbers may shift slightly')
    if still:
        raise SystemExit('missing %d hour(s), e.g. %s; try again later'
                         % (len(still), ', '.join(t.strftime('%Y-%m-%d %H:%M') for t in still[:5])))
    print('done in %.0f s; next: python3 series.py' % (time.time() - t0))


if __name__ == '__main__':
    sys.exit(main())
