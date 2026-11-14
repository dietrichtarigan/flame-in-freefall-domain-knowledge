#!/usr/bin/env python3
"""Deep learning pada telemetri mentah ACME: ResNet-1D multi-tugas + pra-latih swa-awasan.

Tugas (label NASA, hanya PSI-159 CFI-G, 320 uji):
  ign      menyala (hot ignition)                      klasifikasi
  selfext  padam sendiri vs dihentikan aliran          klasifikasi (hanya yang menyala)
  burn     waktu bakar (s)                             regresi pada log(s)

Pembanding, semuanya divalidasi PER-HARI (GroupKFold menurut hari uji):
  aturan   ambang termokopel 0,0006 V (scripts/telemetry_mine.py)
  fitur+GB fitur ringkasan buatan tangan per kanal + HistGradientBoosting
  CNN      ResNet-1D dari nol
  CNN+pra  ResNet-1D yang encodernya dipra-latih merekonstruksi bentang sinyal
           yang ditutupi (masked reconstruction) pada ~600 rekaman PSI-10 + PSI-23
           TANPA label. PSI-159 tidak dipakai saat pra-latih -> tidak ada kebocoran.

Akhirnya: ansambel model lipatan memprediksi PSI-10 dan PSI-23 (tanpa label NASA),
dengan ketidakpastian (simpangan antar-model). Itu EKSTRAPOLASI ke investigasi lain.

  python scripts/ml_telemetry_prep.py   # sekali
  python scripts/ml_telemetry_dl.py     # -> analysis/ml/telemetry_dl_report.md, telemetry_predictions.csv
"""
import csv
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "ml"
SEED = 7
torch.set_num_threads(max(1, torch.get_num_threads()))
DEV = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class CFG:            # diisi dari argumen baris perintah di main()
    epochs, seeds, width, pre_epochs, tag = 40, 2, 32, 40, ""


# ------------------------------------------------------------------ data
def load():
    d = dict(np.load(OUT / "telemetry_tensors.npz", allow_pickle=False))
    X = d["X"].astype(np.float32)
    # skala robust per kanal (tanpa label), lalu kompres sign*log1p
    nz = np.abs(X).max(axis=2)                                  # (N, C)
    scale = np.array([np.median(c[c > 0]) if (c > 0).any() else 1.0 for c in nz.T], np.float32)
    Xn = X / scale[None, :, None]
    Xn = np.sign(Xn) * np.log1p(np.abs(Xn))
    Xn = np.concatenate([Xn, d["mask"][:, None, :]], axis=1).astype(np.float32)
    d["Xn"] = Xn
    return d


# ------------------------------------------------------------------ model
class Block(nn.Module):
    def __init__(self, cin, cout, dil, drop):
        super().__init__()
        self.c1 = nn.Conv1d(cin, cout, 7, padding=3 * dil, dilation=dil)
        self.b1 = nn.BatchNorm1d(cout)
        self.c2 = nn.Conv1d(cout, cout, 7, padding=3 * dil, dilation=dil)
        self.b2 = nn.BatchNorm1d(cout)
        self.sk = nn.Conv1d(cin, cout, 1) if cin != cout else nn.Identity()
        self.dr = nn.Dropout(drop)

    def forward(self, x):
        h = F.gelu(self.b1(self.c1(x)))
        h = self.dr(h)
        h = self.b2(self.c2(h))
        return F.gelu(h + self.sk(x))


class Encoder(nn.Module):
    def __init__(self, cin=19, w=32, drop=0.1):
        super().__init__()
        self.stem = nn.Sequential(nn.Conv1d(cin, w, 9, stride=2, padding=4), nn.BatchNorm1d(w), nn.GELU())
        self.blocks = nn.Sequential(Block(w, w, 1, drop), Block(w, 2 * w, 2, drop),
                                    nn.MaxPool1d(2), Block(2 * w, 2 * w, 4, drop),
                                    Block(2 * w, 2 * w, 8, drop))
        self.dim = 2 * w

    def forward(self, x):                      # (B, C, 512) -> (B, D, 128)
        return self.blocks(self.stem(x))


class Net(nn.Module):
    def __init__(self, enc):
        super().__init__()
        self.enc = enc
        D = enc.dim * 2
        self.head = nn.Sequential(nn.Linear(D, 64), nn.GELU(), nn.Dropout(0.3))
        self.ign, self.se, self.bt = nn.Linear(64, 1), nn.Linear(64, 1), nn.Linear(64, 1)

    def forward(self, x):
        h = self.enc(x)
        z = torch.cat([h.mean(2), h.amax(2)], 1)
        z = self.head(z)
        return self.ign(z)[:, 0], self.se(z)[:, 0], self.bt(z)[:, 0]


