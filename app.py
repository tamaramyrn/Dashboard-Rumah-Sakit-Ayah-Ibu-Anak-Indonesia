#!/usr/bin/env python3
"""Dashboard BI BPJS Rawat Inap — RSU AIA (Dash by Plotly). Dibuat mirip HTML.
Sidebar, filter Tahun/Kelas/Departemen, 6 halaman. Jalankan: python3 app.py
"""
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from dash import Dash, html, dcc, Input, Output, ctx, ALL, no_update

# Semua teks di chart tebal (ticks, sumbu, anotasi, legenda plotly)
pio.templates["plotly_white"].layout.font.weight = "bold"

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")

# ─────────── STAR SCHEMA — baca dimensi & fakta, lalu JOIN jadi tabel analisis ───────────
def _rd(name):
    return pd.read_csv(os.path.join(D, name + ".csv"))

dim_waktu = _rd("dim_waktu")                                               # kalender (FK tanggal)
dim_icd10 = _rd("dim_icd10").rename(columns={"nama_diagnosis": "diagnosis"})  # dimensi ICD-10
dim_departemen = _rd("dim_departemen").rename(columns={"nama_departemen": "departemen"})
dim_kelas = _rd("dim_kelas")
_kelas_nm = dim_kelas[["id_kelas", "nama_kelas"]].rename(columns={"nama_kelas": "kelas"})
dim_modalitas = _rd("dim_radiologi")
dim_jenis_lab = _rd("dim_lab")
# tarif diambil dari DIMENSI (bukan hardcode) — satu sumber kebenaran
TARIF_KAMAR = dict(zip(dim_kelas.nama_kelas, dim_kelas.tarif_kamar_per_hari))
TARIF_RAD = dict(zip(dim_modalitas.nama_modalitas, dim_modalitas.tarif_per_pemeriksaan))
TARIF_LAB = int(dim_jenis_lab.tarif_per_tes.iloc[0])

# fact_klaim_ri + dimensi → tabel analisis utama 'df'
df = _rd("fact_klaim_ri")
df["tgl_masuk"] = pd.to_datetime(df.tgl_masuk); df["tgl_keluar"] = pd.to_datetime(df.tgl_keluar)
df["tahun"] = df.tgl_masuk.dt.year; df["bulan"] = df.tgl_masuk.dt.month   # turunan dari FK tanggal (dim_waktu)
df = df.merge(dim_icd10, on="kode_icd", how="left")
df = df.merge(dim_departemen, on="id_departemen", how="left")
df = df.merge(_kelas_nm, on="id_kelas", how="left")
# fact_penunjang_diagnostik (LAB + RADIOLOGI disatukan) → flag & ukuran per admisi
_fp = _rd("fact_penunjang_diagnostik")[["id_admisi", "jenis_lab", "jumlah_tes_lab", "modalitas_radiologi", "jumlah_radiologi"]]
df = df.merge(_fp, on="id_admisi", how="left")
df["jumlah_tes_lab"] = df.jumlah_tes_lab.fillna(0).astype(int)
df["jumlah_radiologi"] = df.jumlah_radiologi.fillna(0).astype(int)
df["jenis_lab"] = df.jenis_lab.fillna("")
df["modalitas_radiologi"] = df.modalitas_radiologi.fillna("—")
df["pakai_lab"] = np.where(df.jumlah_tes_lab > 0, "Ya", "Tidak")
df["pakai_radiologi"] = np.where(df.jumlah_radiologi > 0, "Ya", "Tidak")

# fact_operasi + dimensi → 'op'
op = _rd("fact_operasi").merge(dim_departemen, on="id_departemen", how="left").merge(_kelas_nm, on="id_kelas", how="left")
op["tahun"] = pd.to_datetime(op.tgl_operasi).dt.year

# dim_obat (snapshot formularium) + reklasifikasi status stok (>2× titik pesan ulang = Overstock)
obat = _rd("dim_obat")
obat["status_stok"] = np.where(obat.stok_saat_ini > obat.reorder_point * 2, "Overstock",
                               np.where(obat.stok_saat_ini < obat.reorder_point, "Understock", "Normal"))

# fact_okupansi_kamar + dim_kelas → 'bor' ; fact_stok_obat_bulanan → 'stok_ts'
bor = _rd("fact_okupansi_kamar").merge(dim_kelas[["id_kelas", "nama_kelas"]], on="id_kelas", how="left").rename(columns={"nama_kelas": "kode_kelas"})
stok_ts = _rd("fact_stok_obat_bulanan").rename(columns={"jml_understock": "understock", "jml_overstock": "overstock"})

YEARS = sorted(int(y) for y in df["tahun"].unique())
KELASES = ["Semua Kelas"] + dim_kelas.nama_kelas.tolist()
DEPTS = ["Semua Departemen"] + sorted(df["departemen"].unique().tolist())

# Konstanta urutan tampilan (jenis lab & penyebab overrun sudah jadi kolom data dari fakta)
CAUSES = ["Komplikasi saat operasi", "Kesulitan teknis/anatomi", "Masalah anestesi", "Keterlambatan persiapan", "Lainnya"]
LAB_KAT = ["Hematologi", "Kimia Klinik", "Mikrobiologi", "Imunologi", "Urinalisis"]

# Readmisi 30 hari (metrik mutu nyata): admisi ≤30 hari setelah pasien yg sama pulang (dari tanggal asli).
_gap = (df.sort_values(["id_pasien", "tgl_masuk"])
        .pipe(lambda x: (x["tgl_masuk"] - x.groupby("id_pasien")["tgl_keluar"].shift()).dt.days))
df["readmisi_30"] = ((_gap >= 0) & (_gap <= 30)).reindex(df.index)

