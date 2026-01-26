import streamlit as st
import pandas as pd
import math
import json
from io import BytesIO

# --- 1. CONFIGURASI HALAMAN ---
st.set_page_config(page_title="House Estimator - Modul Pondasi", layout="wide")

st.title("🏠 Prototype: Struktur Bawah Rumah Tinggal")
st.caption("Alur: Analisa Beban → Dimensi Pondasi & Sloof → RAB")
st.divider()

# --- 2. LOGIKA STRUKTUR (THE BRAIN) ---
def analisa_struktur_pondasi(lantai, jenis_tanah, panjang_total):
    # A. ANALISA BEBAN (LOAD)
    # Asumsi Beban Merata (q) dari Atap + Dinding + Plafon
    if lantai == "1 Lantai":
        beban_per_m = 1800 # kg/m' (Estimasi rumah standar)
        dim_sloof = "15/20"
        besi_utama = 4
    else: # 2 Lantai
        beban_per_m = 3500 # kg/m' (Lebih berat)
        dim_sloof = "20/30"
        besi_utama = 6
        
    # B. DAYA DUKUNG TANAH (SOIL BEARING)
    # Sigma tanah (kg/cm2) konversi ke kg/m2
    if jenis_tanah == "Tanah Keras/Cadas":
        sigma = 2.0 * 10000 # 20.000 kg/m2
    elif jenis_tanah == "Tanah Sedang/Liat":
        sigma = 1.0 * 10000 # 10.000 kg/m2
    else: # Tanah Lunak
        sigma = 0.6 * 10000 # 6.000 kg/m2
        
    # C. HITUNG LEBAR PERLU (B)
    # Rumus: Area Perlu = Beban / Daya Dukung
    # Lebar (B) = Beban_per_m / (Sigma * 1m)
    lebar_perlu_m = beban_per_m / sigma
    
    # Safety Factor & Minimal Width (Empiris)
    lebar_rekomendasi = max(lebar_perlu_m * 1.5, 0.60) # Minimal 60cm
    
    return {
        "beban": beban_per_m,
        "sigma": sigma,
        "lebar_min": round(lebar_rekomendasi, 2),
        "sloof_rec": dim_sloof,
        "besi_rec": besi_utama
    }

def hitung_volume_rab(l_atas, l_bawah, tinggi, pjg, h_sloof, b_sloof, prices, oh):
    # 1. Volume Galian (Trapisum + Space Kiri Kanan)
    # Asumsi kedalaman galian = Tinggi Pondasi + 5cm Pasir + 15cm Aanstamping
    dalam_galian = tinggi + 0.20
    l_galian_atas = l_bawah + 0.20 # Space kerja
    vol_galian = ((l_bawah + l_galian_atas)/2 * dalam_galian) * pjg
    
    # 2. Pasangan Batu Kali (Trapesium)
    luas_penampang = ((l_atas + l_bawah)/2) * tinggi
    vol_batu = luas_penampang * pjg
    
    # 3. Sloof Beton (Balok)
    vol_sloof = (b_sloof * h_sloof) * pjg
    
    # 4. Besi Sloof (kg)
    # Asumsi Besi Utama D10, Begel d8-150
    berat_d10 = 0.617
    berat_d8 = 0.395
    # Besi Utama
    kg_utama = (pjg * 4) * berat_d10 * 1.05 # 4 batang + waste
    # Begel
    keliling_begel = 2 * ((h_sloof-0.05) + (b_sloof-0.05))
    jml_begel = (pjg / 0.15) + 1
    kg_begel = (keliling_begel * jml_begel) * berat_d8 * 1.05
    total_besi = kg_utama + kg_begel
    
    # 5. Bekisting Sloof (Kiri Kanan)
    luas_bek = (2 * h_sloof) * pjg
    
    # HITUNG BIAYA (HSP)
    # Koefisien Sederhana (Bisa disesuaikan SE 182)
    hsp_galian = (0.75 * prices['u_pekerja']) * oh
    
    # AHSP Batu Kali 1:5
    hsp_batu = ((1.2*prices['m_batu'] + 136*prices['m_semen'] + 0.54*prices['m_pasir']) + \
               (1.5*prices['u_pekerja'] + 0.75*prices['u_tukang'])) * oh
               
    # AHSP Beton Sloof (Campuran Manual 1:2:3)
    hsp_sloof = ((326*prices['m_semen'] + 0.52*prices['m_pasir'] + 0.76*prices['m_split']) + \
                (1.65*prices['u_pekerja'] + 0.275*prices['u_tukang'])) * oh
                
    # AHSP Besi
    hsp_besi = (1.05*prices['m_besi'] + (0.007*prices['u_pekerja'] + 0.007*prices['u_tukang'])) * oh
    
    # AHSP Bekisting
    hsp_bek = (0.045*prices['m_kayu'] + (0.66*prices['u_pekerja'] + 0.33*prices['u_tukang'])) * oh
    
    return {
        "vol": [vol_galian, vol_batu, vol_sloof, total_besi, luas_bek],
        "hsp": [hsp_galian, hsp_batu, hsp_sloof, hsp_besi, hsp_bek]
    }

