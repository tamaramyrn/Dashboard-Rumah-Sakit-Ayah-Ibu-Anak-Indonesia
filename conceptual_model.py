#!/usr/bin/env python3
"""Conceptual Modelling (Dimensional Fact Model / DFM) — notasi Golfarelli-Rizzi (IF5240).
Gaya: monokrom abu, font Inter.
Notasi:
  - Kotak fakta = 2 section: (atas) atribut admisi/degenerate+status, (bawah) MEASURES.
  - Dimensi = lingkaran terisi (root) berlabel ATRIBUT PRIMARY dimensi, nempel langsung ke fakta.
  - Dimensional attribute (○) = lingkaran kosong  -> dipakai grouping/agregasi (hierarki).
  - Descriptive attribute     = GARIS TANPA lingkaran -> info 1:1, bukan kriteria agregasi (daun).
Jalankan: python conceptual_model.py
"""
import os
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch

# ── daftarkan font Inter (lokal di assets/fonts) ──
HERE = os.path.dirname(os.path.abspath(__file__))
FONTDIR = os.path.join(HERE, "assets", "fonts")
for _f in ("Inter-Regular.ttf", "Inter-Bold.ttf", "Inter-Italic.ttf"):
    _p = os.path.join(FONTDIR, _f)
    if os.path.exists(_p):
        fm.fontManager.addfont(_p)
plt.rcParams["font.family"] = "Inter"

# ── palet MONOKROM abu ──
INK = "#1F1F1F"     # teks utama / measures
DARK = "#3D3D3D"    # root fill, border kotak, judul
MID = "#8C8C8C"     # garis penghubung & tepi lingkaran
LIGHT = "#9A9A9A"   # descriptive attribute
EDGE = "#5A5A5A"    # tepi lingkaran dimensional


def node(label, kind="dim", children=None):
    # kind: "root" (primary dimensi), "dim" (dimensional ○), "desc" (descriptive — garis tanpa ○)
    return {"label": label, "kind": kind, "children": children or []}


def n_leaves(nd):
    return 1 if not nd["children"] else sum(n_leaves(c) for c in nd["children"])


def layout(nd, a0, a1, depth, R0, RSTEP, cx, cy):
    ang = (a0 + a1) / 2
    nd["angle"] = ang
    r = R0 + depth * RSTEP
    nd["x"] = cx + r * math.cos(math.radians(ang))
    nd["y"] = cy + r * math.sin(math.radians(ang))
    kids = nd["children"]
    if kids:
        tot = sum(n_leaves(c) for c in kids)
        a = a0
        for c in kids:
            w = (a1 - a0) * n_leaves(c) / tot
            layout(c, a, a + w, depth + 1, R0, RSTEP, cx, cy)
            a += w


def draw_edges(ax, nd):
    for c in nd["children"]:
        ax.plot([nd["x"], c["x"]], [nd["y"], c["y"]], color=MID, lw=1.15, zorder=1)
        draw_edges(ax, c)


def draw_nodes(ax, nd):
    x, y, ang, kind = nd["x"], nd["y"], nd["angle"], nd["kind"]
    if kind == "root":
        ax.scatter([x], [y], s=150, color=DARK, edgecolors="white", lw=1.5, zorder=4)
        fw, fs, col, style = "bold", 11, INK, "normal"
    elif kind == "dim":
        ax.scatter([x], [y], s=52, color="white", edgecolors=EDGE, lw=1.4, zorder=4)
        fw, fs, col, style = "bold", 10, INK, "normal"
    else:  # desc -> tanpa lingkaran (garis saja)
        fw, fs, col, style = "normal", 9.5, LIGHT, "italic"
    c = math.cos(math.radians(ang))
    ha = "left" if c >= -0.1 else "right"
    dx = (4 if kind == "desc" else 11) * (1 if c >= -0.1 else -1)
    ax.annotate(nd["label"], (x, y), xytext=(dx, 0), textcoords="offset points",
                ha=ha, va="center", fontsize=fs, fontweight=fw, color=col, style=style, zorder=5)
    for ch in nd["children"]:
        draw_nodes(ax, ch)


