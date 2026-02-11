


import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import ai_engine as ai
from streamlit_drawable_canvas import st_canvas

# --- IMPORT SEMUA MODULE ---
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
if 'arsitek_mep' not in st.session_state: st.session_state['arsitek_mep'] = {}
if 'drawing' not in st.session_state: st.session_state['drawing'] = {} # State Canvas

for k in ['report_struk', 'report_baja', 'report_gempa', 'report_geo']:
    if k not in st.session_state: st.session_state[k] = {}

# --- SIDEBAR (GLOBAL INPUT) ---
with st.sidebar:
    st.title("IndoBIM Enterprise")
    st.caption("Integrated: BIM • Draw • Structure • Geotech")
    
    with st.expander("1. Material & Tanah", expanded=False):
        fc_in = st.number_input("Mutu Beton f'c (MPa)", 20, 50, 25)
        fy_in = st.number_input("Mutu Besi fy (MPa)", 240, 500, 400)
        gamma_tanah = st.number_input("Berat Isi Tanah (kN/m3)", 14.0, 22.0, 18.0)
        phi_tanah = st.number_input("Sudut Geser (deg)", 10.0, 45.0, 30.0)
        c_tanah = st.number_input("Kohesi (kN/m2)", 0.0, 50.0, 5.0)
        sigma_tanah = st.number_input("Daya Dukung Izin (kN/m2)", 50.0, 300.0, 150.0)

    with st.expander("2. Harga Satuan (HSD)", expanded=True):
        u_tukang = st.number_input("Tukang (Rp/Hari)", 135000)
        u_pekerja = st.number_input("Pekerja (Rp/Hari)", 110000)
        
        st.markdown("---")
        p_semen = st.number_input("Semen (Rp/kg)", 1500)
        p_pasir = st.number_input("Pasir (Rp/m3)", 250000)
        p_split = st.number_input("Split (Rp/m3)", 300000)
        p_besi = st.number_input("Besi (Rp/kg)", 14000)
        p_kayu = st.number_input("Kayu Bekisting (Rp/m3)", 2500000)
        p_batu = st.number_input("Batu Kali (Rp/m3)", 280000)
        p_beton_ready = st.number_input("Readymix K300 (Rp/m3)", 1100000)
        p_bata = st.number_input("Bata Merah (Rp/bh)", 800)
        p_cat = st.number_input("Cat Tembok (Rp/kg)", 25000)
        p_pipa = st.number_input("Pipa PVC 3/4 (Rp/m)", 15000)

# --- INIT ENGINES ---
calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
calc_biaya = ahsp.AHSP_Engine()
calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
calc_fdn = fdn.Foundation_Engine(sigma_tanah)
engine_export = exp.Export_Engine()

# --- TABS UTAMA ---
tabs = st.tabs([
    "🏠 Dash", "📂 BIM (Ars+MEP)", "✏️ Modeling & Drawing", "🏗️ Struktur", 
    "🔩 Baja/Atap", "🌋 Gempa", "⛰️ Geoteknik", "💰 RAB Final"
])

