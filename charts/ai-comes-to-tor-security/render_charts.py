#!/usr/bin/env python3
"""Render responsive SVGs and high-resolution PNGs for the Tor version-status post.

Outputs two 100%-stacked share charts in desktop SVG (800px), mobile SVG (360px),
and high-resolution PNG (2400px wide for sharing and social metadata):
  - ai-tor-security-yearly-version-status-2017-2026.{svg,-mobile.svg,.png}
  - ai-tor-security-monthly-version-status-2026.{svg,-mobile.svg,.png}

Usage:
  python3 render_charts.py [--output-dir ../../site/blog/images]
"""
from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import PercentFormatter  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import blog_chart_style as style  # noqa: E402
import blog_display_numbers as fmt  # noqa: E402
from reconstruct import ANNUAL_SUMMARY, MONTHLY_2026_SUMMARY  # noqa: E402

STACK_ORDER = (
    ("obsolete", "Obsolete", style.PALETTE["closed_wait"]),
    ("unrecommended", "Unrecommended", style.PALETTE["hs_get"]),
    ("experimental", "Experimental", style.PALETTE["consensus"]),
    ("new_in_series", "New in series", style.PALETTE["begin_dir"]),
    ("unknown", "Unknown", style.PALETTE["mixed"]),
    ("recommended", "Recommended", style.PALETTE["written"]),
)

DESKTOP_INCHES = (style.MAIN_WIDTH / 72.0, 540.0 / 72.0)  # 800 x 540 pt
MOBILE_INCHES = (style.NARROW_WIDTH / 72.0, 540.0 / 72.0)  # 360 x 540 pt
PNG_DPI = 216  # 800/72 * 216 = 2400 px wide (high-res social & sharing PNG)


def exact_share(part: int, total: int) -> Fraction:
    return Fraction(100 * part, total)