TEAL, CORAL, INK, AMBER, NAVY = "#0E9F8A", "#E15A3F", "#1F4E79", "#F2A93B", "#0F3B5E"  # INK = biru tua (bukan hitam)
PALETTE = [TEAL, CORAL, NAVY, AMBER, "#7B5EA7", "#3FA7D6", "#E8505B", "#5B8C5A", "#D98E04", "#2D6A8E"]
TINT = {TEAL: "#E8F7F4", CORAL: "#FFF4F0", NAVY: "#E7EEF5", AMBER: "#FEF7E6", INK: "#E7EEF5"}
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def num(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")  # desimal koma (Indonesia)


def rp(n, d=2):
    neg = n < 0; a = abs(n)
    if a >= 1e12: s = "Rp " + num(a / 1e12, 2) + " Triliun"
    elif a >= 1e9: s = "Rp " + num(a / 1e9, d) + " Miliar"
    elif a >= 1e6: s = "Rp " + num(a / 1e6, 1) + " Juta"
    else: s = "Rp " + f"{a:,.0f}".replace(",", ".")
    return ("−" if neg else "") + s


def pid(n, d=1):
    return f"{n:.{d}f}".replace(".", ",") + "%"


def claims(year=None, kelas="Semua Kelas", dept="Semua Departemen"):
    d = df
    if year not in (None, "all"): d = d[d.tahun == year]
    if kelas != "Semua Kelas": d = d[d.kelas == kelas]
    if dept != "Semua Departemen": d = d[d.departemen == dept]
    return d


def surg(year=None, kelas="Semua Kelas", dept="Semua Departemen"):
    o = op
    if year not in (None, "all"): o = o[o.tahun == year]
    if kelas != "Semua Kelas": o = o[o.kelas == kelas]
    if dept != "Semua Departemen": o = o[o.departemen == dept]
    return o


# ── SATU SUMBER KEBENARAN ── semua halaman pakai fungsi ini agar angka untuk hal yang sama IDENTIK.
def fin(d):
    """Metrik finansial kanonik dari fact_klaim_ri (shortfall < 0 = rugi)."""
    biaya = float(d.biaya_riil.sum()); tarif = float(d.tarif_inacbg.sum())
    sf = float(d.shortfall.sum()); n = len(d)
    rate = abs(sf / biaya * 100) if biaya else 0           # % kerugian thd biaya riil
    covered = tarif / biaya * 100 if biaya else 0          # % biaya yg diganti BPJS
    per_adm = sf / n if n else 0                           # rugi rata-rata per admisi (negatif)
    return {"biaya": biaya, "tarif": tarif, "sf": sf, "n": n, "rate": rate, "covered": covered, "per_adm": per_adm}


def alos_kerugian(d):
    """Kerugian akibat lama rawat melebihi paket BPJS — DITURUNKAN dari data, bukan konstanta.
    pct = bagian kerugian yg terkait hari-ekstra; rupiah = pct × kerugian NET (subset dari total
    kerugian di Ringkasan, jadi tidak akan pernah melebihinya)."""
    if not len(d): return 0.0, 0.0
    daily = d.biaya_riil / d.los_hari.clip(lower=1)
    cost_extra = (d.los_hari - d.los_paket_bpjs).clip(lower=0) * daily
    loss = d.shortfall.clip(upper=0).abs()                 # rugi per admisi (kotor, positif)
    attrib = float(pd.concat([cost_extra, loss], axis=1).min(axis=1).sum())
    gross_loss = float(loss.sum())
    pct = 100 * attrib / gross_loss if gross_loss else 0   # % rugi yg terkait lama rawat berlebih
    net_loss = abs(float(d.shortfall.sum()))               # = "kerugian" headline Ringkasan
    return pct / 100 * net_loss, pct                       # rupiah ≤ kerugian net (konsisten)


def style(fig, h=320, legend=True):
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=8, r=8, t=14, b=8),
                      font=dict(family="Plus Jakarta Sans, sans-serif", size=12, color=INK),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      separators=",.",  # desimal koma, ribuan titik (Indonesia)
                      showlegend=legend, legend=dict(orientation="h", y=1.16, x=1, xanchor="right"),
                      hoverlabel=dict(bordercolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    fig.update_xaxes(showgrid=False, showline=False)
    fig.update_yaxes(gridcolor="rgba(14,27,44,.07)", zeroline=False)
    fig.update_traces(marker_cornerradius=7, selector=dict(type="bar"))  # batang membulat
    return fig


def card(title, fig, cls="card", h=320, legend=True):
    return html.Div(className=cls, children=[html.Div(title, className="card-title"),
                    dcc.Graph(figure=style(fig, h, legend), config={"displayModeBar": False})])


def legend_item(color, label, line=False):
    sym = html.Span(className="lg-line" if line else "lg-dot", style={"background": color})
    return html.Span([sym, label], className="lg-item")


def card_lg(title, fig, items, h=320):
    return html.Div(className="card", children=[
        html.Div(className="card-head", children=[
            html.Div(title, className="card-title", style={"marginBottom": "0"}),
            html.Div(items, className="card-legend")]),
        dcc.Graph(figure=style(fig, h, legend=False), config={"displayModeBar": False})])


def hbar(labels, vals, color):
    f = go.Figure(go.Bar(y=labels, x=vals, orientation="h", marker_color=color, marker_line_width=0))
    f.update_layout(yaxis=dict(autorange="reversed"))
    return f


def vbar(labels, vals, color, text=None):
    return go.Figure(go.Bar(x=labels, y=vals, marker_color=color, marker_line_width=0,
                            text=text, textposition="outside"))


def donut(labels, vals, colors=None):
    return go.Figure(go.Pie(labels=labels, values=vals, hole=.58,
                            marker=dict(colors=colors or PALETTE), texttemplate="<b>%{percent}</b>", textposition="inside"))


def card_donut(title, labels, vals, colors=None, h=320, topn=None):
    if topn and len(labels) > topn:
        labels = labels[:topn] + ["Lainnya"]
        vals = vals[:topn] + [sum(vals[topn:])]
    fig = go.Figure(go.Pie(labels=labels, values=vals, hole=.58, sort=False,
                           marker=dict(colors=colors or PALETTE, line=dict(color="#FFFFFF", width=2)),
                           texttemplate="<b>%{percent}</b>", textposition="inside", textfont=dict(weight="bold", size=11),
                           hovertemplate="%{label}: %{value:,} (%{percent})<extra></extra>"))
    fig.update_layout(template="plotly_white", height=h, margin=dict(l=8, r=8, t=8, b=8),
                      font=dict(family="Plus Jakarta Sans, sans-serif", size=11, color=INK),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
                      showlegend=True, legend=dict(orientation="h", y=-0.06, x=0.5, xanchor="center", font=dict(size=10.5)),
                      hoverlabel=dict(bordercolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    return html.Div(className="card", children=[html.Div(title, className="card-title"),
                    dcc.Graph(figure=fig, config={"displayModeBar": False})])


# ── komponen ala HTML ──
def bar_item(label, value, pct, color, note=None):
    ch = [html.Div([html.Span(label, className="bar-label"), html.Span(value, className="bar-value")], className="bar-head"),
          html.Div(html.Div(className="bar-fill", style={"width": f"{min(pct,100)}%", "background": color}), className="bar-track")]
    if note: ch.append(html.Div(note, className="bar-note"))
    return html.Div(className="bar-item", children=ch)


def mod(label, value, sub, color, page=None):
    kids = [html.Div(label, className="mod-label"),
            html.Div(value, className="mod-value", style={"color": color}), html.Div(sub, className="mod-sub")]
    if page:  # card bisa diklik → buka page terkait
        return html.Div(className="mod mod-link", id={"type": "navcard", "page": page}, n_clicks=0, children=kids)
    return html.Div(className="mod", children=kids)


def head_stat(label, value, sub, color, badge=None, badge_bg="#FFF4F0"):
    val = [html.Span(value, className="head-stat-val", style={"color": color})]
    if badge:
        val.append(html.Span(badge, className="head-badge", style={"color": color, "background": badge_bg}))
    return html.Div(className="head-col bl", children=[
        html.Div(label, className="head-label"),
        html.Div(val, className="head-stat-wrap"),
        html.Div(sub, className="head-sub")])


# ════════════════════ HALAMAN ════════════════════
def page_ringkasan(year, kelas, dept):
    d = claims(year, kelas, dept)
    F = fin(d); sf, by, tf, rate, covered = F["sf"], F["biaya"], F["tarif"], F["rate"], F["covered"]
    appr = 100 * (d.status_klaim == "Disetujui").mean()
    alos = float(d.los_hari.mean()) if len(d) else 0          # Operasional Bangsal
    o_sum = surg(year, kelas, dept)                            # Kamar Operasi
    op_over = 100 * (o_sum.durasi_menit > o_sum.durasi_rencana_menit).mean() if len(o_sum) else 0
    fornas = 100 * (d.fornas == "Ya").mean()                   # Farmasi & Obat
    lab = 100 * (d.pakai_lab == "Ya").mean()                   # Lab & Radiologi
    kronis = 100 * (d.kategori_penyakit == "Kronis").mean()    # Profil Pasien
    head = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("tahun buku", className="head-label"),
            html.Div("2020–25" if year == "all" else str(year), className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else "1 Jan – 31 Des", className="head-sub")]),
        head_stat("biaya riil RS", rp(by), "Total Biaya Pelayanan", INK),
        head_stat("diganti BPJS", rp(tf), "Berdasarkan Hasil Klaim BPJS", TEAL, pid(covered), "#E8F7F4"),
        head_stat("kerugian (ditanggung RS)", rp(sf), "Selisih dari Tarif INA-CBGs", CORAL, pid(rate))])
    # Tren ikut filter. "Semua Tahun" -> per tahun; tahun spesifik -> per bulan. Sumbu kiri auto-fit.
    if year == "all":
        m = d.groupby("tahun").agg(b=("biaya_riil", "sum"), t=("tarif_inacbg", "sum"), s=("shortfall", "sum"))
        months = [str(int(y)) for y in m.index]
    else:
        m = d.groupby("bulan").agg(b=("biaya_riil", "sum"), t=("tarif_inacbg", "sum"), s=("shortfall", "sum")).reindex(range(1, 13))
        m = m[m.b.notna() & (m.b > 0)]  # buang bulan tanpa data biar tidak ada gap
        months = [BULAN[i - 1] for i in m.index]
    sh = (m.s / m.b * 100)
    bmax = float(m.b.max()) if len(m) else 0.0
    div, unit = (1e9, " M") if bmax >= 1e9 else (1e6, " Jt")  # satuan otomatis
    fig = go.Figure()
    fig.add_bar(x=months, y=m.b / div, name="Biaya Riil", marker_color=INK,
                hovertemplate="<b>Biaya Riil</b>: Rp %{y:.1f}" + unit + "<extra></extra>")
    fig.add_bar(x=months, y=m.t / div, name="INA-CBGs", marker_color=TEAL,
                hovertemplate="<b>INA-CBGs</b>: Rp %{y:.1f}" + unit + "<extra></extra>")
    fig.add_scatter(x=months, y=sh, name="Kerugian %", yaxis="y2",
                    line=dict(color=CORAL, width=3), mode="lines+markers",
                    marker=dict(size=6, line=dict(width=2, color="#FFFFFF")),
                    hovertemplate="<b>Kerugian</b>: %{y:.1f}%<extra></extra>")
    shv = sh.dropna()
    if len(shv):
        # range ikut data — jangan dipaksa mentok 0, krn saat difilter bisa ada periode surplus (>0%)
        sp = max(float(shv.max() - shv.min()), 4.0); pad = sp * 0.35
        r2 = [float(shv.min()) - pad, max(float(shv.max()) + pad, 0)]
    else:
        r2 = [-20, 0]
    fig.update_layout(yaxis=dict(tickprefix="Rp ", ticksuffix=unit, gridcolor="rgba(14,27,44,.07)", rangemode="tozero", nticks=6),
                      yaxis2=dict(overlaying="y", side="right", showgrid=False, ticksuffix="%", range=r2, nticks=6),
                      barmode="group", bargap=0.3, bargroupgap=0.06, hovermode="x unified")
    mods = html.Div(className="mod-row", children=[
        mod("klaim", pid(appr), "Klaim disetujui", TEAL, page="klaim"),
        mod("bangsal", num(alos) + " hari", "Rata-rata lama rawat", AMBER, page="mutu"),
        mod("operasi", pid(op_over), "Operasi lewat rencana", CORAL, page="operasi"),
        mod("farmasi", pid(fornas), "Resep Fornas", NAVY, page="obat"),
        mod("lab & radiologi", pid(lab), "Pasien pakai lab", TEAL, page="penunjang"),
        mod("profil", pid(kronis), "Pasien kronis", CORAL, page="profil")])
    leg = [legend_item(INK, "Biaya Riil"), legend_item(TEAL, "INA-CBGs"), legend_item(CORAL, "Kerugian %", line=True)]
    judul = f"Tren Klaim BPJS Rawat Inap {'2020–2025' if year == 'all' else year}"
    if kelas != "Semua Kelas": judul += f" · {kelas}"
    if dept != "Semua Departemen": judul += f" · {dept}"
    trend = card_lg(judul, fig, leg, h=360)
    # tren pakai hover gabungan (x unified) → 1 kotak utk banyak garis, beri bg solid navy biar tak transparan
    fig.update_layout(hoverlabel=dict(bgcolor="#1F4E79", bordercolor="#1F4E79",
                                      font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    return [head, mods, trend]


def kl_stat(label, value, color):
    return html.Div(className="kl-stat", children=[
        html.Span(label, className="kl-stat-label"),
        html.Span(value, className="kl-stat-val", style={"color": color})])


def status_row(label, count, pct, nominal, color, note=None):
    ch = [
        html.Div(className="kl-status-head", children=[
            html.Span(label, className="kl-status-label"),
            html.Div(className="kl-status-meta", children=[
                html.Span(f"{count:,} klaim", className="kl-status-count"),
                html.Span(rp(nominal, 1), className="kl-status-val", style={"color": color}),
                html.Span(pid(pct), className="kl-status-pct", style={"color": color})])]),
        html.Div(className="kl-bar", children=html.Div(className="kl-bar-fill", style={"width": f"{pct}%", "background": color}))]
    if note:
        ch.append(html.Div(note, className="kl-status-note"))
    return html.Div(children=ch)


def rank_row(i, name, barpct, val):
    return html.Div(className="kl-rank", children=[
        html.Span(f"{i:02d}", className="kl-rank-no"),
        html.Div(name, className="kl-rank-name", title=name),
        html.Div(className="kl-rank-bar", children=html.Div(className="kl-rank-bar-fill", style={"width": f"{barpct}%"})),
        html.Div(val, className="kl-rank-val")])


def decomp_row(label, pct, nominal, color):
    return html.Div(children=[
        html.Div(className="kl-d-head", children=[
            html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": color}), html.Span(label, className="kl-d-label")]),
            html.Div(className="kl-d-right", children=[html.Span(f"{pct}%", className="kl-d-pct"), html.Span(rp(-nominal, 1), className="kl-d-val")])]),
        html.Div(className="kl-d-bar", children=html.Div(className="kl-d-bar-fill", style={"width": f"{pct}%", "background": color}))])


def cat_row(label, pct, nominal, color):
    return html.Div(children=[
        html.Div(className="kl-d-head", children=[
            html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": color}), html.Span(label, className="kl-d-label")]),
            html.Div(className="kl-d-right", children=[html.Span(f"{pct:.0f}%", className="kl-d-pct"), html.Span(rp(nominal, 1), className="kl-d-val", style={"color": "#1F4E79"})])]),
        html.Div(className="kl-d-bar", children=html.Div(className="kl-d-bar-fill", style={"width": f"{pct}%", "background": color}))])


def cat_legend(label, nominal, color, pct=None):
    val = rp(nominal, 1) if pct is None else f"{num(pct)}% · {rp(nominal, 1)}"
    return html.Div(className="kl-d-head", children=[
        html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": color}), html.Span(label, className="kl-d-label")]),
        html.Span(val, className="kl-d-val", style={"color": "#1F4E79"})])


def cnt_legend(label, n, color):
    return html.Div(className="kl-d-head", children=[
        html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": color}), html.Span(label, className="kl-d-label")]),
        html.Span(f"{ribu(n)} admisi", className="kl-d-val", style={"color": "#1F4E79"})])


def page_klaim(year, kelas, dept):
    d = claims(year, kelas, dept)
    F = fin(d); n, sf_total, biaya, tarif = F["n"], F["sf"], F["biaya"], F["tarif"]
    appr = 100 * (d.status_klaim == "Disetujui").mean() if n else 0
    rej = 100 * (d.status_klaim == "Ditolak").mean() if n else 0
    ytxt = "2020–2025" if year == "all" else year
    setuju = round(n * appr / 100); tolak = round(n * rej / 100); pending = n - setuju - tolak
    pend_pct = 100 * pending / n if n else 0
    # Header KPI (ala Ringkasan) — biaya riil, diganti BPJS, kerugian
    head = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("total klaim", className="head-label"),
            html.Div(f"{n:,}", className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else f"Tahun {ytxt}", className="head-sub")]),
        head_stat("biaya riil RS", rp(biaya), "Total biaya pelayanan", INK),
        head_stat("diganti BPJS", rp(tarif), "Berdasarkan tarif INA-CBGs", TEAL, pid(F["covered"]), "#E8F7F4"),
        head_stat("kerugian (ditanggung RS)", rp(sf_total), "Selisih dari tarif INA-CBGs", CORAL, pid(F["rate"]))])
    # Card B — Status Klaim
    statuses = [
        ("Disetujui", setuju, appr, tarif * appr / 100, TEAL),
        ("Ditolak", tolak, rej, -biaya * rej / 100, CORAL),
        ("Pending", pending, pend_pct, biaya * pend_pct / 100, "#7D8898")]
    cardB = html.Div(className="card", children=[
        html.Div("status klaim rawat inap", className="card-title"),
        html.Div(className="kl-status-list", children=[status_row(*s) for s in statuses])])
    # Card C — Top 10 diagnosis penyumbang kerugian (bar horizontal ala "kelebihan menit per departemen")
    g = d.groupby("diagnosis").agg(sf=("shortfall", "sum")).sort_values("sf").head(10)
    names = g.index.tolist(); loss = g.sf.abs().tolist()
    f_diag = go.Figure(go.Bar(y=names, x=loss, orientation="h", marker_color=CORAL, marker_line_width=0,
                              text=[rp(v, 1) for v in g.sf], textposition="outside", cliponaxis=False,
                              textfont=dict(weight="bold", color=INK, size=12),
                              hovertemplate="%{y}<br>%{text}<extra></extra>"))
    f_diag.update_layout(yaxis=dict(autorange="reversed"),
                         xaxis=dict(range=[0, max(loss) * 1.3] if loss else None, showticklabels=False))
    cardC = html.Div(className="card", children=[
        html.Div("top 10 diagnosis penyumbang kerugian", className="card-title"),
        dcc.Graph(figure=style(f_diag, 280, legend=False), config={"displayModeBar": False})])
    # Card D — Kategorisasi Biaya (dari data nyata). Semua komponen biaya riil masuk sini.
    akom = float((d.los_hari * d.kelas.map(TARIF_KAMAR)).sum())   # tarif kamar ← dim_kelas
    operasi = float(surg(year, kelas, dept).biaya_operasi.sum())
    labc = float(d.jumlah_tes_lab.sum()) * TARIF_LAB              # tarif ← dim_jenis_lab
    radc = float((d.jumlah_radiologi * d.modalitas_radiologi.map(TARIF_RAD).fillna(0)).sum())  # ← dim_modalitas
    lainnya = max(biaya - akom - operasi - labc - radc, 0.0)
    cats = sorted([("Kamar Operasi", operasi, TEAL), ("Akomodasi Kamar", akom, NAVY),
                   ("Laboratorium", labc, AMBER), ("Radiologi", radc, "#3FA7D6"),
                   ("Obat & Tindakan", lainnya, "#7B5EA7")], key=lambda x: -x[1])
    cc = [c[2] for c in cats]
    catfig = go.Figure(go.Pie(
        labels=[c[0] for c in cats], values=[c[1] for c in cats], hole=.5, sort=False,
        marker=dict(colors=cc, line=dict(color="#FFFFFF", width=2)),
        customdata=[rp(c[1], 1) for c in cats], texttemplate="<b>%{percent}</b>", textposition="inside",
        insidetextorientation="horizontal", textfont=dict(weight="bold", size=12, color="#FFFFFF"),
        hovertemplate="<b>%{label}</b><br>%{percent} · %{customdata}<extra></extra>",
        hoverlabel=dict(bgcolor=cc, bordercolor=cc, font=dict(color="#FFFFFF", size=12.5))))
    catfig.update_layout(uniformtext=dict(minsize=10, mode="hide"))  # sembunyikan label yg kekecilan
    tot_cat = sum(c[1] for c in cats) or 1
    def _shrp(v): return rp(v, 1).replace(" Miliar", " M").replace(" Juta", " Jt")
    leg_items = [html.Div(className="kl-d-head", style={"alignItems": "center"}, children=[
        html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": col}),
            html.Span(lbl, className="kl-d-label", style={"whiteSpace": "nowrap"})]),
        html.Span(_shrp(val), className="kl-d-val",
                  style={"color": "#1F4E79", "whiteSpace": "nowrap"})]) for lbl, val, col in cats]
    cardD = html.Div(className="card", style={"display": "flex", "flexDirection": "column"}, children=[
        html.Div("kategorisasi biaya", className="card-title"),
        html.Div(style={"display": "grid", "gridTemplateColumns": "0.9fr 1.1fr", "columnGap": "6px",
                        "alignItems": "center", "flex": "1"},
                 children=[
                     dcc.Graph(figure=style(catfig, 250, legend=False), config={"displayModeBar": False}),
                     html.Div(style={"display": "flex", "flexDirection": "column", "gap": "15px", "justifyContent": "center"},
                              children=leg_items)]),
        html.Div(className="kl-decomp-total", children=[html.Span("Total Biaya Riil Rumah Sakit"),
            html.Span(rp(biaya), className="kl-decomp-totval", style={"color": "#1F4E79", "background": "#E7EEF5"})]),
        html.Div(className="kl-decomp-total", children=[html.Span("Total Biaya Ditanggung BPJS"),
            html.Span(f"{pid(F['covered'])} · {rp(tarif)}", className="kl-decomp-totval", style={"color": "#0E9F8A", "background": "#E8F7F4"})])])
    return [head, html.Div(className="g-7-5", children=[
        html.Div(children=[cardB, cardC]),
        cardD])]


