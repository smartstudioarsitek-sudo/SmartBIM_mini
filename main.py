import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
import ai_engine as ai

# --- IMPORT SEMUA MODULE (WAJIB LENGKAP) ---
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo
import libs_export as exp
import libs_baja as steel
import libs_gempa as quake
import libs_pdf as pdf_engine
import libs_optimizer as opt

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
# SIDEBAR UTAMA
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
    
    # --- INPUT GLOBAL (GLOBAL INPUTS) ---
    # Variabel ini harus didefinisikan di level Sidebar agar bisa diakses oleh Mode manapun
    # Kita berikan nilai default agar tidak Error saat pindah mode
    
    st.divider()
    
    # Input Material & Tanah (Selalu muncul atau minimal terdefinisi)
    # Jika mode Chat, kita sembunyikan tapi tetap set nilai defaultnya
    
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
        # Nilai Default untuk Mode Chat (Agar variabel tidak 'undefined')
        fc_in = 25
        fy_in = 400
        gamma_tanah = 18.0
        phi_tanah = 30.0
        c_tanah = 5.0
        sigma_tanah = 150.0
        
        p_semen = 1500
        p_pasir = 250000
        p_split = 300000
        p_besi = 14000
        p_kayu = 2500000
        p_batu = 280000
        p_beton_ready = 1100000
        u_tukang = 135000
        u_pekerja = 110000

# --- INIT ENGINES (ENGINE DINYALAKAN SETELAH VARIABEL DIDEFINISIKAN) ---
# Sekarang variabel gamma_tanah dll sudah pasti ada nilainya
calc_sni = sni.SNI_Concrete_2847(fc_in, fy_in)
calc_biaya = ahsp.AHSP_Engine()
calc_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
calc_fdn = fdn.Foundation_Engine(sigma_tanah)
engine_export = exp.Export_Engine()

