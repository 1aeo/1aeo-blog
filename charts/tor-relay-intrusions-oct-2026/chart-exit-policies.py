#!/usr/bin/env python3
"""Chart: relays per hourly Tor consensus on the intruders' two exit policies.

Usage:  python3 chart-exit-policies.py        (after python3 series.py)
Reads out/hourly_exit_policies.csv, writes png/tor-relay-intrusions-oct-2026-chart-exit-policies.png.
Every number printed on the chart is asserted against the data first.
"""
import csv
import datetime as dt
import os

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HOURLY = os.path.join(HERE, 'out', 'hourly_exit_policies.csv')
OUT = os.path.join(HERE, 'png', 'tor-relay-intrusions-oct-2026-chart-exit-policies.png')

BG, GRID, SPINE, TITLE, SUB = '#1e1e1e', '#333333', '#555555', '#e6e6e6', '#9a9a9a'
RED, GREEN = '#ff6b6b', '#00ff7f'
plt.rcParams.update({'font.family': 'DejaVu Sans'})

with open(HOURLY, newline='') as fh:
    rows = list(csv.DictReader(fh))
t = np.array([dt.datetime.strptime(r['valid_after_utc'], '%Y-%m-%d %H:%M') for r in rows])
y = np.array([int(r['total']) for r in rows])          # relays on policy A or B
T0, T1 = dt.datetime(2026, 9, 30), dt.datetime(2026, 10, 10, 3)
m = (t >= T0) & (t <= T1)
t, y = t[m], y[m]

# facts asserted from the data
ipk = int(np.argmax(y))
PEAK, PEAK_T = int(y[ipk]), t[ipk]
assert PEAK == 353 and PEAK_T == dt.datetime(2026, 10, 4, 4)
nz = np.nonzero(y)[0]
FIRST, LAST = t[nz[0]], t[nz[-1]]
assert FIRST == dt.datetime(2026, 10, 1, 15) and LAST == dt.datetime(2026, 10, 5, 16)
assert (y[t > LAST] == 0).all() and (y[t < FIRST] == 0).all()
NONE_LEFT = LAST + dt.timedelta(hours=1)           # first consensus with zero: Oct 5 17:00
assert NONE_LEFT in set(t) and y[list(t).index(NONE_LEFT)] == 0
# Tor Project notice on the Tor forum, posted 2026-10-05 17:50:10 UTC:
# https://forum.torproject.org/t/tor-relays-security-incident-affecting-some-relay-operators/22231
WARN = dt.datetime(2026, 10, 5, 17, 50)


def day_label(x, pos=None):
    """'Oct 1' style tick label (portable version of strftime '%b %-d')."""
    d = mdates.num2date(x)
    return d.strftime('%b ') + str(d.day)


fig = plt.figure(figsize=(10.4, 5.6), dpi=200, facecolor=BG)
ax = fig.add_axes([0.085, 0.10, 0.895, 0.68], facecolor=BG)
for s in ('top', 'right'):
    ax.spines[s].set_visible(False)
for s in ('left', 'bottom'):
    ax.spines[s].set_color(SPINE)
ax.grid(axis='y', color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.tick_params(colors=SUB, labelsize=11, length=3.5)

ax.fill_between(t, y, step='post', color=RED, linewidth=0, zorder=3)
# green zero line where no relay ran the policies
z1 = t <= FIRST
z2 = t >= NONE_LEFT
ax.plot(t[z1], np.zeros(z1.sum()), color=GREEN, linewidth=3.2, zorder=4, solid_capstyle='butt')
ax.plot(t[z2], np.zeros(z2.sum()), color=GREEN, linewidth=3.2, zorder=4, solid_capstyle='butt')

ax.set_xlim(T0, T1)
ax.set_ylim(0, 420)
ax.set_yticks([0, 100, 200, 300, 400])
ax.xaxis.set_major_locator(mdates.DayLocator())
ax.xaxis.set_major_formatter(mticker.FuncFormatter(day_label))
ax.set_ylabel("relays on the intruders' exit policies", color=SUB, fontsize=11, labelpad=8)

# three labels only
ax.text(dt.datetime(2026, 9, 30, 4), 22, 'none before\nOct 1', color=GREEN, fontsize=12,
        ha='left', va='bottom', linespacing=1.25, zorder=5)
ax.annotate('Oct 4: %d relays' % PEAK, xy=(PEAK_T, PEAK), xytext=(PEAK_T, 392), color=RED, fontsize=13,
            fontweight='bold', ha='center', va='bottom', zorder=5,
            arrowprops=dict(arrowstyle='-', color=RED, lw=1.2, shrinkA=2, shrinkB=2))
ax.axvline(WARN, color=SUB, linestyle=(0, (4, 3)), linewidth=1.1, ymax=0.62, zorder=4)
ax.text(WARN + dt.timedelta(hours=5), 238, 'Oct 5, 17:00 UTC: none left', color=GREEN, fontsize=12.5,
        fontweight='bold', ha='left', va='bottom', zorder=5)
ax.text(WARN + dt.timedelta(hours=5), 205, 'Tor Project warning at 17:50 UTC', color=SUB, fontsize=11.5,
        ha='left', va='bottom', zorder=5)

L = ax.get_position().x0
fig.text(L, 0.955, "Zero, then 353, then zero: relays running the intruders' exit policies",
         color=TITLE, fontsize=15, fontweight='bold', ha='left', va='top')
fig.text(L, 0.885, "Relays per hourly Tor consensus advertising either of two exit policies the intruders wrote. Both open SSH\n"
         "(port 22), so the relays could intercept SSH logins made through Tor and steal the credentials.",
         color=SUB, fontsize=11, ha='left', va='top', linespacing=1.35)
fig.text(0.015, 0.012, "Source: Tor CollecTor consensus archives, Sep 30 to Oct 10, 2026 (UTC).",
         color=SUB, fontsize=11, ha='left', va='bottom')
fig.text(0.985, 0.012, 'Produced by 1AEO', color=SUB, fontsize=11, ha='right', va='bottom')

# layout checks: nothing clipped, no overlapping text
fig.canvas.draw()
rnd = fig.canvas.get_renderer()
texts = [x for x in fig.texts + ax.texts + ax.get_xticklabels() + ax.get_yticklabels() + [ax.yaxis.label] if x.get_text()]
texts = list({id(x): x for x in texts}.values())
bbs = [x.get_window_extent(rnd) for x in texts]
W, H = fig.bbox.width, fig.bbox.height
for x, bb in zip(texts, bbs):
    assert bb.x0 >= 4 and bb.y0 >= 4 and bb.x1 <= W - 4 and bb.y1 <= H - 4, ('clipped', x.get_text())
for i in range(len(bbs)):
    for j in range(i + 1, len(bbs)):
        assert not bbs[i].overlaps(bbs[j]), ('overlap', texts[i].get_text()[:30], texts[j].get_text()[:30])
lbl = [x for x in ax.texts if x.get_text().startswith('none before')][0].get_window_extent(rnd)
assert lbl.x1 < ax.transData.transform((mdates.date2num(FIRST), 0))[0] - 8, 'label hits bars'
os.makedirs(os.path.dirname(OUT), exist_ok=True)
fig.savefig(OUT, dpi=200, facecolor=BG)
print('wrote', os.path.relpath(OUT, HERE), '| peak', PEAK, PEAK_T, '| first', FIRST, '| none left', NONE_LEFT)