def metric_bar(label, value, color, fill, target=None, note=None):
    bar = [html.Div(className="mb-fill", style={"width": f"{min(max(fill, 0), 100)}%", "background": color})]
    if target is not None:
        bar.append(html.Div(className="mb-target", style={"left": f"{min(max(target, 0), 100)}%"}))
    ch = [html.Div(label, className="mb-label"), html.Div(value, className="mb-value", style={"color": color}),
          html.Div(className="mb-track", children=bar)]
    if note:
        ch.append(html.Div(note, className="mb-note"))
    return html.Div(className="card mb-card", children=ch)


def dept_gap_row(name, ak, pk, gap, maxd):
    return html.Div(className="dg-row", children=[
        html.Div(name, className="dg-name"),
        html.Div(f"{num(ak)}h vs {num(pk)}h", className="dg-meta"),
        html.Div(className="dg-bar", children=[
            html.Div(style={"width": f"{pk/maxd*100}%", "background": TEAL, "height": "100%"}),
            html.Div(style={"width": f"{max(gap,0)/maxd*100}%", "background": CORAL, "height": "100%"})]),
        html.Div(f"+{num(gap)}h", className="dg-gap")])


def bor_row(kelas, val):
    color = CORAL if val > 90 else (AMBER if val > 85 else TEAL)
    return html.Div(children=[
        html.Div(className="kl-status-head", children=[
            html.Span(kelas, className="kl-status-label"),
            html.Span(pid(val), className="kl-status-pct", style={"color": color})]),
        html.Div(className="kl-bar", children=html.Div(className="kl-bar-fill", style={"width": f"{min(val,100)}%", "background": color}))])