class Recon(nn.Module):
    """Dekoder ringan untuk pra-latih: rekonstruksi sinyal dari representasi encoder."""
    def __init__(self, enc, cout=18):
        super().__init__()
        self.enc = enc
        self.dec = nn.Sequential(nn.Upsample(scale_factor=4, mode="linear"),
                                 nn.Conv1d(enc.dim, 32, 5, padding=2), nn.GELU(),
                                 nn.Conv1d(32, cout, 5, padding=2))

    def forward(self, x):
        return self.dec(self.enc(x))


# ------------------------------------------------------------------ latih
def augment(x, g):
    B, C, L = x.shape
    x = x.clone()
    sh = torch.randint(-12, 13, (B,), generator=g)
    for i in range(B):                               # geser waktu kecil
        x[i] = torch.roll(x[i], int(sh[i]), dims=1)
    amp = 1 + 0.15 * torch.randn(B, C - 1, 1, generator=g)
    x[:, :-1] *= amp
    x[:, :-1] += 0.03 * torch.randn(B, C - 1, L, generator=g)
    drop = (torch.rand(B, C - 1, 1, generator=g) < 0.1).float()   # kanal hilang
    x[:, :-1] *= 1 - drop
    return x


def pretrain(Xu, epochs=None, seed=SEED):
    epochs = epochs or CFG.pre_epochs
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    enc = Encoder(w=CFG.width)
    m = Recon(enc).to(DEV)
    opt = torch.optim.AdamW(m.parameters(), 2e-3, weight_decay=1e-4)
    X = torch.from_numpy(Xu)
    n = len(X)
    for ep in range(epochs):
        m.train()
        perm = torch.randperm(n, generator=g)
        tot = 0.0
        for b in range(0, n, 32):
            xb = X[perm[b:b + 32]]
            # tutup 4 bentang acak @ 32 langkah di semua kanal sinyal
            msk = torch.zeros(xb.shape[0], 1, xb.shape[2])
            for i in range(xb.shape[0]):
                for s in torch.randint(0, xb.shape[2] - 32, (4,), generator=g):
                    msk[i, 0, s:s + 32] = 1
            xb, msk = xb.to(DEV), msk.to(DEV)
            inp = xb.clone()
            inp[:, :-1] *= 1 - msk
            pred = m(inp)
            w = msk * xb[:, -1:]                         # hanya di dalam rekaman
            loss = (((pred - xb[:, :-1]) ** 2) * w).sum() / (w.sum() * 18 + 1e-6)
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(xb)
        if ep % 10 == 9:
            print(f"    pra-latih epoch {ep+1}: mse tertutup {tot/n:.4f}", flush=True)
    return {k: v.cpu() for k, v in enc.state_dict().items()}


def train(Xtr, ytr, enc_state=None, epochs=None, seed=SEED):
    epochs = epochs or CFG.epochs
    torch.manual_seed(seed)
    g = torch.Generator().manual_seed(seed)
    enc = Encoder(w=CFG.width)
    if enc_state is not None:
        enc.load_state_dict(enc_state)
    net = Net(enc).to(DEV)
    lr_enc = 5e-4 if enc_state is not None else 2e-3
    opt = torch.optim.AdamW([{"params": net.enc.parameters(), "lr": lr_enc},
                             {"params": [p for n_, p in net.named_parameters() if not n_.startswith("enc.")],
                              "lr": 2e-3}], weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)
    X = torch.from_numpy(Xtr)
    yi, ys, yb = (torch.from_numpy(v) for v in ytr)
    n = len(X)
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(n, generator=g)
        for b in range(0, n, 32):
            idx = perm[b:b + 32]
            xb = augment(X[idx], g).to(DEV)
            li, ls, lb = net(xb)
            ti, ts, tb = yi[idx].to(DEV), ys[idx].to(DEV), yb[idx].to(DEV)
            loss = F.binary_cross_entropy_with_logits(li, ti.float())
            m = ts >= 0
            if m.any():
                loss = loss + F.binary_cross_entropy_with_logits(ls[m], ts[m].float())
            m = torch.isfinite(tb)
            if m.any():
                loss = loss + 0.5 * F.huber_loss(lb[m], torch.log(tb[m].clamp(min=1.0)), delta=0.5)
            opt.zero_grad(); loss.backward()
            nn.utils.clip_grad_norm_(net.parameters(), 5.0)
            opt.step()
        sched.step()
    return net


