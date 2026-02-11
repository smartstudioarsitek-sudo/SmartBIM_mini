import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches  # PENTING: Untuk visualisasi balok/denah
from io import BytesIO
import json
import re
import time
from PIL import Image
import docx  # python-docx
from streamlit_drawable_canvas import st_canvas # Wajib ada di requirements.txt

# --- AI & GOOGLE LIBRARIES ---
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- IMPORT MODULE ENGINEERING LOKAL ---
# Pastikan 8 file libs_*.py ada di folder yang sama
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

# --- IMPORT BACKEND DATABASE (Untuk Chat History) ---
try:
    from backend_enginex import EnginexBackend
except ImportError:
    st.error("⚠️ File 'backend_enginex.py' tidak ditemukan. Upload file tersebut agar fitur Chat berfungsi.")
    st.stop()

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(
    page_title="IndoBIM x ENGINEX Ultimate", 
    layout="wide", 
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# --- CSS CUSTOM ---
st.markdown("""
<style>
    .main-header {font-size: 28px; font-weight: bold; color: #1E3A8A; margin-bottom: 5px;}
    .sub-header {font-size: 18px; font-weight: bold; color: #444;}
    
    /* Tabs Customization */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px 4px 0 0; gap: 1px; padding-top: 10px; padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A; color: white; }
    
    /* Chat Styling */
    .stChatMessage .avatar {background-color: #1E3A8A; color: white;}
    
    /* Button Styling */
    div.stButton > button {width: 100%; border-radius: 6px; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI STATE (MEMORY)
# ==========================================

# A. State Kalkulator (IndoBIM)
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'structure' not in st.session_state: st.session_state['structure'] = {}
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}
if 'arsitek_mep' not in st.session_state: st.session_state['arsitek_mep'] = {}
if 'drawing' not in st.session_state: st.session_state['drawing'] = {} # Untuk Data Gambar Canvas

# State untuk Report Excel (Menyimpan hasil hitungan terakhir)
for k in ['report_struk', 'report_baja', 'report_gempa', 'report_geo']:
    if k not in st.session_state: st.session_state[k] = {}

# B. State AI Chat (ENGINEX)
if 'backend' not in st.session_state: st.session_state.backend = EnginexBackend()
db = st.session_state.backend

if 'processed_files' not in st.session_state: st.session_state.processed_files = set()
if 'current_expert_active' not in st.session_state: st.session_state.current_expert_active = "👑 The GEMS Grandmaster"

# ==========================================
# 3. HELPER FUNCTIONS (AI BRIDGE)
# ==========================================

def get_project_summary_context():
    """
    Fungsi Pintar: Mengambil data teknis dari Tab Kalkulator 
    untuk dikirim ke AI sebagai konteks diskusi.
    """
    summary = "DATA TEKNIS PROYEK SAAT INI (Dari Kalkulator IndoBIM):\n"
    
    # 1. Struktur Beton
    if st.session_state.get('report_struk'):
        s = st.session_state['report_struk']
        summary += f"- Beton: Dimensi {s.get('Dimensi')}, Mu={s.get('Mu')} kNm, Perlu Tulangan={s.get('Tulangan')}\n"
    
    # 2. Struktur Baja
    if st.session_state.get('report_baja'):
        b = st.session_state['report_baja']
        summary += f"- Baja: Profil {b.get('Profil')}, Ratio Kekuatan={b.get('Ratio')}, Status={b.get('Status')}\n"
        
    # 3. Geoteknik
    if st.session_state.get('report_geo'):
        g = st.session_state['report_geo']
        summary += f"- Geoteknik: SF Talud={g.get('Talud_SF')}, Qall Bore Pile={g.get('Pile_Qall')} kN\n"
    
    # 4. Drawing/BIM
    if st.session_state.get('drawing'):
        d = st.session_state['drawing']
        summary += f"- Estimasi Gambar: Dinding {d.get('vol_dinding')} m2, Beton {d.get('vol_beton')} m3\n"
        
    return summary

def create_docx_from_text(text_content):
    """Export Jawaban AI ke MS Word"""
    try:
        doc = docx.Document()
        doc.add_heading('Laporan Konsultasi AI - IndoBIM', 0)
        for line in text_content.split('\n'):
            clean = line.strip()
            if clean.startswith('## '): doc.add_heading(clean.replace('## ', ''), level=2)
            elif clean.startswith('### '): doc.add_heading(clean.replace('### ', ''), level=3)
            elif clean.startswith('- ') or clean.startswith('* '): 
                try: doc.add_paragraph(clean, style='List Bullet')
                except: doc.add_paragraph(clean)
            elif clean: doc.add_paragraph(clean)
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except: return None

def execute_generated_code(code_str):
    """Menjalankan kode Python (Plotting) dari AI"""
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {e}")
        return False

# ==========================================
# 4. SIDEBAR GLOBAL (CONTROLLER)
# ==========================================
with st.sidebar:
    st.title("🏗️ SYSTEM CONTROLLER")
    
    # --- PILIH MODE APLIKASI ---
    app_mode = st.radio(
        "Pilih Mode Operasi:", 
        ["🧮 Kalkulator Teknik (Tools)", "🤖 Konsultan AI (Chat)"], 
        index=0
    )
    
    st.divider()
    
    # --- SETTING PROYEK (DATABASE) ---
    st.markdown("### 📁 Database Proyek")
    existing_projects = db.daftar_proyek()
    proj_mode = st.radio("Opsi:", ["Baru", "Buka"], horizontal=True, label_visibility="collapsed")
    
    if proj_mode == "Baru":
        nama_proyek = st.text_input("Nama Proyek Baru:", "Proyek Gedung A")
    else:
        nama_proyek = st.selectbox("Pilih Proyek:", existing_projects) if existing_projects else "Belum ada data"
    
    st.divider()

    # --- PARAMETER GLOBAL (HSD & Material) ---
    # Parameter ini dipakai oleh Kalkulator, tapi bisa diakses AI juga
    with st.expander("⚙️ Parameter & Harga Satuan", expanded=False):
        st.markdown("**Material & Tanah**")
        fc_in = st.number_input("Mutu Beton f'c (MPa)", 20, 50, 25)
        fy_in = st.number_input("Mutu Besi fy (MPa)", 240, 500, 400)
        gamma_tanah = st.number_input("Berat Tanah (kN/m3)", 14.0, 22.0, 18.0)
        phi_tanah = st.number_input("Sudut Geser (deg)", 10.0, 45.0, 30.0)
        c_tanah = st.number_input("Kohesi (kN/m2)", 0.0, 50.0, 5.0)
        sigma_tanah = st.number_input("Daya Dukung (kN/m2)", 50.0, 300.0, 150.0)
        
        st.markdown("---")
        st.markdown("**Harga Satuan (HSD)**")
        u_tukang = st.number_input("Tukang (Rp/OH)", 135000)
        u_pekerja = st.number_input("Pekerja (Rp/OH)", 110000)
        p_semen = st.number_input("Semen (Rp/kg)", 1500)
        p_pasir = st.number_input("Pasir (Rp/m3)", 250000)
        p_split = st.number_input("Split (Rp/m3)", 300000)
        p_besi = st.number_input("Besi (Rp/kg)", 14000)
        p_kayu = st.number_input("Kayu (Rp/m3)", 2500000)
        p_batu = st.number_input("Batu Kali (Rp/m3)", 280000)
        p_beton_ready = st.number_input("Readymix K300", 1100000)
        p_bata = st.number_input("Bata Merah (Bh)", 800)
        p_cat = st.number_input("Cat Tembok (Kg)", 25000)
        p_pipa = st.number_input("Pipa PVC 3/4 (m)", 15000)

# ==========================================
# 5. LOGIKA MODE: KALKULATOR TEKNIK (INDOBIM)
# ==========================================
if app_mode == "🧮 Kalkulator Teknik (Tools)":
    
    # Init Engines Engineering
    calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
    calc_biaya = ahsp.AHSP_Engine()
    calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
    calc_fdn = fdn.Foundation_Engine(sigma_tanah)
    engine_export = exp.Export_Engine()

    st.markdown(f'<div class="main-header">🛠️ Engineering Workspace: {nama_proyek}</div>', unsafe_allow_html=True)

    # --- NAVIGASI TABS TOOLS ---
    # Tab Modeling & Drawing digabung agar user bisa pilih metode input
    tabs = st.tabs([
        "🏠 Dash", "📂 BIM Import", "✏️ Model & Draw", "🏗️ Beton", 
        "🔩 Baja/Atap", "🌋 Gempa", "⛰️ Geoteknik", "💰 RAB Final"
    ])

    # --- TAB 1: DASHBOARD ---
    with tabs[0]:
        col1, col2, col3 = st.columns(3)
        col1.metric("Mutu Beton", f"{fc_in} MPa")
        col2.metric("Mutu Baja", f"{fy_in} MPa")
        col3.metric("Tanah (Phi)", f"{phi_tanah}°")
        st.info("Selamat Datang di IndoBIM Ultimate. Silakan gunakan tab di atas untuk perhitungan teknik.")

    # --- TAB 2: BIM IMPORT ---
    with tabs[1]:
        st.markdown('<p class="sub-header">Import Data IFC (Revit/ArchiCAD)</p>', unsafe_allow_html=True)
        uploaded_ifc = st.file_uploader("Upload .IFC", type=["ifc"], key="upl_ifc")
        
        if uploaded_ifc:
            try:
                with st.spinner("Analisa IFC..."):
                    eng_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                    df_s = eng_ifc.parse_structure()
                    q_a = eng_ifc.parse_architectural_quantities()
                    q_m = eng_ifc.parse_mep_quantities()
                    
                    c1, c2 = st.columns(2)
                    c1.success(f"Struktur: {len(df_s)} items")
                    c1.dataframe(df_s.head(3))
                    c2.info("Volume Arsitek & MEP:")
                    c2.write(q_a)
                    c2.write(q_m)
                    
                    if st.button("Simpan Data BIM ke RAB"):
                        st.session_state['arsitek_mep'] = {**q_a, **q_m}
                        st.session_state['bim_loads'] = eng_ifc.calculate_architectural_loads()['Total Load Tambahan (kN)']
                        st.toast("Data BIM Tersimpan!", icon="💾")
            except Exception as e: st.error(f"Error IFC: {e}")

    # --- TAB 3: MODELING & DRAWING (FITUR S_BawahRT PULIH DISINI) ---
    with tabs[2]:
        st.markdown('<p class="sub-header">Modeling Geometri</p>', unsafe_allow_html=True)
        sub_mod1, sub_mod2 = st.tabs(["A. Input Grid (Detail)", "B. Gambar Denah (Visual Canvas)"])
        
        # A. INPUT GRID
        with sub_mod1:
            col_mod1, col_mod2 = st.columns([1, 2])
            with col_mod1:
                L = st.number_input("Panjang Bentang (m)", 2.0, 12.0, st.session_state['geo']['L'])
                b = st.number_input("Lebar Balok (mm)", 150, 800, st.session_state['geo']['b'])
                h = st.number_input("Tinggi Balok (mm)", 200, 1500, st.session_state['geo']['h'])
                st.session_state['geo'] = {'L': L, 'b': b, 'h': h}
            with col_mod2:
                fig, ax = plt.subplots(figsize=(6, 2))
                # Menggunakan patches yang sudah diimport
                ax.add_patch(patches.Rectangle((0, 0), L, h/1000, facecolor='#2E86C1', edgecolor='black'))
                ax.set_xlim(-0.5, L+0.5); ax.set_ylim(-0.5, 2)
                ax.set_title(f"Visualisasi Balok {b}x{h} mm")
                st.pyplot(fig)

        # B. GAMBAR CANVAS (RESTORED FEATURE)
        with sub_mod2:
            st.info("💡 Gambar kotak ruangan di bawah ini. Sistem akan menghitung Luas Dinding & Volume Beton secara otomatis.")
            
            col_cv1, col_cv2 = st.columns([3, 1])
            with col_cv2:
                scale_factor = st.slider("Skala (Px/m)", 10, 50, 20)
                st.caption(f"1 Meter = {scale_factor} pixel")
            
            with col_cv1:
                # Canvas Interaktif
                canvas_result = st_canvas(
                    fill_color="rgba(46, 134, 193, 0.3)",
                    stroke_width=2,
                    stroke_color="#000",
                    background_color="#f0f2f6",
                    height=400, width=600,
                    drawing_mode="rect",
                    key="canvas",
                )
                
            # Proses Data Gambar
            rooms_data = []
            if canvas_result.json_data is not None:
                for i, obj in enumerate(canvas_result.json_data["objects"]):
                    w_m = obj["width"] / scale_factor
                    h_m = obj["height"] / scale_factor
                    rooms_data.append({
                        "Ruang": f"R-{i+1}",
                        "Keliling": round(2*(w_m+h_m), 2),
                        "Luas": round(w_m*h_m, 2)
                    })
            
            if rooms_data:
                df_rooms = pd.DataFrame(rooms_data)
                st.dataframe(df_rooms)
                
                # Rumus Estimasi Cepat (Rule of Thumb)
                keliling_total = df_rooms["Keliling"].sum()
                vol_dinding_draw = keliling_total * 3.5 # Tinggi 3.5m
                # Sloof + Ring + Kolom (Asumsi dimensi 15x15)
                vol_beton_draw = (keliling_total * 0.15 * 0.20) + (keliling_total * 0.15 * 0.15) + (len(rooms_data) * 4 * 0.15 * 0.15 * 3.5)
                
                st.success(f"✅ Estimasi Otomatis: Dinding {vol_dinding_draw:.2f} m2 | Beton {vol_beton_draw:.2f} m3")
                
                if st.button("Gunakan Data Gambar ini untuk RAB"):
                    st.session_state['drawing'] = {
                        'vol_dinding': vol_dinding_draw,
                        'vol_beton': vol_beton_draw
                    }
                    st.toast("Data Gambar Masuk ke RAB!", icon="💰")

    # --- TAB 4: BETON (SNI) ---
    with tabs[3]:
        st.markdown('<p class="sub-header">Analisa Struktur Atas (SNI 2847)</p>', unsafe_allow_html=True)
        c_s1, c_s2 = st.columns(2)
        with c_s1:
            q_dl = st.number_input("Beban Mati (DL) kN/m", 0.0, 50.0, 15.0)
            if st.session_state.get('bim_loads'):
                st.info(f"Ditambah Beban BIM: {st.session_state['bim_loads']} kN")
                q_dl += st.session_state['bim_loads'] / st.session_state['geo']['L']
            q_ll = st.number_input("Beban Hidup (LL) kN/m", 0.0, 50.0, 5.0)
            
        with c_s2:
            q_u = sni.SNI_Load_1727.komb_pembebanan(q_dl, q_ll)
            Mu = (1/8) * q_u * (st.session_state['geo']['L']**2)
            Vu = 0.5 * q_u * st.session_state['geo']['L']
            
            st.metric("Momen Ultimate (Mu)", f"{Mu:.2f} kNm", f"Geser Vu: {Vu:.2f} kN")
            
            As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
            dia = st.selectbox("Diameter Tulangan", [13, 16, 19, 22])
            n_bars = np.ceil(As_req / (0.25 * 3.14 * dia**2))
            
            st.success(f"Rekomen Tulangan: {int(n_bars)} D{dia} (As: {As_req:.0f} mm2)")
            
            # Simpan
            vol_beton = st.session_state['geo']['L'] * (st.session_state['geo']['b']/1000) * (st.session_state['geo']['h']/1000)
            berat_besi = vol_beton * 150 
            st.session_state['structure'] = {'vol_beton': vol_beton, 'berat_besi': berat_besi}
            
            # Simpan ke Context AI
            st.session_state['report_struk'] = {
                'Mu': round(Mu, 2), 'Vu': round(Vu, 2), 'Qu': round(q_u, 2), 
                'As_req': round(As_req, 2), 'Tulangan': f"{int(n_bars)} D{dia}",
                'Dimensi': f"{st.session_state['geo']['b']}x{st.session_state['geo']['h']}"
            }
            
            # Export DXF
            params_balok = {'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'dia': dia, 'n': n_bars, 'pjg': st.session_state['geo']['L']}
            dxf_balok = engine_export.create_dxf("BALOK", params_balok)
            st.download_button("📥 Download Shop Drawing Balok (.dxf)", dxf_balok, "Detail_Balok.dxf")

    # --- TAB 5: BAJA & ATAP ---
    with tabs[4]:
        sub_b1, sub_b2 = st.tabs(["A. Balok WF", "B. Atap Baja Ringan"])
        
        with sub_b1:
            c1, c2 = st.columns(2)
            with c1:
                Mu_baja = st.number_input("Momen Ultimate (kNm)", 10.0, 500.0, 50.0)
                Lb_baja = st.number_input("Panjang Bentang (m)", 1.0, 12.0, 4.0)
            with c2:
                db_wf = {"WF 150x75": {'Zx': 88.8}, "WF 200x100": {'Zx': 213}, "WF 250x125": {'Zx': 324}, "WF 300x150": {'Zx': 481}, "WF 400x200": {'Zx': 1190}}
                pilih_wf = st.selectbox("Pilih Profil WF", list(db_wf.keys()))
                
                engine_baja = steel.SNI_Steel_1729(fy_in, 410)
                res_baja = engine_baja.cek_balok_lentur(Mu_baja, db_wf[pilih_wf], Lb_baja)
                
                if res_baja['Ratio'] <= 1.0: st.success(f"✅ {pilih_wf} AMAN")
                else: st.error(f"❌ {pilih_wf} GAGAL")
                st.caption(res_baja['Keterangan'])
                
                st.session_state['report_baja'] = {'Profil': pilih_wf, 'Mu': Mu_baja, 'Phi_Mn': round(res_baja['Phi_Mn'], 2), 'Ratio': round(res_baja['Ratio'], 3), 'Status': res_baja['Status']}

        with sub_b2:
            luas_atap = st.number_input("Luas Atap Miring (m2)", 20.0, 500.0, 100.0)
            jenis = st.radio("Penutup Atap", ["Metal Pasir", "Genteng Keramik"])
            calc_ringan = steel.Baja_Ringan_Calc()
            res_ringan = calc_ringan.hitung_kebutuhan_atap(luas_atap, jenis)
            st.write(res_ringan)

    # --- TAB 6: GEMPA ---
    with tabs[5]:
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
            
            st.metric("Gaya Geser Dasar (V)", f"{V_gempa:.2f} kN")
            st.caption(f"Sds={sds:.2f}, Sd1={sd1:.2f}")
            st.session_state['report_gempa'] = {'V_gempa': round(V_gempa, 2), 'Sds': round(sds, 3), 'Sd1': round(sd1, 3), 'R': R_faktor, 'Site': site_class}

    # --- TAB 7: GEOTEKNIK ---
    with tabs[6]:
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
                st.download_button("📥 Shop Drawing (.dxf)", dxf_fp, "Pondasi.dxf")
                
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
                st.download_button("📥 Shop Drawing (.dxf)", dxf_talud, "Talud.dxf")

            with c2:
                dia_pile = st.selectbox("Diameter (cm)", [30, 40, 50, 60])
                depth = st.number_input("Kedalaman (m)", 6.0, 20.0, 10.0)
                nspt = st.number_input("N-SPT Rata2", 5, 50, 20)
                res_pile = calc_geo.hitung_bore_pile(dia_pile, depth, nspt)
                st.metric("Daya Dukung Izin", f"{res_pile['Q_allow']:.1f} kN")
                
            st.session_state['geotech'] = {
                'vol_talud': res_talud['Vol_Per_M'] * 20, 
                'vol_pile': res_pile['Vol_Beton'] * 10
            }
            
            st.session_state['report_geo'] = {
                'Talud_SF': f"{res_talud['SF_Geser']:.2f}", 
                'Pile_Qall': f"{res_pile['Q_allow']:.2f}",
                'Dimensi_Pile': f"D{dia_pile} L{depth}m"
            }

    # --- TAB 8: RAB FINAL ---
    with tabs[7]:
        st.markdown('<p class="sub-header">Rekapitulasi Anggaran Biaya (RAB)</p>', unsafe_allow_html=True)
        
        # 1. Collect Volume dari Semua Tab & Modul
        vol_struk = st.session_state['structure'].get('vol_beton', 0)
        besi_struk = st.session_state['structure'].get('berat_besi', 0)
        
        vol_fp = st.session_state['pondasi'].get('fp_beton', 0)
        besi_fp = st.session_state['pondasi'].get('fp_besi', 0)
        vol_bk = st.session_state['pondasi'].get('bk_batu', 0)
        vol_gal = st.session_state['pondasi'].get('galian', 0)
        
        vol_talud = st.session_state['geotech'].get('vol_talud', 0)
        vol_pile = st.session_state['geotech'].get('vol_pile', 0)
        
        # Prioritas: Gambar (Canvas) > BIM Import > Manual
        data_bim = st.session_state.get('arsitek_mep', {})
        data_draw = st.session_state.get('drawing', {})
        
        if data_draw: # Jika ada gambar manual, tambah ke volume
            vol_dinding = data_draw.get('vol_dinding', 0)
            vol_struk += data_draw.get('vol_beton', 0)
        else:
            vol_dinding = data_bim.get('Luas Dinding (m2)', 0)
            
        jml_pintu = data_bim.get('Jumlah Pintu (Unit)', 0)
        jml_jendela = data_bim.get('Jumlah Jendela (Unit)', 0)
        pjg_pipa = data_bim.get("Panjang Pipa (m')", 0)
        
        # 2. Harga Dasar
        h_bahan = {
            'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 
            'kayu': p_kayu, 'batu kali': p_batu, 'beton k300': p_beton_ready,
            'bata merah': p_bata, 'cat tembok': p_cat, 'pipa pvc': p_pipa
        }
        h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
        
        # 3. Hitung HSP
        hsp_beton = calc_biaya.hitung_hsp('beton_k250', h_bahan, h_upah)
        hsp_besi = calc_biaya.hitung_hsp('pembesian_polos', h_bahan, h_upah) / 10
        hsp_galian = 85000
        hsp_talud = calc_biaya.hitung_hsp('pasangan_batu_kali', h_bahan, h_upah)
        hsp_dinding = calc_biaya.hitung_hsp('pasangan_bata_merah', h_bahan, h_upah)
        hsp_plester = calc_biaya.hitung_hsp('plesteran', h_bahan, h_upah) * 2
        hsp_aci = calc_biaya.hitung_hsp('acian', h_bahan, h_upah) * 2
        hsp_cat = calc_biaya.hitung_hsp('cat_tembok', h_bahan, h_upah) * 2
        hsp_pintu = calc_biaya.hitung_hsp('pasang_kus_pintu', h_bahan, h_upah) + 500000 
        hsp_pipa = calc_biaya.hitung_hsp('pasang_pipa_pvc', h_bahan, h_upah)
        
        # 4. Tabel RAB Lengkap
        data_rab = [
            {"Pek": "I. PEKERJAAN TANAH", "Vol": None, "Hrg": None, "Tot": None},
            {"Pek": "   Galian Tanah", "Vol": vol_gal, "Hrg": hsp_galian, "Tot": vol_gal*hsp_galian},
            
            {"Pek": "II. PEKERJAAN STRUKTUR", "Vol": None, "Hrg": None, "Tot": None},
            {"Pek": "   Pas. Batu Kali", "Vol": vol_bk, "Hrg": hsp_talud, "Tot": vol_bk*hsp_talud},
            {"Pek": "   Beton Struktur", "Vol": vol_struk+vol_fp, "Hrg": hsp_beton, "Tot": (vol_struk+vol_fp)*hsp_beton},
            {"Pek": "   Pembesian", "Vol": besi_struk+besi_fp, "Hrg": hsp_besi, "Tot": (besi_struk+besi_fp)*hsp_besi},
            
            {"Pek": "III. PEKERJAAN ARSITEKTUR", "Vol": None, "Hrg": None, "Tot": None},
            {"Pek": "   Pas. Dinding Bata", "Vol": vol_dinding, "Hrg": hsp_dinding, "Tot": vol_dinding*hsp_dinding},
            {"Pek": "   Plesteran Dinding", "Vol": vol_dinding, "Hrg": hsp_plester, "Tot": vol_dinding*hsp_plester},
            {"Pek": "   Acian Dinding", "Vol": vol_dinding, "Hrg": hsp_aci, "Tot": vol_dinding*hsp_aci},
            {"Pek": "   Pengecatan Dinding", "Vol": vol_dinding, "Hrg": hsp_cat, "Tot": vol_dinding*hsp_cat},
            {"Pek": "   Pasang Pintu/Jendela", "Vol": jml_pintu+jml_jendela, "Hrg": hsp_pintu, "Tot": (jml_pintu+jml_jendela)*hsp_pintu},
            
            {"Pek": "IV. PEKERJAAN MEP", "Vol": None, "Hrg": None, "Tot": None},
            {"Pek": "   Instalasi Pipa Air", "Vol": pjg_pipa, "Hrg": hsp_pipa, "Tot": pjg_pipa*hsp_pipa},
            
            {"Pek": "V. PEKERJAAN GEOTEKNIK", "Vol": None, "Hrg": None, "Tot": None},
            {"Pek": "   Talud Penahan Tanah", "Vol": vol_talud, "Hrg": hsp_talud, "Tot": vol_talud*hsp_talud},
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
        
        # Download Excel Report (Multi Sheet)
        def generate_excel():
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet 1: Input Data
                df_in = pd.DataFrame({
                    'Parameter': ['Mutu Beton', 'Mutu Baja', 'Tanah'],
                    'Nilai': [f"fc {fc_in} MPa", f"fy {fy_in} MPa", f"C {c_tanah}"]
                })
                df_in.to_excel(writer, sheet_name='1. Input Data', index=False)
                
                # Sheet 2: Gaya Dalam & Desain
                d_struk = st.session_state.get('report_struk', {})
                df_force = pd.DataFrame({
                    'Item': ['Momen Mu', 'Geser Vu', 'Tulangan Perlu'],
                    'Nilai': [d_struk.get('Mu',0), d_struk.get('Vu',0), d_struk.get('Tulangan','-')]
                })
                df_force.to_excel(writer, sheet_name='2. Desain', index=False)
                
                # Sheet 3: RAB
                df_rab.to_excel(writer, sheet_name='3. RAB Final', index=False)
                
            return output.getvalue()

        excel_data = generate_excel()
        st.download_button(
            label="📊 Download Laporan Lengkap (.xlsx)",
            data=excel_data,
            file_name="Laporan_Lengkap_IndoBIM.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==========================================
# 6. LOGIKA MODE: KONSULTAN AI (ENGINEX)
# ==========================================
elif app_mode == "🤖 Konsultan AI (Chat)":
    
    st.markdown(f'<div class="main-header">🤖 AI Consultant: {nama_proyek}</div>', unsafe_allow_html=True)
    
    # --- SETUP API KEY ---
    with st.expander("🔑 Konfigurasi AI Key", expanded=False):
        user_key = st.text_input("Google API Key:", type="password")
        final_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    
    if not final_key:
        st.warning("⚠️ Masukkan API Key di sidebar atau secrets.")
        st.stop()
        
    genai.configure(api_key=final_key)
    
    # --- PILIH AHLI (PERSONA) ---
    personas = {
        "👑 The GEMS Grandmaster": "Anda adalah Project Director yang tahu segalanya. Jawab dengan bijak, strategis, dan teknis.",
        "🏗️ Ahli Struktur": "Anda adalah Senior Structural Engineer. Fokus pada keamanan, SNI, dan efisiensi material.",
        "💰 Ahli Estimator": "Anda adalah Quantity Surveyor. Fokus pada biaya, RAB, dan analisa harga.",
        "⚖️ Ahli Kontrak": "Anda adalah Ahli Hukum Konstruksi. Fokus pada FIDIC dan legalitas.",
        "🕌 Dewan Syariah": "Anda adalah Ulama Fiqih Bangunan. Fokus pada hukum halal/haram dalam properti."
    }
    
    c_p1, c_p2 = st.columns([3, 1])
    with c_p1:
        expert = st.selectbox("Pilih Ahli:", list(personas.keys()))
    with c_p2:
        if st.button("🧹 Clear Chat"):
            db.clear_chat(nama_proyek, expert)
            st.rerun()
            
    # --- CHAT INTERFACE ---
    history = db.get_chat_history(nama_proyek, expert)
    
    # Render History
    for chat in history:
        role_icon = "👤" if chat['role'] == "user" else "🤖"
        with st.chat_message(chat['role'], avatar=role_icon):
            st.markdown(chat['content'])
            
    # Input User
    if prompt := st.chat_input("Tanya sesuatu..."):
        # Save & Show User
        db.simpan_chat(nama_proyek, expert, "user", prompt)
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        # Generate Response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Berpikir..."):
                try:
                    model = genai.GenerativeModel("gemini-1.5-flash", system_instruction=personas[expert])
                    
                    # Konteks Data dari Kalkulator
                    context_data = get_project_summary_context()
                    
                    # Konteks History (Limited)
                    chat_context = [{"role": "user", "parts": [context_data + "\n\n" + prompt]}]
                    
                    response = model.generate_content(chat_context)
                    ans = response.text
                    
                    st.markdown(ans)
                    db.simpan_chat(nama_proyek, expert, "assistant", ans)
                    
                    # Cek Plotting
                    code_blocks = re.findall(r"```python(.*?)```", ans, re.DOTALL)
                    for code in code_blocks:
                        if "plt" in code:
                            st.caption("📈 Rendering Grafik...")
                            execute_generated_code(code)
                            
                    # Download Docs
                    docx_bio = create_docx_from_text(ans)
                    if docx_bio:
                        st.download_button("📄 Simpan Jawaban ke Word", docx_bio, "Jawaban_AI.docx")
                        
                except Exception as e:
                    st.error(f"Error AI: {e}")