def ribu(x):
    return f"{x:,.0f}".replace(",", ".")  # ribuan titik (Indonesia)


def dx_row(name, extra, maxe):
    # baris diagnosis ringkas: nama, bar total hari ekstra, label total hari ekstra
    return html.Div(className="dg-row", style={"gridTemplateColumns": "1.5fr 2.4fr auto"}, children=[
        html.Div(name, className="dg-name"),
        html.Div(className="dg-bar", children=[
            html.Div(style={"width": f"{extra/maxe*100 if maxe else 0}%", "background": CORAL, "height": "100%"})]),
        html.Div(f"+{ribu(extra)} hari", className="dg-gap")])


def page_mutu(year, kelas, dept):
    d = claims(year, kelas, dept)
    alos = float(d.los_hari.mean()) if len(d) else 0
    paket = float(d.los_paket_bpjs.mean()) if len(d) else 0
    lewat = 100 * (d.los_hari > d.los_paket_bpjs).mean() if len(d) else 0  # % admisi lama rawat di atas paket
    alos_loss, alos_pct = alos_kerugian(d)  # diturunkan dari data, bukan konstanta
    ytxt = "2020–25" if year == "all" else str(year)
    head = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("tahun buku", className="head-label"),
            html.Div(ytxt, className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else "1 Jan – 31 Des", className="head-sub")]),
        head_stat("rata-rata lama rawat", f"{num(alos)} hari", f"Paket BPJS {num(paket)} hari", CORAL, f"+{num(alos - paket)}h"),
        head_stat("admisi lewat paket", pid(lewat), "Lama rawat di atas paket BPJS", CORAL if lewat > 50 else AMBER),
        head_stat("kerugian karena ALOS", rp(-alos_loss), "Dari kelebihan hari rawat", CORAL, f"{alos_pct:.0f}%")])
    # Tren ikut filter (ala Ringkasan): "Semua Tahun" -> per tahun; tahun spesifik -> per bulan.
    if year == "all":
        m = d.groupby("tahun").agg(ak=("los_hari", "mean"), pk=("los_paket_bpjs", "mean"))
        months = [str(int(y)) for y in m.index]
    else:
        m = d.groupby("bulan").agg(ak=("los_hari", "mean"), pk=("los_paket_bpjs", "mean")).reindex(range(1, 13))
        m = m[m.ak.notna()]
        months = [BULAN[i - 1] for i in m.index]
    gap = (m.ak - m.pk).clip(lower=0)
    gmax = float(gap.max()) if len(gap) else 1.0
    f1 = go.Figure()
    f1.add_bar(x=months, y=m.ak, name="ALOS Aktual", marker_color=INK,
               hovertemplate="<b>ALOS Aktual</b>: %{y:.1f} hr<extra></extra>")
    f1.add_bar(x=months, y=m.pk, name="Paket BPJS", marker_color=TEAL,
               hovertemplate="<b>Paket BPJS</b>: %{y:.1f} hr<extra></extra>")
    f1.add_scatter(x=months, y=gap, name="Kelebihan hari", yaxis="y2",
                   line=dict(color=CORAL, width=3), mode="lines+markers",
                   marker=dict(size=6, line=dict(width=2, color="#FFFFFF")),
                   hovertemplate="<b>Kelebihan</b>: +%{y:.1f} hr<extra></extra>")
    f1.update_layout(yaxis=dict(ticksuffix=" hari", gridcolor="rgba(14,27,44,.07)", rangemode="tozero", nticks=6),
                     yaxis2=dict(overlaying="y", side="right", showgrid=False, ticksuffix=" hari", range=[0, gmax * 2.4], nticks=6),
                     barmode="group", bargap=0.3, bargroupgap=0.06, hovermode="x unified")
    judul = f"Tren Lama Rawat Inap {'2020–2025' if year == 'all' else year}"
    if kelas != "Semua Kelas": judul += f" · {kelas}"
    if dept != "Semua Departemen": judul += f" · {dept}"
    cardTrend = card_lg(judul, f1, [legend_item(INK, "ALOS Aktual"), legend_item(TEAL, "Paket BPJS"),
                                    legend_item(CORAL, "Kelebihan hari", line=True)], h=160)
    f1.update_layout(hoverlabel=dict(bgcolor="#1F4E79", bordercolor="#1F4E79",
                                     font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    # Overrun lama rawat per diagnosis — total hari di luar paket (volume × selisih) = fokus clinical pathway
    od = d.copy()
    od["over"] = (od.los_hari - od.los_paket_bpjs).clip(lower=0)
    rd = od.groupby("diagnosis").over.sum().sort_values(ascending=False).head(5)
    f_read = go.Figure(go.Bar(y=rd.index.tolist(), x=rd.values, orientation="h", marker_color=CORAL, marker_line_width=0,
                              text=["+" + ribu(v) + " hari" for v in rd.values], textposition="auto", insidetextanchor="end",
                              textfont=dict(weight="bold", color="#FFFFFF", size=12.5)))
    f_read.update_layout(yaxis=dict(autorange="reversed"),
                         xaxis=dict(range=[0, float(rd.max()) * 1.3] if len(rd) else None, showticklabels=False))
    cardDx = html.Div(className="card", children=[
        html.Div("kelebihan lama rawat per diagnosis", className="card-title"),
        html.Div("Total hari rawat di luar paket BPJS",
                 style={"fontSize": "11.5px", "color": "#7D8898", "fontWeight": "600", "marginTop": "-4px", "marginBottom": "14px"}),
        dcc.Graph(figure=style(f_read, 185, legend=False), config={"displayModeBar": False})])
    # BOR (tingkat hunian tempat tidur) per kelas — metrik operasional bangsal, lepas dari ALOS
    if year == "all":
        bser = bor.groupby("kode_kelas").bor.mean()
    else:
        bser = bor[bor.tahun == year].set_index("kode_kelas").bor
    bser = bser.reindex(["VIP", "Kelas 1", "Kelas 2", "Kelas 3"]).dropna()

    def _borcol(v):
        if v > 90: return CORAL      # overload
        if v > 85: return AMBER      # padat (di atas ideal)
        if v >= 60: return TEAL      # ideal
        return NAVY                  # sepi (di bawah ideal)
    bcol = [_borcol(v) for v in bser.values]
    f_bor = go.Figure(go.Bar(x=bser.index.tolist(), y=bser.values, marker_color=bcol, marker_line_width=0,
                             text=[pid(v, 0) for v in bser.values], textposition="outside",
                             textfont=dict(weight="bold", size=12.5, color=INK),
                             hovertemplate="<b>%{x}</b><br>BOR: %{y:.1f}%<extra></extra>"))
    f_bor.update_layout(yaxis=dict(ticksuffix="%", range=[0, 109], showticklabels=False), xaxis=dict(title=None))
    bor_legend = html.Div(style={"display": "flex", "gap": "14px", "flexWrap": "wrap", "marginTop": "4px"}, children=[
        legend_item(TEAL, "Ideal 60–85%"), legend_item(AMBER, "Padat 85–90%"),
        legend_item(CORAL, "Overload >90%"), legend_item(NAVY, "Sepi <60%")])
    cardDept = html.Div(className="card", children=[
        html.Div("tingkat hunian tempat tidur (BOR) per kelas", className="card-title"),
        csub("Standar ideal Kemenkes: 60–85%"),
        dcc.Graph(figure=style(f_bor, 158, legend=False), config={"displayModeBar": False}),
        bor_legend])
    return [head, cardTrend, html.Div(className="grid2", children=[cardDx, cardDept])]


def ok_row(ruang, count, jam, util, color):
    return html.Div(children=[
        html.Div(className="kl-status-head", children=[
            html.Span(ruang, className="kl-status-label"),
            html.Div(className="kl-status-meta", children=[
                html.Span(f"{count:,} operasi", className="kl-status-count"),
                html.Span(f"{jam:,.0f} jam", className="kl-status-count"),
                html.Span(pid(util), className="kl-status-pct", style={"color": color})])]),
        html.Div(className="kl-bar", children=html.Div(className="kl-bar-fill", style={"width": f"{util}%", "background": color}))])


def page_operasi(year, kelas, dept):
    o = surg(year, kelas, dept)
    if not len(o):
        return [html.Div("Tidak ada data operasi untuk filter ini", className="card", style={"textAlign": "center", "color": "#7D8898"})]
    o = o.copy()
    o["over_min"] = (o.durasi_menit - o.durasi_rencana_menit).clip(lower=0)        # menit melebihi rencana
    o["over_cost"] = o.over_min * (o.biaya_operasi / o.durasi_menit.clip(lower=1))  # biaya menit ekstra (proxy)
    biaya_tot = float(o.biaya_operasi.sum())
    n_over = int((o.over_min > 0).sum())
    pct_over = 100 * n_over / len(o)
    biaya_over = float(o.over_cost.sum())
    # Header ala halaman lain (head-row r4): tahun + 3 metrik kunci
    ytxt = "2020–25" if year == "all" else str(year)
    kpis = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("tahun buku", className="head-label"),
            html.Div(ytxt, className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else "1 Jan – 31 Des", className="head-sub")]),
        head_stat("total operasi", ribu(len(o)), "Tindakan operasi pasien BPJS", INK),
        head_stat("operasi melebihi rencana", pid(pct_over), f"{ribu(n_over)} operasi",
                  CORAL if pct_over > 25 else AMBER),
        head_stat("estimasi biaya kelebihan", rp(-biaya_over), "Kelebihan Menit Operasi", CORAL)])

    over = o[o.over_min > 0]  # hanya operasi yang molor

    # C1 — penyebab overrun → DONUT + legend (apanya yang bikin molor)
    pc = over.penyebab_overrun.value_counts().reindex(CAUSES).fillna(0)
    ptot = float(pc.sum()) or 1
    pcol = [CORAL, AMBER, "#7B5EA7", NAVY, "#9AA6B2"]
    f_pen = go.Figure(go.Pie(labels=CAUSES, values=pc.values, hole=.6, sort=False,
                             marker=dict(colors=pcol, line=dict(color="#FFFFFF", width=2)),
                             texttemplate="<b>%{percent}</b>", textposition="inside", insidetextorientation="horizontal",
                             textfont=dict(weight="bold", size=11, color="#FFFFFF"),
                             hovertemplate="%{label}<br>%{value:,} operasi · %{percent}<extra></extra>"))
    f_pen.update_layout(template="plotly_white", height=168, margin=dict(l=4, r=4, t=4, b=4),
                        font=dict(family="Plus Jakarta Sans, sans-serif", size=11, color=INK),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.", showlegend=False,
                        hoverlabel=dict(bordercolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    pen_legend = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "11px", "justifyContent": "center"},
                          children=[html.Div(className="kl-d-head", children=[
                              html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": pcol[i]}),
                                                                        html.Span(CAUSES[i], className="kl-d-label")]),
                              html.Span(pid(pc.values[i] / ptot * 100), className="kl-d-val", style={"color": "#1F4E79"})]) for i in range(len(CAUSES))])
    cardPen = html.Div(className="card", children=[
        html.Div("penyebab operasi melebihi rencana", className="card-title"),
        csub("Dari operasi yang melebihi durasi rencana"),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1.15fr", "columnGap": "14px", "alignItems": "center"},
                 children=[dcc.Graph(figure=f_pen, config={"displayModeBar": False}), pen_legend])])

    # C2 — overrun elektif vs cito → GAUGE (beda dari bar, tetap gampang)
    gs = o.groupby("sifat").agg(rate=("over_min", lambda s: 100 * (s > 0).mean())).reindex(["Elektif", "Cito"]).fillna(0)
    er, cr = float(gs.rate["Elektif"]), float(gs.rate["Cito"])
    f_sf = go.Figure(go.Bar(x=["Terjadwal", "Darurat"], y=[er, cr], marker_color=[TEAL, CORAL], marker_line_width=0,
                            text=[pid(er), pid(cr)], textposition="outside", textfont=dict(weight="bold", size=14, color=INK),
                            hovertemplate="%{x}<br>Molor: %{y:.1f}% operasi<extra></extra>"))
    f_sf.update_layout(yaxis=dict(range=[0, max(er, cr) * 1.25 if max(er, cr) else 1], ticksuffix="%"))
    cardSifat = html.Div(className="card", children=[
        html.Div("operasi dengan durasi berlebih: terjadwal dan darurat", className="card-title"),
        csub("Berapa % operasi yang durasinya lewat rencana"),
        dcc.Graph(figure=style(f_sf, 168, legend=False), config={"displayModeBar": False})])

    # C3 — rata-rata kelebihan durasi per departemen → bar horizontal sederhana
    gd = o.groupby("departemen").over_min.mean().sort_values(ascending=False).head(6)
    f_dept = go.Figure(go.Bar(y=gd.index.tolist(), x=gd.values, orientation="h", marker_color=CORAL, marker_line_width=0,
                              text=[f"{m:.0f} menit" for m in gd.values], textposition="auto", insidetextanchor="end",
                              textfont=dict(weight="bold", color="#FFFFFF", size=12.5)))
    f_dept.update_layout(yaxis=dict(autorange="reversed"),
                         xaxis=dict(range=[0, float(gd.max()) * 1.2] if len(gd) else None, showticklabels=False))
    cardDept = html.Div(className="card", children=[
        html.Div("kelebihan menit per departemen", className="card-title"),
        csub("Prioritas audit klinis"),
        dcc.Graph(figure=style(f_dept, 168, legend=False), config={"displayModeBar": False})])

    # C4 — biaya kelebihan per jenis operasi → FUNNEL (urut dari yg terbesar)
    gc = o.groupby("jenis_operasi").over_cost.sum().sort_values(ascending=False).head(6)
    fcol = [PALETTE[i % len(PALETTE)] for i in range(len(gc))]
    f_cost = go.Figure(go.Funnel(y=gc.index.tolist(), x=gc.values.tolist(),
                                 text=[rp(v, 1) for v in gc.values], textinfo="text",
                                 textposition="inside", textfont=dict(weight="bold", color="#FFFFFF", size=12),
                                 marker=dict(color=fcol), connector=dict(fillcolor="rgba(0,0,0,0)", line=dict(width=0)),
                                 hovertemplate="%{y}<br>%{text}<extra></extra>"))
    f_cost.update_layout(height=168, margin=dict(l=4, r=4, t=6, b=6), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                         font=dict(family="Plus Jakarta Sans, sans-serif", size=11, color=INK), separators=",.",
                         yaxis=dict(showticklabels=True),
                         hoverlabel=dict(bordercolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    cardCost = html.Div(className="card", children=[
        html.Div("biaya kelebihan per jenis operasi", className="card-title"),
        csub("Biaya menit ekstra di luar paket INA-CBGs"),
        dcc.Graph(figure=f_cost, config={"displayModeBar": False})])

    return [kpis,
            html.Div(className="g-7-5", children=[cardPen, cardSifat]),
            html.Div(className="g-7-5", children=[cardDept, cardCost])]


def page_obat(year, kelas, dept):
    d = claims(year, kelas, dept)
    F = fin(d); n_tot = F["n"]
    fornas_pct = 100 * (d.fornas == "Ya").mean() if n_tot else 0
    nonf_pct = 100 - fornas_pct
    n_fornas = int((d.fornas == "Ya").sum()); n_nonf = n_tot - n_fornas
    n_under = int((obat.status_stok == "Understock").sum())
    n_over = int((obat.status_stok == "Overstock").sum())
    ytxt = "2020–25" if year == "all" else str(year)
    head = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("tahun buku", className="head-label"),
            html.Div(ytxt, className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else "1 Jan – 31 Des", className="head-sub")]),
        head_stat("biaya obat", rp(float(obat.nilai_konsumsi.sum())), "Total nilai konsumsi obat", INK),
        head_stat("kepatuhan fornas", pid(fornas_pct), "Resep sesuai Formularium Nasional",
                  CORAL if fornas_pct < 80 else TEAL, f"non {nonf_pct:.0f}%"),
        head_stat("obat stok kurang", f"{n_under} obat", "Berisiko kehabisan stok", CORAL)])

    # Top 5 obat penyerap biaya → bar horizontal (teal = Fornas, merah = non-Fornas)
    top = obat.sort_values("nilai_konsumsi", ascending=False).head(5)
    tnames = [r.nama_obat for _, r in top.iterrows()]
    tvals = top.nilai_konsumsi.tolist()
    tcols = [TEAL if r.fornas == "Ya" else CORAL for _, r in top.iterrows()]
    f_top = go.Figure(go.Bar(y=tnames, x=tvals, orientation="h", marker_color=tcols, marker_line_width=0,
                             text=[rp(v, 1) for v in tvals], textposition="auto", insidetextanchor="end",
                             textfont=dict(weight="bold", color="#FFFFFF", size=12.5)))
    f_top.update_layout(yaxis=dict(autorange="reversed"), xaxis=dict(range=[0, max(tvals) * 1.18] if tvals else None, showticklabels=False))
    cardTop = html.Div(className="card", children=[
        html.Div(className="card-head", children=[
            html.Div("obat dengan nilai pemakaian tertinggi", className="card-title", style={"marginBottom": "0"}),
            html.Div([legend_item(TEAL, "Fornas"), legend_item(CORAL, "Non-Fornas")], className="card-legend")]),
        dcc.Graph(figure=style(f_top, 168, legend=False), config={"displayModeBar": False})])

    # Tren stok obat per bulan (stok kurang vs berlebih) — ikut filter tahun
    if year == "all":
        g = stok_ts.groupby("tahun")[["understock", "overstock"]].mean()
        xs = [str(int(y)) for y in g.index]
        uu, oo = g.understock.values, g.overstock.values
    else:
        g = stok_ts[stok_ts.tahun == year].sort_values("bulan")
        xs = [BULAN[m - 1] for m in g.bulan]
        uu, oo = g.understock.values, g.overstock.values
    f_stok = go.Figure()
    f_stok.add_bar(x=xs, y=uu, name="Stok Kurang", marker_color=INK, marker_line_width=0,
                   hovertemplate="Stok Kurang: %{y:.0f} obat<extra></extra>")
    f_stok.add_bar(x=xs, y=oo, name="Stok Berlebih", marker_color=TEAL, marker_line_width=0,
                   hovertemplate="Stok Berlebih: %{y:.0f} obat<extra></extra>")
    f_stok.update_layout(barmode="group", bargap=0.28, bargroupgap=0.06,
                         yaxis=dict(ticksuffix=" obat", rangemode="tozero"), hovermode="x unified")
    cardStok = card_lg("tren stok obat per bulan", f_stok,
                       [legend_item(INK, "Stok Kurang"), legend_item(TEAL, "Stok Berlebih")], h=210)
    f_stok.update_layout(hoverlabel=dict(bgcolor="#1F4E79", bordercolor="#1F4E79",
                                         font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))

    # Kelas ABC — satu sumbu saja (nilai). Jumlah obat jadi label di batang biar tak perlu dual-axis.
    abc = obat.groupby("kategori_abc").nilai_konsumsi.sum().reindex(["A", "B", "C"]).fillna(0)
    abc_n = obat.groupby("kategori_abc").size().reindex(["A", "B", "C"]).fillna(0)
    abccol = {"A": CORAL, "B": AMBER, "C": TEAL}
    f_abc = go.Figure(go.Bar(x=["A", "B", "C"], y=abc.values, marker_color=[abccol[k] for k in ["A", "B", "C"]],
                             marker_line_width=0,
                             text=[f"<b>{rp(v, 1)}</b><br>{int(n)} obat" for v, n in zip(abc.values, abc_n.values)],
                             textposition="outside", textfont=dict(size=11, color=INK),
                             hovertemplate="Kelas %{x}<extra></extra>"))
    f_abc.update_layout(yaxis=dict(showticklabels=False, range=[0, float(abc.max()) * 1.45] if len(abc) else None),
                        xaxis=dict(title=None))
    abc_legend = html.Div(style={"display": "flex", "gap": "14px", "flexWrap": "wrap", "marginTop": "4px"}, children=[
        legend_item(CORAL, "A — nilai tinggi"), legend_item(AMBER, "B — nilai sedang"),
        legend_item(TEAL, "C — nilai rendah")])
    cardAbc = html.Div(className="card", children=[
        html.Div("nilai obat per kelas ABC", className="card-title"),
        csub("Kelas A paling bernilai walau jenis obatnya sedikit"),
        dcc.Graph(figure=style(f_abc, 135, legend=False), config={"displayModeBar": False}),
        abc_legend])


    return [head,
            html.Div(className="g-7-5", children=[cardTop, cardAbc]),
            cardStok]


