#!/usr/bin/env python3
"""Digitize one Appendix B plot of NASA/TP-2015-216046 (DIGITIZED data, not original measurements).

Pipeline (every step is recorded in the calibration/digitization record):
  1. Extract the embedded JPEG of the figure page with `pdfimages -j` (bytes unchanged; SHA-256 recorded).
  2. Axis calibration.  Major tick marks are found automatically on each axis edge as the longest inward
     runs of dark pixels next to the frame line given in the config; their pixel centres are paired, in
     pixel order, with the tick-label values a human reader typed into the config.  A least-squares line
     value = a + b * pixel is fitted per axis; residuals at the ticks are reported (they measure tick
     placement/detection error, not data uncertainty).  The run fails if the number of detected major ticks
     differs from the number of labels.
  3. Marker detection.  Markers are open circles.  For each series colour a per-pixel colour score is
     computed (e.g. red: R - max(G, B), clipped at 0) and correlated with a zero-mean ring kernel of the
     measured marker radius.  Local maxima above a threshold, at least MIN_SEP px apart, are taken as marker
     centres.  Regions listed in exclude_px (legend) are ignored.
  3b. Up to PASSES passes: after each pass, pixels on the rings of accepted centres are blanked and the
      detection is repeated on what is left (finds markers suppressed next to stronger neighbours).
  4. Self-check.  A ring is redrawn at each detected centre; the script reports the fraction of coloured
     pixels covered by redrawn rings ("recall") and the fraction of redrawn ring pixels that are coloured in
     the image ("precision").  An overlay PNG (detected centres on the source image) is written for visual
     inspection.

Known limits (stated in every output): where markers overlap heavily (dense trails), detected centres
sample the trail and do not correspond one-to-one to camera frames; number of frames and exact frame times
cannot be recovered.  Points hidden under other markers are missed.  JPEG compression blurs colours.

Usage: python3 -I tools/digitize_figure.py <TP.pdf> <config.json> <repo-root>
"""
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

RADIUS = 5.5        # px, measured on legend markers (outer diameter 12 px)
RING_SIGMA = 0.9    # px, ring line half-width of the kernel
MIN_SEP = 4         # px, minimum distance between accepted centres
THRESH_FRAC = 0.30  # accept peaks scoring >= this fraction of the legend-marker score (1.1.0: was 0.40, missed isolated markers in Fig. 114)
DARK = 110          # max(R, G, B) below this = black (axes/ticks); coloured markers excluded
METHOD_VERSION = "1.1.0"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def extract_image(pdf, page, index, tmp):
    subprocess.run(["pdfimages", "-j", "-f", str(page), "-l", str(page), pdf, os.path.join(tmp, "img")], check=True)
    names = sorted(f for f in os.listdir(tmp) if f.startswith("img-"))
    path = os.path.join(tmp, names[index])
    if not path.endswith(".jpg"):
        raise SystemExit("embedded image is not a JPEG; method assumes DCT-encoded image")
    return open(path, "rb").read()


def runs_centres(idx):
    out, s, p = [], None, None
    for i in idx:
        if s is None:
            s = p = i
        elif i == p + 1:
            p = i
        else:
            out.append((s + p) / 2.0); s = p = i
    if s is not None:
        out.append((s + p) / 2.0)
    return out


def tick_positions(dark, frame, edge, major_min_len=None):
    t, b, l, r = frame["top"], frame["bottom"], frame["left"], frame["right"]
    if edge == "bottom":
        coords = range(l + 3, r - 2)
        lens = [sum(1 for n in range(1, 40) if all(dark[b - k, x] for k in range(1, n + 1))) for x in coords]
    elif edge == "left":
        coords = range(t + 3, b - 2)
        lens = [sum(1 for n in range(1, 40) if all(dark[y, l + k] for k in range(1, n + 1))) for y in coords]
    else:
        coords = range(t + 3, b - 2)
        lens = [sum(1 for n in range(1, 40) if all(dark[y, r - k] for k in range(1, n + 1))) for y in coords]
    lens = np.array(lens)
    base = int(np.bincount(lens).argmax())          # frame thickness beyond the line (usually 0 or 1)
    lens = lens - base
    major_min = major_min_len if major_min_len is not None else 0.75 * lens.max()
    return runs_centres([c for c, v in zip(coords, lens) if v >= major_min]), int(lens.max())


