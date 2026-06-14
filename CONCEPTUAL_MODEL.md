# 🧩 Conceptual Model (DFM) — Dashboard BI BPJS Rawat Inap (RSU AIA)

Dokumentasi *Dimensional Fact Model* (DFM, notasi **Golfarelli–Rizzi** — mata kuliah **IF5240** Intelijen Bisnis & Analitik) untuk seluruh fakta data warehouse RSU Ayah Ibu Anak Indonesia.

- **Sumber gambar:** `conceptual_model.py` → menghasilkan `conceptual_fact_*.png` / `.svg` / `.drawio` (sekali jalan).
- **Skema data aktual (star schema fisik):** lihat [`SKEMA_DATA.md`](SKEMA_DATA.md).
- **Jumlah fakta:** **6** (5 berbasis data + 1 usulan: peresepan).

> ⚠️ **Aktual vs Ideal.** Sebagian fakta digambar sebagai **desain ideal** yang lebih granular daripada CSV yang ada sekarang (ditandai 🔶 *diagram-only*). Ini disengaja untuk model konseptual yang sehat; data & dashboard belum tentu se-granular itu.

---

## 1. Notasi DFM

| Simbol | Arti |
|---|---|
| **Kotak** (2 section) | **Fakta** — section atas = atribut admisi/*degenerate* + flag kategorikal; section bawah = **measures** |
| ● **Lingkaran terisi** | **Atribut primary dimensi** — leaf yang menempel langsung ke fakta |
| ○ **Lingkaran kosong** | **Dimensional attribute** — dipakai *grouping*/agregasi (membentuk hierarki) |
| — **Garis tanpa lingkaran** (miring) | **Descriptive attribute** — info 1:1, *bukan* kriteria agregasi (biasanya daun) |
| **Degenerate dimension (DD)** | Kunci transaksi yang nempel di fakta tanpa tabel dimensi (mis. `id_admisi`, `id_operasi`, `id_resep`) |

---

## 2. Conformed Dimensions (dipakai banyak fakta)

| Dimensi | Leaf / primary | Hierarki & atribut |
|---|---|---|
| **Waktu** | `waktu` / `tanggal` | `tanggal → nama_hari`; `bulan → nama_bulan`; `bulan → kuartal → tahun`. *(periode_masuk hanya di Klaim — turunan jam admisi.)* |
| **Pasien** | `id_pasien` | `jenis_kelamin` (○); `nama_pasien`, `alamat`, `tanggal_lahir` (descriptive). *(kelompok_usia hanya di Klaim — disimpan di fakta.)* |
| **Kelas** | `id_kelas` | `nama_kelas`, `tarif_kamar_per_hari` (descriptive) |
| **Departemen** | `id_departemen` | `nama_departemen`, `jumlah_dokter` (descriptive) |
| **Obat** | `id_obat` | `kategori_abc` (○), `fornas` (○); `nama_obat`, `reorder_point` (descriptive) |

> Waktu disambungkan **di grain masing-masing fakta**: harian → leaf `waktu`/`tanggal`; bulanan → leaf `bulan`; tahunan → leaf `tahun`.

---

## 3. Daftar Fakta

### 3.1 `Fact_Klaim_RI` — *fakta pusat*
**Grain:** 1 admisi rawat inap. · Gambar: `conceptual_fact_klaim_ri.png`

| Section | Isi |
|---|---|
| Atas | `id_admisi` (DD), `status_klaim` |
| Measures | `biaya_riil`, `tarif_inacbg`, `shortfall`, `los_hari`, `los_paket_bpjs` |

**Dimensi (6):** Waktu (+`periode_masuk`), Pasien (+`kelompok_usia`), **ICD-10** (`kode_icd` → `kategori_penyakit` ○, `nama_diagnosis`), **INA-CBG** (`kode_inacbg` → `deskripsi`, `tarif_dasar`, `alos_standar`), Departemen, Kelas.

> `fornas` ada sebagai kolom di data (flag kepatuhan per-admisi) tapi **tidak digambar** — sumber kebenaran kepatuhan dipindah ke `Fact_Peresepan_Obat`.

### 3.2 `Fact_Penunjang_Diagnostik` — Lab & Radiologi
**Grain:** 1 admisi yang memakai lab dan/atau radiologi. · Gambar: `conceptual_fact_penunjang_diagnostik.png`

| Section | Isi |
|---|---|
| Atas | `id_admisi` (DD → drill-across ke Klaim) |
| Measures | `jumlah_tes_lab`, `jumlah_radiologi` |

**Dimensi (6):** Waktu 🔶, Pasien 🔶, **Lab** (`jenis_lab` → `tarif_per_tes`), **Radiologi** (`modalitas_radiologi` → `tarif_per_pemeriksaan`), Departemen, Kelas.

> 🔶 Waktu & Pasien = tambahan konseptual; di CSV fakta ini tak punya kolom tanggal/`id_pasien` (terhubung via `id_admisi`). Lab & Radiologi di-*join* lewat **nama** (bukan id surrogate), sesuai data.

### 3.3 `Fact_Operasi`
**Grain:** 1 operasi. · Gambar: `conceptual_fact_operasi.png`