def _hbar_card(title, sub, ser, colors, fmt=num, h=128):
    f = go.Figure(go.Bar(y=ser.index.tolist(), x=ser.values, orientation="h", marker_color=colors,
                         marker_line_width=0, text=[fmt(v) for v in ser.values], textposition="auto",
                         insidetextanchor="end", textfont=dict(weight="bold", color="#FFFFFF", size=14)))
    f.update_layout(yaxis=dict(autorange="reversed"),
                    xaxis=dict(range=[0, float(ser.max()) * 1.15] if len(ser) else None, showticklabels=False))
    return html.Div(className="card", children=[html.Div(title, className="card-title"), csub(sub),
                    dcc.Graph(figure=style(f, h, legend=False), config={"displayModeBar": False})])


def page_penunjang(year, kelas, dept):  # Penunjang diagnostik: Lab & Radiologi
    d = claims(year, kelas, dept)
    n_tot = len(d)
    n_lab = int((d.pakai_lab == "Ya").sum()); labpct = 100 * n_lab / n_tot if n_tot else 0
    n_rad = int((d.pakai_radiologi == "Ya").sum()); radpct = 100 * n_rad / n_tot if n_tot else 0
    # biaya diagnostik = lab (70rb/tes) + radiologi (per modalitas), konsisten dgn Kategorisasi di Klaim
    _labc = float(d.jumlah_tes_lab.sum()) * TARIF_LAB
    _radc = float((d.jumlah_radiologi * d.modalitas_radiologi.map(TARIF_RAD).fillna(0)).sum())
    _diagc = _labc + _radc
    _biaya = float(d.biaya_riil.sum())
    _kontrib = 100 * _diagc / _biaya if _biaya else 0
    ytxt = "2020–25" if year == "all" else str(year)
    head = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("tahun buku", className="head-label"),
            html.Div(ytxt, className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else "1 Jan – 31 Des", className="head-sub")]),
        head_stat("pasien pakai lab", pid(labpct), f"{ribu(n_lab)} dari {ribu(n_tot)} pasien", TEAL),
        head_stat("pasien pakai radiologi", pid(radpct), f"{ribu(n_rad)} dari {ribu(n_tot)} pasien", NAVY),
        head_stat("biaya lab & radiologi", rp(_diagc), "Kontribusi ke biaya riil RS", AMBER, pid(_kontrib), "#FEF7E6")])

    # ── KIRI: SATU grouped bar — % pakai lab & radiologi per departemen ──
    lab_util = (100 * d.groupby("departemen").pakai_lab.apply(lambda s: (s == "Ya").mean())).sort_values(ascending=False)
    order = lab_util.index.tolist()
    rad_util = (100 * d.groupby("departemen").pakai_radiologi.apply(lambda s: (s == "Ya").mean())).reindex(order)
    f_util = go.Figure()
    f_util.add_bar(y=order, x=lab_util.values, orientation="h", name="Lab", marker_color=TEAL, marker_line_width=0,
                   text=[pid(v, 0) for v in lab_util.values], textposition="outside", textfont=dict(weight="bold", size=10.5, color=INK), cliponaxis=False)
    f_util.add_bar(y=order, x=rad_util.values, orientation="h", name="Radiologi", marker_color=NAVY, marker_line_width=0,
                   text=[pid(v, 0) for v in rad_util.values], textposition="outside", textfont=dict(weight="bold", size=10.5, color=INK), cliponaxis=False)
    f_util.update_layout(barmode="group", bargap=0.3, bargroupgap=0.04, yaxis=dict(autorange="reversed"),
                         xaxis=dict(range=[0, 118], showticklabels=False))
    cardUtil = card_lg("pasien pakai lab & radiologi per departemen", f_util,
                       [legend_item(TEAL, "Lab"), legend_item(NAVY, "Radiologi")], h=430)

    # ── KANAN: dua donut komposisi kategori lab & radiologi ──
    def _donut_card(title, sub, labels, vals, colors):
        tot = float(sum(vals)) or 1
        slice_txt = [pid(v / tot * 100) if (v / tot * 100) >= 8 else "" for v in vals]  # slice kecil tanpa label
        fig = go.Figure(go.Pie(labels=labels, values=vals, hole=0, sort=False,
                               marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
                               text=slice_txt, textinfo="text", textposition="inside", insidetextorientation="horizontal",
                               textfont=dict(weight="bold", size=11, color="#FFFFFF"),
                               hovertemplate="<b>%{label}</b><br>%{percent} · %{value:,} pemeriksaan<extra></extra>"))
        fig.update_layout(template="plotly_white", height=158, margin=dict(l=4, r=4, t=6, b=6),
                          font=dict(family="Plus Jakarta Sans, sans-serif", size=11, color=INK),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.", showlegend=False,
                          hoverlabel=dict(bordercolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
        legend = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "8px", "justifyContent": "center"},
                          children=[html.Div(className="kl-d-head", style={"alignItems": "center"}, children=[
                              html.Div(className="kl-d-left", children=[html.Span(className="kl-d-dot", style={"background": colors[i]}),
                                  html.Span(labels[i], className="kl-d-label")]),
                              html.Span(pid(100 * vals[i] / tot), className="kl-d-val", style={"color": "#1F4E79"})])
                              for i in range(len(labels))])
        return html.Div(className="card", children=[html.Div(title, className="card-title"), csub(sub),
                        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1.1fr", "columnGap": "12px", "alignItems": "center"},
                                 children=[dcc.Graph(figure=fig, config={"displayModeBar": False}), legend])])

    dlab = d[d.pakai_lab == "Ya"]
    lab_kat = dlab.jenis_lab.value_counts().reindex(LAB_KAT).fillna(0)
    cardKatLab = _donut_card("komposisi kategori lab", "Porsi tiap jenis tes lab",
                             LAB_KAT, lab_kat.values.tolist(), [TEAL, NAVY, AMBER, "#7B5EA7", "#9AA6B2"])
    dr = d[d.pakai_radiologi == "Ya"]
    mods = ["X-Ray", "USG", "CT-Scan", "MRI"]
    vol = dr.modalitas_radiologi.value_counts().reindex(mods).fillna(0)
    cardKatRad = _donut_card("komposisi kategori radiologi", "Porsi tiap jenis pencitraan",
                             mods, vol.values.tolist(), [NAVY, TEAL, AMBER, "#7B5EA7"])

    return [head,
            html.Div(className="grid2", children=[
                cardUtil,
                html.Div(children=[cardKatLab, cardKatRad])])]


