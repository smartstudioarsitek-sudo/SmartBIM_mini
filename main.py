import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# --- IMPORT MODULE LOKAL ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim # Import modul baru
import libs_pondasi as fdn # Import modul pondasi

# --- CONFIG ---
st.set_page_config(page_title="IndoBIM Pro", layout="wide", page_icon="🇮🇩")

# --- CUSTOM CSS (UI FRIENDLY) ---
st.markdown("""
    <style>
    .main_header {font-size: 24px; font-weight: bold; color: #2E86C1;}
    .sub_header {font-size: 18px; font-weight: bold; color: #555;}
    div.stButton > button:first-child {background-color: #2E86C1; color: white; border-radius: 8px;}
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR (INPUT GLOBAL) ---
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/engineer.png", width=80)
    st.markdown("### IndoBIM Pro 2025")
    st.caption("Integrated Structural & Cost Estimator")
    
    st.divider()
    st.markdown("#### 1. Material (SNI)")
    fc_in = st.number_input("Mutu Beton f'c (MPa)", 20, 50, 25)
    fy_in = st.number_input("Mutu Besi fy (MPa)", 240, 500, 400)
    
    st.divider()
    st.markdown("#### 2. Harga Dasar (Market)")
    p_semen = st.number_input("Semen (Rp/kg)", value=1500)
    p_pasir = st.number_input("Pasir (Rp/m3)", value=250000)
    p_split = st.number_input("Split (Rp/m3)", value=300000)
    p_besi = st.number_input("Besi (Rp/kg)", value=14000)
    p_kayu = st.number_input("Kayu Bekisting (Rp/m3)", value=2500000)
    
    u_tukang = st.number_input("Upah Tukang (Rp/Hari)", value=135000)
    u_pekerja = st.number_input("Upah Pekerja (Rp/Hari)", value=110000)

# --- INIT OBJECTS ---
# Panggil class dari file libs_sni
calc_struktur = sni.SNI_Concrete_2847(fc_in, fy_in)
# Panggil class dari file libs_ahsp
calc_biaya = ahsp.AHSP_Engine()

# --- TABS NAVIGASI ---
tab_home, tab_import, tab_model, tab_analisa, tab_pondasi, tab_rab = st.tabs([
    "🏠 Dashboard", 
    "📂 Import Revit/IFC", 
    "📐 Modeling (Arsitek)", 
    "⚙️ Analisa (Struktur)", 
    "uD83EuDDF1 Pondasi (Bawah)", # Tab Baru
    "💰 RAB (AHSP)" 
])

# 1. DASHBOARD
with tab_home:
    st.markdown('<p class="main_header">Selamat Datang di IndoBIM Pro</p>', unsafe_allow_html=True)
    st.info("Aplikasi ini menggunakan standar **SNI 2847:2019** dan **AHSP Permen PUPR** terbaru.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Mutu Beton", f"K-{int(fc_in * 10 / 0.83)}", f"f'c {fc_in} MPa")
    col2.metric("Tegangan Leleh", f"U-{int(fy_in/10)}", f"fy {fy_in} MPa")
    col3.metric("Wilayah Gempa", "Medan (D)", "Ss=1.0g (Asumsi)")
# 2. DASHBOARD
with tab_import:
    st.markdown('<p class="sub_header">Import Model dari Revit (via IFC)</p>', unsafe_allow_html=True)
    st.info("Di Revit: File > Export > IFC. Lalu upload file .ifc tersebut di sini.")
    
    uploaded_ifc = st.file_uploader("Upload File IFC", type=["ifc"])
    
    if uploaded_ifc is not None:
        try:
            with st.spinner("Membaca Geometri & Parameter IFC..."):
                # Panggil Engine IFC
                engine_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                
                # 1. Parse Struktur
                df_struktur = engine_ifc.parse_structure()
                st.success(f"Berhasil membaca {len(df_struktur)} elemen struktur!")
                
                # Tampilkan Preview Data Struktur
                st.dataframe(df_struktur.head())
                
                # Visualisasi Sebaran Titik Struktur (Preview Denah)
                fig, ax = plt.subplots()
                ax.scatter(df_struktur['X'], df_struktur['Y'], c='blue', marker='s')
                ax.set_title("Preview Titik Kolom/Balok dari Revit")
                st.pyplot(fig)
                
                st.divider()
                
                # 2. Parse Arsitek/MEP jadi Beban
                loads = engine_ifc.calculate_architectural_loads()
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.metric("Beban Dinding (Arsitek)", f"{loads['Total Beban Dinding (kN)']} kN")
                with col_b2:
                    st.metric("Beban MEP (Pipa/Duct)", f"{loads['Estimasi Beban MEP (kN)']} kN")
                
                st.warning(f"Total Beban Mati Tambahan (SDL) yang akan diaplikasikan: **{loads['Total Load Tambahan (kN)']} kN**")
                
                # Tombol Simpan ke Session State
                if st.button("📥 Gunakan Data Ini ke Analisa"):
                    st.session_state['imported_loads'] = loads['Total Load Tambahan (kN)']
                    st.session_state['imported_geometry'] = df_struktur
                    st.toast("Data Revit berhasil masuk ke Engine Analisa!", icon="✅")
                    
        except Exception as e:
            st.error(f"Gagal membaca file IFC: {e}")
            st.caption("Pastikan file IFC valid export dari Revit 2020+")

# 3. MODELING (Simple Grid)
with tab_model:
    st.markdown('<p class="sub_header">Input Geometri Grid</p>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 2])
    with c1:
        pjg_balok = st.number_input("Panjang Bentang Balok (m)", 3.0, 10.0, 6.0)
        b_balok = st.number_input("Lebar Balok (mm)", 150, 1000, 250)
        h_balok = st.number_input("Tinggi Balok (mm)", 200, 2000, 500)
        st.caption(f"Dimensi: {b_balok}x{h_balok} mm")
    
    with c2:
        # Visualisasi Matplotlib Sederhana
        fig, ax = plt.subplots(figsize=(6,3))
        # Gambar balok
        rect = plt.Rectangle((0, 0), pjg_balok, h_balok/1000, facecolor='#3498DB', edgecolor='black')
        ax.add_patch(rect)
        ax.set_xlim(-1, pjg_balok+1)
        ax.set_ylim(-1, 2)
        ax.set_aspect('equal')
        ax.set_title(f"Visualisasi Balok B1 ({b_balok}x{h_balok})")
        st.pyplot(fig)
        
        # Simpan data ke session state agar bisa dibaca tab lain
        st.session_state['geo'] = {'L': pjg_balok, 'b': b_balok, 'h': h_balok}

# 4. ANALISA STRUKTUR
with tab_analisa:
    st.markdown('<p class="sub_header">Analisa Kekuatan & Kebutuhan Besi</p>', unsafe_allow_html=True)
    
    # Input Beban
    col_load1, col_load2 = st.columns(2)
    with col_load1:
        q_dl = st.number_input("Beban Mati (DL) - kN/m", 0.0, 50.0, 15.0)
    with col_load2:
        q_ll = st.number_input("Beban Hidup (LL) - kN/m", 0.0, 50.0, 5.0)
        
    # Kalkulasi Beban Terfaktor (SNI 1727)
    q_u = sni.SNI_Load_1727.komb_pembebanan(q_dl, q_ll)
    L = st.session_state['geo']['L']
    
    # Hitung Momen (Momen Simple Beam 1/8 qL^2)
    # Catatan: Ini simplifikasi, di real project pakai FEM
    Mu = (1/8) * q_u * (L**2)
    
    st.write("---")
    st.metric("Momen Ultimate (Mu)", f"{Mu:.2f} kNm", f"Beban Terfaktor: {q_u:.2f} kN/m")
    
    # Hitung Kebutuhan Besi (Pakai Module libs_sni)
    b, h = st.session_state['geo']['b'], st.session_state['geo']['h']
    As_req = calc_struktur.kebutuhan_tulangan(Mu, b, h, 40) # ds asumsi 40mm
    
    # Konversi ke Tulangan
    dia = st.selectbox("Diameter Tulangan Utama", [13, 16, 19, 22, 25])
    As_satu = 0.25 * 3.14 * dia**2
    n_bars = np.ceil(As_req / As_satu)
    
    st.success(f"### Rekomendasi Desain: {int(n_bars)} D{dia}")
    st.caption(f"Luas Tulangan Perlu: {As_req:.1f} mm2")
    
    # Simpan hasil untuk RAB
    st.session_state['structure'] = {'vol_beton': L * b/1000 * h/1000, 'berat_besi': (As_req * L * 7850 / 1e6) * 1.5} # 1.5 factor sengkang dll
# --- LOGIKA TAB PONDASI ---
with tab_pondasi:
    st.markdown('<p class="sub_header">Perencanaan Struktur Bawah (Pondasi)</p>', unsafe_allow_html=True)
    
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.info("Parameter Tanah")
        sigma = st.number_input("Daya Dukung Tanah (kN/m2)", 50.0, 300.0, 150.0)
        engine_pondasi = fdn.Foundation_Engine(sigma)
        
        st.divider()
        st.markdown("#### A. Cakar Ayam (Footplate)")
        fp_beban = st.number_input("Beban Aksial Kolom (Pu) - kN", 10.0, 500.0, 150.0)
        fp_L = st.number_input("Panjang Pondasi (m)", 0.6, 3.0, 1.0)
        fp_B = st.number_input("Lebar Pondasi (m)", 0.6, 3.0, 1.0)
        fp_jumlah = st.number_input("Jumlah Titik Pondasi", 1, 100, 12)
        
        # Hitung Footplate
        res_fp = engine_pondasi.hitung_footplate(fp_beban, fp_B, fp_L, 300)
        
        if "AMAN" in res_fp['status']:
            st.success(f"Status: {res_fp['status']} (SF: {res_fp['ratio_safety']:.2f})")
        else:
            st.error(f"Status: {res_fp['status']}")
            
    with col_p2:
        st.markdown("#### B. Batu Kali (Menerus)")
        bk_panjang = st.number_input("Total Panjang Pondasi Menerus (m)", 10.0, 500.0, 60.0)
        bk_la = st.number_input("Lebar Atas (m)", 0.2, 0.5, 0.3)
        bk_lb = st.number_input("Lebar Bawah (m)", 0.4, 1.0, 0.6)
        bk_t = st.number_input("Tinggi (m)", 0.5, 2.0, 0.8)
        
        # Hitung Batu Kali
        res_bk = engine_pondasi.hitung_batu_kali(bk_panjang, bk_la, bk_lb, bk_t)
        
        st.metric("Volume Pasangan Batu", f"{res_bk['vol_pasangan']:.2f} m3")
        
    # Simpan ke Session State untuk RAB
    st.session_state['pondasi'] = {
        'fp_beton': res_fp['vol_beton'] * fp_jumlah,
        'fp_besi': res_fp['berat_besi'] * fp_jumlah,
        'bk_batu': res_bk['vol_pasangan'],
        'galian_total': (res_fp['vol_galian'] * fp_jumlah) + res_bk['vol_galian']
    }

# 5. RAB / AHSP
with tab_rab:
    st.markdown('<p class="sub_header">Rencana Anggaran Biaya (RAB)</p>', unsafe_allow_html=True)
    
    if 'structure' in st.session_state:
        vol_beton = st.session_state['structure']['vol_beton']
        berat_besi_total = st.session_state['structure']['berat_besi']
        luas_bekisting = (2 * st.session_state['geo']['h']/1000 + st.session_state['geo']['b']/1000) * st.session_state['geo']['L']
        
        # Susun Harga Dasar Dictionary
        h_bahan = {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 'kayu': p_kayu}
        h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2} # Mandor simplified
        
        # Hitung HSP pakai Module libs_ahsp
        hsp_beton = calc_biaya.hitung_hsp('beton_k250', h_bahan, h_upah)
        hsp_besi = calc_biaya.hitung_hsp('pembesian_polos', h_bahan, h_upah) / 10 # Karena analisa per 10kg
        hsp_bek = calc_biaya.hitung_hsp('bekisting_balok', h_bahan, h_upah)
        
        # Tabel RAB
        data_rab = [
            {"Item": "Pekerjaan Beton K-250", "Vol": vol_beton, "Sat": "m3", "Harga": hsp_beton},
            {"Item": "Pembesian", "Vol": berat_besi_total, "Sat": "kg", "Harga": hsp_besi},
            {"Item": "Bekisting Balok", "Vol": luas_bekisting, "Sat": "m2", "Harga": hsp_bek},
        ]
        df_rab = pd.DataFrame(data_rab)
        df_rab["Total"] = df_rab["Vol"] * df_rab["Harga"]
        
        st.dataframe(df_rab.style.format({"Vol": "{:.2f}", "Harga": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
        
        total_biaya = df_rab["Total"].sum()
        st.success(f"### Total Biaya Balok: Rp {total_biaya:,.0f}")
        
    else:

        st.warning("Silakan lakukan Analisa Struktur terlebih dahulu.")

with tab_rab:
    st.markdown('<p class="sub_header">Rencana Anggaran Biaya (RAB)</p>', unsafe_allow_html=True)
    
    # Cek kelengkapan data
    if 'structure' in st.session_state and 'pondasi' in st.session_state:
        
        # Data Struktur Atas
        vol_beton_atas = st.session_state['structure']['vol_beton']
        berat_besi_atas = st.session_state['structure']['berat_besi']
        luas_bekisting = (2 * st.session_state['geo']['h']/1000 + st.session_state['geo']['b']/1000) * st.session_state['geo']['L']
        
        # Data Struktur Bawah
        vol_beton_bawah = st.session_state['pondasi']['fp_beton']
        berat_besi_bawah = st.session_state['pondasi']['fp_besi']
        vol_batu_kali = st.session_state['pondasi']['bk_batu']
        vol_galian = st.session_state['pondasi']['galian_total']
        
        # Harga Dasar (Dictionary)
        h_bahan = {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 'kayu': p_kayu}
        h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
        
        # Hitung HSP (Panggil libs_ahsp)
        hsp_beton = calc_biaya.hitung_hsp('beton_k250', h_bahan, h_upah)
        hsp_besi = calc_biaya.hitung_hsp('pembesian_polos', h_bahan, h_upah) / 10
        hsp_bek = calc_biaya.hitung_hsp('bekisting_balok', h_bahan, h_upah)
        # Asumsi HSP Batu Kali & Galian (Bisa ditambah di libs_ahsp.py)
        hsp_batu = 1100000 # Default kasar
        hsp_galian = 85000
        
        # Tabel RAB Lengkap
        data_rab = [
            {"Pekerjaan": "I. PEKERJAAN TANAH", "Vol": "", "Sat": "", "Total": ""},
            {"Pekerjaan": "   1. Galian Tanah Pondasi", "Vol": vol_galian, "Sat": "m3", "Harga": hsp_galian, "Total": vol_galian*hsp_galian},
            
            {"Pekerjaan": "II. PEKERJAAN PONDASI", "Vol": "", "Sat": "", "Total": ""},
            {"Pekerjaan": "   1. Pasangan Batu Kali", "Vol": vol_batu_kali, "Sat": "m3", "Harga": hsp_batu, "Total": vol_batu_kali*hsp_batu},
            {"Pekerjaan": "   2. Beton Footplate (K-250)", "Vol": vol_beton_bawah, "Sat": "m3", "Harga": hsp_beton, "Total": vol_beton_bawah*hsp_beton},
            {"Pekerjaan": "   3. Pembesian Pondasi", "Vol": berat_besi_bawah, "Sat": "kg", "Harga": hsp_besi, "Total": berat_besi_bawah*hsp_besi},
            
            {"Pekerjaan": "III. PEKERJAAN STRUKTUR ATAS", "Vol": "", "Sat": "", "Total": ""},
            {"Pekerjaan": "   1. Beton Balok/Kolom", "Vol": vol_beton_atas, "Sat": "m3", "Harga": hsp_beton, "Total": vol_beton_atas*hsp_beton},
            {"Pekerjaan": "   2. Pembesian Struktur", "Vol": berat_besi_atas, "Sat": "kg", "Harga": hsp_besi, "Total": berat_besi_atas*hsp_besi},
            {"Pekerjaan": "   3. Bekisting", "Vol": luas_bekisting, "Sat": "m2", "Harga": hsp_bek, "Total": luas_bekisting*hsp_bek},
        ]
        
        df_rab = pd.DataFrame(data_rab)
        
        # Formatting Tabel agar cantik (Menghilangkan NaN di header)
        st.dataframe(df_rab.style.format(subset=["Vol", "Harga", "Total"], formatter="{:,.0f}"), use_container_width=True)
        
        # Total Grand
        # Filter hanya baris yang punya nilai total (bukan judul kategori)
        grand_total = df_rab[pd.to_numeric(df_rab['Total'], errors='coerce').notnull()]['Total'].sum()
        
        st.success(f"### GRAND TOTAL PROYEK: Rp {grand_total:,.0f}")
        
    else:
        st.warning("⚠️ Data belum lengkap! Pastikan sudah menghitung di Tab 'Analisa Struktur' DAN Tab 'Pondasi'.")


