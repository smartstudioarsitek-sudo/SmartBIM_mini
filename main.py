import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import libs_baja as steel   # Modul baru
import libs_gempa as quake  # Modul baru
import libs_baja as steel
import libs_gempa as quake

# --- IMPORT SEMUA MODULE (PASTIKAN 5 FILE INI ADA) ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp # Import modul baru kita

# --- CONFIG ---
st.set_page_config(page_title="IndoBIM Ultimate Enterprise", layout="wide", page_icon="🏗️")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main_header {font-size: 24px; font-weight: bold; color: #2E86C1;}
    .sub_header {font-size: 18px; font-weight: bold; color: #444;}
    div.stButton > button:first-child {background-color: #2E86C1; color: white; border-radius: 8px; width: 100%;}
    </style>
""", unsafe_allow_html=True)

# --- INIT SESSION STATE (Agar data tidak hilang saat pindah tab) ---
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'structure' not in st.session_state: st.session_state['structure'] = {}
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}

# --- SIDEBAR (GLOBAL INPUT) ---
with st.sidebar:
    st.title("IndoBIM Enterprise")
    st.caption("Integrated: BIM • Structure • Geotech • QS")
    
    with st.expander("1. Material & Tanah", expanded=True):
        fc_in = st.number_input("Mutu Beton f'c (MPa)", 20, 50, 25)
        fy_in = st.number_input("Mutu Besi fy (MPa)", 240, 500, 400)
        
        st.markdown("---")
        gamma_tanah = st.number_input("Berat Isi Tanah (kN/m3)", 14.0, 22.0, 18.0)
        phi_tanah = st.number_input("Sudut Geser (deg)", 10.0, 45.0, 30.0)
        c_tanah = st.number_input("Kohesi (kN/m2)", 0.0, 50.0, 5.0)
        sigma_tanah = st.number_input("Daya Dukung Izin (kN/m2)", 50.0, 300.0, 150.0)

    with st.expander("2. Harga Satuan (HSD)"):
        p_semen = st.number_input("Semen (Rp/kg)", 1500)
        p_pasir = st.number_input("Pasir (Rp/m3)", 250000)
        p_split = st.number_input("Split (Rp/m3)", 300000)
        p_besi = st.number_input("Besi (Rp/kg)", 14000)
        p_kayu = st.number_input("Kayu Bekisting (Rp/m3)", 2500000)
        p_batu = st.number_input("Batu Kali (Rp/m3)", 280000)
        p_beton_ready = st.number_input("Readymix K300 (Rp/m3)", 1100000)
        
        u_tukang = st.number_input("Upah Tukang (Rp/Hari)", 135000)
        u_pekerja = st.number_input("Upah Pekerja (Rp/Hari)", 110000)

# --- INIT ENGINES ---
calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
calc_biaya = ahsp.AHSP_Engine()
calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
calc_fdn = fdn.Foundation_Engine(sigma_tanah)
engine_export = exp.Export_Engine()

# --- TABS UTAMA ---
tabs = st.tabs([
    "🏠 Dash", 
    "📂 BIM Import", 
    "📐 Modeling Grid", 
    "🏗️ Struktur Beton", 
    "🔩 Struktur Baja & Atap", # Tab Baru
    "🌋 Analisa Gempa",       # Tab Baru
    "⛰️ Geoteknik & Pondasi", 
    "💰 RAB Final"
])

# ==============================================================================
# TAB 1: DASHBOARD
# ==============================================================================
with tabs[0]:
    st.markdown('<p class="main_header">Dashboard Proyek Terintegrasi</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Standar Beton", "SNI 2847:2019", f"fc' {fc_in} MPa")
    c2.metric("Standar Gempa", "SNI 1726:2019", "Wilayah D (Medan)")
    c3.metric("Standar Biaya", "SE PUPR 182", "Update 2025")

# ==============================================================================
# TAB 2: BIM IMPORT
# ==============================================================================
with tabs[1]:
    st.markdown('<p class="sub_header">Import Data dari Revit/ArchiCAD (IFC)</p>', unsafe_allow_html=True)
    uploaded_ifc = st.file_uploader("Upload File .IFC", type=["ifc"])
    
    if uploaded_ifc:
        try:
            with st.spinner("Parsing BIM Data..."):
                engine_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                df_struk = engine_ifc.parse_structure()
                loads = engine_ifc.calculate_architectural_loads()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.success(f"Terdeteksi {len(df_struk)} Elemen Struktur")
                    st.dataframe(df_struk.head(3))
                with c2:
                    st.info(f"Beban Dinding & MEP Terdeteksi: {loads['Total Load Tambahan (kN)']} kN")
                    
                if st.button("Simpan Data BIM ke Analisa"):
                    st.session_state['bim_loads'] = loads['Total Load Tambahan (kN)']
                    st.toast("Data BIM tersimpan!", icon="✅")
        except Exception as e:
            st.error(f"Gagal baca IFC: {e}")

# ==============================================================================
# TAB 3: MODELING (ARSITEK) - Fitur Lama Dikembalikan
# ==============================================================================
with tabs[2]:
    st.markdown('<p class="sub_header">Modeling Geometri (Grid & Dimensi)</p>', unsafe_allow_html=True)
    
    col_mod1, col_mod2 = st.columns([1, 2])
    with col_mod1:
        L = st.number_input("Panjang Bentang (m)", 2.0, 12.0, st.session_state['geo']['L'])
        b = st.number_input("Lebar Balok (mm)", 150, 800, st.session_state['geo']['b'])
        h = st.number_input("Tinggi Balok (mm)", 200, 1500, st.session_state['geo']['h'])
        
        # Simpan state real-time
        st.session_state['geo'] = {'L': L, 'b': b, 'h': h}
        
    with col_mod2:
        # Visualisasi
        fig, ax = plt.subplots(figsize=(6, 2))
        rect = plt.Rectangle((0, 0), L, h/1000, facecolor='#3498DB', edgecolor='black')
        ax.add_patch(rect)
        ax.set_xlim(-0.5, L+0.5); ax.set_ylim(-0.5, 2)
        ax.set_title(f"Visualisasi Balok {b}x{h} mm")
        st.pyplot(fig)

# ==============================================================================
# TAB 4: STRUKTUR ATAS (SNI) - Fitur Lama Dikembalikan
# ==============================================================================
with tabs[3]:
    st.markdown('<p class="sub_header">Analisa Struktur Atas (SNI 2847)</p>', unsafe_allow_html=True)
    
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        q_dl = st.number_input("Beban Mati (DL) kN/m", 0.0, 50.0, 15.0)
        q_ll = st.number_input("Beban Hidup (LL) kN/m", 0.0, 50.0, 5.0)
        
        # Ambil data BIM jika ada
        if 'bim_loads' in st.session_state:
            st.info(f"Ditambah Beban BIM: {st.session_state['bim_loads']} kN (dikonversi ke rata)")
            q_dl += st.session_state['bim_loads'] / st.session_state['geo']['L']
            
    with c_s2:
        # Hitung SNI
        q_u = sni.SNI_Load_1727.komb_pembebanan(q_dl, q_ll)
        Mu = (1/8) * q_u * (st.session_state['geo']['L']**2)
        
        st.metric("Momen Ultimate (Mu)", f"{Mu:.2f} kNm", f"Qu: {q_u:.2f} kN/m")
        
        # Hitung Tulangan
        As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
        dia = st.selectbox("Diameter Tulangan", [13, 16, 19, 22])
        n_bars = np.ceil(As_req / (0.25 * 3.14 * dia**2))
        
        st.success(f"Rekomen Tulangan: {int(n_bars)} D{dia} (As: {As_req:.0f} mm2)")
        
        # Simpan Vol Struktur Atas
        vol_beton = st.session_state['geo']['L'] * (st.session_state['geo']['b']/1000) * (st.session_state['geo']['h']/1000)
        berat_besi = vol_beton * 150 # Ratio 150 kg/m3
        st.session_state['structure'] = {'vol_beton': vol_beton, 'berat_besi': berat_besi}
# ... (setelah st.success Rekomen Tulangan)
        # ... (Kode hitungan SNI sebelumnya) ...
        
        st.success(f"Rekomen Tulangan: {int(n_bars)} D{dia} (As: {As_req:.0f} mm2)")
        
        # Simpan Vol Struktur Atas
        vol_beton = st.session_state['geo']['L'] * (st.session_state['geo']['b']/1000) * (st.session_state['geo']['h']/1000)
        berat_besi = vol_beton * 150 
        st.session_state['structure'] = {'vol_beton': vol_beton, 'berat_besi': berat_besi}
        
        # [UPDATED] Download DXF Balok Detail (Potongan & Memanjang)
        st.write("---")
        st.markdown("##### 📥 Output Gambar Kerja (Shop Drawing)")
        
        params_balok = {
            'b': st.session_state['geo']['b'],  # mm
            'h': st.session_state['geo']['h'],  # mm
            'dia': dia,                         # mm (Diameter Tulangan Utama)
            'n': n_bars,                        # Jumlah Tulangan Utama
            'pjg': st.session_state['geo']['L'] # Panjang Balok
        }
        
        dxf_balok = engine_export.create_dxf("BALOK", params_balok)
        st.download_button(
            label="📄 Download Detail Balok (Potongan A-A & Memanjang) .dxf",
            data=dxf_balok,
            file_name=f"Detail_Balok_{params_balok['b']}x{params_balok['h']}.dxf",
            mime="application/dxf"
        )
        # [NEW] Download DXF Balok
        params_balok = {'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'dia': dia, 'n': n_bars}
        dxf_balok = engine_export.create_dxf("BALOK", params_balok)
        st.download_button("📥 Download Shop Drawing Balok (.dxf)", dxf_balok, "Detail_Balok.dxf")
# ==============================================================================
# TAB 5: GEOTEKNIK & PONDASI - Fitur Baru + Fitur Pondasi Lama
# ==============================================================================
with tabs[4]:
    st.markdown('<p class="sub_header">Analisa Bawah (Geoteknik & Pondasi)</p>', unsafe_allow_html=True)
    
    subtab_a, subtab_b = st.tabs(["A. Pondasi Dangkal (Rumah)", "B. Geoteknik & Pile (Lereng)"])
    
    # --- SUBTAB A: PONDASI DANGKAL ---
    with subtab_a:
        c_fp1, c_fp2 = st.columns(2)
        with c_fp1:
            st.markdown("**1. Cakar Ayam (Footplate)**")
            Pu = st.number_input("Beban Aksial (kN)", 50.0, 1000.0, 150.0)
            B_fp = st.number_input("Lebar Pondasi (m)", 0.6, 2.0, 1.0)
            n_fp = st.number_input("Jumlah Titik", 1, 50, 12)
            
            res_fp = calc_fdn.hitung_footplate(Pu, B_fp, B_fp, 300)
            if "AMAN" in res_fp['status']: st.success(res_fp['status'])
            else: st.error(res_fp['status'])
            # ... (setelah hitung Cakar Ayam)
            
            # [NEW] Download DXF Footplate
            params_fp = {'B': B_fp}
            dxf_fp = engine_export.create_dxf("FOOTPLATE", params_fp)
            st.download_button("📥 Shop Drawing Footplate (.dxf)", dxf_fp, "Denah_Pondasi.dxf")
        with c_fp2:
            st.markdown("**2. Batu Kali (Menerus)**")
            L_bk = st.number_input("Panjang Total (m')", 10.0, 200.0, 50.0)
            res_bk = calc_fdn.hitung_batu_kali(L_bk, 0.3, 0.6, 0.8)
            st.metric("Volume Batu Kali", f"{res_bk['vol_pasangan']:.1f} m3")
            
        # Simpan State Pondasi
        st.session_state['pondasi'] = {
            'fp_beton': res_fp['vol_beton'] * n_fp,
            'fp_besi': res_fp['berat_besi'] * n_fp,
            'bk_batu': res_bk['vol_pasangan'],
            'galian': (res_fp['vol_galian'] * n_fp) + res_bk['vol_galian']
        }

    # --- SUBTAB B: GEOTEKNIK (LERENG & PILE) ---
    with subtab_b:
        c_geo1, c_geo2 = st.columns(2)
        with c_geo1:
            st.markdown("**1. Analisa Talud (Rankine)**")
            H_talud = st.number_input("Tinggi Talud (m)", 2.0, 8.0, 3.0)
            res_talud = calc_geo.hitung_talud_batu_kali(H_talud, 0.4, 1.5)
            
            if res_talud['Status'] == "AMAN": st.success(f"Talud AMAN (SF Geser: {res_talud['SF_Geser']:.2f})")
            else: st.error("Talud BAHAYA")
# ... (setelah hitung Talud)
            
            # [NEW] Download DXF Talud
            params_talud = {'H': H_talud, 'Ba': 0.4, 'Bb': 1.5} # Sesuaikan dgn input user
            dxf_talud = engine_export.create_dxf("TALUD", params_talud)
            st.download_button("📥 Shop Drawing Talud (.dxf)", dxf_talud, "Potongan_Talud.dxf")            
            # Download DXF
            dxf = calc_geo.generate_shop_drawing_dxf("TALUD", res_talud)
            st.download_button("📥 Shop Drawing (.dxf)", dxf, "talud.dxf")

        with c_geo2:
            st.markdown("**2. Bore Pile / Tiang Pancang**")
            dia_pile = st.selectbox("Diameter (cm)", [30, 40, 50, 60])
            depth = st.number_input("Kedalaman (m)", 6.0, 20.0, 10.0)
            nspt = st.number_input("N-SPT Rata2", 5, 50, 20)
            
            res_pile = calc_geo.hitung_bore_pile(dia_pile, depth, nspt)
            st.metric("Daya Dukung Izin", f"{res_pile['Q_allow']:.1f} kN")
            
        # Simpan State Geoteknik
        L_talud_total = st.number_input("Panjang Rencana Talud (m)", 0.0, 500.0, 20.0)
        n_pile_total = st.number_input("Jumlah Titik Pile", 0, 100, 0)
        
        st.session_state['geotech'] = {
            'vol_talud': res_talud['Vol_Per_M'] * L_talud_total,
            'vol_pile': res_pile['Vol_Beton'] * n_pile_total
        }
# ... (Di dalam blok tab Baja)
with tabs[4]:
    st.markdown('<p class="sub_header">Struktur Baja (WF) & Baja Ringan</p>', unsafe_allow_html=True)
    
    sub_b1, sub_b2 = st.tabs(["A. Balok WF (Heavy Steel)", "B. Atap Baja Ringan"])
    
    with sub_b1:
        st.info("Cek Kapasitas Lentur Balok WF (SNI 1729)")
        c1, c2 = st.columns(2)
        with c1:
            Mu_baja = st.number_input("Momen Ultimate (kNm)", 10.0, 500.0, 50.0)
            Lb = st.number_input("Panjang Bentang Tak Terkekang (m)", 1.0, 10.0, 3.0)
            fy_baja = st.number_input("Mutu Baja Fy (MPa)", 240, 450, 250)
        
        with c2:
            # Database Profil Sederhana (Bisa diperlengkap di libs)
            profil_opt = {"WF 200x100": 213, "WF 250x125": 324, "WF 300x150": 481, "WF 400x200": 1190}
            pilihan = st.selectbox("Pilih Profil WF", list(profil_opt.keys()))
            Zx = profil_opt[pilihan] # Modulus Plastis (cm3)
            
            engine_baja = steel.SNI_Steel_1729(fy_baja, 410)
            res_baja = engine_baja.cek_balok_lentur(Mu_baja, Zx, Lb, 2.0, 6.0)
            
            if res_baja['Status'] == "AMAN":
                st.success(f"✅ Profil {pilihan} AMAN (Ratio: {res_baja['Ratio']:.2f})")
            else:
                st.error(f"❌ Profil {pilihan} GAGAL (Ratio: {res_baja['Ratio']:.2f})")
            
            st.metric("Kapasitas Momen (Phi Mn)", f"{res_baja['Phi_Mn']:.1f} kNm")

    with sub_b2:
        st.info("Kalkulator Kuda-Kuda Baja Ringan (SNI 7971)")
        luas_atap = st.number_input("Luas Atap Miring (m2)", 20.0, 1000.0, 100.0)
        jenis = st.radio("Penutup Atap", ["Metal Pasir", "Genteng Keramik"])
        
        calc_ringan = steel.Baja_Ringan_Calc()
        res_ringan = calc_ringan.hitung_kebutuhan_atap(luas_atap, jenis)
        
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.metric("Kanal C (Batang)", res_ringan['Kanal C (btg)'])
        c_r2.metric("Reng (Batang)", res_ringan['Reng (btg)'])
        c_r3.metric("Sekrup (Pcs)", res_ringan['Sekrup (pcs)'])
# --- IMPORT ---
import libs_baja as steel
import libs_gempa as quake

# ... (Kode Setup Lainnya) ...

# === TAB 6: BAJA & GEMPA ===
with tabs[5]: # Asumsi ini tab baru
    st.markdown('<p class="sub_header">Analisa Baja & Beban Gempa</p>', unsafe_allow_html=True)
    
    sub_1, sub_2, sub_3 = st.tabs(["A. Balok WF", "B. Baja Ringan", "C. Beban Gempa"])
    
    # 1. BALOK BAJA WF
    with sub_1:
        st.info("Cek Kekuatan Balok WF (Lentur)")
        c1, c2 = st.columns(2)
        with c1:
            Mu_baja = st.number_input("Momen Mu (kNm)", 10.0, 500.0, 50.0)
            Lb_baja = st.number_input("Panjang Bentang (m)", 1.0, 12.0, 4.0)
            fy_baja = st.number_input("Mutu Baja Fy (MPa)", 240, 410, 250)
        with c2:
            # Database Profil Simple
            db_wf = {
                "WF 150x75": {'Zx': 88.8},
                "WF 200x100": {'Zx': 213},
                "WF 250x125": {'Zx': 324},
                "WF 300x150": {'Zx': 481},
                "WF 400x200": {'Zx': 1190}
            }
            pilih_wf = st.selectbox("Pilih Profil", list(db_wf.keys()))
            
            # Hitung
            eng_baja = steel.SNI_Steel_1729(fy_baja, 410)
            res_baja = eng_baja.cek_balok_lentur(Mu_baja, db_wf[pilih_wf], Lb_baja)
            
            if res_baja['Ratio'] <= 1.0:
                st.success(f"✅ {pilih_wf} AMAN (Ratio {res_baja['Ratio']:.2f})")
            else:
                st.error(f"❌ {pilih_wf} GAGAL (Ratio {res_baja['Ratio']:.2f})")
            st.caption(res_baja['Keterangan'])

    # 2. BAJA RINGAN
    with sub_2:
        st.info("Estimasi Material Atap")
        luas_atap = st.number_input("Luas Atap Miring (m2)", 20.0, 500.0, 100.0)
        jenis_atap = st.radio("Penutup Atap", ["Metal Pasir (Ringan)", "Genteng Keramik (Berat)"])
        
        calc_truss = steel.Baja_Ringan_Calc()
        mat_atap = calc_truss.hitung_kebutuhan_atap(luas_atap, jenis_atap)
        
        c_a, c_b, c_c = st.columns(3)
        c_a.metric("Kanal C (Btg)", mat_atap['C75.75 (Btg)'])
        c_b.metric("Reng (Btg)", mat_atap['Reng 30.45 (Btg)'])
        c_c.metric("Sekrup (Box)", mat_atap['Sekrup (Box)'])

    # 3. GEMPA
    with sub_3:
        st.info("Hitung Gaya Geser Dasar (V) SNI 1726")
        W_total = st.number_input("Berat Total Bangunan (kN)", 100.0, 10000.0, 2000.0)
        R_gempa = st.number_input("Faktor R (8=SRPMK, 3=Dinding)", 3.0, 8.0, 8.0)
        ss_in = st.number_input("Ss (Peta Gempa)", 0.0, 2.0, 0.7)
        s1_in = st.number_input("S1 (Peta Gempa)", 0.0, 1.0, 0.3)
        site_in = st.selectbox("Kelas Tanah", ["SD", "SE", "SC"])
        
        eng_gempa = quake.SNI_Gempa_1726(ss_in, s1_in, site_in)
        V_gempa, sds, sd1 = eng_gempa.hitung_base_shear(W_total, R_gempa)
        
        st.metric("Gaya Geser Dasar (V)", f"{V_gempa:.1f} kN")
        st.caption(f"Parameter Respon Spektrum: SDS={sds:.2f}, SD1={sd1:.2f}")


# ==============================================================================
# TAB 7: RAB FINAL (GABUNGAN SEMUA)
# ==============================================================================
with tabs[6]:
    st.markdown('<p class="sub_header">Rencana Anggaran Biaya (RAB) Terintegrasi</p>', unsafe_allow_html=True)
    
    # Collect Data
    vol_struk = st.session_state['structure'].get('vol_beton', 0)
    besi_struk = st.session_state['structure'].get('berat_besi', 0)
    
    vol_fp = st.session_state['pondasi'].get('fp_beton', 0)
    besi_fp = st.session_state['pondasi'].get('fp_besi', 0)
    vol_bk = st.session_state['pondasi'].get('bk_batu', 0)
    vol_gal = st.session_state['pondasi'].get('galian', 0)
    
    vol_talud = st.session_state['geotech'].get('vol_talud', 0)
    vol_pile = st.session_state['geotech'].get('vol_pile', 0)
    
    # Harga Dasar
    h_bahan = {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 'kayu': p_kayu, 'batu kali': p_batu, 'beton k300': p_beton_ready}
    h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
    
    # Hitung HSP
    hsp_beton = calc_biaya.hitung_hsp('beton_k250', h_bahan, h_upah)
    hsp_besi = calc_biaya.hitung_hsp('pembesian_polos', h_bahan, h_upah) / 10
    hsp_talud = calc_biaya.hitung_hsp('pasangan_batu_kali', h_bahan, h_upah)
    hsp_pile = calc_biaya.hitung_hsp('bore_pile_k300', h_bahan, h_upah)
    hsp_galian = 85000
    
    # Tabel RAB
    data_rab = [
        {"Pek": "I. STRUKTUR ATAS (BALOK/KOLOM)", "Vol": None, "Hrg": None, "Tot": None},
        {"Pek": "   Beton K-250", "Vol": vol_struk, "Hrg": hsp_beton, "Tot": vol_struk*hsp_beton},
        {"Pek": "   Pembesian", "Vol": besi_struk, "Hrg": hsp_besi, "Tot": besi_struk*hsp_besi},
        
        {"Pek": "II. STRUKTUR BAWAH (RUMAH)", "Vol": None, "Hrg": None, "Tot": None},
        {"Pek": "   Galian Tanah", "Vol": vol_gal, "Hrg": hsp_galian, "Tot": vol_gal*hsp_galian},
        {"Pek": "   Pas. Batu Kali (Sloof)", "Vol": vol_bk, "Hrg": hsp_talud, "Tot": vol_bk*hsp_talud},
        {"Pek": "   Beton Footplate", "Vol": vol_fp, "Hrg": hsp_beton, "Tot": vol_fp*hsp_beton},
        {"Pek": "   Pembesian Footplate", "Vol": besi_fp, "Hrg": hsp_besi, "Tot": besi_fp*hsp_besi},
        
        {"Pek": "III. GEOTEKNIK (LERENG & DALAM)", "Vol": None, "Hrg": None, "Tot": None},
        {"Pek": "   Dinding Penahan (Talud)", "Vol": vol_talud, "Hrg": hsp_talud, "Tot": vol_talud*hsp_talud},
        {"Pek": "   Bore Pile K-300", "Vol": vol_pile, "Hrg": hsp_pile, "Tot": vol_pile*hsp_pile},
    ]
    
    df_rab = pd.DataFrame(data_rab)
    
    # Formatter Aman
    def fmt(x): return f"{x:,.0f}" if pd.notnull(x) and x != "" else ""
    def fmt_vol(x): return f"{x:.2f}" if pd.notnull(x) and x != "" else ""
    
    df_show = df_rab.copy()
    df_show['Vol'] = df_show['Vol'].apply(fmt_vol)
    df_show['Hrg'] = df_show['Hrg'].apply(fmt)
    df_show['Tot'] = df_show['Tot'].apply(fmt)
    
    st.dataframe(df_show, use_container_width=True)
    
    grand_total = df_rab['Tot'].sum()
    st.success(f"### GRAND TOTAL PROYEK: Rp {grand_total:,.0f}")

# ... (setelah tabel RAB muncul)
    
    st.divider()
    st.markdown("### 📤 Export Laporan Proyek")
    
    # Siapkan Data untuk Excel
    session_summary = {
        'fc': fc_in, 'fy': fy_in, 
        'b': st.session_state['geo']['b'], 
        'h': st.session_state['geo']['h'],
        'sigma': sigma_tanah
    }
    
    # Generate Excel
    excel_file = engine_export.create_excel_report(df_rab, session_summary)
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📊 Download Laporan RAB & Teknis (.xlsx)",
            data=excel_file,
            file_name="Laporan_Proyek_IndoBIM.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col_dl2:
        st.info("File Excel mencakup: Rekap Biaya (RAB) dan Parameter Desain Teknis.")



