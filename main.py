import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

# --- IMPORT SEMUA MODULE (PASTIKAN 8 FILE INI ADA DI FOLDER SAMA) ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

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

# --- INIT SESSION STATE ---
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'structure' not in st.session_state: st.session_state['structure'] = {}
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}

# [NEW] Init State untuk Report Excel Lengkap
if 'report_struk' not in st.session_state: st.session_state['report_struk'] = {}
if 'report_baja' not in st.session_state: st.session_state['report_baja'] = {}
if 'report_gempa' not in st.session_state: st.session_state['report_gempa'] = {}
if 'report_geo' not in st.session_state: st.session_state['report_geo'] = {}

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

# --- TABS UTAMA (8 MODUL) ---
tabs = st.tabs([
    "🏠 Dash", 
    "📂 BIM Import", 
    "📐 Modeling Grid", 
    "🏗️ Struktur Beton", 
    "🔩 Struktur Baja & Atap", 
    "🌋 Analisa Gempa", 
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
# TAB 3: MODELING (ARSITEK)
# ==============================================================================
with tabs[2]:
    st.markdown('<p class="sub_header">Modeling Geometri (Grid & Dimensi)</p>', unsafe_allow_html=True)
    
    col_mod1, col_mod2 = st.columns([1, 2])
    with col_mod1:
        L = st.number_input("Panjang Bentang (m)", 2.0, 12.0, st.session_state['geo']['L'])
        b = st.number_input("Lebar Balok (mm)", 150, 800, st.session_state['geo']['b'])
        h = st.number_input("Tinggi Balok (mm)", 200, 1500, st.session_state['geo']['h'])
        st.session_state['geo'] = {'L': L, 'b': b, 'h': h}
        
    with col_mod2:
        fig, ax = plt.subplots(figsize=(6, 2))
        rect = plt.Rectangle((0, 0), L, h/1000, facecolor='#3498DB', edgecolor='black')
        ax.add_patch(rect)
        ax.set_xlim(-0.5, L+0.5); ax.set_ylim(-0.5, 2)
        ax.set_title(f"Visualisasi Balok {b}x{h} mm")
        st.pyplot(fig)

# ==============================================================================
# TAB 4: STRUKTUR BETON (SNI)
# ==============================================================================
with tabs[3]:
    st.markdown('<p class="sub_header">Analisa Struktur Atas (SNI 2847)</p>', unsafe_allow_html=True)
    
    c_s1, c_s2 = st.columns(2)
    with c_s1:
        q_dl = st.number_input("Beban Mati (DL) kN/m", 0.0, 50.0, 15.0)
        q_ll = st.number_input("Beban Hidup (LL) kN/m", 0.0, 50.0, 5.0)
        
        if 'bim_loads' in st.session_state:
            st.info(f"Ditambah Beban BIM: {st.session_state['bim_loads']} kN")
            q_dl += st.session_state['bim_loads'] / st.session_state['geo']['L']
            
    with c_s2:
        # Hitung SNI
        q_u = sni.SNI_Load_1727.komb_pembebanan(q_dl, q_ll)
        Mu = (1/8) * q_u * (st.session_state['geo']['L']**2)
        Vu = 0.5 * q_u * st.session_state['geo']['L'] # [NEW] Hitung Geser untuk Report
        
        st.metric("Momen Ultimate (Mu)", f"{Mu:.2f} kNm", f"Geser Vu: {Vu:.2f} kN")
        
        As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
        dia = st.selectbox("Diameter Tulangan", [13, 16, 19, 22])
        n_bars = np.ceil(As_req / (0.25 * 3.14 * dia**2))
        
        st.success(f"Rekomen Tulangan: {int(n_bars)} D{dia} (As: {As_req:.0f} mm2)")
        
        # Simpan Vol Struktur Atas
        vol_beton = st.session_state['geo']['L'] * (st.session_state['geo']['b']/1000) * (st.session_state['geo']['h']/1000)
        berat_besi = vol_beton * 150 
        st.session_state['structure'] = {'vol_beton': vol_beton, 'berat_besi': berat_besi}
        
        # [NEW] Simpan Data Report Lengkap
        st.session_state['report_struk'] = {
            'Mu': round(Mu, 2), 'Vu': round(Vu, 2), 'Qu': round(q_u, 2), 
            'As_req': round(As_req, 2), 'Tulangan': f"{int(n_bars)} D{dia}",
            'Dimensi': f"{st.session_state['geo']['b']}x{st.session_state['geo']['h']}"
        }
        
        st.write("---")
        params_balok = {'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'dia': dia, 'n': n_bars, 'pjg': st.session_state['geo']['L']}
        dxf_balok = engine_export.create_dxf("BALOK", params_balok)
        st.download_button("📥 Download Shop Drawing Balok (.dxf)", dxf_balok, "Detail_Balok.dxf")

# ==============================================================================
# TAB 5: BAJA & ATAP (Updated with Report)
# ==============================================================================
with tabs[4]:
    st.markdown('<p class="sub_header">Struktur Baja (WF) & Baja Ringan</p>', unsafe_allow_html=True)
    sub_b1, sub_b2 = st.tabs(["A. Balok WF", "B. Atap Baja Ringan"])
    
    with sub_b1:
        st.info("Cek Kapasitas Lentur Balok WF (SNI 1729)")
        c1, c2 = st.columns(2)
        with c1:
            Mu_baja = st.number_input("Momen Ultimate (kNm)", 10.0, 500.0, 50.0)
            Lb_baja = st.number_input("Panjang Bentang (m)", 1.0, 12.0, 4.0)
            fy_baja = st.number_input("Mutu Baja Fy (MPa)", 240, 450, 250)
        with c2:
            db_wf = {
                "WF 150x75": {'Zx': 88.8},
                "WF 200x100": {'Zx': 213},
                "WF 250x125": {'Zx': 324},
                "WF 300x150": {'Zx': 481},
                "WF 400x200": {'Zx': 1190}
            }
            pilih_wf = st.selectbox("Pilih Profil WF", list(db_wf.keys()))
            
            engine_baja = steel.SNI_Steel_1729(fy_baja, 410)
            res_baja = engine_baja.cek_balok_lentur(Mu_baja, db_wf[pilih_wf], Lb_baja)
            
            if res_baja['Ratio'] <= 1.0:
                st.success(f"✅ {pilih_wf} AMAN (Ratio: {res_baja['Ratio']:.2f})")
            else:
                st.error(f"❌ {pilih_wf} GAGAL (Ratio: {res_baja['Ratio']:.2f})")
            st.caption(res_baja['Keterangan'])
            
            # [NEW] Simpan Data Report
            st.session_state['report_baja'] = {
                'Profil': pilih_wf, 'Mu': Mu_baja, 'Phi_Mn': round(res_baja['Phi_Mn'], 2), 
                'Ratio': round(res_baja['Ratio'], 3), 'Status': res_baja['Status']
            }

    with sub_b2:
        st.info("Kalkulator Kuda-Kuda Baja Ringan (SNI 7971)")
        luas_atap = st.number_input("Luas Atap Miring (m2)", 20.0, 500.0, 100.0)
        jenis = st.radio("Penutup Atap", ["Metal Pasir", "Genteng Keramik"])
        
        calc_ringan = steel.Baja_Ringan_Calc()
        res_ringan = calc_ringan.hitung_kebutuhan_atap(luas_atap, jenis)
        
        c_r1, c_r2, c_r3 = st.columns(3)
        c_r1.metric("Kanal C (Batang)", res_ringan['C75.75 (Btg)'])
        c_r2.metric("Reng (Batang)", res_ringan['Reng 30.45 (Btg)'])
        c_r3.metric("Sekrup (Box)", res_ringan['Sekrup (Box)'])

# ==============================================================================
# TAB 6: ANALISA GEMPA (Updated with Report)
# ==============================================================================
with tabs[5]:
    st.markdown('<p class="sub_header">Analisa Beban Gempa (SNI 1726:2019)</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        Ss = st.number_input("Ss (Short Period)", 0.0, 2.0, 0.8)
        S1 = st.number_input("S1 (1-Sec Period)", 0.0, 1.5, 0.4)
        site_class = st.selectbox("Kelas Situs Tanah", ["SE", "SD", "SC"], index=1)
    with c2:
        W_total = st.number_input("Berat Total Bangunan (kN)", 100.0, 50000.0, 2000.0)
        R_faktor = st.number_input("Faktor Reduksi Gempa (R)", 3.0, 8.0, 8.0)
        
        engine_gempa = quake.SNI_Gempa_1726(Ss, S1, site_class)
        V_gempa, sds, sd1 = engine_gempa.hitung_base_shear(W_total, R_faktor)
        
        st.divider()
        st.metric("Gaya Geser Dasar (V)", f"{V_gempa:.2f} kN")
        st.caption(f"Sds={sds:.2f}, Sd1={sd1:.2f}")
        
        # [NEW] Simpan Data Report
        st.session_state['report_gempa'] = {
            'V_gempa': round(V_gempa, 2), 'Sds': round(sds, 3), 'Sd1': round(sd1, 3), 
            'R': R_faktor, 'Site': site_class
        }

# ==============================================================================
# TAB 7: GEOTEKNIK & PONDASI (Updated with Report)
# ==============================================================================
with tabs[6]:
    st.markdown('<p class="sub_header">Analisa Bawah (Geoteknik & Pondasi)</p>', unsafe_allow_html=True)
    subtab_a, subtab_b = st.tabs(["A. Pondasi Rumah", "B. Geoteknik Lereng"])
    
    with subtab_a:
        c1, c2 = st.columns(2)
        with c1:
            Pu = st.number_input("Beban Aksial (kN)", 50.0, 1000.0, 150.0)
            B_fp = st.number_input("Lebar Pondasi (m)", 0.6, 2.0, 1.0)
            n_fp = st.number_input("Jumlah Titik", 1, 50, 12)
            res_fp = calc_fdn.hitung_footplate(Pu, B_fp, B_fp, 300)
            if "AMAN" in res_fp['status']: st.success(res_fp['status'])
            else: st.error(res_fp['status'])
            
            params_fp = {'B': B_fp}
            dxf_fp = engine_export.create_dxf("FOOTPLATE", params_fp)
            st.download_button("📥 Shop Drawing Footplate (.dxf)", dxf_fp, "Denah_Pondasi.dxf")
            
        with c2:
            L_bk = st.number_input("Panjang Total (m')", 10.0, 200.0, 50.0)
            res_bk = calc_fdn.hitung_batu_kali(L_bk, 0.3, 0.6, 0.8)
            st.metric("Volume Batu Kali", f"{res_bk['vol_pasangan']:.1f} m3")
            
        st.session_state['pondasi'] = {
            'fp_beton': res_fp['vol_beton'] * n_fp, 'fp_besi': res_fp['berat_besi'] * n_fp,
            'bk_batu': res_bk['vol_pasangan'], 'galian': (res_fp['vol_galian'] * n_fp) + res_bk['vol_galian']
        }

    with subtab_b:
        c1, c2 = st.columns(2)
        with c1:
            H_talud = st.number_input("Tinggi Talud (m)", 2.0, 8.0, 3.0)
            res_talud = calc_geo.hitung_talud_batu_kali(H_talud, 0.4, 1.5)
            if res_talud['Status'] == "AMAN": st.success("Talud AMAN")
            else: st.error("Talud BAHAYA")
            
            params_talud = {'H': H_talud, 'Ba': 0.4, 'Bb': 1.5}
            dxf_talud = engine_export.create_dxf("TALUD", params_talud)
            st.download_button("📥 Shop Drawing Talud (.dxf)", dxf_talud, "Potongan_Talud.dxf")

        with c2:
            dia_pile = st.selectbox("Diameter (cm)", [30, 40, 50, 60])
            depth = st.number_input("Kedalaman (m)", 6.0, 20.0, 10.0)
            nspt = st.number_input("N-SPT Rata2", 5, 50, 20)
            res_pile = calc_geo.hitung_bore_pile(dia_pile, depth, nspt)
            st.metric("Daya Dukung Izin", f"{res_pile['Q_allow']:.1f} kN")
            
        st.session_state['geotech'] = {
            'vol_talud': res_talud['Vol_Per_M'] * 20, # Asumsi 20m panjang
            'vol_pile': res_pile['Vol_Beton'] * 10    # Asumsi 10 titik
        }
        
        # [NEW] Simpan Report Geo
        st.session_state['report_geo'] = {
            'Talud_SF': f"{res_talud['SF_Geser']:.2f}", 
            'Pile_Qall': f"{res_pile['Q_allow']:.2f}",
            'Dimensi_Pile': f"D{dia_pile} L{depth}m"
        }

# ==============================================================================
# TAB 8: RAB FINAL & REPORTING EXCEL
# ==============================================================================
with tabs[7]:
    st.markdown('<p class="sub_header">Rencana Anggaran Biaya (RAB) Terintegrasi</p>', unsafe_allow_html=True)
    
    vol_struk = st.session_state['structure'].get('vol_beton', 0)
    besi_struk = st.session_state['structure'].get('berat_besi', 0)
    vol_fp = st.session_state['pondasi'].get('fp_beton', 0)
    besi_fp = st.session_state['pondasi'].get('fp_besi', 0)
    vol_bk = st.session_state['pondasi'].get('bk_batu', 0)
    vol_gal = st.session_state['pondasi'].get('galian', 0)
    vol_talud = st.session_state['geotech'].get('vol_talud', 0)
    vol_pile = st.session_state['geotech'].get('vol_pile', 0)
    
    h_bahan = {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 'kayu': p_kayu, 'batu kali': p_batu, 'beton k300': p_beton_ready}
    h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
    
    hsp_beton = calc_biaya.hitung_hsp('beton_k250', h_bahan, h_upah)
    hsp_besi = calc_biaya.hitung_hsp('pembesian_polos', h_bahan, h_upah) / 10
    hsp_talud = calc_biaya.hitung_hsp('pasangan_batu_kali', h_bahan, h_upah)
    hsp_pile = calc_biaya.hitung_hsp('bore_pile_k300', h_bahan, h_upah)
    hsp_galian = 85000
    
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
    
    def fmt(x): return f"{x:,.0f}" if pd.notnull(x) and x != "" else ""
    def fmt_vol(x): return f"{x:.2f}" if pd.notnull(x) and x != "" else ""
    
    df_show = df_rab.copy()
    df_show['Vol'] = df_show['Vol'].apply(fmt_vol)
    df_show['Hrg'] = df_show['Hrg'].apply(fmt)
    df_show['Tot'] = df_show['Tot'].apply(fmt)
    
    st.dataframe(df_show, use_container_width=True)
    grand_total = df_rab['Tot'].sum()
    st.success(f"### GRAND TOTAL PROYEK: Rp {grand_total:,.0f}")
    
    st.divider()
    st.markdown("### 📤 Download Laporan Lengkap")
    
    # [NEW] ENGINE EXCEL 5 SHEET
    def generate_excel():
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Sheet 1: Data Input
            df_in = pd.DataFrame({
                'Parameter': ['Mutu Beton (fc)', 'Mutu Baja (fy)', 'Berat Isi Tanah', 'Sudut Geser', 'Kohesi', 'Daya Dukung Tanah', 'Panjang Balok', 'Beban DL', 'Beban LL'],
                'Nilai': [fc_in, fy_in, gamma_tanah, phi_tanah, c_tanah, sigma_tanah, st.session_state['geo']['L'], q_dl, q_ll],
                'Satuan': ['MPa', 'MPa', 'kN/m3', 'deg', 'kN/m2', 'kN/m2', 'm', 'kN/m', 'kN/m']
            })
            df_in.to_excel(writer, sheet_name='1. Input Data', index=False)
            
            # Sheet 2: Standar & Acuan
            df_std = pd.DataFrame({
                'Item': ['Beton', 'Baja', 'Gempa', 'Geoteknik', 'Biaya'],
                'Acuan': ['SNI 2847:2019', 'SNI 1729:2015', 'SNI 1726:2019', 'SNI 8460:2017 (Rankine/Reese)', 'SE PUPR No. 182/2025']
            })
            df_std.to_excel(writer, sheet_name='2. Standar', index=False)
            
            # Sheet 3: Output Gaya Dalam (Forces)
            d_struk = st.session_state.get('report_struk', {})
            d_baja = st.session_state.get('report_baja', {})
            d_gempa = st.session_state.get('report_gempa', {})
            
            df_force = pd.DataFrame({
                'Elemen': ['Balok Beton', 'Balok Beton', 'Gempa Dasar (V)', 'Balok Baja'],
                'Jenis Gaya': ['Momen Ultimate (Mu)', 'Gaya Geser (Vu)', 'Base Shear', 'Momen Beban'],
                'Nilai': [d_struk.get('Mu',0), d_struk.get('Vu',0), d_gempa.get('V_gempa',0), d_baja.get('Mu',0)],
                'Satuan': ['kNm', 'kN', 'kN', 'kNm']
            })
            df_force.to_excel(writer, sheet_name='3. Gaya Dalam', index=False)
            
            # Sheet 4: Hasil Desain (Design Ratio)
            d_geo = st.session_state.get('report_geo', {})
            df_des = pd.DataFrame({
                'Elemen': ['Balok Beton', 'Balok Baja', 'Talud Lereng', 'Bore Pile'],
                'Parameter Cek': ['Tulangan Perlu', 'Ratio Kapasitas', 'Safety Factor (Geser)', 'Daya Dukung Izin'],
                'Hasil': [d_struk.get('Tulangan','-'), d_baja.get('Ratio','-'), d_geo.get('Talud_SF','-'), d_geo.get('Pile_Qall','-')],
                'Status': ['OK', d_baja.get('Status','-'), 'Lihat Tab', 'Lihat Tab']
            })
            df_des.to_excel(writer, sheet_name='4. Hasil Desain', index=False)
            
            # Sheet 5: RAB
            df_rab.to_excel(writer, sheet_name='5. RAB Final', index=False)
            
        return output.getvalue()

    excel_data = generate_excel()
    st.download_button(
        label="📊 Download Excel Report (5 Sheet)",
        data=excel_data,
        file_name="Laporan_Lengkap_IndoBIM.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.caption("Berisi: Input Data, Standar SNI, Rekap Gaya Dalam, Hasil Desain, dan RAB.")