@torch.no_grad()
def predict(nets, X, zero_ch=None):
    out = []
    Xt = torch.from_numpy(X)
    if zero_ch is not None:
        Xt = Xt.clone(); Xt[:, zero_ch] = 0
    for net in nets:
        net.eval()
        li, ls, lb = net(Xt.to(DEV))
        out.append(np.stack([torch.sigmoid(li).cpu().numpy(), torch.sigmoid(ls).cpu().numpy(),
                             torch.exp(lb).cpu().numpy()], 1))
    return np.stack(out)          # (models, N, 3)


# ------------------------------------------------------------------ fitur buatan tangan (pembanding)
def handcrafted(X, mask):
    fe = []
    for x, m in zip(X, mask):
        L = int(m.sum()) or 1
        s = x[:, :L]
        tmax = s.argmax(1) / 4.0
        fe.append(np.concatenate([s.max(1), s.min(1), s.mean(1), s[:, -8:].mean(1),
                                  tmax, np.abs(np.diff(s, axis=1)).sum(1), [L / 4.0]]))
    return np.array(fe, np.float32)


# ------------------------------------------------------------------ metrik
def clf_m(y, p):
    if len(set(y)) < 2:
        return {}
    return {"auc": round(float(roc_auc_score(y, p)), 4), "brier": round(float(brier_score_loss(y, p)), 4),
            "acc": round(float(np.mean((p > 0.5) == y)), 4)}


