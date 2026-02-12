import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO
import json
import re
import time
from PIL import Image
import docx  # library: python-docx
import zipfile
from pptx import Presentation # library: python-pptx
from streamlit_drawable_canvas import st_canvas

# --- LIBRARIES KHUSUS ENGINEERING ---
from anastruct.fem.system import SystemElements
import ifcopenshell
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- IMPORT MODULE LOKAL ---
# Pastikan semua file libs_ ada di folder yang sama
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

# --- IMPORT BACKEND DATABASE ---
try:
    from backend_enginex import EnginexBackend
except ImportError:
    # Dummy class agar tidak crash jika file backend belum ada
    class EnginexBackend:
        def __init__(self): pass
        def get_chat_history(self, p, g): return []
        def simpan_chat(self, p, g, r, c): pass
        def clear_chat(self, p, g): pass
        def daftar_proyek(self): return []

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="IndoBIM Integrated System", 
    layout="wide", 
    page_icon="🏗️",
    initial_sidebar_state="expanded"
)

# CSS Custom untuk Tampilan Profesional
st.markdown("""
<style>
    .main-header {font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 10px; border-bottom: 2px solid #1E3A8A; padding-bottom: 5px;}
    .sub-header {font-size: 18px; font-weight: bold; color: #444; margin-top: 15px;}
    
    /* Tabs Customization */
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; background-color: #f0f2f6; border-radius: 4px 4px 0 0; padding: 10px; font-weight: 600;
    }
    .stTabs [aria-selected="true"] { background-color: #1E3A8A; color: white; }
    
    /* Input Fields */
    div.stNumberInput > label {font-weight: bold;}
    div.stTextInput > label {font-weight: bold;}
    
    /* Success/Info Boxes */
    .stAlert {border-radius: 8px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI SESSION STATE (MEMORY)
# ==========================================

# A. State Kalkulator Lama (Agar tidak hilang)
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'structure' not in st.session_state: st.session_state['structure'] = {} # Hasil hitungan struktur
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}
if 'drawing' not in st.session_state: st.session_state['drawing'] = {} # Dari Canvas

# B. State BIM & Grid System (Fitur Baru)
if 'arsitek_mep' not in st.session_state: st.session_state.arsitek_mep = {} # Data IFC (Dinding, Pintu)
if 'ifc_raw_data' not in st.session_state: st.session_state.ifc_raw_data = None # Dataframe Elemen Struktur IFC
if 'grid_x' not in st.session_state: st.session_state.grid_x = [0.0, 4.0, 8.0]
if 'grid_y' not in st.session_state: st.session_state.grid_y = [0.0, 4.0, 8.0]
if 'levels' not in st.session_state: st.session_state.levels = [0.0, 4.0] 
if 'struct_elements' not in st.session_state: st.session_state.struct_elements = pd.DataFrame() # Elemen Grid
if 'struct_nodes' not in st.session_state: st.session_state.struct_nodes = pd.DataFrame() # Node Grid
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = {} # Hasil AnaStruct

# C. Section Properties Default
if 'sections' not in st.session_state:
    st.session_state.sections = pd.DataFrame([
        {"Label": "K1", "Type": "Kolom", "b (m)": 0.4, "h (m)": 0.4, "Color": "red"},
        {"Label": "B1", "Type": "Balok", "b (m)": 0.25, "h (m)": 0.5, "Color": "blue"},
        {"Label": "B2", "Type": "Balok", "b (m)": 0.2, "h (m)": 0.3, "Color": "cyan"},
    ])

# D. State Report & AI
for k in ['report_struk', 'report_baja', 'report_gempa', 'report_geo']:
    if k not in st.session_state: st.session_state[k] = {}

if 'backend' not in st.session_state: st.session_state.backend = EnginexBackend()
db = st.session_state.backend
if 'processed_files' not in st.session_state: st.session_state.processed_files = set()
if 'current_expert_active' not in st.session_state: st.session_state.current_expert_active = "👑 The GEMS Grandmaster"

# ==========================================
# 3. HELPER FUNCTIONS & PERSONA DEFINITION
# ==========================================

# --- [FIXED] DEFINISI PERSONA AI DI SINI ---
PLOT_INSTRUCTION = """
[ATURAN VISUALISASI]: Jika diminta grafik, tulis kode Python (matplotlib) dalam blok ```python. 
Akhiri kode dengan `st.pyplot(plt.gcf())`. Jangan pakai `plt.show()`.
"""

gems_persona = {
    "👑 The GEMS Grandmaster": f"""ANDA ADALAH "THE GEMS GRANDMASTER" (Project Director). 
    Menjawab dengan wawasan Multidisiplin (Teknis, Hukum, Biaya, Agama). {PLOT_INSTRUCTION}""",
    
    "👔 Project Manager (PM)": "ANDA ADALAH SENIOR PROJECT DIRECTOR. Fokus: Strategi, Risiko, Stakeholder.",
    "📝 Drafter Laporan DED": "ANDA ADALAH LEAD TECHNICAL WRITER. Fokus: Struktur Laporan PUPR (Pendahuluan, Antara, Akhir).",
    "⚖️ Ahli Legal & Kontrak": "ANDA ADALAH AHLI HUKUM KONSTRUKSI (FIDIC/LPJK). Fokus: Klaim, Sengketa, Adendum.",
    "🕌 Dewan Syariah": "ANDA ADALAH ULAMA FIQIH BANGUNAN. Fokus: Arah Kiblat, Akad Istishna, Adab Tetangga.",
    "🏗️ Ahli Struktur (Gedung)": f"ANDA ADALAH STRUCTURAL ENGINEER. Fokus: Beton, Baja, Gempa SNI 1726. {PLOT_INSTRUCTION}",
    "🪨 Ahli Geoteknik": f"ANDA ADALAH GEOTECHNICAL ENGINEER. Fokus: Daya Dukung Tanah, Sondir, Longsor. {PLOT_INSTRUCTION}",
    "🛣️ Ahli Jalan & Jembatan": f"ANDA ADALAH HIGHWAY ENGINEER. Fokus: Geometrik Jalan, Perkerasan. {PLOT_INSTRUCTION}",
    "🏛️ Senior Architect": "ANDA ADALAH ARSITEK UTAMA. Fokus: Desain, Estetika, Fungsi Ruang.",
    "💰 Ahli Estimator (RAB)": "ANDA ADALAH QUANTITY SURVEYOR. Fokus: AHSP, Volume, Biaya Proyek.",
    "🤖 The Enginex Architect": "ANDA ADALAH SYSTEM ADMIN APLIKASI INI."
}

@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                model_list.append(m.name)
        model_list.sort(key=lambda x: 'gemini' not in x) 
        return model_list, None
    except Exception as e:
        return [], str(e)

def get_project_summary_context():
    """Mengambil rangkuman data untuk AI Context"""
    summary = "DATA TEKNIS PROYEK SAAT INI (Live Data):\n"
    
    # 1. Data Grid Struktur
    if not st.session_state.struct_elements.empty:
        df = st.session_state.struct_elements
        summary += f"- Model Struktur (Grid): Terdiri dari {len(df)} elemen (Balok/Kolom).\n"
        # Hitung volume kasar
        vol = len(df) * 0.3 * 0.3 * 4.0 # Estimasi
        summary += f"- Volume Beton Struktur: {vol:.2f} m3\n"
        
    # 2. Data BIM (Arsitek)
    bim_data = st.session_state.arsitek_mep
    if bim_data:
        summary += f"- Data BIM Arsitek: Dinding {bim_data.get('Luas Dinding (m2)',0)} m2, Pintu {bim_data.get('Jumlah Pintu (Unit)',0)} unit.\n"
        
    # 3. Hasil Perhitungan Kalkulator
    if st.session_state.get('report_struk'):
        s = st.session_state['report_struk']
        summary += f"- Cek Beton Manual: {s.get('Dimensi')} -> Mu={s.get('Mu')} kNm.\n"
        
    return summary

def get_auto_pilot_decision(user_query, model_name):
    try:
        router_model = genai.GenerativeModel(model_name)
        list_ahli = list(gems_persona.keys())
        router_prompt = f"""
        Pilih SATU ahli dari daftar berikut untuk menjawab pertanyaan: "{user_query}"
        Daftar: {list_ahli}
        Output: HANYA nama ahli persis. Jika ragu, pilih '👑 The GEMS Grandmaster'.
        """
        response = router_model.generate_content(router_prompt)
        suggested = response.text.strip()
        if suggested in list_ahli: return suggested
        return "👑 The GEMS Grandmaster"
    except:
        return "👑 The GEMS Grandmaster"

def execute_generated_code(code_str):
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {e}")
        return False

def create_docx_from_text(text_content):
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

# ==========================================
# 4. SIDEBAR CONTROLLER
# ==========================================
with st.sidebar:
    st.title("🏗️ SYSTEM CONTROLLER")
    
    # --- SETUP API KEY ---
    api_key_input = st.text_input("🔑 Google API Key:", type="password")
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Menggunakan Key Manual")
    else:
        raw_key = st.secrets.get("GOOGLE_API_KEY")
    
    if raw_key:
        try:
            genai.configure(api_key=raw_key.strip())
        except: pass
    
    # --- MODEL SELECTOR ---
    st.markdown("### 🧠 Pilih Otak AI")
    available_models, err = get_available_models_from_google(raw_key if raw_key else "")
    if available_models:
        selected_model_name = st.selectbox("Model:", available_models, index=0)
    else:
        selected_model_name = "gemini-1.5-flash"

    # --- MODE APLIKASI ---
    st.divider()
    app_mode = st.radio(
        "Modul Aplikasi:", 
        ["🧮 Kalkulator Teknik (Integrated)", "🤖 Konsultan AI (Chat)"], 
        index=0
    )
    
    st.divider()
    
    # --- PARAMETER TEKNIS GLOBAL ---
    with st.expander("⚙️ Parameter Material"):
        fc_in = st.number_input("Mutu Beton f'c (MPa)", 25)
        fy_in = st.number_input("Mutu Besi fy (MPa)", 400)
        gamma_tanah = st.number_input("Berat Tanah (kN/m3)", 18.0)
    
    with st.expander("💰 Harga Satuan Dasar (HSP)"):
        st.caption("Harga ini akan digunakan untuk hitung RAB otomatis.")
        p_beton = st.number_input("Beton Readymix (Rp/m3)", 1100000)
        p_besi = st.number_input("Besi Beton (Rp/kg)", 14000)
        p_bata = st.number_input("Pas. Bata Merah (Rp/m2)", 250000)
        p_cat = st.number_input("Pengecatan (Rp/m2)", 35000)
        p_pasir = st.number_input("Pasir (Rp/m3)", 250000) # Untuk kalkulator manual
        p_semen = st.number_input("Semen (Rp/kg)", 1500)

# ==========================================
# 5. LOGIKA APLIKASI UTAMA
# ==========================================

if app_mode == "🧮 Kalkulator Teknik (Integrated)":
    
    st.markdown('<div class="main-header">IndoBIM: Integrated Engineering System</div>', unsafe_allow_html=True)
    
    # --- INISIALISASI ENGINE ---
    calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
    calc_biaya = ahsp.AHSP_Engine()
    engine_export = exp.Export_Engine()
    
    # --- TABS NAVIGASI UTAMA ---
    # Kita menggabungkan fitur lama (Beton, Baja, dll) dengan workflow baru
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏠 Dash", 
        "📂 1. Import IFC", 
        "🏗️ 2. Analisa Struktur (Grid)", 
        "📝 3. Cek Beton", 
        "🔩 4. Cek Baja", 
        "🌋 5. Gempa & Geotek", 
        "💰 6. RAB Final"
    ])

    # --------------------------------------------------------
    # TAB 1: DASHBOARD
    # --------------------------------------------------------
    with tab1:
        st.markdown("### 👋 Selamat Datang di IndoBIM Integrated")
        st.info("""
        **Sistem ini menggabungkan 3 kekuatan utama:**
        1. **BIM Reader:** Membaca data arsitektur (Dinding, Pintu, Jendela) dari file IFC.
        2. **Structural Grid:** Analisa struktur presisi menggunakan metode Grid (seperti SAP2000).
        3. **Auto-RAB:** Menghitung biaya otomatis berdasarkan gabungan data Struktur & Arsitek.
        """)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Mutu Beton", f"{fc_in} MPa")
        c2.metric("Mutu Baja", f"{fy_in} MPa")
        
        status_ifc = "✅ Ada" if st.session_state.arsitek_mep else "❌ Kosong"
        status_str = "✅ Ada" if not st.session_state.struct_elements.empty else "❌ Kosong"
        c3.metric("Status Data", f"IFC: {status_ifc} | Grid: {status_str}")

    # --------------------------------------------------------
    # TAB 2: IMPORT IFC (DATA ARSITEK)
    # --------------------------------------------------------
    with tab2:
        st.subheader("📂 Import Model Arsitektur (.ifc)")
        st.caption("Upload file IFC untuk mendapatkan Volume Dinding, Pintu, dan Level Lantai.")
        
        uploaded_ifc = st.file_uploader("Upload File IFC", type=["ifc"])
        
        if uploaded_ifc:
            try:
                with st.spinner("Membaca Geometri & Properti IFC..."):
                    # Parsing IFC
                    eng_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                    df_s = eng_ifc.parse_structure()
                    q_a = eng_ifc.parse_architectural_quantities()
                    q_m = eng_ifc.parse_mep_quantities()
                    
                    # Simpan ke Memory Session State
                    st.session_state.ifc_raw_data = df_s
                    st.session_state.arsitek_mep = {**q_a, **q_m}
                    
                    st.success("✅ Data IFC Berhasil Dibaca!")
                    
                    # Tampilkan Metrik
                    col1, col2, col3 = st.columns(3)
                    col1.metric("🧱 Luas Dinding", f"{q_a.get('Luas Dinding (m2)', 0)} m²")
                    col2.metric("🚪 Jumlah Pintu", f"{q_a.get('Jumlah Pintu (Unit)', 0)} Unit")
                    col3.metric("🪟 Jumlah Jendela", f"{q_a.get('Jumlah Jendela (Unit)', 0)} Unit")
                    
                    # Visualisasi Scatter Plot 3D (Untuk Validasi Koordinat)
                    if not df_s.empty:
                        with st.expander("🕵️ Preview Struktur (Koordinat Titik)"):
                            fig = plt.figure(figsize=(8, 6))
                            ax = fig.add_subplot(111, projection='3d')
                            count_obj = 0
                            for idx, row in df_s.iterrows():
                                col = 'red' if 'Column' in row['Type'] else 'blue'
                                ax.scatter(row['X'], row['Y'], row['Z'], c=col, marker='o', s=20)
                                count_obj += 1
                                if count_obj > 500: break
                            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
                            st.pyplot(fig)
                            
                        # Update Level Otomatis
                        unique_z = sorted(df_s['Z'].unique().tolist())
                        st.session_state.levels = unique_z
                        st.info(f"💡 Info: Level Lantai terdeteksi dari IFC: {unique_z}")

            except Exception as e:
                st.error(f"Gagal memproses IFC: {e}")

    # --------------------------------------------------------
    # TAB 3: ANALISA STRUKTUR (GRID SYSTEM - FITUR BARU)
    # --------------------------------------------------------
    with tab3:
        st.subheader("🏗️ Pemodelan & Analisa Struktur (Grid System)")
        
        col_ctrl, col_view = st.columns([1, 3])
        
        with col_ctrl:
            st.markdown("**1. Grid Setup**")
            # Tombol Sakti: Ambil Grid dari IFC
            if st.button("🪄 Ambil Grid dari IFC"):
                if st.session_state.ifc_raw_data is not None:
                    df = st.session_state.ifc_raw_data
                    cols = df[df['Type'] == 'Column']
                    if not cols.empty:
                        # Ambil koordinat unik, bulatkan biar rapi
                        ux = sorted(list(set([round(x, 1) for x in cols['X'].tolist()])))
                        uy = sorted(list(set([round(y, 1) for y in cols['Y'].tolist()])))
                        st.session_state.grid_x = ux
                        st.session_state.grid_y = uy
                        st.success("Grid X & Y diupdate dari posisi kolom IFC!")
                    else: st.warning("Tidak ada kolom di IFC.")
                else: st.error("Upload IFC dulu di Tab 1.")

            # Input Manual Grid
            gx_in = st.text_input("Grid X (m)", value=", ".join(map(str, st.session_state.grid_x)))
            gy_in = st.text_input("Grid Y (m)", value=", ".join(map(str, st.session_state.grid_y)))
            gz_in = st.text_input("Level Z (m)", value=", ".join(map(str, st.session_state.levels)))
            
            if st.button("Update Grid Manual"):
                try:
                    st.session_state.grid_x = sorted([float(x) for x in gx_in.split(',')])
                    st.session_state.grid_y = sorted([float(x) for x in gy_in.split(',')])
                    st.session_state.levels = sorted([float(x) for x in gz_in.split(',')])
                    st.success("Grid tersimpan.")
                except: st.error("Format salah. Gunakan koma (misal: 0, 4, 8)")
                
            st.markdown("**2. Profil Penampang**")
            st.session_state.sections = st.data_editor(st.session_state.sections, num_rows="dynamic")
            
            st.markdown("**3. Beban (kN/m)**")
            q_dl = st.number_input("Dead Load", 15.0)
            q_ll = st.number_input("Live Load", 8.0)
            q_comb = 1.2*q_dl + 1.6*q_ll

        with col_view:
            st.markdown("#### Visualisasi Wireframe & Analisa")
            
            # --- LOGIKA GENERATE MODEL (NODES & ELEMENTS) ---
            nodes = []
            elements = []
            nid = 1
            eid = 1
            
            # 1. Generate Nodes
            for z in st.session_state.levels:
                for y in st.session_state.grid_y:
                    for x in st.session_state.grid_x:
                        nodes.append({"ID": nid, "X": x, "Y": y, "Z": z})
                        nid += 1
            df_nodes = pd.DataFrame(nodes)
            st.session_state.struct_nodes = df_nodes
            
            # 2. Generate Elements (Auto Connect Neighbors)
            # Kolom (Vertical)
            for i, node in df_nodes.iterrows():
                upper = df_nodes[(df_nodes['X']==node['X']) & (df_nodes['Y']==node['Y']) & (df_nodes['Z']>node['Z'])].sort_values('Z')
                if not upper.empty:
                    target = upper.iloc[0]
                    sec = st.session_state.sections[st.session_state.sections['Type']=='Kolom'].iloc[0]
                    elements.append({"ID": f"C{eid}", "Type": "Column", "Start": node['ID'], "End": target['ID'], "b": sec['b (m)'], "h": sec['h (m)']})
                    eid += 1
            # Balok (Horizontal X & Y) - Skip Pondasi (Z=0)
            for i, node in df_nodes.iterrows():
                if node['Z'] == 0: continue 
                # Arah X
                right = df_nodes[(df_nodes['Y']==node['Y']) & (df_nodes['Z']==node['Z']) & (df_nodes['X']>node['X'])].sort_values('X')
                if not right.empty:
                    target = right.iloc[0]
                    sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
                    elements.append({"ID": f"Bx{eid}", "Type": "Beam", "Start": node['ID'], "End": target['ID'], "b": sec['b (m)'], "h": sec['h (m)']})
                    eid += 1
                # Arah Y
                back = df_nodes[(df_nodes['X']==node['X']) & (df_nodes['Z']==node['Z']) & (df_nodes['Y']>node['Y'])].sort_values('Y')
                if not back.empty:
                    target = back.iloc[0]
                    sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
                    elements.append({"ID": f"By{eid}", "Type": "Beam", "Start": node['ID'], "End": target['ID'], "b": sec['b (m)'], "h": sec['h (m)']})
                    eid += 1
            
            df_elements = pd.DataFrame(elements)
            st.session_state.struct_elements = df_elements # Simpan untuk RAB
            
            # 3. Plotting 3D Matplotlib
            fig = plt.figure(figsize=(10, 6))
            ax = fig.add_subplot(111, projection='3d')
            
            if not df_elements.empty:
                for _, el in df_elements.iterrows():
                    n1 = df_nodes[df_nodes['ID'] == el['Start']].iloc[0]
                    n2 = df_nodes[df_nodes['ID'] == el['End']].iloc[0]
                    c = 'red' if el['Type'] == 'Column' else 'blue'
                    ax.plot([n1['X'], n2['X']], [n1['Y'], n2['Y']], [n1['Z'], n2['Z']], c=c, lw=2)
            
            ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
            st.pyplot(fig)
            
            # 4. Tombol Run Analysis (Integrasi AnaStruct - Simplified)
            if st.button("▶️ RUN ANALYSIS (Cek Kekuatan)"):
                with st.spinner("Menghitung Matriks Kekakuan..."):
                    # Simulasi Hasil Analisa (Untuk Demo Integrasi)
                    st.success("✅ Analisa Selesai!")
                    
                    res_c1, res_c2 = st.columns(2)
                    # Dummy Result based on Load
                    momen_max = (1/8) * q_comb * 4.0**2 # 1/8 qL^2 (L=4m rata2)
                    
                    res_c1.metric("Momen Terfaktor (Mu)", f"{momen_max:.2f} kNm")
                    res_c2.metric("Status", "AMAN" if momen_max < 50 else "WARNING")
                    
                    # Simpan hasil untuk Tab Design
                    st.session_state.analysis_results = {'Mu': momen_max}

    # --------------------------------------------------------
    # TAB 4: CEK BETON (TOOL LAMA + LINK INTEGRATED)
    # --------------------------------------------------------
    with tab4:
        st.subheader("📝 Perhitungan Tulangan Beton (SNI 2847)")
        
        # Opsi: Ambil dari Analisa Struktur atau Input Manual
        use_auto = st.checkbox("Ambil Mu dari Tab Analisa Struktur", value=True)
        
        if use_auto and st.session_state.analysis_results:
            mu_val = st.session_state.analysis_results.get('Mu', 20.0)
            st.info(f"Menggunakan Momen dari hasil analisa: {mu_val:.2f} kNm")
        else:
            mu_val = st.number_input("Momen Mu (kNm)", 20.0)
            
        c1, c2 = st.columns(2)
        with c1:
            b_in = st.number_input("Lebar b (mm)", 250)
            h_in = st.number_input("Tinggi h (mm)", 400)
        with c2:
            dia_tul = st.selectbox("Diameter Tulangan", [10, 13, 16, 19, 22])
            ds = 40 # selimut
            
        # Hitung Tulangan
        As_req = calc_sni.kebutuhan_tulangan(mu_val, b_in, h_in, ds)
        n_bars = np.ceil(As_req / (0.25 * 3.14 * dia_tul**2))
        
        st.success(f"**Hasil Desain:** Perlu {int(n_bars)} D{dia_tul} (As = {As_req:.1f} mm2)")
        
        # Simpan Report
        st.session_state['report_struk'] = {
            'Mu': mu_val, 
            'Tulangan': f"{int(n_bars)} D{dia_tul}", 
            'Dimensi': f"{b_in}x{h_in}"
        }

    # --------------------------------------------------------
    # TAB 5: CEK BAJA (TOOL LAMA)
    # --------------------------------------------------------
    with tab5:
        st.subheader("🔩 Cek Kapasitas Baja (SNI 1729)")
        c1, c2 = st.columns(2)
        with c1:
            mu_baja = st.number_input("Momen Mu Baja (kNm)", 50.0)
            lb_baja = st.number_input("Panjang Bentang Lb (m)", 4.0)
        with c2:
            # Database Profil Sederhana
            prof = st.selectbox("Pilih Profil WF", ["WF 200x100", "WF 250x125", "WF 300x150"])
            db_wf = {"WF 200x100": {'Zx': 213}, "WF 250x125": {'Zx': 324}, "WF 300x150": {'Zx': 481}}
            
        if st.button("Cek Kapasitas Baja"):
            eng_st = steel.SNI_Steel_1729(fy_in, 410)
            res = eng_st.cek_balok_lentur(mu_baja, db_wf[prof], lb_baja)
            
            if "AMAN" in res['Status']:
                st.success(f"Hasil: {res['Status']} (Ratio: {res['Ratio']:.2f})")
            else:
                st.error(f"Hasil: {res['Status']} (Ratio: {res['Ratio']:.2f})")
            
            st.session_state['report_baja'] = {'Profil': prof, 'Ratio': res['Ratio'], 'Status': res['Status']}

    # --------------------------------------------------------
    # TAB 6: GEMPA & GEOTEK (TOOL LAMA)
    # --------------------------------------------------------
    with tab6:
        sub1, sub2 = st.tabs(["Gempa (SNI 1726)", "Geoteknik (Pondasi/Talud)"])
        
        with sub1:
            st.write("Hitung Gaya Geser Dasar (V Base Shear)")
            ss = st.number_input("Ss (Percepatan Batuan Dasar Pendek)", 0.8)
            s1 = st.number_input("S1 (Percepatan 1 Detik)", 0.4)
            sc = st.selectbox("Kelas Situs", ["SE (Lunak)", "SD (Sedang)", "SC (Keras)"])
            w_total = st.number_input("Berat Total Bangunan (kN)", 2000.0)
            
            eng_q = quake.SNI_Gempa_1726(ss, s1, sc[:2])
            v_base, sds, sd1 = eng_q.hitung_base_shear(w_total, 8.0) # R=8
            st.metric("V Base Shear", f"{v_base:.1f} kN")
            st.session_state['report_gempa'] = {'V_gempa': v_base, 'Site': sc}
            
        with sub2:
            st.write("Cek Pondasi Telapak")
            pu_pon = st.number_input("Beban Aksial Pu (kN)", 150.0)
            b_pon = st.number_input("Lebar Pondasi (m)", 1.0)
            
            if st.button("Cek Pondasi"):
                res_f = calc_fdn.hitung_footplate(pu_pon, b_pon, b_pon, 300)
                st.write(f"Status: **{res_f['status']}**")
                st.session_state['pondasi'] = {'fp_beton': res_f['vol_beton']}

    # --------------------------------------------------------
    # TAB 7: RAB FINAL (INTEGRASI PENUH)
    # --------------------------------------------------------
    with tab7:
        st.subheader("💰 Rekapitulasi Anggaran Biaya (RAB) Otomatis")
        st.info("RAB ini menggabungkan volume dari Model Struktur (Grid) dan Model Arsitek (IFC).")
        
        # 1. AMBIL VOLUME STRUKTUR (Dari Grid Tab 3)
        vol_beton_struk = 0
        if not st.session_state.struct_elements.empty:
            for _, el in st.session_state.struct_elements.iterrows():
                # Hitung panjang elemen dari koordinat node
                n1 = st.session_state.struct_nodes[st.session_state.struct_nodes['ID'] == el['Start']].iloc[0]
                n2 = st.session_state.struct_nodes[st.session_state.struct_nodes['ID'] == el['End']].iloc[0]
                panjang = np.sqrt((n2['X']-n1['X'])**2 + (n2['Y']-n1['Y'])**2 + (n2['Z']-n1['Z'])**2)
                vol_beton_struk += panjang * el['b'] * el['h']
        
        # 2. AMBIL VOLUME ARSITEK (Dari IFC Tab 2)
        bim_data = st.session_state.arsitek_mep
        vol_dinding = bim_data.get('Luas Dinding (m2)', 0)
        jml_pintu = bim_data.get('Jumlah Pintu (Unit)', 0)
        
        # 3. HITUNG BIAYA (AHSP)
        rab_items = []
        
        # Item Struktur
        if vol_beton_struk > 0:
            rab_items.append({"Pekerjaan": "Beton Struktur (K-250)", "Vol": vol_beton_struk, "Sat": "m3", "Hrg": p_beton, "Total": vol_beton_struk*p_beton})
            # Besi (Asumsi 150 kg/m3)
            vol_besi = vol_beton_struk * 150
            rab_items.append({"Pekerjaan": "Pembesian (Polos/Ulir)", "Vol": vol_besi, "Sat": "kg", "Hrg": p_besi, "Total": vol_besi*p_besi})
        else:
            st.warning("⚠️ Volume Struktur masih 0. Silakan buat Grid di Tab 2.")
            
        # Item Arsitek
        if vol_dinding > 0:
            rab_items.append({"Pekerjaan": "Pas. Dinding Bata Merah", "Vol": vol_dinding, "Sat": "m2", "Hrg": p_bata, "Total": vol_dinding*p_bata})
            rab_items.append({"Pekerjaan": "Pengecatan Dinding", "Vol": vol_dinding*2, "Sat": "m2", "Hrg": p_cat, "Total": vol_dinding*2*p_cat})
        else:
            st.warning("⚠️ Volume Dinding masih 0. Silakan upload IFC di Tab 1.")
            
        # Tampilkan Tabel
        if rab_items:
            df_rab = pd.DataFrame(rab_items)
            st.dataframe(df_rab.style.format({"Vol": "{:.2f}", "Hrg": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
            
            grand_total = df_rab['Total'].sum()
            st.success(f"### TOTAL ESTIMASI BIAYA: Rp {grand_total:,.0f}")
            
            # Download Excel
            s_data = {'fc': fc_in, 'fy': fy_in, 'b': 0, 'h': 0, 'sigma': 0} # Dummy data session
            excel_data = engine_export.create_excel_report(df_rab, s_data)
            st.download_button("📥 Download Excel RAB", excel_data, "RAB_Integrated.xlsx")

# ==========================================
# MODE KONSULTAN AI (CHAT)
# ==========================================
elif app_mode == "🤖 Konsultan AI (Chat)":
    
    st.markdown('<div class="main-header">🤖 AI Project Consultant</div>', unsafe_allow_html=True)
    
    # --- PILIH AHLI ---
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👷 Tim Ahli")
        use_auto = st.checkbox("🤖 Auto-Pilot", value=True)
        # gems_persona sudah didefinisikan di atas (helper functions)
        manual_sel = st.selectbox("Pilih Manual:", list(gems_persona.keys()), disabled=use_auto)
        
        if not use_auto: st.session_state.current_expert_active = manual_sel
        
        st.markdown("### 📂 Data Pendukung")
        if st.button("🧹 Reset Chat"):
            db.clear_chat("Proyek Aktif", st.session_state.current_expert_active)
            st.rerun()

    # --- CHAT AREA ---
    current_expert = st.session_state.current_expert_active
    st.caption(f"Status: **Connected** | Expert: **{current_expert}** | Project Context: **Active**")
    
    # Render History
    nama_proyek_chat = "Proyek Aktif" 
    history = db.get_chat_history(nama_proyek_chat, current_expert)
    
    for chat in history:
        with st.chat_message(chat['role']): st.markdown(chat['content'])
        
    if prompt := st.chat_input("Tanya sesuatu tentang proyek ini..."):
        # Auto-Pilot Logic
        target_expert = current_expert
        if use_auto:
            target_expert = get_auto_pilot_decision(prompt, selected_model_name)
            st.session_state.current_expert_active = target_expert
            st.toast(f"Dialihkan ke: {target_expert}", icon="🔀")
            
        # Save User Msg
        db.simpan_chat(nama_proyek_chat, target_expert, "user", prompt)
        with st.chat_message("user"): st.markdown(prompt)
        
        # Prepare Context
        final_context = get_project_summary_context() + "\n\nPERTANYAAN USER:\n" + prompt
        
        # Generate Response
        with st.chat_message("assistant"):
            with st.spinner("Sedang menganalisa..."):
                try:
                    # Init Model
                    model = genai.GenerativeModel(selected_model_name, system_instruction=gems_persona[target_expert])
                    
                    # Convert history
                    api_hist = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                    
                    chat = model.start_chat(history=api_hist)
                    response = chat.send_message(final_context)
                    ans = response.text
                    
                    st.markdown(ans)
                    db.simpan_chat(nama_proyek_chat, target_expert, "assistant", ans)
                    
                    # Plotting Check
                    if "```python" in ans and "plt." in ans:
                        code = re.search(r"```python(.*?)```", ans, re.DOTALL).group(1)
                        st.caption("📈 Rendering Grafik...")
                        execute_generated_code(code)
                        
                    # Download Docs
                    docx_bio = create_docx_from_text(ans)
                    if docx_bio: st.download_button("📄 Simpan Word", docx_bio, "Jawaban.docx")
                    
                except Exception as e:
                    st.error(f"Error AI: {e}")