def render(fact, dims, fname):
    cx, cy = 0.0, 0.0
    RSTEP = 1.5
    fig, ax = plt.subplots(figsize=(16.5, 11.5), dpi=130)
    ax.set_aspect("equal"); ax.axis("off")
    fig.patch.set_facecolor("white")

    # ── ukuran kotak fakta (UML-like: judul | section atas | section bawah) ──
    top, meas = fact["top"], fact["measures"]
    TITLE, ROW, GAP, PAD = 0.64, 0.44, 0.32, 0.30
    top_block = (len(top) * ROW + GAP) if top else 0.0
    bh = PAD + TITLE + GAP + top_block + len(meas) * ROW + PAD
    title_w = 0.135 * len(fact["title"]) + 0.6                       # lebar kotak adaptif ke judul/baris
    row_w = max([0.108 * len(a) + 0.65 for a in top] +
                [0.108 * (len(m) + 3) + 0.65 for m in meas] + [3.0])
    bw = max(3.0, title_w, row_w)
    hw, hh = bw / 2, bh / 2

    # dimensi radial
    for base, root in dims:
        c, s = abs(math.cos(math.radians(base))), abs(math.sin(math.radians(base)))
        edge = min(hw / c if c > 1e-3 else 1e9, hh / s if s > 1e-3 else 1e9)
        R0 = edge + 1.55
        layout(root, base - 20, base + 20, 0, R0, RSTEP, cx, cy)
        ax.plot([cx, root["x"]], [cy, root["y"]], color=MID, lw=1.5, zorder=1)
        draw_edges(ax, root)
    for base, root in dims:
        draw_nodes(ax, root)

    # ── kotak fakta (digambar terakhir → menutup pangkal garis) ──
    box = FancyBboxPatch((cx - hw, cy - hh), bw, bh,
                         boxstyle="round,pad=0.05,rounding_size=0.14",
                         fc="white", ec=DARK, lw=2.2, zorder=8)
    ax.add_patch(box)

    def divider(y):
        ax.plot([cx - hw + 0.14, cx + hw - 0.14], [y, y], color=MID, lw=1.2, zorder=9)

    cur = cy + hh - PAD
    ax.annotate(fact["title"], (cx, cur - TITLE / 2), ha="center", va="center",
                fontsize=14, fontweight="bold", color=DARK, zorder=9)
    cur -= TITLE
    divider(cur - GAP / 2); cur -= GAP
    if top:                                         # section atas (opsional)
        for a in top:
            ax.annotate(a, (cx - hw + 0.32, cur - ROW / 2), ha="left", va="center",
                        fontsize=11, color=INK, zorder=9)
            cur -= ROW
        divider(cur - GAP / 2); cur -= GAP
    for m in meas:                                  # section bawah (measures)
        ax.annotate("•  " + m, (cx - hw + 0.32, cur - ROW / 2), ha="left", va="center",
                    fontsize=11, fontweight="bold", color=INK, zorder=9)
        cur -= ROW

    ax.annotate("Conceptual Model (DFM) — " + fact["title"] + "  ·  RSU AIA  ·  IF5240",
                (0.5, 0.99), xycoords="axes fraction", ha="center", va="top",
                fontsize=13, fontweight="bold", color=DARK)

    ax.autoscale_view()
    ax.set_xlim(ax.get_xlim()[0] - 0.6, ax.get_xlim()[1] + 0.6)
    ax.set_ylim(ax.get_ylim()[0] - 0.5, ax.get_ylim()[1] + 0.5)

    # legenda notasi — strip bawah pakai marker ASLI (axis khusus, bukan glyph unicode)
    lax = fig.add_axes([0.06, 0.004, 0.88, 0.045]); lax.axis("off")
    lax.set_xlim(0, 1); lax.set_ylim(0, 1)
    lax.scatter([0.16], [0.5], s=120, color=DARK, edgecolors="white", lw=1.2)
    lax.text(0.175, 0.5, "atribut primary dimensi", va="center", ha="left", fontsize=10.5, color=INK)
    lax.scatter([0.45], [0.5], s=46, color="white", edgecolors=EDGE, lw=1.3)
    lax.text(0.465, 0.5, "dimensional attribute (grouping)", va="center", ha="left", fontsize=10.5, color=INK)
    lax.plot([0.72, 0.745], [0.5, 0.5], color=MID, lw=1.6)
    lax.text(0.755, 0.5, "descriptive attribute (1:1, tanpa lingkaran)", va="center", ha="left",
             fontsize=10.5, color=LIGHT, style="italic")

    fig.savefig(fname + ".png", bbox_inches="tight", facecolor="white")
    fig.savefig(fname + ".svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("OK ->", fname + ".png /.svg")


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_drawio(fact, dims, fname):
    """Emit file .drawio (mxGraph XML) — buka di draw.io / diagrams.net, editable, gaya sama."""
    SCALE = 70
    top, meas = fact["top"], fact["measures"]
    START, RH, LH, PAD = 70, 34, 10, 14
    H = START + (len(top) * RH + LH if top else 0) + len(meas) * RH + PAD
    W = max(210, int(9.2 * len(fact["title"])) + 40,
            int(7.4 * max([len(a) for a in top] + [len(m) + 3 for m in meas] + [0])) + 60)
    hw_u, hh_u = (W / 2) / SCALE, (H / 2) / SCALE

    nodes = []  # (id, node)
    cid = [10]

    def assign(nd):
        cid[0] += 1
        nd["_id"] = "n%d" % cid[0]
        nodes.append(nd)
        for c in nd["children"]:
            assign(c)

    for base, root in dims:
        c, s = abs(math.cos(math.radians(base))), abs(math.sin(math.radians(base)))
        edge = min(hw_u / c if c > 1e-3 else 1e9, hh_u / s if s > 1e-3 else 1e9)
        layout(root, base - 20, base + 20, 0, edge + 1.55, 1.5, 0.0, 0.0)
        assign(root)

    # map ke px (flip y), lalu geser supaya semua positif
    def px(nd):
        return nd["x"] * SCALE, -nd["y"] * SCALE
    xs = [px(n)[0] for n in nodes] + [-W / 2, W / 2]
    ys = [px(n)[1] for n in nodes] + [-H / 2, H / 2]
    ox, oy = -min(xs) + 220, -min(ys) + 120
    bx, by = ox - W / 2, oy - H / 2

    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    FF = "fontFamily=Inter;"
    # kotak fakta (UML class / swimlane 2 section)
    cells.append(
        '<mxCell id="fact" value="%s" style="swimlane;rounded=1;arcSize=8;html=1;'
        'fillColor=#ffffff;strokeColor=#3D3D3D;fontColor=#3D3D3D;fontStyle=1;fontSize=15;'
        'align=center;verticalAlign=top;startSize=%d;%s" vertex="1" parent="1">'
        '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
        % (_esc(fact["title"]), START, FF, bx, by, W, H))
    y = START
    if top:
        for a in top:
            cid[0] += 1
            cells.append(
                '<mxCell id="r%d" value="%s" style="text;html=1;align=left;verticalAlign=middle;'
                'spacingLeft=14;fontColor=#1F1F1F;fontSize=12;%s" vertex="1" parent="fact">'
                '<mxGeometry x="0" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                % (cid[0], _esc(a), FF, y, W, RH))
            y += RH
        cells.append(
            '<mxCell id="ln1" value="" style="line;strokeWidth=1;strokeColor=#8C8C8C;html=1;" '
            'vertex="1" parent="fact"><mxGeometry x="0" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
            % (y, W, LH))
        y += LH
    for m in meas:
        cid[0] += 1
        cells.append(
            '<mxCell id="m%d" value="%s" style="text;html=1;align=left;verticalAlign=middle;'
            'spacingLeft=14;fontColor=#1F1F1F;fontStyle=1;fontSize=12;%s" vertex="1" parent="fact">'
            '<mxGeometry x="0" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
            % (cid[0], _esc("•  " + m), FF, y, W, RH))
        y += RH

    # node dimensi + descriptive
    eid = [0]
    edges = []

    def emit(nd, parent_id):
        x, yy = px(nd); x += ox; yy += oy
        c = math.cos(math.radians(nd["angle"]))
        right = c >= -0.1
        if nd["kind"] == "desc":
            w_, h_ = 130, 20
            xx = x + 4 if right else x - w_ - 4
            al = "left" if right else "right"
            cells.append(
                '<mxCell id="%s" value="%s" style="text;html=1;align=%s;verticalAlign=middle;'
                'fontColor=#9A9A9A;fontStyle=2;fontSize=10;%s" vertex="1" parent="1">'
                '<mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                % (nd["_id"], _esc(nd["label"]), al, FF, xx, yy - h_ / 2, w_, h_))
        else:
            if nd["kind"] == "root":
                d = 18; fill = "#3D3D3D"; stroke = "#ffffff"; fsz = 11
            else:
                d = 16; fill = "#ffffff"; stroke = "#5A5A5A"; fsz = 10
            lab = ("labelPosition=right;align=left;spacingLeft=6;" if right
                   else "labelPosition=left;align=right;spacingRight=6;")
            cells.append(
                '<mxCell id="%s" value="%s" style="ellipse;fillColor=%s;strokeColor=%s;'
                'fontColor=#1F1F1F;fontStyle=1;fontSize=%d;verticalLabelPosition=middle;verticalAlign=middle;'
                '%s%s" vertex="1" parent="1"><mxGeometry x="%d" y="%d" width="%d" height="%d" as="geometry"/></mxCell>'
                % (nd["_id"], _esc(nd["label"]), fill, stroke, fsz, lab, FF, x - d / 2, yy - d / 2, d, d))
        eid[0] += 1
        edges.append(
            '<mxCell id="e%d" style="endArrow=none;html=1;strokeColor=#8C8C8C;edgeStyle=none;rounded=0;" '
            'edge="1" parent="1" source="%s" target="%s"><mxGeometry relative="1" as="geometry"/></mxCell>'
            % (eid[0], parent_id, nd["_id"]))
        for ch in nd["children"]:
            emit(ch, nd["_id"])

    for base, root in dims:
        emit(root, "fact")

    xml = ('<mxfile><diagram name="%s"><mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" '
           'guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" math="0" shadow="0">'
           '<root>%s</root></mxGraphModel></diagram></mxfile>'
           % (_esc(fact["title"]), "".join(cells + edges)))
    with open(fname + ".drawio", "w", encoding="utf-8") as f:
        f.write(xml)
    print("OK ->", fname + ".drawio")


# ════════════════ FACT_KLAIM_RI (aktual, notasi DFM) ════════════════
fact_klaim = {
    "title": "Fact_Klaim_RI",
    "top": ["id_admisi", "status_klaim"],          # section atas
    "measures": ["biaya_riil", "tarif_inacbg", "shortfall", "los_hari", "los_paket_bpjs"],
}

# Waktu — leaf = waktu (saat admisi); periode_masuk = roll-up paralel; lalu tanggal→bulan→kuartal→tahun
dim_waktu = node("waktu", "root", [
    node("periode_masuk", "dim"),
    node("tanggal", "dim", [
        node("nama_hari", "dim"),
        node("bulan", "dim", [
            node("nama_bulan", "desc"),
            node("kuartal", "dim", [node("tahun", "dim")]),
        ]),
    ]),
])
dim_pasien = node("id_pasien", "root", [
    node("jenis_kelamin", "dim"),
    node("kelompok_usia", "dim"),
    node("nama_pasien", "desc"),
    node("alamat", "desc"),
    node("tanggal_lahir", "desc"),
])
dim_icd10 = node("kode_icd", "root", [
    node("kategori_penyakit", "dim"),
    node("nama_diagnosis", "desc"),
])
dim_inacbg = node("kode_inacbg", "root", [
    node("deskripsi", "desc"),
    node("tarif_dasar", "desc"),
    node("alos_standar", "desc"),
])
dim_dept = node("id_departemen", "root", [
    node("nama_departemen", "desc"),
    node("jumlah_dokter", "desc"),
])
dim_kelas = node("id_kelas", "root", [
    node("nama_kelas", "desc"),
    node("tarif_kamar_per_hari", "desc"),
])

dims_klaim = [
    (20,  dim_kelas),
    (62,  dim_waktu),
    (118, dim_pasien),
    (152, dim_icd10),
    (200, dim_inacbg),
    (340, dim_dept),
]

render(fact_klaim, dims_klaim, "conceptual_fact_klaim_ri")
build_drawio(fact_klaim, dims_klaim, "conceptual_fact_klaim_ri")


def make_waktu():
    """dim_waktu CONFORMED (dipakai semua fakta) — struktur sama: waktu→tanggal→bulan→kuartal→tahun.
    (periode_masuk hanya ada di Fact_Klaim_RI karena itu atribut waktu-admisi, bukan kolom dim_waktu.)"""
    return node("waktu", "root", [
        node("tanggal", "dim", [
            node("nama_hari", "dim"),
            node("bulan", "dim", [
                node("nama_bulan", "desc"),
                node("kuartal", "dim", [node("tahun", "dim")]),
            ]),
        ]),
    ])


def make_pasien():
    """dim_pasien CONFORMED — id_pasien → jenis_kelamin, nama_pasien, alamat, tanggal_lahir.
    (kelompok_usia hanya di Fact_Klaim_RI: itu band-usia yg disimpan di fakta, bukan kolom dim_pasien.)"""
    return node("id_pasien", "root", [
        node("jenis_kelamin", "dim"),
        node("nama_pasien", "desc"),
        node("alamat", "desc"),
        node("tanggal_lahir", "desc"),
    ])


# ════════════════ FACT_PENUNJANG_DIAGNOSTIK (Lab + Radiologi) ════════════════
# kolom aktual: id_admisi, id_departemen, id_kelas, jenis_lab, jumlah_tes_lab,
#               modalitas_radiologi, jumlah_radiologi   (grain: 1 admisi pakai lab/radiologi)
# Terhubung ke dim Waktu (conformed). id_admisi tetap jadi degenerate (drill-across ke klaim).
fact_pen = {
    "title": "Fact_Penunjang_Diagnostik",
    "top": ["id_admisi"],
    "measures": ["jumlah_tes_lab", "jumlah_radiologi"],
}
pen_dept = node("id_departemen", "root", [
    node("nama_departemen", "desc"),
    node("jumlah_dokter", "desc"),
])
pen_kelas = node("id_kelas", "root", [
    node("nama_kelas", "desc"),
    node("tarif_kamar_per_hari", "desc"),
])
pen_lab = node("jenis_lab", "root", [node("tarif_per_tes", "desc")])          # → dim_lab (by nama)
pen_rad = node("modalitas_radiologi", "root", [node("tarif_per_pemeriksaan", "desc")])  # → dim_radiologi

# sebar merata; dimensi ber-anak-banyak (pasien/kelas/dept) di sudut diagonal supaya label tak tumpuk
dims_pen = [
    (90,  make_waktu()),    # atas (hierarki terdalam)
    (135, make_pasien()),   # NW (pasien yg di-lab/radiologi)
    (225, pen_kelas),       # SW
    (270, pen_rad),         # bawah
    (305, pen_dept),        # SE
    (45,  pen_lab),         # NE
]

render(fact_pen, dims_pen, "conceptual_fact_penunjang_diagnostik")
build_drawio(fact_pen, dims_pen, "conceptual_fact_penunjang_diagnostik")


# ════════════════ FACT_OPERASI ════════════════
# kolom aktual: id_operasi, id_admisi, tgl_operasi, id_departemen, id_kelas, id_ruang_operasi,
#               jenis_operasi, sifat, penyebab_overrun, durasi_menit, durasi_rencana_menit, biaya_operasi
# grain: 1 operasi. jenis_operasi/sifat/penyebab_overrun = atribut kategorikal di fakta (tanpa tabel dim).
fact_op = {
    "title": "Fact_Operasi",
    "top": ["id_operasi", "id_admisi", "jenis_operasi", "sifat", "penyebab_overrun"],
    "measures": ["durasi_menit", "durasi_rencana_menit", "biaya_operasi"],
}
# Waktu — conformed (struktur sama dgn klaim/penunjang); FK aktual = tgl_operasi
op_waktu = make_waktu()
op_dept = node("id_departemen", "root", [
    node("nama_departemen", "desc"),
    node("jumlah_dokter", "desc"),
])
op_kelas = node("id_kelas", "root", [
    node("nama_kelas", "desc"),
    node("tarif_kamar_per_hari", "desc"),
])
op_ruang = node("id_ruang_operasi", "root", [
    node("kode_ok", "desc"),
    node("nama_ruang", "desc"),
])
dims_op = [
    (90,  op_waktu),        # atas (hierarki terdalam)
    (125, make_pasien()),   # kiri-atas (pasien yg dioperasi)
    (235, op_dept),         # kiri-bawah
    (305, op_kelas),        # kanan-bawah
    (55,  op_ruang),        # kanan-atas
]

render(fact_op, dims_op, "conceptual_fact_operasi")
build_drawio(fact_op, dims_op, "conceptual_fact_operasi")


# ════════════════ FACT_OKUPANSI_KAMAR (redesain: harian per tempat tidur) ════════════════
# grain: 1 tempat_tidur × 1 hari (sensus hunian ranjang harian) → menyambungkan dim_tempat_tidur.
# (Diagram = desain ideal; CSV aktual masih agregat per tahun.)
fact_ok = {
    "title": "Fact_Okupansi_Kamar",
    "top": [],
    "measures": ["terisi"],            # 1 = ranjang terisi hari itu; BOR diturunkan dari rata-rata
}
# Tempat Tidur (roll-up ke Kelas): id_tempat_tidur → id_kelas → (nama_kelas, tarif_kamar_per_hari)
ok_tt = node("id_tempat_tidur", "root", [
    node("id_kelas", "dim", [
        node("nama_kelas", "desc"),
        node("tarif_kamar_per_hari", "desc"),
    ]),
])
dims_ok = [
    (90,  make_waktu()),    # Waktu (atas)
    (230, ok_tt),           # Tempat Tidur (kiri-bawah)
    (300, make_pasien()),   # Pasien yg menempati ranjang (kanan-bawah)
]
render(fact_ok, dims_ok, "conceptual_fact_okupansi_kamar")
build_drawio(fact_ok, dims_ok, "conceptual_fact_okupansi_kamar")


# ════════════════ FACT_STOK_OBAT_BULANAN (redesain: per obat × bulan) ════════════════
# grain: 1 obat × 1 bulan → menyambungkan dim_obat. understock/overstock diturunkan dari stok vs reorder_point.
# (Diagram = desain ideal; CSV aktual masih agregat jumlah understock/overstock.)
fact_stok = {
    "title": "Fact_Stok_Obat_Bulanan",
    "top": [],
    "measures": ["stok_akhir", "nilai_konsumsi"],
}
stok_waktu = node("bulan", "root", [
    node("nama_bulan", "desc"),
    node("kuartal", "dim", [node("tahun", "dim")]),
])
stok_obat = node("id_obat", "root", [
    node("kategori_abc", "dim"),
    node("fornas", "dim"),
    node("nama_obat", "desc"),
    node("reorder_point", "desc"),
])
dims_stok = [
    (135, stok_waktu),   # Waktu (kiri-atas)
    (315, stok_obat),    # Obat (kanan-bawah)
]
render(fact_stok, dims_stok, "conceptual_fact_stok_obat_bulanan")
build_drawio(fact_stok, dims_stok, "conceptual_fact_stok_obat_bulanan")


# ════════════════ FACT_PERESEPAN_OBAT (mendukung analitik kepatuhan Fornas) ════════════════
# grain: 1 obat diresepkan per admisi. id_resep = degenerate (BUKAN dim_resep).
# Kepatuhan Fornas diturunkan dari dim_obat.fornas (○), bukan flag fakta.
fact_pres = {
    "title": "Fact_Peresepan_Obat",
    "top": ["id_resep", "id_admisi"],          # degenerate (id_admisi → drill ke klaim)
    "measures": ["jumlah_obat", "biaya_obat"],
}
pres_obat = node("id_obat", "root", [
    node("kategori_abc", "dim"),
    node("fornas", "dim"),                     # status formularium → sumber % kepatuhan Fornas
    node("nama_obat", "desc"),
    node("reorder_point", "desc"),
])
pres_dept = node("id_departemen", "root", [
    node("nama_departemen", "desc"),
    node("jumlah_dokter", "desc"),
])
dims_pres = [
    (90,  make_waktu()),     # Waktu (atas)
    (135, make_pasien()),    # Pasien (NW)
    (225, pres_dept),        # Departemen peresep (SW)
    (305, pres_obat),        # Obat (SE)
]
render(fact_pres, dims_pres, "conceptual_fact_peresepan_obat")
build_drawio(fact_pres, dims_pres, "conceptual_fact_peresepan_obat")