def csub(text):
    return html.Div(text, style={"fontSize": "11.5px", "color": "#7D8898", "fontWeight": "600",
                                 "marginTop": "-4px", "marginBottom": "14px"})


def page_profil(year, kelas, dept):
    d = claims(year, kelas, dept)
    F = fin(d); nadm, sf = F["n"], F["sf"]  # sf negatif = kerugian
    npas = d.id_pasien.nunique()
    kronis_pct = 100 * (d.kategori_penyakit == "Kronis").mean() if nadm else 0
    kl_loss = d.groupby("kategori_penyakit").shortfall.sum().sort_values()  # paling negatif = rugi terbesar
    kronis_share = 100 * kl_loss.get("Kronis", 0) / sf if sf else 0
    lansia_pct = 100 * (d.kelompok_usia == "≥65").mean() if nadm else 0
    rugi_per = F["per_adm"]  # negatif — sama persis dgn halaman Klaim
    ytxt = "2020–25" if year == "all" else str(year)
    head = html.Div(className="head-row r4", children=[
        html.Div(className="head-col", children=[
            html.Div("tahun buku", className="head-label"),
            html.Div(ytxt, className="head-year"),
            html.Div("6 tahun agregat" if year == "all" else "1 Jan – 31 Des", className="head-sub")]),
        head_stat("total pasien", f"{npas:,}".replace(",", "."), f"{nadm:,}".replace(",", ".") + " admisi BPJS", INK),
        head_stat("pasien kronis", pid(kronis_pct), "Segmen penyumbang rugi terbesar", CORAL, f"{kronis_share:.0f}%"),
        head_stat("rata-rata rugi / pasien", rp(rugi_per), "Rata-rata kerugian per admisi", CORAL)])

    # Q1 — diagnosis mana yang paling menguras: ranking by total shortfall (biaya riil − tarif INA-CBGs)
    gl = d.groupby("diagnosis").shortfall.sum().sort_values().head(10)  # 10 kerugian terbesar
    loss = (-gl)
    maxl = float(loss.max()) if len(loss) else 1
    diag_rows = [rank_row(i + 1, name, 100 * loss[name] / maxl, rp(loss[name], 1)) for i, name in enumerate(gl.index)]
    cardDiag = html.Div(className="card", children=[
        html.Div("top 10 diagnosis penyumbang kerugian", className="card-title"),
        csub("Diagnosis dengan kerugian terbesar"),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "columnGap": "36px"}, children=[
            html.Div(className="kl-rank-list compact", children=diag_rows[:5]),
            html.Div(className="kl-rank-list compact", children=diag_rows[5:])])])

    # Q3 — kerugian per kategori penyakit (bukan sekadar jumlah kasus — tapi rupiah tekor)
    catcol = {"Kronis": CORAL, "Infeksi": AMBER, "Akut": NAVY, "Maternal": TEAL}
    kat_lbl = kl_loss.index.tolist()
    kat_val = [float(-kl_loss[name]) for name in kat_lbl]
    kat_col = [catcol.get(name, TEAL) for name in kat_lbl]
    f_kat = go.Figure(go.Pie(labels=kat_lbl, values=kat_val, hole=.58, sort=False,
                             marker=dict(colors=kat_col, line=dict(color="#FFFFFF", width=2)),
                             customdata=[rp(v, 1) for v in kat_val], texttemplate="<b>%{percent}</b>", textposition="inside", textfont=dict(weight="bold", size=11),
                             hovertemplate="<b>%{label}</b><br>%{percent} · %{customdata}<extra></extra>"))
    f_kat.update_layout(template="plotly_white", height=210, margin=dict(l=4, r=4, t=4, b=4),
                        font=dict(family="Plus Jakarta Sans, sans-serif", size=11, color=INK),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", separators=",.",
                        showlegend=False,
                        hoverlabel=dict(bordercolor="#FFFFFF", font=dict(family="Plus Jakarta Sans, sans-serif", size=12.5, color="#FFFFFF")))
    kat_legend = html.Div(style={"display": "flex", "flexDirection": "column", "gap": "16px", "justifyContent": "center"},
                          children=[cat_legend(name, kat_val[i], kat_col[i]) for i, name in enumerate(kat_lbl)])
    cardKat = html.Div(className="card", children=[
        html.Div("kerugian per kategori penyakit", className="card-title"),
        csub("Mayoritas rugi dari pasien kronis"),
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "columnGap": "20px", "alignItems": "center"},
                 children=[dcc.Graph(figure=f_kat, config={"displayModeBar": False}), kat_legend])])

    # Q4 — readmisi 30 hari (data riil): pasien masuk lagi ≤30 hari setelah pulang = sinyal mutu klinis
    ul = d.groupby("kategori_penyakit").apply(lambda x: 100 * x.readmisi_30.mean()).sort_values(ascending=False)
    f4 = go.Figure(go.Bar(x=ul.index.tolist(), y=ul.values, marker_color=CORAL,
                          text=[pid(v) for v in ul.values], textposition="outside"))
    f4.update_layout(yaxis=dict(ticksuffix="%", range=[0, float(ul.max()) * 1.22] if len(ul) else None))
    cardBerulang = html.Div(className="card", children=[
        html.Div("readmisi 30 hari per kategori", className="card-title"),
        csub("Pasien masuk lagi ≤30 hari setelah pulang"),
        dcc.Graph(figure=style(f4, 200, legend=False), config={"displayModeBar": False})])

    return [head, cardDiag, html.Div(className="grid2", children=[cardKat, cardBerulang])]


