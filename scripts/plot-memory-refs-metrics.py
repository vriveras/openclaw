#!/usr/bin/env python3
"""Plot memory refs metrics from a report JSON.

No external deps: uses only the Python stdlib.
Writes simple SVG bar charts next to the report.

Usage:
  python3 scripts/plot-memory-refs-metrics.py memory/metrics/<report>.json
"""

import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape


def _svg_bar_chart(title, labels, series, colors, y_label, out_path: Path):
    # series: list of (name, values)
    assert len(series) == len(colors)

    w, h = 1400, 520
    pad_l, pad_r, pad_t, pad_b = 80, 40, 60, 140
    plot_w = w - pad_l - pad_r
    plot_h = h - pad_t - pad_b

    max_val = max(max(vals) for _, vals in series) if series else 1
    max_val = max_val * 1.1 if max_val > 0 else 1

    n = len(labels)
    if n == 0:
        out_path.write_text("<svg xmlns='http://www.w3.org/2000/svg' width='200' height='50'></svg>")
        return

    group_w = plot_w / n
    bar_w = group_w / (len(series) + 1)

    def y(v):
        return pad_t + plot_h - (v / max_val) * plot_h

    def x(i, s_idx):
        return pad_l + i * group_w + (s_idx + 0.5) * bar_w

    parts = []
    parts.append(f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>")
    parts.append("<rect x='0' y='0' width='100%' height='100%' fill='#0b1220' />")

    # Title
    parts.append(f"<text x='{pad_l}' y='32' fill='#e5e7eb' font-family='ui-sans-serif,system-ui' font-size='20' font-weight='600'>{escape(title)}</text>")

    # Axes
    parts.append(f"<line x1='{pad_l}' y1='{pad_t}' x2='{pad_l}' y2='{pad_t+plot_h}' stroke='#94a3b8' stroke-width='2' />")
    parts.append(f"<line x1='{pad_l}' y1='{pad_t+plot_h}' x2='{pad_l+plot_w}' y2='{pad_t+plot_h}' stroke='#94a3b8' stroke-width='2' />")

    # Y label
    parts.append(f"<text x='16' y='{pad_t+plot_h/2}' fill='#cbd5e1' font-family='ui-sans-serif,system-ui' font-size='14' transform='rotate(-90 16 {pad_t+plot_h/2})'>{escape(y_label)}</text>")

    # Y ticks
    for t in range(6):
        v = max_val * t / 5
        yy = y(v)
        parts.append(f"<line x1='{pad_l-6}' y1='{yy}' x2='{pad_l}' y2='{yy}' stroke='#94a3b8' />")
        parts.append(f"<text x='{pad_l-10}' y='{yy+4}' fill='#cbd5e1' font-family='ui-sans-serif,system-ui' font-size='12' text-anchor='end'>{int(v)}</text>")

    # Bars
    for i, lab in enumerate(labels):
        # x label
        lx = pad_l + i * group_w + group_w / 2
        parts.append(
            f"<text x='{lx}' y='{pad_t+plot_h+22}' fill='#cbd5e1' font-family='ui-sans-serif,system-ui' font-size='12' text-anchor='middle' transform='rotate(35 {lx} {pad_t+plot_h+22})'>{escape(lab)}</text>"
        )

        for s_idx, ((name, vals), color) in enumerate(zip(series, colors)):
            v = vals[i]
            bx = x(i, s_idx)
            by = y(v)
            bh = pad_t + plot_h - by
            parts.append(f"<rect x='{bx}' y='{by}' width='{bar_w*0.8}' height='{bh}' fill='{color}' />")

    # Legend
    leg_x = pad_l
    leg_y = h - 60
    for idx, ((name, _), color) in enumerate(zip(series, colors)):
        x0 = leg_x + idx * 260
        parts.append(f"<rect x='{x0}' y='{leg_y}' width='14' height='14' fill='{color}' />")
        parts.append(f"<text x='{x0+20}' y='{leg_y+12}' fill='#e5e7eb' font-family='ui-sans-serif,system-ui' font-size='13'>{escape(name)}</text>")

    parts.append("</svg>")
    out_path.write_text("\n".join(parts))


def main():
    if len(sys.argv) != 2:
        print("usage: plot-memory-refs-metrics.py <report.json>")
        return 2

    report_path = Path(sys.argv[1])
    data = json.loads(report_path.read_text())

    # Support both legacy report shape (top-level cases) and suite-based reports.
    if "cases" in data:
        suites = [(data.get("label") or "report", data["cases"])]
    else:
        suites = []
        for s in data.get("suites", []):
            if isinstance(s, dict) and isinstance(s.get("cases"), list):
                suites.append((s.get("label", "suite"), s["cases"]))

    if not suites:
        raise KeyError("No cases found (expected data.cases or data.suites[].cases)")

    out_dir = report_path.parent

    # Pick the default suite for per-case charts (usually the first),
    # and optionally overlay recursive(best) if present.
    default_label, default_cases = suites[0]
    overlay = None
    for lab, cs in suites:
        if "recursive" in lab:
            overlay = (lab, cs)
            break

    cases = default_cases
    labels = [c["id"] for c in cases]
    baseline = [c["sizes"]["baseline"]["tokens"] for c in cases]
    refs = [c["sizes"]["refs"]["tokens"] for c in cases]
    expand = [c["sizes"]["expanded"]["tokens"] for c in cases]

    recursive = [0 for _ in cases]
    latency_recursive = [0 for _ in cases]
    if overlay:
        _, overlay_cases = overlay
        by_id = {c["id"]: c for c in overlay_cases}
        for i, cid in enumerate(labels):
            oc = by_id.get(cid)
            if oc:
                rr = oc.get("sizes", {}).get("recursiveRefs")
                recursive[i] = rr.get("tokens", 0) if rr else 0
                latency_recursive[i] = oc.get("latencyMs", {}).get("recursiveRefs", 0) or 0

    refs_count = [c["counts"]["refsReturned"] for c in cases]
    expand_count = [c["counts"]["expandedRequested"] for c in cases]

    # out_dir set above

    series1 = [
        ("baseline (memory_search)", baseline),
        ("refs (memory_search_refs)", refs),
        ("expand(top2) (memory_expand)", expand),
    ]
    colors1 = ["#60a5fa", "#a78bfa", "#34d399"]
    if any(v > 0 for v in recursive):
        series1.append(("recursive(best)", recursive))
        colors1.append("#fbbf24")

    out1 = out_dir / (report_path.stem + "-tokens.svg")
    _svg_bar_chart(
        title="Token Cost: baseline vs refs-first vs expansion" + (" vs recursive" if any(v > 0 for v in recursive) else ""),
        labels=labels,
        series=series1,
        colors=colors1,
        y_label="Approx tokens (chars/4)",
        out_path=out1,
    )

    out2 = out_dir / (report_path.stem + "-expansion-counts.svg")
    _svg_bar_chart(
        title="Retrieval: refs returned vs expanded",
        labels=labels,
        series=[("refs returned", refs_count), ("refs expanded", expand_count)],
        colors=["#93c5fd", "#fbbf24"],
        y_label="Count",
        out_path=out2,
    )

    # Latency chart (ms)
    latency_baseline = [c.get("latencyMs", {}).get("baseline", 0) for c in cases]
    latency_refs = [c.get("latencyMs", {}).get("refs", 0) for c in cases]
    latency_expand = [c.get("latencyMs", {}).get("expand", 0) for c in cases]
    latency_total = [c.get("latencyMs", {}).get("total", 0) for c in cases]
    latency_recursive = [
        c.get("latencyMs", {}).get("recursiveRefs", 0) if c.get("latencyMs", {}).get("recursiveRefs") is not None else 0
        for c in cases
    ]

    series3 = [
        ("baseline", latency_baseline),
        ("refs", latency_refs),
        ("expand", latency_expand),
        ("total", latency_total),
    ]
    colors3 = ["#60a5fa", "#a78bfa", "#34d399", "#f87171"]
    if any(v > 0 for v in latency_recursive):
        series3.append(("recursive", latency_recursive))
        colors3.append("#fbbf24")

    out3 = out_dir / (report_path.stem + "-latency.svg")
    _svg_bar_chart(
        title="Latency per stage (ms)" + (" + recursive" if any(v > 0 for v in latency_recursive) else ""),
        labels=labels,
        series=series3,
        colors=colors3,
        y_label="Milliseconds",
        out_path=out3,
    )

    print(f"Wrote: {out1}")
    print(f"Wrote: {out2}")
    print(f"Wrote: {out3}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
