import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import ai_engine as ai # Menggunakan file ai_engine.py yang baru diupdate

# --- IMPORT SEMUA MODULE LAMA (JANGAN DIHAPUS) ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake

# --- CONFIG PAGE ---
st.set_page_config(page_title="EnginEx Titan: IndoBIM Ultimate", layout="wide", page_icon="🏗️")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main_header {font-size: 24px; font-weight: bold; color: #2E86C1;}
    .sub_header {font-size: 18px; font-weight: bold; color: #444;}
    div.stButton > button:first-child {border-radius: 8px; width: 100%;}
    .stChatMessage {background-color: #f1f8ff; border-radius: 10px; border: 1px solid #e1e4e8;}
    </style>
""", unsafe_allow_html=True)

# --- INIT SESSION STATE (LENGKAP) ---
# Ini penting agar data tidak hilang saat pindah-pindah tab
if 'geo' not in st.session_state: st.session_state['geo'] = {'L': 6.0, 'b': 250, 'h': 400}
if 'structure' not in st.session_state: st.session_state['structure'] = {}
if 'pondasi' not in st.session_state: st.session_state['pondasi'] = {}
if 'geotech' not in st.session_state: st.session_state['geotech'] = {}
if 'report_struk' not in st.session_state: st.session_state['report_struk'] = {}
if 'report_baja' not in st.session_state: st.session_state['report_baja'] = {}
if 'report_gempa' not in st.session_state: st.session_state['report_gempa'] = {}
if 'report_geo' not in st.session_state: st.session_state['report_geo'] = {}
if "messages" not in st.session_state: st.session_state.messages = []

# ==============================================================================
# SIDEBAR UTAMA
# ==============================================================================
with st.sidebar:
    st.title("ENGINEX TITAN")
    st.caption("AI + BIM + Structural Calculation")
    
    # 1. API KEY & MODEL
    st.divider()
    api_key = st.text_input("🔑 Google API Key", type="password", help="Wajib untuk fitur AI Chat")
    
    # LIST MODEL LENGKAP
    st.caption("Pilih Model Gemini:")
    model_opt = st.selectbox(
        "🧠 Versi Model",
        [
            "models/gemini-2.0-flash",
            "models/gemini-2.0-flash-lite",
            "models/gemini-flash-latest",
            "models/gemini-1.5-pro",
            "models/gemini-1.5-flash"
        ],
        index=0
    )
    
    # 2. MODE SELECTOR (HYBRID SWITCH)
    st.divider()
    app_mode = st.radio(
        "🛠️ Pilih Mode Aplikasi:",
        ["🤖 AI Consultant (Chat)", "🏗️ Engineering Studio (Full App)"],
        captions=["Tanya Jawab & Analisa Cepat", "Aplikasi Lengkap 8 Tab (Manual)"]
    )
    st.divider()

# ==============================================================================
# MODE 1: AI CONSULTANT (CHAT INTERFACE) - SUDAH DIUPDATE
# ==============================================================================
if app_mode == "🤖 AI Consultant (Chat)":
    st.header("🤖 AI Engineering Consultant")
    
    # Fitur Baru: Tampilkan Data yang Dibaca AI
    with st.expander("ℹ️ Lihat Data yang Dibaca AI dari Tab Manual"):
        context_preview = ai.generate_context_from_state(st.session_state)
        st.text(context_preview)
        st.caption("AI akan otomatis mengetahui data di atas saat Anda chatting.")
    
    col_chat1, col_chat2 = st.columns([1, 3])
    with col_chat1:
        persona = st.selectbox("Pilih Ahli:", list(ai.PERSONAS.keys()))
        if st.button("🧹 Hapus Chat"):
            st.session_state.messages = []
            st.rerun()
            
    with col_chat2:
        # Render Chat History
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Chat Input
        if prompt := st.chat_input("Contoh: 'Apakah balok saya aman?' atau 'Hitung ulang dengan mutu beton K-300'"):
            if not api_key:
                st.error("❌ Masukkan API Key di Sidebar dulu!")
                st.stop()
                
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("Sedang menganalisa data proyek Anda..."):
                    # 1. GENERATE CONTEXT DARI STATE
                    # Ini langkah kuncinya: Ambil data dari tab manual
                    current_context = ai.generate_context_from_state(st.session_state)
                    
                    # 2. INISIALISASI BRAIN
                    brain = ai.SmartBIM_Brain(api_key, model_opt, ai.PERSONAS[persona])
                    
                    # 3. KIRIM PERTANYAAN + DATA KONTEKS
                    response = brain.ask(prompt, context_data=current_context)
                    
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

# ==============================================================================
# MODE 2: ENGINEERING STUDIO (FULL ORIGINAL APP)
# ==============================================================================
elif app_mode == "🏗️ Engineering Studio (Full App)":
    
    # --- SIDEBAR INPUT KHUSUS STUDIO ---
    with st.sidebar:
        with st.expander("📝 Input Material & Tanah", expanded=True):
            fc_in = st.number_input("Mutu Beton f'c (MPa)", 20, 50, 25)
            fy_in = st.number_input("Mutu Besi fy (MPa)", 240, 500, 400)
            gamma_tanah = st.number_input("Berat Isi Tanah", 14.0, 22.0, 18.0)
            phi_tanah = st.number_input("Sudut Geser", 10.0, 45.0, 30.0)
            c_tanah = st.number_input("Kohesi", 0.0, 50.0, 5.0)
            sigma_tanah = st.number_input("Daya Dukung Izin", 50.0, 300.0, 150.0)

        with st.expander("💲 Input Harga Satuan"):
            p_semen = st.number_input("Semen (Rp/kg)", 1500)
            p_pasir = st.number_input("Pasir (Rp/m3)", 250000)
            p_split = st.number_input("Split (Rp/m3)", 300000)
            p_besi = st.number_input("Besi (Rp/kg)", 14000)
            p_kayu = st.number_input("Kayu Bekisting", 2500000)
            p_batu = st.number_input("Batu Kali", 280000)
            p_beton_ready = st.number_input("Readymix K300", 1100000)
            u_tukang = st.number_input("Upah Tukang", 135000)
            u_pekerja = st.number_input("Upah Pekerja", 110000)

    # --- INIT ENGINES LAMA ---
    calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
    calc_biaya = ahsp.AHSP_Engine()
    calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
    calc_fdn = fdn.Foundation_Engine(sigma_tanah)
    engine_export = exp.Export_Engine()

    # --- TABS ORIGINAL (8 MODUL) ---
    st.markdown("### 🏗️ Studio Perhitungan Teknik Sipil Terintegrasi")
    tabs = st.tabs([
        "🏠 Dash", 
        "📂 BIM Import", 
        "📐 Modeling", 
        "🏗️ Beton", 
        "🔩 Baja & Atap", 
        "🌋 Gempa", 
        "⛰️ Geoteknik", 
        "💰 RAB Final"
    ])

    # TAB 1 - DASHBOARD
    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        c1.metric("Standar Beton", "SNI 2847:2019", f"fc' {fc_in} MPa")
        c2.metric("Standar Gempa", "SNI 1726:2019", "Wilayah D")
        c3.metric("Standar Biaya", "SE PUPR 2025", "Update")

    # TAB 2 - BIM IMPORT (KUNCI AGAR AI BISA BACA IFC)
    with tabs[1]:
        st.markdown('<p class="sub_header">Import IFC</p>', unsafe_allow_html=True)
        uploaded_ifc = st.file_uploader("Upload File .IFC", type=["ifc"])
        if uploaded_ifc:
            try:
                engine_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                df_struk = engine_ifc.parse_structure()
                loads = engine_ifc.calculate_architectural_loads()
                st.dataframe(df_struk.head())
                if st.button("Simpan Data BIM ke AI"):
                    # SIMPAN KE SESSION STATE AGAR DIBACA AI
                    st.session_state['bim_loads'] = loads['Total Load Tambahan (kN)']
                    st.success(f"Data Tersimpan! Beban Tambahan: {st.session_state['bim_loads']} kN. Sekarang Anda bisa tanya AI.")
            except Exception as e: st.error(f"Error: {e}")

    # TAB 3 - MODELING
    with tabs[2]:
        c1, c2 = st.columns([1, 2])
        with c1:
            L = st.number_input("Bentang (m)", 2.0, 12.0, st.session_state['geo']['L'])
            b = st.number_input("Lebar b (mm)", 150, 800, st.session_state['geo']['b'])
            h = st.number_input("Tinggi h (mm)", 200, 1500, st.session_state['geo']['h'])
            # SIMPAN KE SESSION STATE
            st.session_state['geo'] = {'L': L, 'b': b, 'h': h}
        with c2:
            st.info(f"Dimensi Balok: {b} x {h} mm, Panjang: {L} m")

    # TAB 4 - BETON
    with tabs[3]:
        st.markdown("### Analisa Balok")
        c1, c2 = st.columns(2)
        with c1:
            q_dl = st.number_input("DL (kN/m)", 15.0)
            q_ll = st.number_input("LL (kN/m)", 5.0)
            if 'bim_loads' in st.session_state: 
                q_dl += st.session_state['bim_loads'] / st.session_state['geo']['L']
                st.caption(f"Termasuk beban BIM: {st.session_state['bim_loads']} kN")
        with c2:
            Mu = (1/8) * (1.2*q_dl + 1.6*q_ll) * st.session_state['geo']['L']**2
            st.metric("Mu (kNm)", f"{Mu:.2f}")
            As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
            dia = st.selectbox("Diameter", [13, 16, 19, 22])
            n = int(As_req / (0.25*3.14*dia**2)) + 1
            st.success(f"Pakai {n} D{dia}")
            
            # Save State & Report untuk AI
            st.session_state['structure'] = {'vol_beton': st.session_state['geo']['L']*b*h/1e6, 'berat_besi': 100}
            st.session_state['report_struk'] = {'Mu': Mu, 'Tulangan': f"{n}D{dia}"}
            
            if st.button("Download DXF Balok"):
                dxf = engine_export.create_dxf("BALOK", {'b':b,'h':h,'dia':dia,'n':n,'pjg':L})
                st.download_button("📥 .DXF", dxf, "balok.dxf")

    # TAB 5 - BAJA
    with tabs[4]:
        st.info("Analisa Baja WF")
        wf_list = {"WF 300x150": {'Zx': 481}, "WF 400x200": {'Zx': 1190}}
        pilih = st.selectbox("Profil", list(wf_list.keys()))
        if st.button("Cek Profil Baja"):
            res = steel.SNI_Steel_1729(250, 410).cek_balok_lentur(50, wf_list[pilih], 6.0)
            st.write(res)
            # Save Report untuk AI
            st.session_state['report_baja'] = {'Profil': pilih, 'Ratio': res['Ratio'], 'Status': res['Status']}

    # TAB 6 - GEMPA
    with tabs[5]:
        st.info("Base Shear SNI 1726")
        eng_gempa = quake.SNI_Gempa_1726(0.8, 0.4, "SD")
        V, sds, sd1 = eng_gempa.hitung_base_shear(2000, 8)
        st.metric("V Gempa (kN)", f"{V:.2f}")
        # Save Report untuk AI
        st.session_state['report_gempa'] = {'V_gempa': V, 'Site': "SD"}

    # TAB 7 - GEOTEKNIK
    with tabs[6]:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Pondasi Footplate")
            Pu = st.number_input("Beban P (kN)", 100.0)
            res_fp = calc_fdn.hitung_footplate(Pu, 1.0, 1.0, 300)
            st.write(res_fp)
            st.session_state['pondasi'] = {'fp_beton': res_fp['vol_beton'], 'fp_besi': res_fp['berat_besi']}
        with c2:
            st.subheader("Dinding Penahan")
            res_talud = calc_geo.hitung_talud_batu_kali(3.0, 0.4, 1.5)
            st.write(res_talud)
            st.session_state['geotech'] = {'vol_talud': res_talud['Vol_Per_M']}
            # Save Report untuk AI
            st.session_state['report_geo'] = {'Talud_SF': f"{res_talud['SF_Geser']:.2f}", 'Status': res_talud['Status']}

    # TAB 8 - RAB & REPORT
    with tabs[7]:
        st.subheader("RAB Final")
        vol_beton = st.session_state['structure'].get('vol_beton', 0) + st.session_state['pondasi'].get('fp_beton', 0)
        hsp = calc_biaya.hitung_hsp('beton_k250', {'semen': p_semen, 'pasir':p_pasir, 'split':p_split}, {'pekerja':u_pekerja})
        
        st.write(f"Total Beton: {vol_beton:.2f} m3")
        st.write(f"Harga Satuan: Rp {hsp:,.0f}")
        st.metric("Total Biaya Beton", f"Rp {vol_beton*hsp:,.0f}")
        
        if st.button("Generate Excel Report Lengkap"):
            df_dummy = pd.DataFrame({"Item": ["Beton"], "Harga": [vol_beton*hsp]})
            excel_data = engine_export.create_excel_report(df_dummy, st.session_state['geo'])
            st.download_button("📥 Excel Report", excel_data, "Laporan.xlsx")
