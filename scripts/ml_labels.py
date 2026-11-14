#!/usr/bin/env python3
"""Latih ulang model 'menyala' dari telemetri memakai label NASA + label MANUSIA (tahap D).

Dipanggil otomatis oleh scripts/learn.py setiap kali log anotasi berubah.

Label:
  - kolom ignited tabel NASA (PSI-159)                        sumber 'nasa'
  - putusan manusia di kb/gold/annotations.jsonl untuk quantity=ignited:
      value_text ya/tidak                -> label itu
      verdict ok   pada angka turunan    -> nilai turunan dianggap benar
      verdict salah pada angka turunan   -> kebalikan nilai turunan
    (label manusia MENANG atas label NASA bila keduanya ada: manusia sudah melihat kontradiksinya)

Model: HistGradientBoosting pada fitur ringkasan per kanal (cepat; detik, bukan menit).
Evaluasi selalu pada himpunan TETAP: uji berlabel NASA, GroupKFold per hari — supaya angka
sebelum/sesudah label manusia bisa dibandingkan apel-ke-apel.

Keluaran: analysis/ml/telemetry_gb_predictions.csv, analysis/ml/telemetry_gb_card.json
"""
import csv
import json
import re
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
ML = ROOT / "analysis" / "ml"


def features(X, mask):
    out = []
    for x, m in zip(X, mask):
        L = int(m.sum()) or 1
        s = x[:, :L]
        out.append(np.concatenate([s.max(1), s.min(1), s.mean(1), s[:, -8:].mean(1),
                                   s.argmax(1) / 4.0, np.abs(np.diff(s, axis=1)).sum(1), [L / 4.0]]))
    return np.array(out, np.float32)


def human_labels(derived):
    """{(acc, test_point): 0/1} dari log anotasi; putusan terakhir menang."""
    import os
    p = Path(os.environ.get("FREEFALL_ANN", ROOT / "kb" / "gold" / "annotations.jsonl"))
    out = {}
    if not p.exists():
        return out
    for l in p.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        a = json.loads(l)
        if a.get("quantity") != "ignited" or not a.get("entity"):
            continue
        _, acc, tp = a["entity"].split(":", 2)
        key = (acc, tp)
        if a.get("value_text") in ("ya", "tidak"):
            out[key] = int(a["value_text"] == "ya")
        elif key in derived and a["verdict"] in ("ok", "salah"):
            d = derived[key]
            out[key] = d if a["verdict"] == "ok" else 1 - d
    return out


def model():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=10, random_state=7)


def main():
    d = np.load(ML / "telemetry_tensors.npz", allow_pickle=False)
    F = features(d["X"], d["mask"])
    acc, tp, day = d["accession"], d["test_point"], d["day"]
    tel = {(r["accession"], r["test_point"]): int(r["ignited_tel"] == "ya") for r in
           csv.DictReader(open(ROOT / "analysis" / "telemetry" / "telemetry_joined.csv", encoding="utf-8"))}
    hum = human_labels(tel)
    y = np.full(len(F), -1)
    src = np.array([""] * len(F), dtype=object)
    for i in range(len(F)):
        if d["y_ign"][i] >= 0:
            y[i], src[i] = int(d["y_ign"][i]), "nasa"
        h = hum.get((str(acc[i]), str(tp[i])))
        if h is not None:
            y[i], src[i] = h, "manusia"
    lab = np.where(y >= 0)[0]
    evalset = np.where(d["y_ign"] >= 0)[0]                 # tetap: berlabel NASA
    # validasi per hari pada himpunan tetap; label manusia ikut melatih lipatan bila bukan di lipatan uji
    P = np.full(len(F), np.nan)
    groups = day[evalset]
    for tr_i, te_i in GroupKFold(n_splits=5).split(evalset, groups=groups):
        te = evalset[te_i]
        te_days = set(day[te])
        tr = np.array([i for i in lab if day[i] not in te_days])
        P[te] = model().fit(F[tr], y[tr]).predict_proba(F[te])[:, 1]
    yt = np.array([int(d["y_ign"][i]) for i in evalset])
    # label evaluasi: NASA, kecuali manusia sudah mengoreksinya
    ye = np.array([y[i] for i in evalset])
    pe = P[evalset]
    card = {"id": "gb_telemetry_labels", "n_label_nasa": int((src == "nasa").sum()),
            "n_label_manusia": int((src == "manusia").sum()),
            "metrics_vs_nasa": {"auc": round(float(roc_auc_score(yt, pe)), 4), "brier": round(float(brier_score_loss(yt, pe)), 4),
                                "acc": round(float(np.mean((pe > 0.5) == yt)), 4)},
            "metrics_vs_label_terkini": {"auc": round(float(roc_auc_score(ye, pe)), 4),
                                         "brier": round(float(brier_score_loss(ye, pe)), 4),
                                         "acc": round(float(np.mean((pe > 0.5) == ye)), 4)},
            "validasi": "GroupKFold per hari pada uji berlabel NASA (himpunan tetap)"}
    full = model().fit(F[lab], y[lab])
    p_all = full.predict_proba(F)[:, 1]
    with open(ML / "telemetry_gb_predictions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["accession", "test_point", "p_ignite", "label", "label_source"])
        for i in range(len(F)):
            w.writerow([acc[i], tp[i], round(float(p_all[i]), 4), "" if y[i] < 0 else int(y[i]), src[i]])
    (ML / "telemetry_gb_card.json").write_text(json.dumps(card, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(card, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