# --- 3. INPUT USER ---
with st.sidebar:
    st.header("1. Kriteria Desain")
    lantai_in = st.selectbox("Jumlah Lantai", ["1 Lantai", "2 Lantai"])
    tanah_in = st.selectbox("Kondisi Tanah", ["Tanah Keras/Cadas", "Tanah Sedang/Liat", "Tanah Lunak/Rawa"])
    panjang_in = st.number_input("Total Panjang Pondasi (m')", 100.0)

# --- 4. STEP 1: ANALISA STRUKTUR ---
st.subheader("Step 1: Analisa Beban & Dimensi")
analisa = analisa_struktur_pondasi(lantai_in, tanah_in, panjang_in)

c1, c2, c3 = st.columns(3)
c1.info(f"⬇️ **Estimasi Beban:** {analisa['beban']} kg/m'")
c2.info(f"🌍 **Daya Dukung Tanah:** {analisa['sigma']} kg/m2")
c3.warning(f"📐 **Lebar Bawah Perlu:** Min. {analisa['lebar_min']*100:.0f} cm")

# --- 5. STEP 2: PENENTUAN DIMENSI ---
st.divider()
st.subheader("Step 2: Dimensi Final (User Decision)")

col_d1, col_d2 = st.columns(2)
with col_d1:
    st.markdown("### 🪨 Pondasi Batu Kali")
    l_atas = st.number_input("Lebar Atas (m)", 0.30)
    l_bawah = st.number_input("Lebar Bawah (m)", value=analisa['lebar_min'])
    t_pondasi = st.number_input("Tinggi Pondasi (m)", 0.80)

with col_d2:
    st.markdown(f"### 🏗️ Sloof Beton ({analisa['sloof_rec']})")
    b_sloof = st.number_input("Lebar Sloof (m)", 0.15)
    h_sloof = st.number_input("Tinggi Sloof (m)", 0.20)
    st.caption(f"Rekomendasi Tulangan: {analisa['besi_rec']} bh Diameter 10mm")

# --- 6. STEP 3: INPUT HARGA & RAB ---
st.divider()
st.subheader("Step 3: Analisa Biaya (RAB)")

with st.expander("💰 Input Harga Satuan (Buka Disini)", expanded=False):
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        pr_pekerja = st.number_input("Upah Pekerja", 110000)
        pr_tukang = st.number_input("Upah Tukang", 135000)
        pr_batu = st.number_input("Harga Batu Kali (m3)", 250000)
        pr_semen = st.number_input("Harga Semen (kg)", 1600)
    with c_p2:
        pr_pasir = st.number_input("Harga Pasir (m3)", 220000)
        pr_split = st.number_input("Harga Split (m3)", 300000)
        pr_besi = st.number_input("Harga Besi (kg)", 14000)
        pr_kayu = st.number_input("Harga Kayu (m3)", 2500000)
    
    overhead_in = st.slider("Overhead %", 10, 15, 10)

# PACKING HARGA
prices = {
    'u_pekerja': pr_pekerja, 'u_tukang': pr_tukang,
    'm_batu': pr_batu, 'm_semen': pr_semen, 'm_pasir': pr_pasir,
    'm_split': pr_split, 'm_besi': pr_besi, 'm_kayu': pr_kayu
}

# HITUNG TOTAL
rab = hitung_volume_rab(l_atas, l_bawah, t_pondasi, panjang_in, h_sloof, b_sloof, prices, 1+overhead_in/100)

# TABEL OUTPUT
df_rab = pd.DataFrame({
    "Uraian Pekerjaan": ["Galian Tanah", "Pasangan Batu Kali (1:5)", "Beton Sloof (K-175)", "Pembesian Sloof", "Bekisting Sloof"],
    "Volume": rab['vol'],
    "Satuan": ["m3", "m3", "m3", "kg", "m2"],
    "Harga Satuan": rab['hsp'],
})
df_rab["Total Harga"] = df_rab["Volume"] * df_rab["Harga Satuan"]

st.dataframe(df_rab.style.format({
    "Volume": "{:.2f}", "Harga Satuan": "{:,.0f}", "Total Harga": "{:,.0f}"
}), use_container_width=True)

total = df_rab["Total Harga"].sum()
st.success(f"## 💰 Total Biaya Pondasi: Rp {total:,.0f}")