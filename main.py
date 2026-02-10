import streamlit as st
import pandas as pd
import ai_engine as ai
import libs_tools as tools
# Import library asli untuk Mode Studio
import libs_sni as sni
import libs_baja as steel
import libs_gempa as quake

# --- CONFIG ---
st.set_page_config(page_title="EnginEx Titan", layout="wide", page_icon="🏗️")

# --- CUSTOM CSS (Agar mirip screenshot Anda) ---
st.markdown("""
<style>
    .main-header {font-size: 24px; font-weight: bold; color: #1F618D;}
    .stButton>button {width: 100%; border-radius: 5px;}
    .sidebar-text {font-size: 12px; color: #555;}
    /* Chat Bubble Style */
    .stChatMessage {background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR: KONFIGURASI UTAMA ---
with st.sidebar:
    st.title("ENGINEX TITAN")
    st.caption("AI + BIM + Structural Calculation")
    
    st.divider()
    
    # 1. API KEY INPUT
    st.subheader("🔑 API Key & Model AI")
    api_key = st.text_input("Google API Key:", type="password", placeholder="Paste Gemini API Key disini...")
    
    if api_key:
        st.success("✅ API Key Terdeteksi")
    else:
        st.warning("⚠️ Masukkan API Key untuk mengaktifkan AI")
        st.markdown("[Dapatkan API Key Gratis](https://aistudio.google.com/app/apikey)")

    # 2. MODEL SELECTOR
    model_option = st.selectbox(
        "Pilih Model Gemini:",
        ["models/gemini-1.5-flash", "models/gemini-1.5-pro"],
        index=0,
        help="Flash lebih cepat & hemat, Pro lebih pintar untuk analisis kompleks."
    )
    
    st.divider()
    
    # 3. MODE SELECTOR (HYBRID)
    st.subheader("🛠️ Mode Aplikasi")
    app_mode = st.radio(
        "Pilih Tampilan:",
        ["🤖 AI Consultant (Chat)", "🏗️ Engineering Studio (Manual)"],
        captions=["Diskusi & Analisa Otomatis", "Kalkulator & Form Input"]
    )
    
    if st.button("🧹 Reset Data & Chat"):
        st.session_state.messages = []
        st.rerun()

# --- INITIALIZE SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# ==============================================================================
# MODE 1: AI CONSULTANT (CHAT INTERFACE - MIRIP GAMBAR 3)
# ==============================================================================
if app_mode == "🤖 AI Consultant (Chat)":
    st.header("🤖 AI Engineering Consultant")
    
    # Pilih Persona
    selected_persona = st.selectbox(
        "Pilih Ahli:",
        list(ai.PERSONAS.keys())
    )
    
    # Tampilkan Chat History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    # Input User
    if prompt := st.chat_input("Konsultasikan proyek Anda di sini..."):
        if not api_key:
            st.error("❌ Mohon masukkan Google API Key di Sidebar terlebih dahulu!")
            st.stop()
            
        # 1. Tampilkan pesan user
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # 2. Proses AI
        with st.chat_message("assistant"):
            with st.spinner(f"{selected_persona.split(' ')[1]} sedang berpikir & menghitung..."):
                # Init Brain dengan Persona Terpilih
                brain = ai.SmartBIM_Brain(
                    api_key=api_key, 
                    model_name=model_option,
                    system_instruction=ai.PERSONAS[selected_persona]
                )
                
                # Kirim history chat sebelumnya (agar konteks nyambung)
                # (Fitur ini opsional, untuk simplifikasi kita kirim prompt baru saja di demo ini)
                response_text = brain.ask(prompt)
                
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})

# ==============================================================================
# MODE 2: ENGINEERING STUDIO (FORM INPUT - MIRIP GAMBAR 2)
# ==============================================================================
elif app_mode == "🏗️ Engineering Studio (Manual)":
    st.header("🏗️ Engineering Studio (TITAN)")
    
    # Tab Navigasi Kalkulator
    tab1, tab2, tab3, tab4 = st.tabs([
        "Struktur Beton", "Struktur Baja", "Analisa Gempa", "RAB & Report"
    ])
    
    # --- TAB 1: BETON ---
    with tab1:
        st.subheader("Analisa Balok Beton (SNI 2847)")
        col1, col2 = st.columns(2)
        with col1:
            b = st.number_input("Lebar (mm)", 150, 1000, 300)
            h = st.number_input("Tinggi (mm)", 200, 2000, 600)
            fc = st.number_input("Mutu Beton f'c (MPa)", 20, 60, 25)
            fy = st.number_input("Mutu Baja fy (MPa)", 240, 550, 400)
        with col2:
            mu = st.number_input("Momen Ultimate (kNm)", 10.0, 1000.0, 150.0)
            vu = st.number_input("Geser Ultimate (kN)", 10.0, 1000.0, 100.0)
            
            if st.button("Hitung Kapasitas", type="primary"):
                # Panggil Libs Manual (Tanpa AI)
                engine = sni.SNI_Concrete_2847(fc, fy)
                as_req = engine.kebutuhan_tulangan(mu, b, h, 40)
                
                # Tampilkan Hasil Visual
                st.metric("Tulangan Perlu (As)", f"{as_req:.2f} mm2")
                
                n_bars = int(as_req / (0.25 * 3.14 * 16**2)) + 1
                st.info(f"Rekomendasi: {n_bars} D16")
                
                if n_bars > 8:
                    st.warning("⚠️ Tulangan terlalu padat! Perbesar dimensi.")
                else:
                    st.success("✅ Desain Aman")

    # --- TAB 2: BAJA ---
    with tab2:
        st.subheader("Cek Profil Baja WF (SNI 1729)")
        mu_baja = st.number_input("Momen Beban (kNm)", 50.0)
        lb = st.number_input("Panjang Bentang (m)", 6.0)
        
        # Panggil Libs Baja
        wf_data = {'Zx': 481} # Contoh WF 300
        st.caption("Default: WF 300x150 (Zx=481 cm3)")
        
        if st.button("Cek Rasio Baja"):
            eng_steel = steel.SNI_Steel_1729(250, 410)
            res = eng_steel.cek_balok_lentur(mu_baja, wf_data, lb)
            
            st.write(f"Kapasitas Phi_Mn: {res['Phi_Mn']:.2f} kNm")
            st.metric("Ratio Desain", f"{res['Ratio']:.3f}", delta_color="inverse")
            if res['Ratio'] < 1.0:
                st.success("Profil AMAN")
            else:
                st.error("Profil GAGAL (Tekuk)")

    # --- TAB 3: GEMPA ---
    with tab3:
        st.subheader("Base Shear Gempa (SNI 1726)")
        w_gedung = st.number_input("Berat Bangunan (kN)", 5000.0)
        ss_input = st.number_input("Ss (Peta Gempa)", 0.8)
        
        if st.button("Hitung V Gempa"):
            eng_quake = quake.SNI_Gempa_1726(ss_input, 0.4, "SD")
            v, sds, sd1 = eng_quake.hitung_base_shear(w_gedung, 8.0)
            st.metric("Gaya Geser Dasar (V)", f"{v:.2f} kN")
            st.json({"Sds": sds, "Sd1": sd1})