def score(name, lab, P):
    """P: (N,3) prediksi OOF untuk semua baris berlabel."""
    yi, ys, yb = lab
    r = {"ign": clf_m(yi, P[:, 0])}
    m = ys >= 0
    r["selfext"] = clf_m(ys[m], P[m, 1])
    m = np.isfinite(yb)
    if np.isfinite(P[m, 2]).all():
        r["burn_mae_s"] = round(float(np.mean(np.abs(P[m, 2] - yb[m]))), 2)
        r["burn_medae_s"] = round(float(np.median(np.abs(P[m, 2] - yb[m]))), 2)
    print(f"  {name:12s} {json.dumps(r, ensure_ascii=False)}", flush=True)
    return r


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=CFG.epochs)
    ap.add_argument("--seeds", type=int, default=CFG.seeds, help="benih per lipatan (ansambel)")
    ap.add_argument("--width", type=int, default=CFG.width, help="lebar kanal ResNet-1D")
    ap.add_argument("--pre-epochs", type=int, default=CFG.pre_epochs)
    ap.add_argument("--tag", default="", help="akhiran nama berkas keluaran, mis. _gpu")
    a = ap.parse_args()
    CFG.epochs, CFG.seeds, CFG.width, CFG.pre_epochs, CFG.tag = a.epochs, a.seeds, a.width, a.pre_epochs, a.tag
    print(f"perangkat {DEV}; epochs {CFG.epochs}, benih {CFG.seeds}, lebar {CFG.width}, pra-latih {CFG.pre_epochs}", flush=True)
    t0 = time.time()
    d = load()
    Xn, acc = d["Xn"], d["accession"]
    L = np.where(d["y_ign"] >= 0)[0]
    U = np.where(acc != "PSI-159")[0]
    yi, ys, yb = d["y_ign"][L].astype(np.int64), d["y_selfext"][L].astype(np.int64), d["y_burn"][L]
    groups = d["day"][L]
    lab = (yi, ys, yb)
    print(f"berlabel {len(L)} uji, {len(set(groups))} hari; tanpa label (pra-latih/prediksi) {len(U)}")
    folds = list(GroupKFold(n_splits=5).split(L, yi, groups))
    res = {}

    # --- aturan termokopel
    rule = d["rule_ign"][L].astype(float)
    res["aturan termokopel"] = {"ign": {"acc": round(float(np.mean(rule == yi)), 4),
                                        "auc": round(float(roc_auc_score(yi, np.nan_to_num(d['tc_rise'][L]))), 4)}}
    print("  aturan      ", res["aturan termokopel"])
    base_bt = float(np.median(yb[np.isfinite(yb)]))
    res["median saja"] = {"burn_mae_s": round(float(np.mean(np.abs(yb[np.isfinite(yb)] - base_bt))), 2)}

    # --- fitur + gradient boosting
    H = handcrafted(d["X"][L], d["mask"][L])
    P = np.full((len(L), 3), np.nan)
    for tr, te in folds:
        c = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                           min_samples_leaf=10, random_state=SEED).fit(H[tr], yi[tr])
        P[te, 0] = c.predict_proba(H[te])[:, 1]
        m = ys[tr] >= 0
        c = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                           min_samples_leaf=10, random_state=SEED).fit(H[tr][m], ys[tr][m])
        P[te, 1] = c.predict_proba(H[te])[:, 1]
        m = np.isfinite(yb[tr])
        r = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=300,
                                          min_samples_leaf=10, random_state=SEED).fit(H[tr][m], np.log(yb[tr][m]))
        P[te, 2] = np.exp(r.predict(H[te]))
    res["fitur+GB"] = score("fitur+GB", lab, P)

    # --- pra-latih swa-awasan (sekali, hanya data tanpa label PSI-10/23)
    print("pra-latih encoder pada", len(U), "rekaman tanpa label ...", flush=True)
    enc_state = pretrain(Xn[U])

    oof, fold_nets = {}, {}
    for tag, st in (("CNN", None), ("CNN+pra", enc_state)):
        P = np.full((len(L), 3), np.nan)
        nets_all = []
        occl = np.zeros(18)
        for k, (tr, te) in enumerate(folds):
            ytr = (yi[tr], ys[tr], yb[tr])
            nets = [train(Xn[L][tr], ytr, st, seed=SEED + s) for s in range(CFG.seeds)]
            pr = predict(nets, Xn[L][te])
            P[te] = pr.mean(0)
            nets_all += nets
            if len(set(yi[te])) > 1:
                a0 = roc_auc_score(yi[te], pr.mean(0)[:, 0])
                for c in range(18):
                    occl[c] += (a0 - roc_auc_score(yi[te], predict(nets, Xn[L][te], c).mean(0)[:, 0])) / len(folds)
            print(f"  {tag} lipatan {k+1}/5 selesai ({time.time()-t0:.0f} s)", flush=True)
        res[tag] = score(tag, lab, P)
        res[tag]["oklusi_kanal_auc"] = {str(d["channels"][c]): round(float(occl[c]), 4)
                                        for c in np.argsort(-occl)[:8]}
        oof[tag], fold_nets[tag] = P, nets_all

    # --- prediksi untuk PSI-10 / PSI-23 dengan model terbaik (Brier menyala)
    best = min(("CNN", "CNN+pra"), key=lambda t: res[t]["ign"]["brier"])
    pr = predict(fold_nets[best], Xn[U])
    mu, sd = pr.mean(0), pr.std(0)
    rows = []
    for j, i in enumerate(U):
        rows.append({"accession": acc[i], "test_point": d["test_point"][i], "model": best,
                     "p_ignite": round(float(mu[j, 0]), 4), "p_ignite_sd": round(float(sd[j, 0]), 4),
                     "p_selfext": round(float(mu[j, 1]), 4), "burn_s_pred": round(float(mu[j, 2]), 1),
                     "rule_ignited": int(d["rule_ign"][i]), "tc_rise_v": d["tc_rise"][i]})
    with open(OUT / f"telemetry_predictions{CFG.tag}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    agree = {}
    for a in ("PSI-10", "PSI-23"):
        s = [r for r in rows if r["accession"] == a]
        agree[a] = {"n": len(s), "cnn_menyala": sum(r["p_ignite"] > 0.5 for r in s),
                    "aturan_menyala": sum(r["rule_ignited"] for r in s),
                    "setuju": round(sum((r["p_ignite"] > 0.5) == bool(r["rule_ignited"]) for r in s) / len(s), 4),
                    "ragu_sd>0.2": sum(r["p_ignite_sd"] > 0.2 for r in s)}
    res["transfer"] = agree
    res["best"] = best
    res["config"] = {"device": str(DEV), "epochs": CFG.epochs, "seeds": CFG.seeds, "width": CFG.width, "pre_epochs": CFG.pre_epochs}
    (OUT / f"telemetry_dl_results{CFG.tag}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    torch.save({"state_dicts": [n.state_dict() for n in fold_nets[best]], "channels": list(d["channels"])},
               OUT / f"telemetry_cnn_ensemble{CFG.tag}.pt")
    print(json.dumps(agree, ensure_ascii=False))
    print(f"selesai {time.time()-t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