def check_layout(fig, ax) -> None:
    """Fail if any chart text clips outside the canvas or overlaps another text."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    texts = []
    seen = set()
    candidates = [
        *fig.texts,
        *ax.texts,
        *ax.get_xticklabels(),
        *ax.get_yticklabels(),
        ax.xaxis.label,
        ax.yaxis.label,
    ]
    if ax.get_legend() is not None:
        candidates.extend(ax.get_legend().get_texts())
    for fig_leg in fig.legends:
        candidates.extend(fig_leg.get_texts())
    for item in candidates:
        if item is not None and item.get_text().strip() and id(item) not in seen:
            seen.add(id(item))
            texts.append(item)

    boxes = [item.get_window_extent(renderer) for item in texts]
    width, height = fig.bbox.width, fig.bbox.height
    for item, box in zip(texts, boxes):
        label = item.get_text().replace("\n", " / ")
        assert box.x0 >= 2 and box.y0 >= 2, (
            f"Text clipped near min edge: {label!r} -> {box}"
        )
        assert box.x1 <= width - 2 and box.y1 <= height - 2, (
            f"Text clipped near max edge: {label!r} -> {box} vs ({width}, {height})"
        )
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i].overlaps(boxes[j]):
                a = texts[i].get_text().replace("\n", " / ")
                b = texts[j].get_text().replace("\n", " / ")
                raise AssertionError(f"Overlapping text: {a!r} vs {b!r}")


def _render_desktop(
    *,
    rows: tuple[dict, ...],
    stem: str,
    title: str,
    subtitle: str,
    xlabel: str,
    ticks: list[str],
    output_dir: Path,
) -> dict:
    figsize = DESKTOP_INCHES
    width_inches = figsize[0]
    size = lambda role: style.points(
        role, width_inches, narrow=False, display_width=style.MAIN_WIDTH
    )

    fig = plt.figure(figsize=figsize, facecolor=style.PALETTE["background"])
    ax = fig.add_axes(
        [0.115, 0.175, 0.855, 0.515], facecolor=style.PALETTE["background"]
    )
    left_x = 0.045

    fig.text(
        left_x,
        0.955,
        title,
        fontsize=size("title"),
        fontweight="bold",
        color=style.PALETTE["text"],
        ha="left",
        va="top",
        linespacing=1.22,
    )
    fig.text(
        left_x,
        0.896,
        subtitle,
        fontsize=size("subtitle"),
        fontweight="normal",
        color=style.PALETTE["muted"],
        ha="left",
        va="top",
        linespacing=1.25,
    )

    handles = [
        Patch(facecolor=color, edgecolor="none", label=label)
        for _, label, color in STACK_ORDER
    ]
    fig.legend(
        handles=handles,
        ncol=3,
        loc="upper left",
        bbox_to_anchor=(left_x - 0.008, 0.844),
        frameon=False,
        handlelength=1.7,
        handletextpad=0.5,
        columnspacing=2.2,
        labelspacing=0.45,
        fontsize=size("legend"),
        labelcolor=style.PALETTE["text"],
    )

    x = np.arange(len(rows), dtype=float)
    bottom = np.zeros(len(rows), dtype=float)
    ax.axvspan(
        len(rows) - 1 - 0.46,
        len(rows) - 1 + 0.46,
        color=style.PALETTE["written"],
        alpha=0.06,
        zorder=0,
    )
    for key, _, color in STACK_ORDER:
        vals = np.array(
            [float(exact_share(row["sums"][key], row["sums"]["total"])) for row in rows],
            dtype=float,
        )
        ax.bar(
            x,
            vals,
            bottom=bottom,
            width=0.64,
            color=color,
            edgecolor="none",
            linewidth=0,
            zorder=3,
        )
        bottom += vals
    assert np.allclose(bottom, 100.0, rtol=0.0, atol=1e-9)

    obs_shares = [exact_share(r["sums"]["obsolete"], r["sums"]["total"]) for r in rows]
    rec_shares = [exact_share(r["sums"]["recommended"], r["sums"]["total"]) for r in rows]
    unr_shares = [exact_share(r["sums"]["unrecommended"], r["sums"]["total"]) for r in rows]
    for i, (obs_s, rec_s, unr_s) in enumerate(zip(obs_shares, rec_shares, unr_shares)):
        obs_f, rec_f, unr_f = float(obs_s), float(rec_s), float(unr_s)
        ax.text(
            i,
            100.0 - rec_f / 2.0,
            fmt.percentage(rec_s, boundaries=(100,)),
            ha="center",
            va="center",
            fontsize=size("annotation"),
            fontweight="bold",
            color=style.PALETTE["background"],
            zorder=5,
        )
        if obs_f >= 5.5:
            ax.text(
                i,
                obs_f / 2.0,
                fmt.percentage(obs_s, boundaries=(100,)),
                ha="center",
                va="center",
                fontsize=size("annotation"),
                fontweight="bold",
                color=style.PALETTE["background"],
                zorder=5,
            )
        if unr_f >= 7.5:
            ax.text(
                i,
                obs_f + unr_f / 2.0,
                fmt.percentage(unr_s, boundaries=(100,)),
                ha="center",
                va="center",
                fontsize=size("tick"),
                fontweight="bold",
                color=style.PALETTE["background"],
                zorder=5,
            )

    ax.set_xlim(-0.55, len(rows) - 0.45)
    ax.set_ylim(0, 100)
    ax.set_xticks(x)
    ax.set_xticklabels(ticks)
    last_tick = ax.get_xticklabels()[-1]
    last_tick.set_color(style.PALETTE["written"])
    last_tick.set_fontweight("bold")

    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_ylabel("Share of Running relay-hours", labelpad=10)
    ax.set_xlabel(xlabel, labelpad=10)

    style.style_axes(ax, narrow=False, display_width=style.MAIN_WIDTH, legend=False)
    ax.tick_params(colors=style.PALETTE["muted"], length=3.5)
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=style.PALETTE["grid"], linewidth=0.75, alpha=0.7)
    ax.grid(axis="x", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(style.PALETTE["axis"])
    ax.spines["bottom"].set_color(style.PALETTE["axis"])

    fig.text(
        left_x,
        0.024,
        "Source: 1aeo.com",
        fontsize=size("source"),
        color=style.PALETTE["muted"],
        ha="left",
        va="bottom",
    )

    check_layout(fig, ax)

    svg_path = output_dir / f"{stem}.svg"
    fig.savefig(
        svg_path,
        format="svg",
        facecolor=style.PALETTE["background"],
        metadata={"Date": None},
    )
    style.svg_font_fallback(svg_path)

    png_path = output_dir / f"{stem}.png"
    fig.savefig(
        png_path,
        format="png",
        dpi=PNG_DPI,
        facecolor=style.PALETTE["background"],
    )
    plt.close(fig)
    return {
        "desktop_svg": svg_path,
        "png": png_path,
        "png_px": (
            int(round(figsize[0] * PNG_DPI)),
            int(round(figsize[1] * PNG_DPI)),
        ),
        "svg_pt": (
            int(round(figsize[0] * 72)),
            int(round(figsize[1] * 72)),
        ),
    }


def _render_mobile(
    *,
    rows: tuple[dict, ...],
    stem: str,
    title: str,
    subtitle: str,
    xlabel: str,
    ticks: list[str],
    output_dir: Path,
    preview_dir: Path | None = None,
) -> dict:
    """Use horizontal 100%-stacked bars at 360px so period labels & values fit cleanly."""
    figsize = MOBILE_INCHES
    width_inches = figsize[0]
    size = lambda role: style.points(
        role, width_inches, narrow=True, display_width=style.NARROW_WIDTH
    )

    fig = plt.figure(figsize=figsize, facecolor=style.PALETTE["background"])
    ax = fig.add_axes(
        [0.235, 0.150, 0.690, 0.495], facecolor=style.PALETTE["background"]
    )
    left_x = 0.045

    fig.text(
        left_x,
        0.968,
        title,
        fontsize=size("title"),
        fontweight="bold",
        color=style.PALETTE["text"],
        ha="left",
        va="top",
        linespacing=1.22,
    )
    fig.text(
        left_x,
        0.862,
        subtitle,
        fontsize=size("subtitle"),
        fontweight="normal",
        color=style.PALETTE["muted"],
        ha="left",
        va="top",
        linespacing=1.25,
    )

    handles = [
        Patch(facecolor=color, edgecolor="none", label=label)
        for _, label, color in STACK_ORDER
    ]
    fig.legend(
        handles=handles,
        ncol=2,
        loc="upper left",
        bbox_to_anchor=(0.025, 0.790),
        frameon=False,
        handlelength=1.15,
        handletextpad=0.4,
        columnspacing=0.65,
        labelspacing=0.28,
        fontsize=size("legend"),
        labelcolor=style.PALETTE["text"],
    )

    y = np.arange(len(rows), dtype=float)
    left = np.zeros(len(rows), dtype=float)
    ax.axhspan(
        len(rows) - 1 - 0.46,
        len(rows) - 1 + 0.46,
        color=style.PALETTE["written"],
        alpha=0.06,
        zorder=0,
    )
    for key, _, color in STACK_ORDER:
        vals = np.array(
            [float(exact_share(row["sums"][key], row["sums"]["total"])) for row in rows],
            dtype=float,
        )
        ax.barh(
            y,
            vals,
            left=left,
            height=0.66,
            color=color,
            edgecolor="none",
            linewidth=0,
            zorder=3,
        )
        left += vals
    assert np.allclose(left, 100.0, rtol=0.0, atol=1e-9)

    obs_shares = [exact_share(r["sums"]["obsolete"], r["sums"]["total"]) for r in rows]
    rec_shares = [exact_share(r["sums"]["recommended"], r["sums"]["total"]) for r in rows]
    unr_shares = [exact_share(r["sums"]["unrecommended"], r["sums"]["total"]) for r in rows]
    label_fs = size("annotation")
    for i, (obs_s, rec_s, unr_s) in enumerate(zip(obs_shares, rec_shares, unr_shares)):
        obs_f, rec_f, unr_f = float(obs_s), float(rec_s), float(unr_s)
        ax.text(
            100.0 - rec_f / 2.0,
            i,
            fmt.percentage(rec_s, boundaries=(100,)),
            ha="center",
            va="center",
            fontsize=label_fs,
            fontweight="bold",
            color=style.PALETTE["background"],
            zorder=5,
        )
        if obs_f >= 14.0:
            ax.text(
                obs_f / 2.0,
                i,
                fmt.percentage(obs_s, boundaries=(100,)),
                ha="center",
                va="center",
                fontsize=label_fs,
                fontweight="bold",
                color=style.PALETTE["background"],
                zorder=5,
            )
        if unr_f >= 15.0:
            ax.text(
                obs_f + unr_f / 2.0,
                i,
                fmt.percentage(unr_s, boundaries=(100,)),
                ha="center",
                va="center",
                fontsize=label_fs,
                fontweight="bold",
                color=style.PALETTE["background"],
                zorder=5,
            )

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.55, len(rows) - 0.45)
    ax.invert_yaxis()
    ax.set_yticks(y)
    ax.set_yticklabels(ticks)
    last_tick = ax.get_yticklabels()[-1]
    last_tick.set_color(style.PALETTE["written"])
    last_tick.set_fontweight("bold")

    ax.set_xticks([0, 20, 40, 60, 80, 100])
    ax.xaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=0))
    ax.set_xlabel(xlabel, labelpad=8)

    style.style_axes(ax, narrow=True, display_width=style.NARROW_WIDTH, legend=False)
    ax.tick_params(colors=style.PALETTE["muted"], length=3.0)
    # Show every second x-tick on 360px if dense, otherwise 0/25/50/75/100 cleanly
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=style.PALETTE["grid"], linewidth=0.75, alpha=0.7)
    ax.grid(axis="y", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(style.PALETTE["axis"])
    ax.spines["bottom"].set_color(style.PALETTE["axis"])

    fig.text(
        left_x,
        0.022,
        "Source: 1aeo.com",
        fontsize=size("source"),
        color=style.PALETTE["muted"],
        ha="left",
        va="bottom",
    )

    check_layout(fig, ax)

    svg_path = output_dir / f"{stem}-mobile.svg"
    fig.savefig(
        svg_path,
        format="svg",
        facecolor=style.PALETTE["background"],
        metadata={"Date": None},
    )
    style.svg_font_fallback(svg_path)
    if preview_dir is not None:
        preview_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(
            preview_dir / f"{stem}-mobile-preview.png",
            format="png",
            dpi=200,
            facecolor=style.PALETTE["background"],
        )
    plt.close(fig)
    return {
        "mobile_svg": svg_path,
        "mobile_svg_pt": (
            int(round(figsize[0] * 72)),
            int(round(figsize[1] * 72)),
        ),
    }


def render_all(output_dir: Path, preview_dir: Path | None = None) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    style.configure(matplotlib)

    annual_ticks_desktop = [
        f"{r['year']}\nYTD" if r["partial"] else str(r["year"])
        for r in ANNUAL_SUMMARY
    ]
    annual_ticks_mobile = [
        "2026 YTD" if r["partial"] else str(r["year"]) for r in ANNUAL_SUMMARY
    ]
    monthly_ticks_desktop = [
        "Apr*" if r["month_number"] == 4 else ("Oct\nMTD" if r["partial"] else r["label"])
        for r in MONTHLY_2026_SUMMARY
    ]
    monthly_ticks_mobile = [
        "Apr*" if r["month_number"] == 4 else ("Oct MTD" if r["partial"] else r["label"])
        for r in MONTHLY_2026_SUMMARY
    ]

    matplotlib.rcParams["svg.hashsalt"] = "1aeo-yearly-version-status"
    yearly = {
        **_render_desktop(
            rows=ANNUAL_SUMMARY,
            stem="ai-tor-security-yearly-version-status-2017-2026",
            title="Running Tor relay version-status shares, 2017–2026",
            subtitle="Obsolete versions reached 15% of Running relay-hours in 2026 YTD, up from 6% in 2025",
            xlabel="Calendar year (UTC); 2026 is year-to-date through Oct 16, 22:00 UTC",
            ticks=annual_ticks_desktop,
            output_dir=output_dir,
        ),
        **_render_mobile(
            rows=ANNUAL_SUMMARY,
            stem="ai-tor-security-yearly-version-status-2017-2026",
            title="Running Tor relay version-status\nshares, 2017–2026",
            subtitle="Obsolete share rose from 6% in 2025 to\n15% in 2026 YTD",
            xlabel="Share of Running relay-hours",
            ticks=annual_ticks_mobile,
            output_dir=output_dir,
            preview_dir=preview_dir,
        ),
    }

    matplotlib.rcParams["svg.hashsalt"] = "1aeo-monthly-version-status"
    monthly = {
        **_render_desktop(
            rows=MONTHLY_2026_SUMMARY,
            stem="ai-tor-security-monthly-version-status-2026",
            title="Monthly Running Tor relay version-status shares, 2026",
            subtitle="Obsolete share jumped from 7% in August to 29% in September; October MTD is 24%",
            xlabel="Calendar month in 2026 (UTC); Oct is month-to-date; Apr* has 36% coverage",
            ticks=monthly_ticks_desktop,
            output_dir=output_dir,
        ),
        **_render_mobile(
            rows=MONTHLY_2026_SUMMARY,
            stem="ai-tor-security-monthly-version-status-2026",
            title="Monthly Running Tor relay\nversion-status shares, 2026",
            subtitle="Obsolete share jumped from 7% in Aug\nto 29% in Sep; Oct MTD is 24%",
            xlabel="Share of Running relay-hours",
            ticks=monthly_ticks_mobile,
            output_dir=output_dir,
            preview_dir=preview_dir,
        ),
    }
    return [yearly, monthly]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default_out = HERE.parents[1] / "site" / "blog" / "images"
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_out,
        help="Destination directory for rendered SVGs and PNGs",
    )
    parser.add_argument(
        "--preview-dir",
        type=Path,
        default=None,
        help="Optional directory for temporary mobile PNG previews during review",
    )
    args = parser.parse_args()
    results = render_all(args.output_dir.resolve(), preview_dir=args.preview_dir)
    for item in results:
        print({k: (str(v) if isinstance(v, Path) else v) for k, v in item.items()})


if __name__ == "__main__":
    main()
