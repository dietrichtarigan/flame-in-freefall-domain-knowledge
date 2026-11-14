---
noteId: "0e87bb20dd0411f193e215b85abd30c6"
tags: []

---

# Spesifikasi model 3D — Freefall Lab

Untuk pemodel: setiap alat eksperimen NASA di bawah ini butuh satu file glTF.
Viewer (`app/hardware_lab.html`) sudah jalan dengan schematic placeholder — begitu
file `.glb` kamu ditaruh di `app/models/`, schematic otomatis tergantikan saat
halaman dimuat ulang. Tidak perlu menyentuh kode.

## Daftar file yang ditunggu

| File | Alat | Prioritas | Referensi bentuk |
|---|---|---|---|
| `models/cir.glb` | Combustion Integrated Rack (rak + chamber silinder) | 1 | foto CIR di NASA.gov; gambar teknik di `kb/raw/psi/files/PSI-23/Engineering Documents/` |
| `models/mdca.glb` | Multi-user Droplet Combustion Apparatus (insert droplet) | 1 | `kb/raw/psi/files/PSI-39/` dokumen MDCA; proof sheet FLEX |
| `models/acme.glb` | ACME burner insert (burner bola + MFC) | 2 | `kb/raw/psi/files/PSI-159/Raw Data/` foto & test sheets |
| `models/msg.glb` | Microgravity Science Glovebox | 2 | foto MSG di NASA.gov |
| `models/spice_duct.glb` | SPICE flow duct (duct 76×76 mm + kipas) | 1 | `kb/raw/psi/files/PSI-107/Engineering Documents/SPICE_ScienceVerificationReport.pdf` |
| `models/saffire.glb` | Modul Cygnus + duct Saffire | 3 | foto Cygnus; `kb/raw/psi/files/PSI-98/Science Documents/` |

Cek juga [NASA 3D Resources](https://github.com/nasa/NASA-3D-Resources) — kalau ada
model ISS/rack yang bisa diadaptasi, lebih cepat daripada modeling dari nol
(lisensi NASA bebas pakai, cantumkan kredit).

## Aturan ekspor (wajib, supaya langsung pas di viewer)

1. **Format**: glTF 2.0 **biner** (`.glb`), satu file per alat, tekstur embedded.
2. **Satuan**: meter. Rak CIR tinggi 2,0 m; kalau modelmu masuk ke scene setinggi
   gedung atau sebesar kacang, berarti satuannya salah.
3. **Orientasi**: +Y ke atas, −Z ke depan (default glTF). Di Blender: ekspor dengan
   `+Y Up` tercentang (default).
4. **Origin**: di pusat-bawah alat (titik alat "berdiri di lantai"). Viewer menaruh
   origin tepat di posisi lantai scene.
5. **Budget**: ≤ 50.000 segitiga per file, tekstur ≤ 2048×2048. Ini dirender di
   laptop venue tanpa GPU diskrit.
6. **Material**: PBR Metallic-Roughness standar (Principled BSDF di Blender
   terekspor otomatis). Jangan pakai shader node eksotis — tidak terbawa ke glTF.
7. **Nama mesh bebas**, KECUALI satu: kalau alatmu punya representasi api, beri nama
   mesh itu `flame` — viewer akan memberinya animasi denyut otomatis.
8. **Jangan sertakan lampu/kamera** di file — scene viewer sudah punya.

## Cara menguji

1. Taruh file di `E:\nasa\app\models\`.
2. Jalankan server lokal (glTF tidak bisa dimuat lewat `file://`):
   ```
   cd E:\nasa\app
   python -m http.server 8000
   ```
3. Buka `http://localhost:8000/hardware_lab.html` — klik alatmu; badge di panel
   kanan berubah dari `SCHEMATIC` menjadi `MODEL GLTF TIM` kalau berhasil dimuat.

## Gaya visual

Arah desain: instrumen teknis / mission-ops — bentuk yang **proporsional dan jujur**
lebih penting daripada detail dekoratif. Juri kita peneliti dan insinyur aerospace;
yang membuat mereka terkesan adalah model yang bisa mereka kenali ("itu memang CIR"),
bukan model yang paling berkilau. Prioritaskan: siluet benar → proporsi benar →
detail fungsional (jendela chamber, port sarung tangan, kipas duct) → baru tekstur.
