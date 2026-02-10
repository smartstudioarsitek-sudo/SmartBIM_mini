import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import ai_engine as ai

# --- IMPORT MODULES ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake
import libs_pdf as pdf_engine # PDF Generator

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

# --- INIT SESSION STATE ---
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
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.title("ENGINEX TITAN")
    st.caption("AI + BIM + Structural Calculation")
    
    st.divider()
    api_key = st.text_input("🔑 Google API Key", type="password", help="Wajib untuk fitur AI Chat")
    
    model_opt = st.selectbox(
        "🧠 Versi Model",
        ["models/gemini-2.0-flash", "models/gemini-2.0-flash-lite", "models/gemini-1.5-flash"],
        index=0
    )
    
    st.divider()
    app_mode = st.radio("🛠️ Mode Aplikasi:", ["🤖 AI Consultant (Chat)", "🏗️ Engineering Studio (Full App)"])
    st.divider()
    
    # Input Global (Hanya muncul di mode Studio untuk rapih)
    if app_mode == "🏗️ Engineering Studio (Full App)":
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
    else:
        # Default value untuk mode chat agar tidak error
        fc_in, fy_in = 25, 400
        p_beton_ready, p_besi, p_kayu = 1100000, 14000, 2500000
        
# --- INIT ENGINES ---
calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
calc_biaya = ahsp.AHSP_Engine()
calc_geo = geo.Geotech_Engine(18.0, 30.0, 5.0) # Default geo
calc_fdn = fdn.Foundation_Engine(150.0) # Default fdn
engine_export = exp.Export_Engine()

# ==============================================================================
# MODE 1: AI CONSULTANT
# ==============================================================================
if app_mode == "🤖 AI Consultant (Chat)":
    st.header("🤖 AI Engineering Consultant")
    
    with st.expander("ℹ️ Lihat Data yang Dibaca AI"):
        st.text(ai.generate_context_from_state(st.session_state))
    
    col1, col2 = st.columns([1, 3])
    with col1:
        persona = st.selectbox("Pilih Ahli:", list(ai.PERSONAS.keys()))
        if st.button("🧹 Hapus Chat"):
            st.session_state.messages = []
            st.rerun()
            
    with col2:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        if prompt := st.chat_input("Contoh: 'Carikan dimensi balok optimal untuk momen 200 kNm bentang 6m'"):
            if not api_key:
                st.error("❌ Masukkan API Key dulu!")
                st.stop()
                
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("Berpikir..."):
                    ctx = ai.generate_context_from_state(st.session_state)
                    brain = ai.SmartBIM_Brain(api_key, model_opt, ai.PERSONAS[persona])
                    response = brain.ask(prompt, context_data=ctx)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})

# ==============================================================================
# MODE 2: ENGINEERING STUDIO
# ==============================================================================
elif app_mode == "🏗️ Engineering Studio (Full App)":
    
    tabs = st.tabs(["🏠 Dash", "📂 BIM", "📐 Model", "🏗️ Beton (Opt)", "🔩 Baja", "🌋 Gempa", "⛰️ Geotek", "💰 Laporan"])

    # TAB 1 - 3 (Standard)
    with tabs[0]:
        st.metric("Status Aplikasi", "Ready", "Optimasi Aktif")
    
    with tabs[1]:
        st.subheader("Import IFC")
        if st.file_uploader("Upload .IFC"):
            st.success("File terupload (Simulasi). Klik Simpan.")
            if st.button("Simpan Data BIM ke AI"):
                st.session_state['bim_loads'] = 15.5
                st.success("Data Tersimpan: Beban 15.5 kN")

    with tabs[2]:
        st.subheader("Modeling")
        L = st.number_input("Bentang (m)", 2.0, 12.0, st.session_state['geo']['L'])
        st.session_state['geo']['L'] = L

    # TAB 4 - BETON (DENGAN OPTIMIZER)
    with tabs[3]:
        st.markdown("### 🏗️ Desain Struktur Beton")
        mode_beton = st.radio("Mode:", ["A. Cek Manual", "B. Cari Dimensi Optimal (Auto)"], horizontal=True)
        
        if mode_beton == "A. Cek Manual":
            mu = st.number_input("Momen (kNm)", 10.0, 500.0, 100.0)
            st.info("Gunakan tab ini untuk cek keamanan balok yang sudah ada.")
            # ... (Kode cek manual standard) ...
            
        elif mode_beton == "B. Cari Dimensi Optimal (Auto)":
            st.info("💡 Cari ukuran balok paling hemat biaya namun AMAN.")
            import libs_optimizer as opt 
            
            c1, c2 = st.columns(2)
            with c1:
                mu_target = st.number_input("Target Momen (kNm)", 50.0, 1000.0, 150.0)
                L_target = st.number_input("Panjang Bentang (m)", 3.0, 12.0, st.session_state['geo']['L'])
            
            with c2:
                if st.button("🔍 Cari Dimensi Terbaik"):
                    harga_real = {'beton': p_beton_ready, 'baja': p_besi, 'bekisting': p_kayu/10}
                    optimizer = opt.BeamOptimizer(fc_in, fy_in, harga_real)
                    hasil = optimizer.cari_dimensi_optimal(mu_target, L_target)
                    
                    if hasil:
                        best = hasil[0]
                        st.success(f"🏆 REKOMENDASI: {best['b']} x {best['h']} mm")
                        st.metric("Biaya per m'", f"Rp {best['Biaya']:,.0f}")
                        st.dataframe(pd.DataFrame(hasil))
                    else:
                        st.error("Tidak ketemu. Coba kurangi beban.")

    # TAB 8 - REPORT
    with tabs[7]:
        st.subheader("Laporan Akhir")
        import libs_pdf as pdf_engine
        
        if st.button("Generate PDF Report (Professional)"):
            with st.spinner("Membuat PDF..."):
                pdf_bytes = pdf_engine.create_professional_report(st.session_state)
                st.download_button("📄 Download PDF", pdf_bytes, "Laporan.pdf", "application/pdf")