def calibrate(dark, frame, axis):
    pos, maxlen = tick_positions(dark, frame, axis["edge"], axis.get("major_min_len_px"))
    if "tick_pairs_as_read" in axis:
        # Used when some labelled ticks are hidden by data markers: each [approximate px, value] pair read from
        # the image is snapped to the nearest detected tick (must be within 8 px), so positions stay measured.
        px, labels = [], []
        for hint, value in axis["tick_pairs_as_read"]:
            near = min(pos, key=lambda p: abs(p - hint)) if pos else None
            if near is None or abs(near - hint) > 8:
                raise SystemExit(f"{axis['edge']} axis: no detected tick within 8 px of {hint} (detected {pos})")
            px.append(near); labels.append(value)
        px, val = np.array(px), np.array(labels, float)
    else:
        labels = axis["tick_labels_as_read"]
        if len(pos) != len(labels):
            raise SystemExit(f"{axis['edge']} axis: {len(pos)} major ticks detected at {pos}, but {len(labels)} labels given")
        px, val = np.array(pos), np.array(labels, float)
    b, a = np.polyfit(px, val, 1)
    res = val - (a + b * px)
    return {"edge": axis["edge"], "quantity": axis["quantity"], "unit": axis["unit"],
            "major_tick_px": [float(x) for x in px], "tick_labels_as_read": [float(v) if not float(v).is_integer() else int(v) for v in labels],
            "tick_matching": "pairs read from image, snapped to detected ticks" if "tick_pairs_as_read" in axis else "all detected major ticks, in pixel order",
            "fit": {"model": "value = a + b * pixel", "a": float(a), "b": float(b)},
            "residuals_at_ticks": [float(x) for x in res],
            "max_abs_residual": float(np.abs(res).max()),
            "max_abs_residual_px": float(np.abs(res).max() / abs(b)),
            "major_tick_length_px": maxlen, "major_min_len_px": axis.get("major_min_len_px", "0.75 x longest")}


def colour_score(a, colour):
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    if colour == "red":
        s = R - np.maximum(G, B)
    elif colour == "blue":
        s = B - np.maximum(R, G)
    elif colour == "green":
        s = G - np.maximum(R, B)
    else:
        raise SystemExit("unknown colour " + colour)
    return np.clip(s, 0, None).astype(np.float32)


def ring_kernel():
    k = int(np.ceil(RADIUS + 3 * RING_SIGMA))
    yy, xx = np.mgrid[-k:k + 1, -k:k + 1]
    d = np.hypot(xx, yy)
    ring = np.exp(-0.5 * ((d - RADIUS) / RING_SIGMA) ** 2)
    return (ring - ring.mean()).astype(np.float32)


PASSES = 3          # detection passes; each later pass works on pixels not explained by earlier rings


def detect(score, mask_valid, ref_score):
    """Return [(x, y, score, pass_no)], the pass-1 score map, and per-pass counts."""
    K = ring_kernel()
    thr = THRESH_FRAC * ref_score
    occ = np.zeros(score.shape, bool)
    yy, xx = np.mgrid[0:score.shape[0], 0:score.shape[1]]
    work = score.copy()
    taken, counts, S1 = [], [], None
    for pas in range(1, PASSES + 1):
        S = cv2.filter2D(work, -1, K, borderType=cv2.BORDER_CONSTANT)
        S[~mask_valid] = 0
        if S1 is None:
            S1 = S
        dil = cv2.dilate(S, np.ones((2 * MIN_SEP + 1, 2 * MIN_SEP + 1), np.uint8))
        ys, xs = np.where((S >= dil) & (S >= thr) & (S > 0))
        n0 = len(taken)
        for i in np.argsort(-S[ys, xs]):
            y, x = ys[i], xs[i]
            if occ[y, x]:
                continue
            taken.append((float(x), float(y), float(S[y, x]), pas, S))
            occ[max(0, y - MIN_SEP):y + MIN_SEP + 1, max(0, x - MIN_SEP):x + MIN_SEP + 1] = True
        counts.append(len(taken) - n0)
        if len(taken) == n0:
            break
        for x, y, _, p, _ in taken[n0:]:                       # blank pixels explained by the new rings
            x, y = int(x), int(y)
            y0, x0 = max(0, y - 9), max(0, x - 9)
            sl = (slice(y0, y + 10), slice(x0, x + 10))
            near = np.abs(np.hypot(xx[sl] - x, yy[sl] - y) - RADIUS) <= 1.6
            work[sl][near] = 0
    return taken, counts