# 1. DASHBOARD
with tabs[0]:
    st.markdown('<p class="main_header">Dashboard Proyek Terintegrasi</p>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Standar Beton", "SNI 2847:2019", f"fc' {fc_in} MPa")
    c2.metric("Standar Gempa", "SNI 1726:2019", "Wilayah D (Medan)")
    c3.metric("Standar Biaya", "SE PUPR 182", "Update 2025")

# 2. BIM IMPORT
with tabs[1]:
    st.markdown('<p class="sub_header">Import BIM (Struktur, Arsitektur, MEP)</p>', unsafe_allow_html=True)
    uploaded_ifc = st.file_uploader("Upload File .IFC", type=["ifc"])
    
    if uploaded_ifc:
        try:
            with st.spinner("Mengekstrak BoQ dari IFC..."):
                engine_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                df_struk = engine_ifc.parse_structure()
                qty_ars = engine_ifc.parse_architectural_quantities()
                qty_mep = engine_ifc.parse_mep_quantities()
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.success(f"✅ Struktur: {len(df_struk)} Elemen")
                    st.dataframe(df_struk.head(3))
                with col_b:
                    st.info("✅ Volume Arsitektur & MEP Terbaca:")
                    st.write(qty_ars)
                    st.write(qty_mep)
                    
                if st.button("Simpan Data BIM ke RAB"):
                    st.session_state['arsitek_mep'] = {**qty_ars, **qty_mep}
                    st.toast("Data Volume Arsitek & MEP tersimpan!", icon="✅")
        except Exception as e:
            st.error(f"Gagal baca IFC: {e}")

# 3. MODELING & DRAWING (FITUR CANVAS KEMBALI!)
with tabs[2]:
    st.markdown('<p class="sub_header">Modeling Geometri & Gambar Denah</p>', unsafe_allow_html=True)
    sub_mod1, sub_mod2 = st.tabs(["A. Input Grid (Detail)", "B. Gambar Denah (Visual)"])
    
    with sub_mod1:
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

    with sub_mod2:
        st.info("💡 Gambar kotak ruangan di bawah ini. Sistem akan menghitung Luas Dinding & Volume Beton secara otomatis.")
        col_cv1, col_cv2 = st.columns([3, 1])
        with col_cv2:
            scale_factor = st.slider("Skala (Px/m)", 10, 50, 20)
        with col_cv1:
            canvas_result = st_canvas(fill_color="rgba(46, 134, 193, 0.3)", stroke_width=2, stroke_color="#000", background_color="#f0f2f6", height=400, width=600, drawing_mode="rect", key="canvas")
            
        rooms_data = []
        if canvas_result.json_data is not None:
            for i, obj in enumerate(canvas_result.json_data["objects"]):
                w_m = obj["width"] / scale_factor
                h_m = obj["height"] / scale_factor
                rooms_data.append({"Ruang": f"R-{i+1}", "Keliling": round(2*(w_m+h_m), 2)})
        
        if rooms_data:
            df_rooms = pd.DataFrame(rooms_data)
            st.dataframe(df_rooms)
            keliling_total = df_rooms["Keliling"].sum()
            
            # Rumus Estimasi Cepat (Rule of Thumb)
            vol_dinding_draw = keliling_total * 3.5 
            vol_beton_draw = (keliling_total * 0.15 * 0.20) + (keliling_total * 0.15 * 0.15) + (len(rooms_data) * 4 * 0.15 * 0.15 * 3.5)
            
            st.success(f"✅ Estimasi: Dinding {vol_dinding_draw:.2f} m2 | Beton {vol_beton_draw:.2f} m3")
            
            if st.button("Gunakan Data Gambar ini untuk RAB"):
                st.session_state['drawing'] = {'vol_dinding': vol_dinding_draw, 'vol_beton': vol_beton_draw}
                st.toast("Data Gambar Masuk ke RAB!", icon="💰")

# 4. STRUKTUR BETON
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
        q_u = sni.SNI_Load_1727.komb_pembebanan(q_dl, q_ll)
        Mu = (1/8) * q_u * (st.session_state['geo']['L']**2)
        Vu = 0.5 * q_u * st.session_state['geo']['L']
        st.metric("Momen Ultimate (Mu)", f"{Mu:.2f} kNm", f"Geser Vu: {Vu:.2f} kN")
        
        As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
        dia = st.selectbox("Diameter Tulangan", [13, 16, 19, 22])
        n_bars = np.ceil(As_req / (0.25 * 3.14 * dia**2))
        st.success(f"Rekomen Tulangan: {int(n_bars)} D{dia}")
        
        vol_beton = st.session_state['geo']['L'] * (st.session_state['geo']['b']/1000) * (st.session_state['geo']['h']/1000)
        berat_besi = vol_beton * 150 
        st.session_state['structure'] = {'vol_beton': vol_beton, 'berat_besi': berat_besi}
        
        st.session_state['report_struk'] = {'Mu': round(Mu, 2), 'Vu': round(Vu, 2), 'As_req': round(As_req, 2)}
        
        params_balok = {'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'dia': dia, 'n': n_bars}
        dxf_balok = engine_export.create_dxf("BALOK", params_balok)
        st.download_button("📥 Download Shop Drawing Balok (.dxf)", dxf_balok, "Detail_Balok.dxf")

# 5. BAJA & ATAP
with tabs[4]:
    st.markdown('<p class="sub_header">Struktur Baja (WF) & Baja Ringan</p>', unsafe_allow_html=True)
    sub_b1, sub_b2 = st.tabs(["A. Balok WF", "B. Atap Baja Ringan"])
    
    with sub_b1:
        c1, c2 = st.columns(2)
        with c1:
            Mu_baja = st.number_input("Momen Ultimate (kNm)", 10.0, 500.0, 50.0)
            Lb_baja = st.number_input("Panjang Bentang (m)", 1.0, 12.0, 4.0)
            fy_baja = st.number_input("Mutu Baja Fy (MPa)", 240, 450, 250)
        with c2:
            db_wf = {"WF 150x75": {'Zx': 88.8}, "WF 200x100": {'Zx': 213}, "WF 250x125": {'Zx': 324}}
            pilih_wf = st.selectbox("Pilih Profil WF", list(db_wf.keys()))
            
            engine_baja = steel.SNI_Steel_1729(fy_baja, 410)
            res_baja = engine_baja.cek_balok_lentur(Mu_baja, db_wf[pilih_wf], Lb_baja)
            
            if res_baja['Ratio'] <= 1.0: st.success(f"✅ {pilih_wf} AMAN")
            else: st.error(f"❌ {pilih_wf} GAGAL")
            st.session_state['report_baja'] = {'Profil': pilih_wf, 'Ratio': res_baja['Ratio']}

    with sub_b2:
        luas_atap = st.number_input("Luas Atap Miring (m2)", 20.0, 500.0, 100.0)
        jenis = st.radio("Penutup Atap", ["Metal Pasir", "Genteng Keramik"])
        calc_ringan = steel.Baja_Ringan_Calc()
        res_ringan = calc_ringan.hitung_kebutuhan_atap(luas_atap, jenis)
        st.write(res_ringan)

# 6. GEMPA
with tabs[5]:
    st.markdown('<p class="sub_header">Analisa Beban Gempa (SNI 1726:2019)</p>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        Ss = st.number_input("Ss", 0.0, 2.0, 0.8); S1 = st.number_input("S1", 0.0, 1.5, 0.4)
        site_class = st.selectbox("Kelas Situs", ["SE", "SD", "SC"], index=1)
    with c2:
        W_total = st.number_input("Berat Bangunan (kN)", 100.0, 50000.0, 2000.0)
        R_faktor = st.number_input("Faktor R", 3.0, 8.0, 8.0)
        engine_gempa = quake.SNI_Gempa_1726(Ss, S1, site_class)
        V_gempa, sds, sd1 = engine_gempa.hitung_base_shear(W_total, R_faktor)
        st.metric("Base Shear (V)", f"{V_gempa:.2f} kN")
        st.session_state['report_gempa'] = {'V_gempa': V_gempa}

# 7. GEOTEKNIK
with tabs[6]:
    st.markdown('<p class="sub_header">Analisa Bawah (Geoteknik)</p>', unsafe_allow_html=True)
    subtab_a, subtab_b = st.tabs(["A. Pondasi", "B. Lereng"])
    
    with subtab_a:
        Pu = st.number_input("Beban Aksial (kN)", 50.0, 1000.0, 150.0)
        B_fp = st.number_input("Lebar Pondasi (m)", 0.6, 2.0, 1.0)
        res_fp = calc_fdn.hitung_footplate(Pu, B_fp, B_fp, 300)
        if "AMAN" in res_fp['status']: st.success(res_fp['status'])
        
        params_fp = {'B': B_fp}
        dxf_fp = engine_export.create_dxf("FOOTPLATE", params_fp)
        st.download_button("📥 Shop Drawing (.dxf)", dxf_fp, "Pondasi.dxf")
        
        st.session_state['pondasi'] = {'fp_beton': res_fp['vol_beton'], 'fp_besi': res_fp['berat_besi'], 'galian': res_fp['vol_galian']}

    with subtab_b:
        H_talud = st.number_input("Tinggi Talud (m)", 2.0, 8.0, 3.0)
        res_talud = calc_geo.hitung_talud_batu_kali(H_talud, 0.4, 1.5)
        st.write(f"SF Guling: {res_talud['SF_Guling']:.2f}")
        
        params_talud = {'H': H_talud, 'Ba': 0.4, 'Bb': 1.5}
        dxf_talud = engine_export.create_dxf("TALUD", params_talud)
        st.download_button("📥 Shop Drawing Talud (.dxf)", dxf_talud, "Talud.dxf")
        
        st.session_state['geotech'] = {'vol_talud': res_talud['Vol_Per_M']}

# 8. RAB FINAL
with tabs[7]:
    st.markdown('<p class="sub_header">Rencana Anggaran Biaya (RAB) Lengkap</p>', unsafe_allow_html=True)
    
    # Ambil Data dari Session
    vol_struk = st.session_state['structure'].get('vol_beton', 0)
    besi_struk = st.session_state['structure'].get('berat_besi', 0)
    vol_fp = st.session_state['pondasi'].get('fp_beton', 0)
    vol_talud = st.session_state['geotech'].get('vol_talud', 0)
    
    # Data dari BIM & Drawing (Digabung)
    data_bim = st.session_state.get('arsitek_mep', {})
    data_draw = st.session_state.get('drawing', {})
    
    # Prioritas Drawing jika ada
    vol_dinding = data_draw.get('vol_dinding', data_bim.get('Luas Dinding (m2)', 0))
    vol_struk += data_draw.get('vol_beton', 0) # Tambah beton gambar ke beton struktur
    
    # Harga Dasar
    h_bahan = {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 'kayu': p_kayu, 'batu kali': p_batu, 'beton k300': p_beton_ready, 'bata merah': p_bata, 'cat tembok': p_cat, 'pipa pvc': p_pipa}
    h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
    
    # Hitung HSP
    hsp_beton = calc_biaya.hitung_hsp('beton_k250', h_bahan, h_upah)
    hsp_besi = calc_biaya.hitung_hsp('pembesian_polos', h_bahan, h_upah) / 10
    hsp_dinding = calc_biaya.hitung_hsp('pasangan_bata_merah', h_bahan, h_upah)
    hsp_talud = calc_biaya.hitung_hsp('pasangan_batu_kali', h_bahan, h_upah)
    
    data_rab = [
        {"Pek": "STRUKTUR BETON", "Vol": vol_struk+vol_fp, "Hrg": hsp_beton, "Tot": (vol_struk+vol_fp)*hsp_beton},
        {"Pek": "PEMBESIAN", "Vol": besi_struk, "Hrg": hsp_besi, "Tot": besi_struk*hsp_besi},
        {"Pek": "DINDING BATA", "Vol": vol_dinding, "Hrg": hsp_dinding, "Tot": vol_dinding*hsp_dinding},
        {"Pek": "TALUD BATU KALI", "Vol": vol_talud, "Hrg": hsp_talud, "Tot": vol_talud*hsp_talud},
    ]
    
    df_rab = pd.DataFrame(data_rab)
    st.dataframe(df_rab, use_container_width=True)
    st.success(f"### TOTAL RAB: Rp {df_rab['Tot'].sum():,.0f}")
    
    st.divider()
    # Excel Report
    def generate_excel():
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_rab.to_excel(writer, sheet_name='RAB Final', index=False)
            # Sheet Input
            pd.DataFrame({'Param': ['Mutu Beton'], 'Val': [fc_in]}).to_excel(writer, sheet_name='Input', index=False)
        return output.getvalue()

    excel_data = generate_excel()
    st.download_button("📊 Download Laporan Lengkap (.xlsx)", excel_data, "Laporan_IndoBIM.xlsx")
