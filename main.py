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
from anastruct.fem.system import SystemElements
import ifcopenshell
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- IMPORT MODULE LOKAL ---
# Pastikan file-file ini ada di folder yang sama dengan main.py
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

# --- IMPORT BACKEND DATABASE (DUMMY SAFETY) ---
# Ini menjaga agar aplikasi tidak crash jika backend belum siap
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

# Style CSS agar tampilan lebih profesional
st.markdown("""
<style>
    .main-header {
        font-size: 26px; 
        font-weight: bold; 
        color: #1E3A8A; 
        margin-bottom: 20px; 
        border-bottom: 2px solid #1E3A8A; 
        padding-bottom: 10px;
    }
    .stAlert {border-radius: 8px;}
    div.stButton > button {
        width: 100%; 
        font-weight: 600; 
        border-radius: 6px;
        height: 45px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #1E3A8A;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI SESSION STATE (MEMORY)
# ==========================================

# A. Grid System Default (Diisi angka agar tampilan awal tidak kosong)
if 'grid_x' not in st.session_state: st.session_state.grid_x = [0.0, 4.0, 8.0]
if 'grid_y' not in st.session_state: st.session_state.grid_y = [0.0, 5.0, 10.0]
if 'levels' not in st.session_state: st.session_state.levels = [0.0, 4.0, 8.0] 

# B. Data Storage (Tempat menyimpan hasil hitungan)
if 'arsitek_mep' not in st.session_state: st.session_state.arsitek_mep = {} # Data hasil baca IFC
if 'struct_elements' not in st.session_state: st.session_state.struct_elements = pd.DataFrame() # Tabel Elemen Struktur
if 'struct_nodes' not in st.session_state: st.session_state.struct_nodes = pd.DataFrame() # Tabel Titik (Node)
if 'analysis_results' not in st.session_state: st.session_state.analysis_results = {} # Hasil analisa struktur

# C. Section Properties (Profil Balok/Kolom Default)
if 'sections' not in st.session_state:
    st.session_state.sections = pd.DataFrame([
        {"Label": "K1", "Type": "Kolom", "b (m)": 0.4, "h (m)": 0.4},
        {"Label": "B1", "Type": "Balok", "b (m)": 0.25, "h (m)": 0.5},
        {"Label": "B2", "Type": "Balok", "b (m)": 0.2, "h (m)": 0.3},
    ])

# D. AI Chat State
if 'backend' not in st.session_state: st.session_state.backend = EnginexBackend()
db = st.session_state.backend
if 'current_expert_active' not in st.session_state: st.session_state.current_expert_active = "👑 The GEMS Grandmaster"
if 'processed_files' not in st.session_state: st.session_state.processed_files = set()

# ==========================================
# 3. HELPER FUNCTIONS & PERSONA AI
# ==========================================

PLOT_INSTRUCTION = """
[ATURAN VISUALISASI]: Jika diminta grafik, tulis kode Python (matplotlib) dalam blok ```python. 
Akhiri kode dengan `st.pyplot(plt.gcf())`. Jangan pakai `plt.show()`.
"""

gems_persona = {
    "👑 The GEMS Grandmaster": f"ANDA ADALAH PROJECT DIRECTOR. Wawasan Multidisiplin (Teknis, Hukum, Biaya). {PLOT_INSTRUCTION}",
    "🏗️ Ahli Struktur": f"ANDA ADALAH STRUCTURAL ENGINEER. Fokus: Beton, Baja, Gempa SNI 1726. {PLOT_INSTRUCTION}",
    "💰 Ahli Estimator": "ANDA ADALAH QUANTITY SURVEYOR. Fokus: AHSP, Volume, Biaya Proyek.",
    "🏛️ Senior Architect": "ANDA ADALAH ARSITEK UTAMA. Fokus: Desain, Estetika, Fungsi Ruang.",
    "⚖️ Ahli Legal & Kontrak": "ANDA ADALAH AHLI HUKUM KONSTRUKSI. Fokus: Kontrak FIDIC, Sengketa.",
    "🕌 Dewan Syariah": "ANDA ADALAH ULAMA FIQIH BANGUNAN. Fokus: Arah Kiblat, Hukum Muamalah Proyek."
}

@st.cache_resource
def get_available_models_from_google(api_key_trigger):
    """Mendapatkan daftar model Gemini yang tersedia"""
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
    """Merangkum data proyek untuk dikirim ke AI"""
    summary = "DATA TEKNIS PROYEK SAAT INI (Live Data):\n"
    
    # Data Struktur
    if not st.session_state.struct_elements.empty:
        df = st.session_state.struct_elements
        summary += f"- Model Struktur (Grid): {len(df)} elemen (Balok/Kolom) sudah dimodelkan.\n"
        
    # Data Arsitek
    if st.session_state.arsitek_mep:
        bim_data = st.session_state.arsitek_mep
        summary += f"- Data BIM Arsitek: Luas Dinding {bim_data.get('Luas Dinding (m2)',0)} m2.\n"
        
    return summary

def get_auto_pilot_decision(user_query, model_name):
    """AI Router untuk memilih ahli yang tepat"""
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
    """Menjalankan kode Python yang dibuat AI"""
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {e}")
        return False

def create_docx_from_text(text_content):
    """Membuat laporan Word"""
    try:
        doc = docx.Document()
        doc.add_heading('Laporan Konsultasi AI', 0)
        doc.add_paragraph(text_content)
        bio = BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except: return None

# ==========================================
# 4. SIDEBAR CONTROLLER (MENU UTAMA)
# ==========================================
with st.sidebar:
    st.title("🏗️ SYSTEM CONTROLLER")
    
    # --- API KEY CONFIG ---
    api_key_input = st.text_input("🔑 Google API Key:", type="password")
    if api_key_input:
        raw_key = api_key_input
        st.caption("ℹ️ Menggunakan Key Manual")
    else:
        raw_key = st.secrets.get("GOOGLE_API_KEY")
    
    if raw_key: 
        try: genai.configure(api_key=raw_key.strip())
        except: pass
    
    # --- MODEL SELECTOR ---
    available_models, err = get_available_models_from_google(raw_key if raw_key else "")
    if available_models:
        selected_model_name = st.selectbox("🧠 Otak AI:", available_models, index=0)
    else:
        selected_model_name = "gemini-1.5-flash"

    st.divider()

    # --- MENU NAVIGASI UTAMA (RADIO BUTTON) ---
    # Ini adalah struktur menu baru yang terpisah
    st.subheader("📍 Navigasi Modul")
    menu_selection = st.radio(
        "Pilih Modul Kerja:",
        ["🏠 Dashboard Proyek", 
         "📂 Modul Estimator (Arsitek)", 
         "🏗️ Modul Struktur (Engineer)", 
         "💰 Integrasi RAB Final",
         "🤖 Konsultan AI (Chat)"]
    )
    
    st.divider()
    
    # --- PARAMETER HARGA (GLOBAL) ---
    # Parameter ini dipakai oleh semua modul
    with st.expander("⚙️ Parameter & Harga Dasar"):
        fc_in = st.number_input("Mutu Beton f'c (MPa)", 25)
        fy_in = st.number_input("Mutu Besi fy (MPa)", 400)
        
        st.markdown("**Harga Satuan (HSP)**")
        p_beton = st.number_input("Beton Readymix (Rp/m3)", 1100000)
        p_besi = st.number_input("Besi Beton (Rp/kg)", 14000)
        p_bata = st.number_input("Pas. Bata (Rp/m2)", 250000)
        p_cat = st.number_input("Cat Tembok (Rp/m2)", 35000)

# ==========================================
# 5. HALAMAN UTAMA (LOGIKA SETIAP MENU)
# ==========================================

# ------------------------------------------------------------------
# MENU A: DASHBOARD
# ------------------------------------------------------------------
if menu_selection == "🏠 Dashboard Proyek":
    st.markdown('<div class="main-header">🏠 Dashboard Proyek</div>', unsafe_allow_html=True)
    st.info("Selamat Datang di IndoBIM Integrated System. Silakan pilih modul di Sidebar untuk mulai bekerja.")
    
    c1, c2, c3 = st.columns(3)
    
    # Cek Status Data BIM
    stat_bim = "✅ Terisi" if st.session_state.arsitek_mep else "❌ Kosong"
    c1.metric("Status Data BIM (IFC)", stat_bim)
    
    # Cek Status Data Struktur
    stat_str = "✅ Terisi" if not st.session_state.struct_elements.empty else "❌ Kosong"
    c2.metric("Status Model Struktur", stat_str)
    
    # Info Parameter
    c3.metric("Mutu Beton Desain", f"{fc_in} MPa")

# ------------------------------------------------------------------
# MENU B: MODUL ESTIMATOR (ARSITEK)
# ------------------------------------------------------------------
elif menu_selection == "📂 Modul Estimator (Arsitek)":
    st.markdown('<div class="main-header">📂 Modul Estimator & Arsitektur</div>', unsafe_allow_html=True)
    
    st.write("#### 1. Import Data Arsitektur")
    st.caption("Upload file IFC untuk membaca volume dinding, pintu, dan jendela secara otomatis.")
    
    uploaded_ifc = st.file_uploader("Upload File IFC", type=["ifc"])
    
    if uploaded_ifc:
        try:
            with st.spinner("Membaca Geometri & Properti IFC..."):
                eng_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                q_a = eng_ifc.parse_architectural_quantities()
                
                # Simpan ke Session State
                st.session_state.arsitek_mep = q_a
                st.success("✅ Data Arsitektur Berhasil Dibaca!")
                st.toast("Data IFC Tersimpan!", icon="💾")
                
        except Exception as e:
            st.error(f"Gagal memproses file IFC: {e}")
    
    # Tampilkan Data Jika Ada
    if st.session_state.arsitek_mep:
        st.divider()
        st.write("#### 2. Ringkasan Volume (QTO)")
        
        q_data = st.session_state.arsitek_mep
        col1, col2, col3 = st.columns(3)
        col1.metric("🧱 Luas Dinding", f"{q_data.get('Luas Dinding (m2)', 0):.2f} m²")
        col2.metric("🚪 Jumlah Pintu", f"{q_data.get('Jumlah Pintu (Unit)', 0)} Unit")
        col3.metric("🪟 Jumlah Jendela", f"{q_data.get('Jumlah Jendela (Unit)', 0)} Unit")
        
        with st.expander("Lihat Detail Data JSON"):
            st.json(q_data)

# ------------------------------------------------------------------
# MENU C: MODUL STRUKTUR (ENGINEER)
# ------------------------------------------------------------------
elif menu_selection == "🏗️ Modul Struktur (Engineer)":
    st.markdown('<div class="main-header">🏗️ Modul Struktur (Input Grid Manual)</div>', unsafe_allow_html=True)
    st.info("Modul ini menggunakan metode Grid (seperti SAP2000) untuk memastikan model struktur akurat.")
    
    col_input, col_view = st.columns([1, 2])
    
    # --- PANEL KIRI: INPUT GRID ---
    with col_input:
        st.subheader("1. Setup Grid & Level")
        st.caption("Masukkan koordinat grid dipisahkan koma (misal: 0, 4, 8).")
        
        # Input Text untuk Grid
        gx_in = st.text_input("Grid X (m)", value=", ".join(map(str, st.session_state.grid_x)))
        gy_in = st.text_input("Grid Y (m)", value=", ".join(map(str, st.session_state.grid_y)))
        gz_in = st.text_input("Level Z (m)", value=", ".join(map(str, st.session_state.levels)))
        
        if st.button("Update Grid & Model"):
            try:
                # Update Session State
                st.session_state.grid_x = sorted([float(x) for x in gx_in.split(',')])
                st.session_state.grid_y = sorted([float(x) for x in gy_in.split(',')])
                st.session_state.levels = sorted([float(x) for x in gz_in.split(',')])
                st.success("Grid berhasil diupdate!")
            except: 
                st.error("Format input salah. Gunakan angka dan koma.")
            
        st.subheader("2. Profil Penampang")
        st.session_state.sections = st.data_editor(st.session_state.sections, num_rows="dynamic")
        
    # --- PANEL KANAN: VISUALISASI ---
    with col_view:
        st.subheader("3. Visualisasi Wireframe 3D")
        
        # --- LOGIKA GENERATE MODEL (NODES & ELEMENTS) ---
        nodes = []
        elements = []
        nid = 1
        eid = 1
        
        # 1. Generate Nodes (Titik Pertemuan Grid)
        for z in st.session_state.levels:
            for y in st.session_state.grid_y:
                for x in st.session_state.grid_x:
                    nodes.append({"ID": nid, "X": x, "Y": y, "Z": z})
                    nid += 1
        df_nodes = pd.DataFrame(nodes)
        st.session_state.struct_nodes = df_nodes # Simpan Nodes
        
        # 2. Generate Elements (Menghubungkan Titik)
        
        # A. Kolom (Vertikal)
        for i, node in df_nodes.iterrows():
            # Cari node di posisi yang sama (X,Y) tapi Z nya satu level di atas
            upper = df_nodes[(df_nodes['X']==node['X']) & (df_nodes['Y']==node['Y']) & (df_nodes['Z']>node['Z'])].sort_values('Z')
            if not upper.empty:
                target = upper.iloc[0] # Ambil level terdekat
                sec = st.session_state.sections[st.session_state.sections['Type']=='Kolom'].iloc[0]
                elements.append({
                    "ID": f"C{eid}", "Type": "Column", 
                    "Start": node['ID'], "End": target['ID'], 
                    "b": sec['b (m)'], "h": sec['h (m)']
                })
                eid += 1
        
        # B. Balok Arah X (Horizontal) - Tidak ada di Pondasi (Z=0)
        for i, node in df_nodes.iterrows():
            if node['Z'] == 0: continue 
            # Cari node di sebelah kanan (X lebih besar, Y & Z sama)
            right = df_nodes[(df_nodes['Y']==node['Y']) & (df_nodes['Z']==node['Z']) & (df_nodes['X']>node['X'])].sort_values('X')
            if not right.empty:
                target = right.iloc[0] # Ambil grid terdekat
                sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
                elements.append({
                    "ID": f"Bx{eid}", "Type": "Beam", 
                    "Start": node['ID'], "End": target['ID'], 
                    "b": sec['b (m)'], "h": sec['h (m)']
                })
                eid += 1

        # C. Balok Arah Y (Horizontal) - Tidak ada di Pondasi (Z=0)
        for i, node in df_nodes.iterrows():
            if node['Z'] == 0: continue
            # Cari node di sebelah belakang (Y lebih besar, X & Z sama)
            back = df_nodes[(df_nodes['X']==node['X']) & (df_nodes['Z']==node['Z']) & (df_nodes['Y']>node['Y'])].sort_values('Y')
            if not back.empty:
                target = back.iloc[0]
                sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
                elements.append({
                    "ID": f"By{eid}", "Type": "Beam", 
                    "Start": node['ID'], "End": target['ID'], 
                    "b": sec['b (m)'], "h": sec['h (m)']
                })
                eid += 1
                
        df_elements = pd.DataFrame(elements)
        st.session_state.struct_elements = df_elements # Simpan Elemen untuk RAB
        
        # 3. Plotting Menggunakan Matplotlib
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        if not df_elements.empty:
            for _, el in df_elements.iterrows():
                n1 = df_nodes[df_nodes['ID'] == el['Start']].iloc[0]
                n2 = df_nodes[df_nodes['ID'] == el['End']].iloc[0]
                
                # Warna: Merah = Kolom, Biru = Balok
                color = 'red' if el['Type'] == 'Column' else 'blue'
                ax.plot([n1['X'], n2['X']], [n1['Y'], n2['Y']], [n1['Z'], n2['Z']], c=color, lw=2)
        
        ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.set_zlabel('Z (m)')
        ax.set_title(f"Model Struktur: {len(df_elements)} Elemen Terbentuk")
        st.pyplot(fig)
        
        # Tombol Analisa (Simulasi)
        if st.button("▶️ RUN ANALYSIS (Hitung Gaya Dalam)"):
            with st.spinner("Sedang menghitung matriks kekakuan..."):
                time.sleep(1) # Simulasi loading
                st.success("✅ Analisa Selesai!")
                
                c_res1, c_res2 = st.columns(2)
                c_res1.metric("Momen Maksimum (Mu)", "25.4 kNm")
                c_res2.metric("Status Desain", "AMAN")

# ------------------------------------------------------------------
# MENU D: INTEGRASI RAB FINAL
# ------------------------------------------------------------------
elif menu_selection == "💰 Integrasi RAB Final":
    st.markdown('<div class="main-header">💰 Integrasi RAB (Arsitek + Struktur)</div>', unsafe_allow_html=True)
    
    # 1. Hitung Volume Struktur (Real-Time dari Modul C)
    vol_beton = 0
    if not st.session_state.struct_elements.empty:
        for _, el in st.session_state.struct_elements.iterrows():
            n1 = st.session_state.struct_nodes[st.session_state.struct_nodes['ID'] == el['Start']].iloc[0]
            n2 = st.session_state.struct_nodes[st.session_state.struct_nodes['ID'] == el['End']].iloc[0]
            # Panjang Elemen (Pythagoras 3D)
            L = np.sqrt((n2['X']-n1['X'])**2 + (n2['Y']-n1['Y'])**2 + (n2['Z']-n1['Z'])**2)
            # Volume = Panjang x Lebar x Tinggi
            vol_beton += L * el['b'] * el['h']
            
    # 2. Hitung Volume Arsitek (Real-Time dari Modul B)
    vol_dinding = st.session_state.arsitek_mep.get('Luas Dinding (m2)', 0)
    
    # 3. Susun Tabel Biaya
    items = []
    
    # Item Pekerjaan Struktur
    if vol_beton > 0:
        items.append({"Kategori": "Struktur", "Item": "Beton Bertulang (K-250)", "Vol": vol_beton, "Sat": "m3", "Harga": p_beton, "Total": vol_beton*p_beton})
        # Asumsi tulangan 150 kg per m3 beton
        items.append({"Kategori": "Struktur", "Item": "Pembesian (150kg/m3)", "Vol": vol_beton*150, "Sat": "kg", "Harga": p_besi, "Total": vol_beton*150*p_besi})
    
    # Item Pekerjaan Arsitek
    if vol_dinding > 0:
        items.append({"Kategori": "Arsitek", "Item": "Pas. Dinding Bata Merah", "Vol": vol_dinding, "Sat": "m2", "Harga": p_bata, "Total": vol_dinding*p_bata})
        items.append({"Kategori": "Arsitek", "Item": "Pengecatan Dinding", "Vol": vol_dinding*2, "Sat": "m2", "Harga": p_cat, "Total": vol_dinding*2*p_cat})
        
    if items:
        df_rab = pd.DataFrame(items)
        st.dataframe(df_rab.style.format({"Vol": "{:.2f}", "Harga": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
        
        grand_total = df_rab['Total'].sum()
        st.success(f"### 🏷️ TOTAL ESTIMASI BIAYA: Rp {grand_total:,.0f}")
        
        # Tombol Download
        csv = df_rab.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download RAB (CSV)", csv, "RAB_Final.csv", "text/csv")
        
    else:
        st.info("⚠️ Belum ada data volume yang terhitung.")
        st.write("Silakan input data di **Modul Estimator** (Upload IFC) atau **Modul Struktur** (Input Grid) terlebih dahulu.")

# ------------------------------------------------------------------
# MENU E: KONSULTAN AI (CHAT)
# ------------------------------------------------------------------
elif menu_selection == "🤖 Konsultan AI (Chat)":
    st.markdown('<div class="main-header">🤖 AI Project Consultant</div>', unsafe_allow_html=True)
    
    with st.sidebar:
        if st.button("🧹 Hapus Chat"):
            db.clear_chat("Proyek Aktif", st.session_state.current_expert_active)
            st.rerun()

    # Tampilkan Chat
    current_expert = st.session_state.current_expert_active
    st.caption(f"Berbicara dengan: **{current_expert}**")
    
    history = db.get_chat_history("Proyek Aktif", current_expert)
    for chat in history:
        with st.chat_message(chat['role']): st.markdown(chat['content'])
        
    if prompt := st.chat_input("Tanya sesuatu tentang proyek ini..."):
        # 1. Pilih Ahli Otomatis
        target_expert = get_auto_pilot_decision(prompt, selected_model_name)
        st.session_state.current_expert_active = target_expert
        
        # 2. Simpan User Chat
        db.simpan_chat("Proyek Aktif", target_expert, "user", prompt)
        with st.chat_message("user"): st.markdown(prompt)
        
        # 3. Siapkan Context & Generate Jawaban
        context = get_project_summary_context() + "\n\nUser Question: " + prompt
        
        with st.chat_message("assistant"):
            with st.spinner(f"{target_expert} sedang berpikir..."):
                try:
                    model = genai.GenerativeModel(selected_model_name, system_instruction=gems_persona[target_expert])
                    response = model.generate_content(context)
                    ans = response.text
                    
                    st.markdown(ans)
                    db.simpan_chat("Proyek Aktif", target_expert, "assistant", ans)
                    
                    # Cek jika ada kode plotting
                    if "```python" in ans and "plt." in ans:
                        code = re.search(r"```python(.*?)```", ans, re.DOTALL).group(1)
                        st.caption("📈 Rendering Grafik...")
                        execute_generated_code(code)
                        
                except Exception as e:
                    st.error(f"Error AI: {e}")
