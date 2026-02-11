import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import json
import re
import io
from PIL import Image
import docx  # python-docx
from streamlit_drawable_canvas import st_canvas

# --- AI & GOOGLE LIBRARIES ---
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# --- IMPORT MODULE ENGINEERING LOKAL ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

# --- IMPORT BACKEND DATABASE ---
# Pastikan file backend_enginex.py ada di folder yang sama
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
    .auto-pilot-msg { background-color: #e0f7fa; border-left: 5px solid #00acc1; padding: 10px; margin-bottom: 10px; border-radius: 5px; color: #006064; font-weight: bold; }
    
    /* Button Styling */
    div.stButton > button {width: 100%; border-radius: 6px; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. INISIALISASI STATE & DATABASE
# ==========================================

# A. State Kalkulator (IndoBIM)
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'structure' not in st.session_state: st.session_state['structure'] = {}
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}
if 'arsitek_mep' not in st.session_state: st.session_state['arsitek_mep'] = {}
if 'drawing' not in st.session_state: st.session_state['drawing'] = {}

# State Report
for k in ['report_struk', 'report_baja', 'report_gempa', 'report_geo']:
    if k not in st.session_state: st.session_state[k] = {}

# B. State AI Chat (ENGINEX)
if 'backend' not in st.session_state: st.session_state.backend = EnginexBackend()
db = st.session_state.backend

if 'processed_files' not in st.session_state: st.session_state.processed_files = set()
if 'current_expert_active' not in st.session_state: st.session_state.current_expert_active = "👑 The GEMS Grandmaster"

# ==========================================
# 3. HELPER FUNCTIONS (AI & TOOLS)
# ==========================================

# --- Fungsi Bantuan Export Dokumen Chat ---
def create_docx_from_text(text_content):
    try:
        doc = docx.Document()
        doc.add_heading('Laporan Konsultasi AI', 0)
        for line in text_content.split('\n'):
            clean = line.strip()
            if clean.startswith('## '): doc.add_heading(clean.replace('## ', ''), level=2)
            elif clean.startswith('### '): doc.add_heading(clean.replace('### ', ''), level=3)
            elif clean.startswith('- ') or clean.startswith('* '): 
                try: doc.add_paragraph(clean, style='List Bullet')
                except: doc.add_paragraph(clean)
            elif clean: doc.add_paragraph(clean)
        bio = io.BytesIO()
        doc.save(bio)
        bio.seek(0)
        return bio
    except: return None

# --- Fungsi Eksekusi Plotting AI ---
def execute_generated_code(code_str):
    try:
        local_vars = {"pd": pd, "np": np, "plt": plt, "st": st}
        exec(code_str, {}, local_vars)
        return True
    except Exception as e:
        st.error(f"⚠️ Gagal Render Grafik: {e}")
        return False

# --- Context Bridge: Mengirim Data Hitungan ke AI ---
def get_project_summary_context():
    """Mengambil data dari session state kalkulator untuk konteks AI"""
    summary = "DATA TEKNIS PROYEK SAAT INI (Dari Kalkulator):\n"
    
    # Struktur
    if st.session_state.get('report_struk'):
        s = st.session_state['report_struk']
        summary += f"- Struktur Beton: Dimensi {s.get('Dimensi')}, Mu={s.get('Mu')} kNm, Tulangan={s.get('Tulangan')}\n"
    
    # Baja
    if st.session_state.get('report_baja'):
        b = st.session_state['report_baja']
        summary += f"- Struktur Baja: Profil {b.get('Profil')}, Ratio={b.get('Ratio')}, Status={b.get('Status')}\n"
        
    # Geo
    if st.session_state.get('report_geo'):
        g = st.session_state['report_geo']
        summary += f"- Geoteknik: SF Talud={g.get('Talud_SF')}, Qall Pile={g.get('Pile_Qall')} kN\n"
        
    return summary

# ==========================================
# 4. SIDEBAR GLOBAL
# ==========================================
with st.sidebar:
    st.title("🏗️ SYSTEM CONTROLLER")
    
    # --- PILIH MODE APLIKASI ---
    app_mode = st.radio("Modul Utama:", ["🧮 Kalkulator Teknik (Tools)", "🤖 Konsultan AI (Chat)"], index=0)
    
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

    # --- PARAMETER GLOBAL (Hanya muncul di Mode Kalkulator / bisa juga di Chat utk info) ---
    with st.expander("⚙️ Parameter Global & Harga", expanded=False):
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
    
    # Init Engines
    calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
    calc_biaya = ahsp.AHSP_Engine()
    calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
    calc_fdn = fdn.Foundation_Engine(sigma_tanah)
    engine_export = exp.Export_Engine()

    st.markdown(f'<div class="main-header">🛠️ Engineering Workspace: {nama_proyek}</div>', unsafe_allow_html=True)

    # TABS TOOLS
    tabs = st.tabs([
        "🏠 Dash", "📂 BIM", "✏️ Draw/Model", "🏗️ Beton", 
        "🔩 Baja", "🌋 Gempa", "⛰️ Geoteknik", "💰 RAB Final"
    ])

    # --- TAB 1: DASHBOARD ---
    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Mutu Beton", f"{fc_in} MPa")
        c2.metric("Mutu Baja", f"{fy_in} MPa")
        c3.metric("Tanah (Phi)", f"{phi_tanah}°")
        st.info("Gunakan tab di atas untuk melakukan perhitungan spesifik.")

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
                    c1.success(f"Struktur: {len(df_s)} items"); c1.dataframe(df_s.head(3))
                    c2.info("Arsitek & MEP:"); c2.write(q_a); c2.write(q_m)
                    
                    if st.button("Simpan Data BIM"):
                        st.session_state['arsitek_mep'] = {**q_a, **q_m}
                        st.session_state['bim_loads'] = eng_ifc.calculate_architectural_loads()['Total Load Tambahan (kN)']
                        st.toast("Data BIM Tersimpan!", icon="💾")
            except Exception as e: st.error(f"Error: {e}")

    # --- TAB 3: MODELING & DRAWING ---
    with tabs[2]:
        sub1, sub2 = st.tabs(["A. Input Grid", "B. Gambar Canvas"])
        with sub1:
            c1, c2 = st.columns([1,2])
            with c1:
                L = st.number_input("Panjang (m)", 2.0, 20.0, st.session_state['geo']['L'])
                b = st.number_input("Lebar (mm)", 150, 1000, st.session_state['geo']['b'])
                h = st.number_input("Tinggi (mm)", 200, 2000, st.session_state['geo']['h'])
                st.session_state['geo'] = {'L': L, 'b': b, 'h': h}
            with c2:
                fig, ax = plt.subplots(figsize=(6,2))
                ax.add_patch(patches.Rectangle((0,0), L, h/1000, facecolor='#2E86C1'))
                ax.set_xlim(-0.5, L+0.5); ax.set_ylim(-0.5, 2); ax.set_aspect('equal')
                st.pyplot(fig)
        
        with sub2:
            st.caption("Gambar denah ruangan untuk estimasi cepat.")
            scale_fac = st.slider("Skala Px/m", 10, 50, 20)
            canvas_res = st_canvas(fill_color="rgba(0, 150, 255, 0.3)", stroke_width=2, height=300, width=600, drawing_mode="rect", key="canvas_rt")
            
            if canvas_res.json_data:
                rooms = []
                for obj in canvas_res.json_data["objects"]:
                    w, h_ = obj["width"]/scale_fac, obj["height"]/scale_fac
                    rooms.append({"Keliling": 2*(w+h_), "Luas": w*h_})
                
                if rooms:
                    df_r = pd.DataFrame(rooms)
                    tot_kel = df_r["Keliling"].sum()
                    v_dinding = tot_kel * 3.5
                    v_beton = (tot_kel * 0.15 * 0.35) # Sloof+Ring+Kolom (Rough Estimate)
                    st.success(f"Est. Dinding: {v_dinding:.1f} m2 | Beton: {v_beton:.1f} m3")
                    if st.button("Pakai Data Gambar"):
                        st.session_state['drawing'] = {'vol_dinding': v_dinding, 'vol_beton': v_beton}

    # --- TAB 4: BETON (SNI) ---
    with tabs[3]:
        c1, c2 = st.columns(2)
        with c1:
            q_dl = st.number_input("DL (kN/m)", 0.0, 50.0, 15.0)
            if st.session_state.get('bim_loads'): st.caption(f"+ Beban BIM: {st.session_state['bim_loads']} kN")
            q_ll = st.number_input("LL (kN/m)", 0.0, 50.0, 5.0)
        with c2:
            q_u = sni.SNI_Load_1727.komb_pembebanan(q_dl, q_ll)
            Mu = (1/8) * q_u * (st.session_state['geo']['L']**2)
            As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
            
            dia = st.selectbox("D Tulangan", [13,16,19,22])
            n_bars = np.ceil(As_req / (0.25 * 3.14 * dia**2))
            
            st.metric("Momen Mu", f"{Mu:.1f} kNm")
            st.success(f"Desain: {int(n_bars)} D{dia}")
            
            # Save
            vol_conc = st.session_state['geo']['L'] * (st.session_state['geo']['b']/1000) * (st.session_state['geo']['h']/1000)
            st.session_state['structure'] = {'vol_beton': vol_conc, 'berat_besi': vol_conc*150}
            st.session_state['report_struk'] = {'Mu': Mu, 'Tulangan': f"{int(n_bars)} D{dia}", 'Dimensi': f"{st.session_state['geo']['b']}x{st.session_state['geo']['h']}"}
            
            # DXF
            params = {'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'dia': dia, 'n': n_bars, 'pjg': st.session_state['geo']['L']}
            st.download_button("📥 DXF Balok", engine_export.create_dxf("BALOK", params), "balok.dxf")

    # --- TAB 5: BAJA & ATAP ---
    with tabs[4]:
        sub1, sub2 = st.tabs(["Baja Berat", "Baja Ringan"])
        with sub1:
            c1, c2 = st.columns(2)
            mu_b = c1.number_input("Mu (kNm)", 10.0, 500.0, 50.0)
            lb_b = c1.number_input("Lb (m)", 1.0, 10.0, 3.0)
            db_wf = {"WF 200": {'Zx': 213}, "WF 250": {'Zx': 324}, "WF 300": {'Zx': 481}}
            sel_wf = c2.selectbox("Profil", list(db_wf.keys()))
            
            eng_steel = steel.SNI_Steel_1729(fy_in, 410)
            res_st = eng_steel.cek_balok_lentur(mu_b, db_wf[sel_wf], lb_b)
            if res_st['Ratio'] <= 1.0: st.success(f"Aman (R={res_st['Ratio']:.2f})")
            else: st.error(f"Gagal (R={res_st['Ratio']:.2f})")
            st.session_state['report_baja'] = {'Profil': sel_wf, 'Ratio': res_st['Ratio'], 'Status': res_st['Status']}
            
        with sub2:
            la = st.number_input("Luas Atap (m2)", 20.0, 1000.0, 100.0)
            typ = st.radio("Tipe", ["Metal Pasir", "Genteng Keramik"])
            calc_tr = steel.Baja_Ringan_Calc()
            mat = calc_tr.hitung_kebutuhan_atap(la, typ)
            st.write(mat)

    # --- TAB 6: GEMPA ---
    with tabs[5]:
        c1, c2 = st.columns(2)
        ss = c1.number_input("Ss", 0.0, 2.0, 0.8)
        s1 = c1.number_input("S1", 0.0, 1.5, 0.4)
        sc = c1.selectbox("Site Class", ["SE", "SD", "SC"], index=1)
        wt = c2.number_input("Berat (kN)", 100.0, 10000.0, 2000.0)
        r = c2.number_input("R", 3.0, 8.0, 8.0)
        
        eng_q = quake.SNI_Gempa_1726(ss, s1, sc)
        v_base, sds, sd1 = eng_q.hitung_base_shear(wt, r)
        st.metric("Base Shear V", f"{v_base:.1f} kN")
        st.session_state['report_gempa'] = {'V_gempa': v_base, 'Sds': sds}

    # --- TAB 7: GEOTEKNIK ---
    with tabs[6]:
        sub1, sub2 = st.tabs(["Pondasi", "Talud"])
        with sub1:
            pu = st.number_input("Pu (kN)", 50.0, 1000.0, 150.0)
            bf = st.number_input("Lebar (m)", 0.5, 3.0, 1.0)
            nf = st.number_input("Jumlah", 1, 50, 10)
            res_f = calc_fdn.hitung_footplate(pu, bf, bf, 300)
            if "AMAN" in res_f['status']: st.success("Aman")
            else: st.error("Perbesar Dimensi")
            
            st.download_button("📥 DXF Pondasi", engine_export.create_dxf("FOOTPLATE", {'B': bf}), "pondasi.dxf")
            st.session_state['pondasi'] = {'fp_beton': res_f['vol_beton']*nf, 'fp_besi': res_f['berat_besi']*nf, 'galian': res_f['vol_galian']*nf, 'bk_batu': 0}
            
        with sub2:
            ht = st.number_input("Tinggi (m)", 2.0, 10.0, 3.0)
            res_t = calc_geo.hitung_talud_batu_kali(ht, 0.4, 1.5)
            st.write(f"SF Guling: {res_t['SF_Guling']:.2f}")
            st.session_state['geotech'] = {'vol_talud': res_t['Vol_Per_M']*10, 'vol_pile': 0}
            st.session_state['report_geo'] = {'Talud_SF': res_t['SF_Geser'], 'Pile_Qall': '-'}

    # --- TAB 8: RAB FINAL ---
    with tabs[7]:
        st.markdown('<p class="sub-header">Rekapitulasi Biaya (RAB)</p>', unsafe_allow_html=True)
        
        # Consolidation Data
        d_str = st.session_state.get('structure', {})
        d_pon = st.session_state.get('pondasi', {})
        d_geo = st.session_state.get('geotech', {})
        d_bim = st.session_state.get('arsitek_mep', {})
        d_draw = st.session_state.get('drawing', {})
        
        # Logic Prioritas Volume
        vol_beton = d_str.get('vol_beton', 0) + d_pon.get('fp_beton', 0) + d_draw.get('vol_beton', 0)
        vol_besi = d_str.get('berat_besi', 0) + d_pon.get('fp_besi', 0)
        vol_dinding = d_draw.get('vol_dinding', 0) if d_draw else d_bim.get('Luas Dinding (m2)', 0)
        
        # Harga Dasar Dictionary
        h_dasar = {
            'semen': p_semen, 'pasir': p_pasir, 'split': p_split, 'besi': p_besi, 
            'kayu': p_kayu, 'batu kali': p_batu, 'beton k300': p_beton_ready,
            'bata merah': p_bata, 'cat tembok': p_cat, 'pipa pvc': p_pipa
        }
        h_upah = {'pekerja': u_pekerja, 'tukang': u_tukang, 'mandor': u_pekerja*1.2}
        
        # Calculate HSP
        hsp_b = calc_biaya.hitung_hsp('beton_k250', h_dasar, h_upah)
        hsp_s = calc_biaya.hitung_hsp('pembesian_polos', h_dasar, h_upah) / 10
        hsp_d = calc_biaya.hitung_hsp('pasangan_bata_merah', h_dasar, h_upah)
        
        # Table Data
        rab_data = [
            {"Item": "Beton Struktur", "Vol": vol_beton, "Sat": "m3", "Hrg": hsp_b, "Tot": vol_beton*hsp_b},
            {"Item": "Pembesian", "Vol": vol_besi, "Sat": "kg", "Hrg": hsp_s, "Tot": vol_besi*hsp_s},
            {"Item": "Dinding Bata", "Vol": vol_dinding, "Sat": "m2", "Hrg": hsp_d, "Tot": vol_dinding*hsp_d},
            {"Item": "Galian Tanah", "Vol": d_pon.get('galian',0), "Sat": "m3", "Hrg": 85000, "Tot": d_pon.get('galian',0)*85000}
        ]
        
        df_rab = pd.DataFrame(rab_data)
        st.dataframe(df_rab.style.format({"Vol": "{:.2f}", "Hrg": "{:,.0f}", "Tot": "{:,.0f}"}), use_container_width=True)
        st.success(f"### TOTAL: Rp {df_rab['Tot'].sum():,.0f}")
        
        # Download Excel
        st.divider()
        sess_data = {'fc': fc_in, 'fy': fy_in, 'b': st.session_state['geo']['b'], 'h': st.session_state['geo']['h'], 'sigma': sigma_tanah}
        excel_bytes = engine_export.create_excel_report(df_rab, sess_data)
        st.download_button("📊 Download Laporan Lengkap (.xlsx)", excel_bytes, "Laporan_Project.xlsx")


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