# ==============================================================================
# MODE 1: AI CONSULTANT
# ==============================================================================
if app_mode == "🤖 AI Consultant (Chat)":
    st.header("🤖 AI Engineering Consultant")
    
    with st.expander("ℹ️ Lihat Data yang Dibaca AI"):
        # Kita bungkus dalam try-except agar aman jika file ai_engine bermasalah
        try:
            st.text(ai.generate_context_from_state(st.session_state))
        except:
            st.text("Menunggu inisialisasi AI...")
    
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
    
    tabs = st.tabs([
        "🏠 Dash", "📂 BIM", "📐 Model", 
        "🏗️ Beton (Opt)", "🔩 Baja", "🌋 Gempa", 
        "⛰️ Geotek", "💰 Laporan"
    ])

    # --- TAB 1: DASHBOARD ---
    with tabs[0]:
        st.subheader("Dashboard Proyek")
        c1, c2, c3 = st.columns(3)
        c1.metric("Mutu Beton", f"fc' {fc_in} MPa")
        c2.metric("Mutu Baja", f"fy {fy_in} MPa")
        c3.metric("Status AI", "Siap")

    # --- TAB 2: BIM IMPORT ---
    with tabs[1]:
        st.subheader("Import IFC")
        uploaded_ifc = st.file_uploader("Upload File .IFC", type=["ifc"])
        if uploaded_ifc:
            try:
                engine_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                df_struk = engine_ifc.parse_structure()
                loads = engine_ifc.calculate_architectural_loads()
                st.dataframe(df_struk.head())
                if st.button("Simpan Data BIM ke AI"):
                    val_load = loads['Total Load Tambahan (kN)']
                    st.session_state['bim_loads'] = val_load
                    st.success(f"Data Tersimpan: Beban Tambahan {val_load} kN")
            except Exception as e: st.error(f"Error: {e}")

    # --- TAB 3: MODELING ---
    with tabs[2]:
        st.subheader("Modeling Geometri")
        col_mod1, col_mod2 = st.columns([1, 2])
        with col_mod1:
            L = st.number_input("Panjang Bentang (m)", 2.0, 12.0, st.session_state['geo']['L'])
            b = st.number_input("Lebar Balok (mm)", 150, 800, st.session_state['geo']['b'])
            h = st.number_input("Tinggi Balok (mm)", 200, 1500, st.session_state['geo']['h'])
            st.session_state['geo'] = {'L': L, 'b': b, 'h': h, 'fc': fc_in} # Update state
        with col_mod2:
            st.info(f"Dimensi Aktif: {b} x {h} mm, Panjang: {L} m")

    # --- TAB 4: BETON (DENGAN OPTIMIZER) ---
    with tabs[3]:
        st.markdown("### 🏗️ Desain Struktur Beton")
        mode_beton = st.radio("Pilih Mode:", ["A. Cek Kapasitas (Manual)", "B. Cari Dimensi Optimal (Auto)"], horizontal=True)
        
        if mode_beton == "A. Cek Kapasitas (Manual)":
            c1, c2 = st.columns(2)
            with c1:
                q_dl = st.number_input("DL (kN/m)", 15.0)
                q_ll = st.number_input("LL (kN/m)", 5.0)
                if 'bim_loads' in st.session_state: 
                    q_dl += st.session_state['bim_loads'] / st.session_state['geo']['L']
                    st.caption(f"Termasuk beban BIM: {st.session_state['bim_loads']} kN")
            with c2:
                Mu = (1/8) * (1.2*q_dl + 1.6*q_ll) * st.session_state['geo']['L']**2
                st.metric("Momen Ultimate (Mu)", f"{Mu:.2f} kNm")
                As_req = calc_sni.kebutuhan_tulangan(Mu, st.session_state['geo']['b'], st.session_state['geo']['h'], 40)
                dia = st.selectbox("Diameter", [13, 16, 19, 22])
                n = int(As_req / (0.25*3.14*dia**2)) + 1
                st.success(f"Pakai {n} D{dia}")
                
                # Volume dalam m3
                vol = (st.session_state['geo']['L'] * st.session_state['geo']['b'] * st.session_state['geo']['h']) / 1e6
                st.session_state['structure'] = {'vol_beton': vol, 'berat_besi': 100}
                st.session_state['report_struk'] = {'Mu': round(Mu, 2), 'Tulangan': f"{n}D{dia}"}
                
                if st.button("Download DXF Balok"):
                    dxf = engine_export.create_dxf("BALOK", {'b':st.session_state['geo']['b'],'h':st.session_state['geo']['h'],'dia':dia,'n':n,'pjg':st.session_state['geo']['L']})
                    st.download_button("📥 .DXF", dxf, "balok.dxf")

        elif mode_beton == "B. Cari Dimensi Optimal (Auto)":
            st.info("💡 Fitur ini mencari ukuran balok paling hemat biaya namun AMAN (SNI).")
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
                        st.error("Tidak ditemukan solusi. Coba kurangi beban.")

    # --- TAB 5: BAJA ---
    with tabs[4]:
        st.subheader("Analisa Baja WF")
        c1, c2 = st.columns(2)
        with c1:
            Mu_baja = st.number_input("Momen (kNm)", 10.0, 500.0, 50.0)
            Lb_baja = st.number_input("Panjang (m)", 1.0, 12.0, 4.0)
        with c2:
            wf_list = {"WF 300x150": {'Zx': 481}, "WF 400x200": {'Zx': 1190}}
            pilih = st.selectbox("Profil", list(wf_list.keys()))
            if st.button("Cek Profil Baja"):
                res = steel.SNI_Steel_1729(250, 410).cek_balok_lentur(Mu_baja, wf_list[pilih], Lb_baja)
                st.write(res)
                st.session_state['report_baja'] = {'Profil': pilih, 'Ratio': res['Ratio'], 'Status': res['Status'], 'Mu': Mu_baja, 'Phi_Mn': res['Phi_Mn']}

    # --- TAB 6: GEMPA ---
    with tabs[5]:
        st.subheader("Analisa Gempa SNI 1726")
        c1, c2 = st.columns(2)
        with c1:
            Ss = st.number_input("Ss", 0.0, 2.0, 0.8)
            site = st.selectbox("Tanah", ["SE", "SD", "SC"])
        with c2:
            Wt = st.number_input("Berat Bangunan (kN)", 100.0, 10000.0, 2000.0)
            eng_gempa = quake.SNI_Gempa_1726(Ss, 0.4, site)
            V, sds, sd1 = eng_gempa.hitung_base_shear(Wt, 8.0)
            st.metric("Base Shear (V)", f"{V:.2f} kN")
            st.session_state['report_gempa'] = {'V_gempa': round(V,2), 'Site': site}

    # --- TAB 7: GEOTEKNIK ---
    with tabs[6]:
        st.subheader("Analisa Geoteknik")
        c1, c2 = st.columns(2)
        with c1:
            Pu = st.number_input("Beban P (kN)", 50.0, 1000.0, 100.0)
            res_fp = calc_fdn.hitung_footplate(Pu, 1.0, 1.0, 300)
            st.write(res_fp)
            st.session_state['pondasi'] = {'fp_beton': res_fp['vol_beton'], 'fp_besi': res_fp['berat_besi']}
        with c2:
            res_talud = calc_geo.hitung_talud_batu_kali(3.0, 0.4, 1.5)
            st.write(res_talud)
            st.session_state['geotech'] = {'vol_talud': res_talud['Vol_Per_M']}
            st.session_state['report_geo'] = {'Talud_SF': f"{res_talud['SF_Geser']:.2f}", 'Status': res_talud['Status']}

    # --- TAB 8: RAB & REPORT ---
    with tabs[7]:
        st.subheader("Laporan Akhir")
        
        # Hitungan RAB Dummy untuk Display
        vol_beton = st.session_state['structure'].get('vol_beton', 0)
        hsp = calc_biaya.hitung_hsp('beton_k250', {'semen': p_semen, 'pasir':p_pasir, 'split':p_split}, {'pekerja':u_pekerja})
        st.metric("Estimasi Biaya Struktur Atas", f"Rp {vol_beton*hsp:,.0f}")
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Generate Excel (Data Mentah)"):
                df_dummy = pd.DataFrame({"Item": ["Beton"], "Harga": [vol_beton*hsp]})
                excel_data = engine_export.create_excel_report(df_dummy, st.session_state['geo'])
                st.download_button("📥 .XLSX", excel_data, "Laporan.xlsx")
                
        with c2:
            if st.button("Generate PDF Report (Professional)"):
                with st.spinner("Membuat PDF..."):
                    pdf_bytes = pdf_engine.create_professional_report(st.session_state)
                    st.download_button("📄 Download PDF", pdf_bytes, "Laporan_Resmi.pdf", "application/pdf")