def kpi(label, value, sub, color=INK):
    return html.Div(className="kpi", children=[html.Div(label, className="kpi-label"),
                    html.Div(value, className="kpi-value", style={"color": color}), html.Div(sub, className="kpi-sub")])


PAGES = {"ringkasan": ("Ringkasan Klaim BPJS Rawat Inap", page_ringkasan), "klaim": ("Klaim BPJS Rawat Inap", page_klaim),
         "mutu": ("Operasional Bangsal", page_mutu), "operasi": ("Penggunaan Kamar Operasi", page_operasi),
         "obat": ("Farmasi & Obat BPJS Rawat Inap", page_obat),
         "penunjang": ("Lab & Radiologi BPJS Rawat Inap", page_penunjang),
         "profil": ("Profil Pasien BPJS Rawat Inap", page_profil)}
NAV = [("ringkasan", "Ringkasan"), ("klaim", "Klaim BPJS"), ("mutu", "Operasional Bangsal"),
       ("operasi", "Kamar Operasi"), ("obat", "Farmasi & Obat"), ("penunjang", "Lab & Radiologi"),
       ("profil", "Profil Pasien")]

app = Dash(__name__, title="BI BPJS Rawat Inap — RSU AIA")
server = app.server  # WSGI entrypoint untuk gunicorn (deploy)
app.layout = html.Div(className="app", children=[
    html.Div(className="sidebar", children=[
        html.Div([html.Div("Ayah Ibu Anak Indonesia", className="brand-name"), html.Div("RSU Tipe A", className="brand-sub")]),
        html.Div("Modul Analitik", className="nav-label"),
        html.Div([html.Button(lbl, id={"type": "nav", "page": p}, className="navitem", n_clicks=0) for p, lbl in NAV]),
        html.Div(className="sidebar-foot", children=[html.Span(className="dot"), html.Div("Data Real-time")]),
    ]),
    html.Div(className="main", children=[
        html.Div(className="topbar", children=[
            html.Div([html.Div([html.B("BPJS rawat inap"), " · dashboard BI"], className="eyebrow"),
                      html.H1(id="page-title", className="page-title")]),
            html.Div(className="filters", children=[
                dcc.Dropdown(id="year", options=[{"label": "Semua Tahun (2020–2025)", "value": "all"}] + [{"label": f"Tahun {y}", "value": y} for y in YEARS], value=2024, clearable=False, className="dd ddw"),
                dcc.Dropdown(id="kelas", options=[{"label": k, "value": k} for k in KELASES], value="Semua Kelas", clearable=False, className="dd"),
                dcc.Dropdown(id="dept", options=[{"label": k, "value": k} for k in DEPTS], value="Semua Departemen", clearable=False, className="dd ddw"),
            ]),
        ]),
        dcc.Store(id="active", data="ringkasan"),
        html.Div(id="content", className="content"),
    ]),
])


@app.callback(Output("active", "data"),
              Input({"type": "nav", "page": ALL}, "n_clicks"),
              Input({"type": "navcard", "page": ALL}, "n_clicks"),
              prevent_initial_call=True)
def _nav(_a, _b):
    t = ctx.triggered_id
    # Abaikan trigger yang bukan klik nyata (mis. navcard baru muncul saat halaman dirender ulang),
    # supaya `active` tidak ter-reset & highlight nav tetap sinkron dgn konten.
    if not t or not ctx.triggered or not ctx.triggered[0].get("value"):
        return no_update
    return t["page"]


@app.callback([Output({"type": "nav", "page": p}, "className") for p, _ in NAV], Input("active", "data"))
def _hl(active):
    return ["navitem active" if p == active else "navitem" for p, _ in NAV]


@app.callback(Output("content", "children"), Output("page-title", "children"),
              Input("active", "data"), Input("year", "value"), Input("kelas", "value"), Input("dept", "value"))
def _render(page, year, kelas, dept):
    title, fn = PAGES[page]
    ytxt = "2020–2025" if year == "all" else year
    return fn(year, kelas, dept), f"{title} · {ytxt}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8050)), debug=False)