def subpixel(S, x, y):
    x, y = int(x), int(y)
    def off(m, c, p):
        den = m - 2 * c + p
        return 0.0 if den == 0 else 0.5 * (m - p) / den
    dx = off(S[y, x - 1], S[y, x], S[y, x + 1]) if 0 < x < S.shape[1] - 1 else 0.0
    dy = off(S[y - 1, x], S[y, x], S[y + 1, x]) if 0 < y < S.shape[0] - 1 else 0.0
    return x + float(np.clip(dx, -0.5, 0.5)), y + float(np.clip(dy, -0.5, 0.5))


def main(pdf, cfg_path, root):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    fig, test = cfg["figure"], cfg["test_id"]
    tag = f"FIG{fig:03d}_{test}"
    with tempfile.TemporaryDirectory() as tmp:
        jpg = extract_image(pdf, cfg["pdf_page"], cfg["image_index_on_page"], tmp)
    src_dir = os.path.join(root, "data", "digitization", "source_images")
    os.makedirs(src_dir, exist_ok=True)
    src_path = os.path.join(src_dir, f"{tag}.jpg")
    open(src_path, "wb").write(jpg)
    img = Image.open(src_path).convert("RGB")
    a = np.array(img).astype(np.int32)
    dark = a.max(2) < DARK
    fr = cfg["frame_px"]
    cal = {k: calibrate(dark, fr, ax) for k, ax in cfg["axes"].items()}

    valid = np.zeros(dark.shape, bool)
    valid[fr["top"] + 2:fr["bottom"] - 1, fr["left"] + 2:fr["right"] - 1] = True
    legend = np.zeros(dark.shape, bool)
    for e in cfg["exclude_px"]:
        legend[e["y0"]:e["y1"], e["x0"]:e["x1"]] = True
    out_series, overlay = [], img.copy()
    draw = ImageDraw.Draw(overlay)
    yy, xx = np.mgrid[0:dark.shape[0], 0:dark.shape[1]]
    for s in cfg["series"]:
        score = colour_score(a, s["color"])
        # reference: score of the legend marker for this colour (an isolated, complete ring)
        K = ring_kernel()
        S_leg = cv2.filter2D(score, -1, K, borderType=cv2.BORDER_CONSTANT)
        ref = float(S_leg[legend].max())
        pts, pass_counts = detect(score, valid & ~legend, ref)
        xcal, ycal = cal["x"]["fit"], cal[s["axis"]]["fit"]
        rows = []
        for x, y, sc, pas, S in pts:
            xs, ys = subpixel(S, x, y)
            rows.append({"t_s": xcal["a"] + xcal["b"] * xs, "value": ycal["a"] + ycal["b"] * ys,
                         "x_px": round(xs, 2), "y_px": round(ys, 2), "match_score_rel": round(sc / ref, 3), "pass": pas})
        rows.sort(key=lambda r: (r["t_s"], r["value"]))
        # self-check: coloured pixels vs redrawn rings
        coloured = (score > 60) & valid & ~legend
        redraw = np.zeros(dark.shape, bool)
        for r in rows:
            d = np.hypot(xx - r["x_px"], yy - r["y_px"])
            redraw |= (np.abs(d - RADIUS) <= 1.2)
        redraw &= valid & ~legend
        recall = float((coloured & cv2.dilate(redraw.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)).sum() / max(1, coloured.sum()))
        precision = float((redraw & cv2.dilate(coloured.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)).sum() / max(1, redraw.sum()))
        mark = {"red": (0, 160, 255), "blue": (255, 140, 0), "green": (200, 0, 200)}[s["color"]]
        for r in rows:
            draw.line([(r["x_px"] - 2, r["y_px"]), (r["x_px"] + 2, r["y_px"])], fill=mark)
            draw.line([(r["x_px"], r["y_px"] - 2), (r["x_px"], r["y_px"] + 2)], fill=mark)
        ds_rel = f"data/digitized/{test}_fig{fig:03d}_{s['name']}.csv"
        os.makedirs(os.path.join(root, "data", "digitized"), exist_ok=True)
        with open(os.path.join(root, ds_rel), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["t_s", f"{s['name']}_{s['unit'].replace('^', '')}", "x_px", "y_px", "match_score_rel", "detection_pass"])
            for r in rows:
                w.writerow([f"{r['t_s']:.4f}", f"{r['value']:.4f}", r["x_px"], r["y_px"], r["match_score_rel"], r["pass"]])
        out_series.append({"name": s["name"], "legend_text": s["legend_text"], "color": s["color"], "axis": s["axis"],
                           "quantity": s["quantity"], "unit": s["unit"], "path": ds_rel, "points": len(rows), "points_per_pass": pass_counts,
                           "t_range_s": [round(rows[0]["t_s"], 3), round(rows[-1]["t_s"], 3)] if rows else None,
                           "quality_flag": ("OK" if recall >= 0.85 and precision >= 0.80 else
                                            "LOW_PRECISION: some centres offset or detected on partly hidden rings (overlap with other series); inspect overlay" if precision < 0.80 else
                                            "LOW_RECALL: some markers missed; inspect overlay"),
                           "self_check": {"recall_coloured_pixels_covered": round(recall, 3),
                                          "precision_redrawn_ring_pixels_coloured": round(precision, 3),
                                          "reference_score_source": "legend marker of the same colour",
                                          "threshold_fraction_of_reference": THRESH_FRAC}})
    ov_rel = f"docs/digitization/{tag}_overlay.png"
    os.makedirs(os.path.join(root, "docs", "digitization"), exist_ok=True)
    overlay.save(os.path.join(root, ov_rel))
    rec = {
        "record_type": "DigitizationRecord", "method_version": METHOD_VERSION,
        "test_id": test, "evidence_class": "DIGITIZED",
        "source": {"source_id": "S01", "locator": f"Appendix B, Figure {fig}, printed p. {cfg['printed_page']} (PDF p. {cfg['pdf_page']})",
                   "source_pdf_sha256": sha(open(pdf, "rb").read())},
        "source_image": {"path": os.path.relpath(src_path, root), "sha256": sha(jpg), "bytes": len(jpg),
                         "width_px": img.width, "height_px": img.height,
                         "extraction": "pdfimages -j (embedded DCT stream copied unchanged)"},
        "config": os.path.relpath(cfg_path, root), "config_sha256": sha(open(cfg_path, "rb").read()),
        "label_reading_note": cfg["label_reading_note"],
        "time_zero": "As in the source plot: time zero = igniter energized (S01 App. B intro, CLM-018).",
        "calibration": cal,
        "marker_detection": {"marker": "open circle", "radius_px": RADIUS, "ring_sigma_px": RING_SIGMA,
                             "min_separation_px": MIN_SEP, "threshold_fraction_of_legend_score": THRESH_FRAC, "passes": PASSES,
                             "colour_score": "e.g. red = max(0, R - max(G, B))", "excluded_regions": cfg["exclude_px"]},
        "series": out_series,
        "overlay_image": ov_rel,
        "limitations": [
            "Values are read from a raster plot, not from NASA's data files; they are not original measurements.",
            "Where markers overlap (dense trails) detected centres sample the trail and do not correspond to individual camera frames; frame count and frame times cannot be recovered.",
            "Markers hidden under other markers, and markers outside the plotted axis range, are missed.",
            "Calibration residuals describe tick placement only. No uncertainty of the digitized values is claimed beyond: one marker radius is about "
            + f"{RADIUS * abs(cal['x']['fit']['b']):.3f} s in time and {RADIUS * abs(cal['y_left']['fit']['b']):.3f} mm^2 on the left axis.",
            "Tick label values were typed by the reader from the image."],
    }
    rec_rel = f"data/digitization/{tag}_record.json"
    with open(os.path.join(root, rec_rel), "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(json.dumps({"record": rec_rel, "cal_max_px": {k: round(v["max_abs_residual_px"], 2) for k, v in cal.items()},
                      "series": [(s["name"], s["points"], s["self_check"]) for s in out_series]}, indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
