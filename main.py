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

# --- LIBRARIES KHUSUS ENGINEERING & AI ---
# Pastikan library ini terinstall di environment: 
# pip install anastruct ifcopenshell google-generativeai
from anastruct.fem.system import SystemElements
import ifcopenshell
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- IMPORT MODULE LOKAL ---
# Pastikan file-file libs_*.py ada di folder yang sama
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

# --- IMPORT BACKEND DATABASE (Safety Mode) ---
# Menggunakan Dummy Class jika backend belum siap agar tidak error
try:
    from backend_enginex import EnginexBackend
except ImportError:
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

st.markdown("""
<style>
    .main-header {font-size: 26px; font-weight: bold; color: #1E3A8A; margin-bottom: 20px; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px;}
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { height: 45px; background-color: #f0f2f6; border-radius: 4px 4px 0 0; font-weight: 600;}
    .stTabs [aria-selected="true"] { background-color: #1E3A8A; color: white; }
    div.stButton > button {width: 100%; font-weight: 600; border-radius: 6px;}
    .metric-card {background-color: #f8f9fa; border-left: 5px solid #1E3A8A; padding: 10px; border-radius: 5px; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CLASS ENGINEERING (ANASTRUCT ENGINE)
# ==========================================
class StructuralEngine:
    def __init__(self, materials):
        self.materials = materials # dictionary: fc, fy
        
    def analyze_simple_frame(self, nodes, elements, load_value):
        """
        Menjalankan analisa 2D sederhana pada frame yang dipilih
        """
        ss = SystemElements() 
        
        # 1. Add Elements
        for idx, el in elements.iterrows():
            # Cari koordinat node start & end
            n1 = nodes[nodes['ID'] == el['Start']].iloc[0]
            n2 = nodes[nodes['ID'] == el['End']].iloc[0]
            
            # Hitung Inersia (I) sederhana berdasarkan dimensi b/h
            # E beton ~ 4700sqrt(fc) -> misal 23500 MPa
            # EI harus dikalikan faktor kekakuan, disini kita pakai dummy stiffness agar solver jalan
            EI_val = 5000 * (el['b'] * el['h']**3 / 12) * 10000 
            EA_val = 15000 * (el['b'] * el['h']) * 1000
            
            # AnaStruct bekerja di 2D (x, y). Kita mapping Z (tinggi) ke Y di AnaStruct.
            # Jarak Horizontal (X) -> x, Jarak Vertikal (Z) -> y
            ss.add_element(location=[[n1['X'], n1['Z']], [n2['X'], n2['Z']]], EI=EI_val, EA=EA_val)

        # 2. Add Supports (Tumpuan)
        # Asumsi Node dengan Z=0 adalah Jepit
        support_ids = []
        for idx, n in nodes.iterrows():
            if n['Z'] == 0:
                # Cari ID node di AnaStruct berdasarkan lokasi
                nid = ss.find_node_id(location=[n['X'], n['Z']])
                if nid:
                    ss.add_support_fixed(node_id=nid)
                    support_ids.append(nid)
        
        # 3. Add Loads (Beban Merata)
        # Tambahkan beban ke semua elemen horizontal (Balok)
        if load_value > 0:
            ss.q_load(q=-load_value, element_id='all', direction='y')

        # 4. Solve
        ss.solve()
        return ss

# ==========================================
# 3. INISIALISASI SESSION STATE (MEMORY)
# ==========================================

# A. State Kalkulator Lama (Agar Data Tidak Hilang)
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'drawing' not in st.session_state: st.session_state['drawing'] = {} 
if 'structure' not in st.session_state: st.session_state['structure'] = {} 
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}
for k in ['report_struk', 'report_baja', 'report_gempa', 'report_geo']:
    if k not in st.session_state: st.session_state[k] = {}

# B. State Fitur Baru (Grid & IFC) - DEFAULT VALUE DIISI AGAR TIDAK KOSONG
if 'grid_x' not in st.session_state: st.session_state.grid_x = [0.0, 4.0, 8.0]
if 'grid_y' not in st.session_state: st.session_state.grid_y = [0.0, 5.0, 10.0]
if 'levels' not in st.session_state: st.session_state.levels = [0.0, 4.0, 8.0] 
if 'arsitek_mep' not in st.session_state: st.session_state.arsitek_mep = {} 
if 'struct_elements' not in st.session_state: st.session_state.struct_elements = pd.DataFrame() 
if 'struct_nodes' not in st.session_state: st.session_state.struct_nodes = pd.DataFrame()
if 'sections' not in st.session_state:
    st.session_state.sections = pd.DataFrame([
        {"Label": "K1", "Type": "Kolom", "b (m)": 0.4, "h (m)": 0.4},
        {"Label": "B1", "Type": "Balok", "b (m)": 0.25, "h (m)": 0.5},
        {"Label": "B2", "Type": "Balok", "b (m)": 0.2, "h (m)": 0.3},
    ])

# C. AI State
if 'backend' not in st.session_state: st.session_state.backend = EnginexBackend()
db = st.session_state.backend
if 'current_expert_active' not in st.session_state: st.session_state.current_expert_active = "👑 The GEMS Grandmaster"
if 'processed_files' not in st.session_state: st.session_state.processed_files = set()

# ==========================================
# 4. HELPER FUNCTIONS (AI & UTILS)
# ==========================================
PLOT_INSTRUCTION = """[ATURAN VISUALISASI]: Gunakan matplotlib. Akhiri dengan st.pyplot(plt.gcf())."""

gems_persona = {
    "👑 The GEMS Grandmaster": f"PROJECT DIRECTOR. {PLOT_INSTRUCTION}",
    "🏗️ Ahli Struktur": f"STRUCTURAL ENGINEER. {PLOT_INSTRUCTION}",
    "💰 Ahli Estimator": "QUANTITY SURVEYOR.",
    "🏛️ Senior Architect": "ARSITEK UTAMA."
}

@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    try:
        model_list = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods: model_list.append(m.name)
        return sorted(model_list, key=lambda x: 'gemini' not in x), None
    except Exception as e: return [], str(e)

def get_auto_pilot_decision(query, model):
    try:
        m = genai.GenerativeModel(model)
        res = m.generate_content(f"Pilih satu ahli: {list(gems_persona.keys())} untuk: '{query}'. Output nama saja.")
        return res.text.strip() if res.text.strip() in gems_persona else "👑 The GEMS Grandmaster"
    except: return "👑 The GEMS Grandmaster"

def execute_generated_code(code_str):
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        exec(code_str, {}, local_vars)
        return True
    except: return False

def create_docx_from_text(text):
    try:
        doc = docx.Document()
        doc.add_paragraph(text)
        bio = BytesIO()
        doc.save(bio); bio.seek(0)
        return bio
    except: return None

def get_project_summary_context():
    summary = "DATA TEKNIS PROYEK:\n"
    if not st.session_state.struct_elements.empty:
        summary += f"- Struktur Grid: {len(st.session_state.struct_elements)} elemen.\n"
    if st.session_state.arsitek_mep:
        bim_data = st.session_state.arsitek_mep
        summary += f"- Arsitek: Dinding {bim_data.get('Luas Dinding (m2)',0)} m2.\n"
    return summary

# ==========================================
# 5. SIDEBAR MENU (NAVIGATION)
# ==========================================
with st.sidebar:
    st.title("🏗️ SYSTEM CONTROLLER")
    
    # API Key
    api_key_input = st.text_input("🔑 Google API Key:", type="password")
    raw_key = api_key_input if api_key_input else st.secrets.get("GOOGLE_API_KEY")
    if raw_key: 
        try: genai.configure(api_key=raw_key.strip())
        except: pass
    
    available_models, err = get_available_models_from_google(raw_key if raw_key else "")
    selected_model_name = st.selectbox("🧠 Otak AI:", available_models) if available_models else "gemini-1.5-flash"

    st.divider()

    # --- MENU NAVIGASI UTAMA (5 MODUL) ---
    st.subheader("📍 Navigasi Modul")
    menu_selection = st.radio(
        "Pilih Modul:",
        ["🏠 Dashboard Proyek", 
         "📂 Estimator (Arsitek)", 
         "🏗️ Analisa Struktur (Global)", 
         "🧮 Kalkulator Teknik (Detail)", 
         "💰 Integrasi RAB Final",
         "🤖 Konsultan AI"]
    )
    
    st.divider()
    
    # --- PARAMETER HARGA GLOBAL ---
    with st.expander("⚙️ Parameter & Harga"):
        fc_in = st.number_input("Mutu Beton f'c (MPa)", 25)
        fy_in = st.number_input("Mutu Besi fy (MPa)", 400)
        
        # Parameter Tanah (Untuk Kalkulator Geotek)
        phi_tanah = st.number_input("Phi Tanah (deg)", 30.0)
        sigma_tanah = st.number_input("Daya Dukung (kN/m2)", 150.0)
        
        st.markdown("**Harga Satuan (HSP)**")
        p_beton = st.number_input("Beton Readymix (Rp/m3)", 1100000)
        p_besi = st.number_input("Besi Beton (Rp/kg)", 14000)
        p_bata = st.number_input("Pas. Bata (Rp/m2)", 250000)
        p_cat = st.number_input("Cat Tembok (Rp/m2)", 35000)
        p_semen = st.number_input("Semen (Rp/kg)", 1500)
        p_pasir = st.number_input("Pasir (Rp/m3)", 250000)
        p_split = st.number_input("Split (Rp/m3)", 300000)
        p_kayu = st.number_input("Kayu (Rp/m3)", 2500000)
        p_batu = st.number_input("Batu Kali (Rp/m3)", 280000)
        p_beton_ready = st.number_input("Readymix K300", 1100000)
        p_pipa = st.number_input("Pipa 3/4 (m)", 15000)
        u_tukang = st.number_input("Tukang (OH)", 135000)
        u_pekerja = st.number_input("Pekerja (OH)", 110000)

# ==========================================
# 6. LOGIKA HALAMAN UTAMA
# ==========================================

# ------------------------------------------------------------------
# MODULE 1: DASHBOARD
# ------------------------------------------------------------------
if menu_selection == "🏠 Dashboard Proyek":
    st.markdown('<div class="main-header">🏠 Dashboard Proyek</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("Status Data BIM", "✅ Terisi" if st.session_state.arsitek_mep else "❌ Kosong")
    c2.metric("Status Model Struktur", "✅ Terisi" if not st.session_state.struct_elements.empty else "❌ Kosong")
    c3.metric("Mutu Beton Desain", f"{fc_in} MPa")
    
    st.info("Selamat Datang di IndoBIM Integrated System. Pilih Modul di Sidebar Kiri untuk memulai.")

# ------------------------------------------------------------------
# MODULE 2: ESTIMATOR (IFC)
# ------------------------------------------------------------------
elif menu_selection == "📂 Estimator (Arsitek)":
    st.markdown('<div class="main-header">📂 Estimator & QTO Arsitek</div>', unsafe_allow_html=True)
    
    uploaded_ifc = st.file_uploader("Upload File IFC", type=["ifc"])
    if uploaded_ifc:
        try:
            with st.spinner("Parsing IFC..."):
                eng_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                q_a = eng_ifc.parse_architectural_quantities()
                st.session_state.arsitek_mep = q_a
                st.success("✅ Data IFC Berhasil Dibaca!")
        except Exception as e: st.error(f"Error: {e}")
        
    if st.session_state.arsitek_mep:
        q = st.session_state.arsitek_mep
        c1, c2 = st.columns(2)
        c1.metric("Luas Dinding", f"{q.get('Luas Dinding (m2)', 0):.2f} m²")
        c2.metric("Jumlah Pintu", f"{q.get('Jumlah Pintu (Unit)', 0)} Unit")
        with st.expander("Lihat Detail JSON"):
            st.json(q)

# ------------------------------------------------------------------
# MODULE 3: ANALISA STRUKTUR (GRID & ANASTRUCT)
# ------------------------------------------------------------------
elif menu_selection == "🏗️ Analisa Struktur (Global)":
    st.markdown('<div class="main-header">🏗️ Analisa Struktur (Grid System)</div>', unsafe_allow_html=True)
    
    tab_grid, tab_model, tab_run = st.tabs(["1️⃣ Input Grid", "2️⃣ Model 3D", "3️⃣ Running Analysis"])
    
    # --- TAB 1: INPUT GRID ---
    with tab_grid:
        c_in, c_prop = st.columns([1, 2])
        with c_in:
            st.subheader("Grid Setup")
            gx_in = st.text_input("Grid X (m)", value=", ".join(map(str, st.session_state.grid_x)))
            gy_in = st.text_input("Grid Y (m)", value=", ".join(map(str, st.session_state.grid_y)))
            gz_in = st.text_input("Level Z (m)", value=", ".join(map(str, st.session_state.levels)))
            if st.button("Update Grid System"):
                try:
                    st.session_state.grid_x = sorted([float(x) for x in gx_in.split(',')])
                    st.session_state.grid_y = sorted([float(x) for x in gy_in.split(',')])
                    st.session_state.levels = sorted([float(x) for x in gz_in.split(',')])
                    st.success("Grid Updated!")
                except: st.error("Format Input Salah (Gunakan Koma)")
        with c_prop:
            st.subheader("Section Properties")
            st.session_state.sections = st.data_editor(st.session_state.sections, num_rows="dynamic")

    # --- TAB 2: MODEL 3D ---
    with tab_model:
        st.subheader("Visualisasi Wireframe")
        
        # LOGIC: GENERATE NODES & ELEMENTS FROM GRID
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
        
        # 2. Generate Elements (Connectivity)
        # Columns (Vertical)
        for i, node in df_nodes.iterrows():
            upper = df_nodes[(df_nodes['X']==node['X']) & (df_nodes['Y']==node['Y']) & (df_nodes['Z']>node['Z'])].sort_values('Z')
            if not upper.empty:
                target = upper.iloc[0]
                sec = st.session_state.sections[st.session_state.sections['Type']=='Kolom'].iloc[0]
                elements.append({"ID": f"C{eid}", "Type": "Column", "Start": node['ID'], "End": target['ID'], "b": sec['b (m)'], "h": sec['h (m)']})
                eid += 1
        
        # Beams (Horizontal) - Skip Foundation Level
        for i, node in df_nodes.iterrows():
            if node['Z'] == 0: continue
            # X-Beams
            right = df_nodes[(df_nodes['Y']==node['Y']) & (df_nodes['Z']==node['Z']) & (df_nodes['X']>node['X'])].sort_values('X')
            if not right.empty:
                target = right.iloc[0]
                sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
                elements.append({"ID": f"Bx{eid}", "Type": "Beam", "Start": node['ID'], "End": target['ID'], "b": sec['b (m)'], "h": sec['h (m)']})
                eid += 1
            # Y-Beams
            back = df_nodes[(df_nodes['X']==node['X']) & (df_nodes['Z']==node['Z']) & (df_nodes['Y']>node['Y'])].sort_values('Y')
            if not back.empty:
                target = back.iloc[0]
                sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
                elements.append({"ID": f"By{eid}", "Type": "Beam", "Start": node['ID'], "End": target['ID'], "b": sec['b (m)'], "h": sec['h (m)']})
                eid += 1
                
        df_elements = pd.DataFrame(elements)
        st.session_state.struct_elements = df_elements # Simpan untuk RAB
        
        # Plotting
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

    # --- TAB 3: RUNNING ANASTRUCT ---
    with tab_run:
        st.subheader("Engine Analisa Struktur (2D Portal)")
        
        # Select Portal Frame to Analyze
        st.write("Pilih Grid Y untuk menganalisa Portal (X-Z plane)")
        sel_grid_y = st.selectbox("Pilih Grid Y:", st.session_state.grid_y)
        
        # Filter Nodes & Elements on this Plane
        plane_nodes = df_nodes[df_nodes['Y'] == sel_grid_y]
        plane_ids = plane_nodes['ID'].tolist()
        plane_els = df_elements[(df_elements['Start'].isin(plane_ids)) & (df_elements['End'].isin(plane_ids))]
        
        load_val = st.number_input("Beban Merata (kN/m)", 15.0)
        
        if st.button("▶️ RUN ANALYSIS"):
            with st.spinner("Menghitung Matriks Kekakuan..."):
                engine = StructuralEngine({'fc': fc_in, 'fy': fy_in})
                # Running Analysis
                ss_result = engine.analyze_simple_frame(plane_nodes, plane_els, load_val)
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Diagram Momen (Bidang M)**")
                    fig_m = ss_result.show_bending_moment(show=False)
                    st.pyplot(fig_m)
                with c2:
                    st.write("**Deformasi Struktur**")
                    fig_d = ss_result.show_displacement(show=False)
                    st.pyplot(fig_d)
                    
                st.success("✅ Analisa Selesai!")

# ------------------------------------------------------------------
# MODULE 4: KALKULATOR TEKNIK (FITUR LAMA DIKEMBALIKAN)
# ------------------------------------------------------------------
elif menu_selection == "🧮 Kalkulator Teknik (Detail)":
    st.markdown('<div class="main-header">🧮 Kalkulator Teknik Detail</div>', unsafe_allow_html=True)
    st.info("Modul ini berisi alat hitung detail (Beton, Baja, Gempa, dll) dari versi aplikasi sebelumnya.")
    
    # Init Engines Lokal
    calc_sni_local = sni.SNI_Concrete_2847(fc_in, fy_in)
    calc_biaya = ahsp.AHSP_Engine()
    calc_fdn = fdn.Foundation_Engine(sigma_tanah)
    calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, 0)
    engine_export = exp.Export_Engine()
    
    tab_calc1, tab_calc2, tab_calc3, tab_calc4, tab_calc5 = st.tabs([
        "✏️ Model & Draw", "🏗️ Beton (SNI)", "🔩 Baja/Atap", "🌋 Gempa", "⛰️ Geoteknik"
    ])
    
    # 1. CANVAS DRAWING
    with tab_calc1:
        st.subheader("Canvas Drawing & Estimasi")
        scale = st.slider("Skala Px/m", 10, 50, 20)
        canvas = st_canvas(fill_color="rgba(0, 150, 255, 0.3)", stroke_width=2, height=300, width=600, drawing_mode="rect", key="cvs")
        if canvas.json_data:
            rooms = []
            for obj in canvas.json_data["objects"]:
                w, h_ = obj["width"]/scale, obj["height"]/scale
                rooms.append({"Keliling": 2*(w+h_), "Luas": w*h_})
            if rooms:
                df_r = pd.DataFrame(rooms)
                v_dinding = df_r["Keliling"].sum() * 3.5
                v_beton = (df_r["Keliling"].sum() * 0.15 * 0.35)
                st.success(f"Est. Dinding: {v_dinding:.1f} m2 | Beton: {v_beton:.1f} m3")
                if st.button("Simpan Data Canvas"):
                    st.session_state['drawing'] = {'vol_dinding': v_dinding, 'vol_beton': v_beton}

    # 2. BETON
    with tab_calc2:
        c1, c2 = st.columns(2)
        with c1:
            q_dl = st.number_input("DL (kN/m)", 0.0, 50.0, 15.0)
            q_ll = st.number_input("LL (kN/m)", 0.0, 50.0, 5.0)
            b_b = st.number_input("b (mm)", 250)
            h_b = st.number_input("h (mm)", 400)
        with c2:
            q_u = 1.2*q_dl + 1.6*q_ll
            L_b = st.number_input("Panjang Bentang (m)", 6.0)
            Mu = (1/8) * q_u * (L_b**2)
            As_req = calc_sni_local.kebutuhan_tulangan(Mu, b_b, h_b, 40)
            dia = st.selectbox("D Tulangan", [13,16,19,22])
            n_bars = np.ceil(As_req / (0.25 * 3.14 * dia**2))
            st.metric("Momen Mu", f"{Mu:.1f} kNm")
            st.success(f"Desain: {int(n_bars)} D{dia}")
            # Simpan data
            st.session_state['structure'] = {'vol_beton': L_b*(b_b/1000)*(h_b/1000), 'berat_besi': 50} 

    # 3. BAJA
    with tab_calc3:
        st.subheader("Cek Kapasitas Baja")
        mu_b = st.number_input("Mu Baja (kNm)", 50.0)
        sel_wf = st.selectbox("Profil", ["WF 200", "WF 250"])
        st.write("Hasil Cek: AMAN (Dummy Result for Demo)")
        st.subheader("Atap Baja Ringan")
        la = st.number_input("Luas Atap (m2)", 100.0)
        st.write(f"Kebutuhan Baja Ringan: {la*1.5} batang (Estimasi)")

    # 4. GEMPA
    with tab_calc4:
        st.subheader("Base Shear SNI 1726")
        ss = st.number_input("Ss", 0.8); s1 = st.number_input("S1", 0.4)
        v_base = 0.8 * 2000 / 8 
        st.metric("Base Shear V", f"{v_base:.1f} kN")

    # 5. GEOTEK
    with tab_calc5:
        st.subheader("Pondasi & Talud")
        pu = st.number_input("Pu (kN)", 150.0)
        bf = st.number_input("Lebar Pondasi (m)", 1.0)
        res_f = calc_fdn.hitung_footplate(pu, bf, bf, 300)
        st.write(f"Status Pondasi: {res_f['status']}")
        st.session_state['pondasi']['fp_beton'] = res_f['vol_beton']

# ------------------------------------------------------------------
# MODULE 5: INTEGRASI RAB FINAL
# ------------------------------------------------------------------
elif menu_selection == "💰 Integrasi RAB Final":
    st.markdown('<div class="main-header">💰 Rekapitulasi Biaya</div>', unsafe_allow_html=True)
    
    calc_biaya = ahsp.AHSP_Engine()
    engine_export = exp.Export_Engine()

    # Combine Data
    d_str = st.session_state.get('structure', {})
    d_pon = st.session_state.get('pondasi', {})
    d_geo = st.session_state.get('geotech', {})
    d_bim = st.session_state.get('arsitek_mep', {})
    d_draw = st.session_state.get('drawing', {})
    
    # Volume Gabungan
    vol_beton = d_str.get('vol_beton', 0) + d_pon.get('fp_beton', 0) + d_draw.get('vol_beton', 0)
    
    # Tambahkan volume dari Modul Struktur (Grid) jika ada
    if not st.session_state.struct_elements.empty:
        # Hitung volume grid simplifikasi
        for _, el in st.session_state.struct_elements.iterrows():
             # Estimasi panjang rata2 4m per elemen
             vol_beton += 4.0 * el['b'] * el['h']

    vol_besi = d_str.get('berat_besi', 0) + d_pon.get('fp_besi', 0) + (vol_beton * 150)
    vol_dinding = d_draw.get('vol_dinding', 0) if d_draw else d_bim.get('Luas Dinding (m2)', 0)
    
    # Harga Dasar (Ambil dari Sidebar)
    h_mat = {'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 'kayu': p_kayu, 'batu kali': p_batu, 'beton k300': p_beton_ready, 'bata merah': p_bata, 'cat tembok': p_cat, 'pipa pvc': p_pipa}
    h_wage = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
    
    # Hitung HSP
    hsp_b = calc_biaya.hitung_hsp('beton_k250', h_mat, h_wage)
    hsp_s = calc_biaya.hitung_hsp('pembesian_polos', h_mat, h_wage) / 10
    hsp_d = calc_biaya.hitung_hsp('pasangan_bata_merah', h_mat, h_wage)
    hsp_t = calc_biaya.hitung_hsp('pasangan_batu_kali', h_mat, h_wage)
    hsp_pile = calc_biaya.hitung_hsp('bore_pile_k300', h_mat, h_wage)
    
    rab_data = [
        {"Item": "Beton Struktur", "Vol": vol_beton, "Sat": "m3", "Hrg": hsp_b, "Tot": vol_beton*hsp_b},
        {"Item": "Pembesian", "Vol": vol_besi, "Sat": "kg", "Hrg": hsp_s, "Tot": vol_besi*hsp_s},
        {"Item": "Dinding Bata", "Vol": vol_dinding, "Sat": "m2", "Hrg": hsp_d, "Tot": vol_dinding*hsp_d},
        {"Item": "Talud/Pondasi", "Vol": d_geo.get('vol_talud',0), "Sat": "m3", "Hrg": hsp_t, "Tot": d_geo.get('vol_talud',0)*hsp_t},
        {"Item": "Bore Pile", "Vol": d_geo.get('vol_pile',0), "Sat": "m3", "Hrg": hsp_pile, "Tot": d_geo.get('vol_pile',0)*hsp_pile},
    ]
    
    df_rab = pd.DataFrame(rab_data)
    st.dataframe(df_rab.style.format({"Vol": "{:.2f}", "Hrg": "{:,.0f}", "Tot": "{:,.0f}"}), use_container_width=True)
    st.success(f"### TOTAL RAB: Rp {df_rab['Tot'].sum():,.0f}")
    
    s_data = {'fc': fc_in, 'fy': fy_in, 'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'sigma': sigma_tanah}
    st.download_button("📊 Download Excel RAB", engine_export.create_excel_report(df_rab, s_data), "RAB.xlsx")

# ------------------------------------------------------------------
# MODULE 6: AI CONSULTANT
# ------------------------------------------------------------------
elif menu_selection == "🤖 Konsultan AI":
    
    st.markdown(f'<div class="main-header">🤖 AI Consultant</div>', unsafe_allow_html=True)
    
    # --- PILIH AHLI (SIDEBAR BAWAH) ---
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 👷 Tim Ahli")
        use_auto = st.checkbox("🤖 Auto-Pilot", value=True)
        manual_sel = st.selectbox("Pilih Manual:", list(gems_persona.keys()), disabled=use_auto)
        if not use_auto: st.session_state.current_expert_active = manual_sel
        
        # File Upload
        st.markdown("### 📂 Upload Data")
        uploaded_files = st.file_uploader("File Pendukung:", accept_multiple_files=True)
        if st.button("🧹 Reset Chat"):
            db.clear_chat("Proyek Aktif", st.session_state.current_expert_active)
            st.rerun()

    # --- CHAT AREA ---
    current_expert = st.session_state.current_expert_active
    st.caption(f"Status: **Connected** | Expert: **{current_expert}** | Brain: **{selected_model_name}**")
    
    # Render History
    history = db.get_chat_history("Proyek Aktif", current_expert)
    for chat in history:
        with st.chat_message(chat['role']): st.markdown(chat['content'])
        
    if prompt := st.chat_input("Tanya sesuatu..."):
        # Auto-Pilot Logic
        target_expert = current_expert
        if use_auto:
            target_expert = get_auto_pilot_decision(prompt, selected_model_name)
            st.session_state.current_expert_active = target_expert
            st.toast(f"Dialihkan ke: {target_expert}", icon="🔀")
            
        # Save User Msg
        db.simpan_chat("Proyek Aktif", target_expert, "user", prompt)
        with st.chat_message("user"): st.markdown(prompt)
        
        # Prepare Context
        context_files = ""
        if uploaded_files:
            # Simplifikasi: Hanya memberi tahu AI ada file
            context_files = "\n[Ada File Terlampir]"
            
        # Simplifikasi summary untuk chat
        final_context = f"User tanya: {prompt}. Data Proyek: {get_project_summary_context()}." + context_files
        
        # Generate Response
        with st.chat_message("assistant"):
            with st.spinner("Berpikir..."):
                try:
                    model = genai.GenerativeModel(selected_model_name, system_instruction=gems_persona[target_expert])
                    
                    # Convert history for API
                    api_hist = [{"role": "user" if h['role']=="user" else "model", "parts": [h['content']]} for h in history]
                    
                    chat = model.start_chat(history=api_hist)
                    response = chat.send_message(final_context)
                    ans = response.text
                    
                    st.markdown(ans)
                    db.simpan_chat("Proyek Aktif", target_expert, "assistant", ans)
                    
                    # Cek Plotting Code
                    if "```python" in ans and "plt." in ans:
                        code = re.search(r"```python(.*?)```", ans, re.DOTALL).group(1)
                        st.caption("📈 Rendering Grafik...")
                        execute_generated_code(code)
                        
                    # Download Docs
                    docx_bio = create_docx_from_text(ans)
                    if docx_bio: st.download_button("📄 Simpan Word", docx_bio, "Jawaban.docx")
                    
                except Exception as e:
                    st.error(f"Error AI: {e}")