| Section | Isi |
|---|---|
| Atas | `id_operasi` (PK), `id_admisi` (DD), `jenis_operasi`, `sifat`, `penyebab_overrun` |
| Measures | `durasi_menit`, `durasi_rencana_menit`, `biaya_operasi` |

**Dimensi (5):** Waktu (`tgl_operasi`), Pasien 🔶, **Ruang Operasi** (`id_ruang_operasi` → `kode_ok`, `nama_ruang`), Departemen, Kelas.

> 🔶 Pasien = tambahan konseptual (CSV hanya simpan `id_admisi`).

### 3.4 `Fact_Okupansi_Kamar` 🔶 *(redesain harian)*
**Grain:** 1 tempat tidur × 1 hari (sensus hunian ranjang). · Gambar: `conceptual_fact_okupansi_kamar.png`

| Section | Isi |
|---|---|
| Atas | — |
| Measures | `terisi` (1 = ranjang dipakai hari itu; **BOR** diturunkan dari rata-rata) |

**Dimensi (3):** Waktu, **Tempat Tidur** (`id_tempat_tidur` → `id_kelas` → `nama_kelas`, `tarif_kamar_per_hari`), Pasien.

> 🔶 CSV aktual masih agregat **per tahun** (`id_kelas, tahun, bor`). Versi ini = desain ideal yang menyambungkan `dim_tempat_tidur`.

### 3.5 `Fact_Stok_Obat_Bulanan` 🔶 *(redesain per-obat)*
**Grain:** 1 obat × 1 bulan. · Gambar: `conceptual_fact_stok_obat_bulanan.png`

| Section | Isi |
|---|---|
| Atas | — |
| Measures | `stok_akhir`, `nilai_konsumsi` |

**Dimensi (2):** Waktu (leaf `bulan` → `nama_bulan`, `kuartal` → `tahun`), **Obat**.

> 🔶 CSV aktual agregat (`tahun, bulan, jml_understock, jml_overstock`). Versi per-obat menyambungkan `dim_obat`; understock/overstock diturunkan dari `stok_akhir` vs `reorder_point`.

### 3.6 `Fact_Peresepan_Obat` 🔶 *(fakta baru — analitik kepatuhan Fornas)*
**Grain:** 1 obat diresepkan per admisi. · Gambar: `conceptual_fact_peresepan_obat.png`

| Section | Isi |
|---|---|
| Atas | `id_resep` (DD), `id_admisi` (DD → drill-across ke Klaim) |
| Measures | `jumlah_obat`, `biaya_obat` |

**Dimensi (4):** Waktu, Pasien, Departemen (peresep), **Obat**.

> 🔶 Belum ada di CSV. **`id_resep` = degenerate dimension** (resep itu *event*, bukan entitas — **tidak** ada `dim_resep`; `dim_resep → dim_obat` akan jadi snowflake redundant karena Obat sudah dimensi langsung). **% kepatuhan Fornas diturunkan dari `dim_obat.fornas`** (○), bukan flag fakta.

---

## 4. Bus Matrix (Fakta × Dimensi)

| Fakta \ Dimensi | Waktu | Pasien | ICD-10 | INA-CBG | Dept | Kelas | Lab | Radiologi | Ruang OK | Tempat Tidur | Obat |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Klaim_RI** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | | | | | |
| **Penunjang_Diagnostik** | 🔶 | 🔶 | | | ✓ | ✓ | ✓ | ✓ | | | |
| **Operasi** | ✓ | 🔶 | | | ✓ | ✓ | | | ✓ | | |
| **Okupansi_Kamar** | 🔶 | 🔶 | | | | (✓) | | | | 🔶 | |
| **Stok_Obat_Bulanan** | 🔶 | | | | | | | | | | 🔶 |
| **Peresepan_Obat** | 🔶 | 🔶 | | | ✓ | | | | | | 🔶 |

✓ = FK langsung di data aktual · 🔶 = sambungan/desain konseptual (diagram-only) · (✓) Kelas dicapai lewat snowflake Tempat Tidur.

**Hasil:** ke-11 dimensi (`dim_waktu, dim_pasien, dim_icd10, dim_ina_cbg, dim_departemen, dim_kelas, dim_lab, dim_radiologi, dim_ruang_operasi, dim_tempat_tidur, dim_obat`) **semuanya terpakai ≥ 1 fakta** — tidak ada *orphan dimension*.

---

## 5. Catatan Pemodelan

- **Degenerate dimension:** `id_admisi`, `id_operasi`, `id_resep` — kunci transaksi tanpa tabel dimensi.
- **Drill-across** lewat `id_admisi`: Penunjang, Operasi, dan Peresepan dapat ditautkan ke Klaim.
- **`dim_obat` dipakai 2 fakta** (Stok + Peresepan) → conformed dimension yang sehat.
- **Snowflake:** `Tempat Tidur → Kelas` (ranjang menggulung ke kelas) di `Fact_Okupansi_Kamar`.
- **Descriptive vs dimensional:** atribut bertarif/numerik referensi (`tarif_*`, `alos_standar`, `jumlah_dokter`, `reorder_point`) = descriptive; atribut kategori untuk *grouping* (`kategori_penyakit`, `kategori_abc`, `fornas`, `jenis_kelamin`, level waktu) = dimensional.

---

*Dibuat untuk tugas IF5240 — RSU Ayah Ibu Anak Indonesia (Tipe A), periode 2020–2025.*
