#!/usr/bin/env python3
"""Ambil SATU berkas dari dalam zip PSI tanpa mengunduh zipnya (HTTP Range).

Zip menyimpan daftar isinya di ujung berkas. Bila server menerima `Range`, cukup:
  1) baca ekor zip (direktori pusat)  -> daftar anggota + offset,
  2) baca rentang byte satu anggota   -> dekompresi lokal.
Jadi deret citra berukuran TB bisa dicuplik per frame.

Hanya pustaka standar. Bila server MENOLAK Range (membalas 200, bukan 206), skrip berhenti
sebelum membaca badan respons, jadi tidak pernah mengunduh berkas utuh tanpa sengaja.

Pakai:
  python scripts/psi_range.py probe  PSI-98 "PSI-98_Raw Data_....zip"
  python scripts/psi_range.py list   PSI-98 "....zip" [--limit 20]
  python scripts/psi_range.py get    PSI-98 "....zip" "anggota/di/dalam.jpg" [-o keluaran]
  python scripts/psi_range.py sample PSI-98 "....zip" --every 100 --ext jpg -o kb/raw/sample/
"""
import argparse
import io
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://psi.nasa.gov/geode-py/ws"
UA = "Mozilla/5.0 (SpaceApps knowledge-base builder)"
TIMEOUT = 45


def signed_url(acc, name, version=""):
    q = {"file": name, "redirect": "false"}
    if version != "":
        q["version"] = version
    api = f"{BASE}/studies/{acc}/download?" + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)
    req = urllib.request.Request(api, headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        url = r.read().decode("utf-8").strip().strip('"')
    if not url.startswith("http"):
        raise RuntimeError("API tidak mengembalikan URL: " + url[:120])
    return url


class RangeFile(io.RawIOBase):
    """Berkas jarak jauh yang bisa di-seek; tiap read = satu permintaan Range (dengan cache blok)."""

    def __init__(self, url, block=1 << 18):
        self.url, self.block = url, block
        self.pos, self.cache = 0, {}
        self.n_req = self.n_bytes = 0
        self.size = self._probe()

    def _req(self, lo, hi):
        req = urllib.request.Request(self.url, headers={"User-Agent": UA, "Range": f"bytes={lo}-{hi}"})
        r = urllib.request.urlopen(req, timeout=TIMEOUT)
        if r.status != 206:                       # server mengabaikan Range -> JANGAN baca badannya
            r.close()
            raise RuntimeError(f"server membalas {r.status}, bukan 206: Range tidak didukung")
        return r

    def _probe(self):
        with self._req(0, 0) as r:
            self.n_req += 1
            cr = r.headers.get("Content-Range", "")         # 'bytes 0-0/12345'
            self.accept = r.headers.get("Accept-Ranges")
            self.server = r.headers.get("Server")
            r.read()
        return int(cr.rsplit("/", 1)[1])

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else self.pos + off if whence == 1 else self.size + off
        return self.pos

    def _block(self, i):
        if i not in self.cache:
            lo = i * self.block
            hi = min(self.size, lo + self.block) - 1
            with self._req(lo, hi) as r:
                self.cache[i] = r.read()
            self.n_req += 1
            self.n_bytes += len(self.cache[i])
            if len(self.cache) > 64:
                self.cache.pop(next(iter(self.cache)))
        return self.cache[i]

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        n = max(0, min(n, self.size - self.pos))
        if n > 8 * self.block:                               # bacaan besar: satu permintaan langsung
            with self._req(self.pos, self.pos + n - 1) as r:
                out = r.read()
            self.n_req += 1
            self.n_bytes += len(out)
            self.pos += len(out)
            return out
        out = bytearray()
        while len(out) < n:
            i, o = divmod(self.pos, self.block)
            chunk = self._block(i)[o:o + n - len(out)]
            if not chunk:
                break
            out += chunk
            self.pos += len(chunk)
        return bytes(out)

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


def open_zip(acc, name):
    rf = RangeFile(signed_url(acc, name))
    return rf, zipfile.ZipFile(rf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "list", "get", "sample"])
    ap.add_argument("acc")
    ap.add_argument("name")
    ap.add_argument("member", nargs="?")
    ap.add_argument("-o", "--out")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--every", type=int, default=100)
    ap.add_argument("--ext", default="")
    ap.add_argument("--max-files", type=int, default=20)
    a = ap.parse_args()
    t0 = time.time()

    if a.cmd == "probe":
        rf = RangeFile(signed_url(a.acc, a.name))
        print(f"206 OK  ukuran={rf.size:,} B  Accept-Ranges={rf.accept}  Server={rf.server}  "
              f"{time.time() - t0:.1f} s", flush=True)
        return

    rf, z = open_zip(a.acc, a.name)
    infos = [i for i in z.infolist() if not i.is_dir()]
    print(f"zip {rf.size / 1e6:,.1f} MB, {len(infos)} anggota; daftar isi dibaca dengan "
          f"{rf.n_bytes / 1e3:,.0f} kB dalam {rf.n_req} permintaan ({time.time() - t0:.1f} s)", flush=True)

    if a.cmd == "list":
        for i in infos[:a.limit]:
            print(f"  {i.file_size:>12,}  {i.filename}")
    elif a.cmd == "get":
        b0 = rf.n_bytes
        data = z.read(a.member)
        out = Path(a.out or Path(a.member).name)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(f"{a.member}: {len(data):,} B -> {out}  (unduh {(rf.n_bytes - b0) / 1e3:,.0f} kB, "
              f"{(rf.n_bytes) / rf.size * 100:.4f} % dari zip)", flush=True)
    else:
        pick = [i for i in infos if i.filename.lower().endswith(a.ext.lower())][::a.every][:a.max_files]
        out = Path(a.out or "sample")
        out.mkdir(parents=True, exist_ok=True)
        for i in pick:
            (out / Path(i.filename).name).write_bytes(z.read(i))
            print(f"  {i.filename}  {i.file_size:,} B", flush=True)
        print(f"{len(pick)} berkas, total unduh {rf.n_bytes / 1e6:.2f} MB = "
              f"{rf.n_bytes / rf.size * 100:.3f} % dari zip, {time.time() - t0:.1f} s", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                                   # gagal dicatat, bukan dibuang diam-diam
        print(f"GAGAL: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
