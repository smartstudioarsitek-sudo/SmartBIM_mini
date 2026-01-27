import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import libs_sni as sni
import libs_ahsp as ahsp
import libs_bim_importer as bim
import libs_pondasi as fdn
import libs_geoteknik as geo # Module Baru

st.set_page_config(page_title="IndoBIM Ultimate: Slope & Structure", layout="wide", page_icon="🏗️")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .header-style {font-size:20px; font-weight:bold; color:#004E98;}
    div.stButton > button {background-color: #004E98; color: white; width: 100%;}
    </style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.title("IndoBIM Ultimate")
    st.info("Support: Revit/ArchiCAD IFC • SNI 2847 • SE 182 PUPR")
    
    st.markdown("### 1. Parameter Tanah (Site)")
    gamma_tanah = st.number_input("Berat Isi Tanah (kN/m3)", 14.0, 22.0, 18.0)
    phi_tanah = st.number_input("Sudut Geser (deg)", 10.0, 45.0, 30.0)
    c_tanah = st.number_input("Kohesi (kN/m2)", 0.0, 50.0, 5.0)
    
    st.divider()
    st.markdown("### 2. Harga Satuan (RAB)")
    p_batu = st.number_input("Batu Kali (Rp/m3)", value=280000)
    p_beton_ready = st.number_input("Beton Readymix (Rp/m3)", value=1100000)
    u_pekerja = st.number_input("Upah Pekerja", value=120000)

# --- INIT ENGINES ---
engine_geo = geo.Geotech_Engine(gamma_tanah, phi_tanah, c_tanah)
calc_biaya = ahsp.AHSP_Engine()

# --- TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Home", "📂 BIM Import", "⛰️ Geoteknik (Lereng)", "🏗️ Struktur & Pile", "💰 RAB & Shop Drawing"
])

# 1. HOME
with tab1:
    st.title("Selamat Datang di IndoBIM Ultimate")
    st.write("Solusi terintegrasi untuk bangunan di lahan kontur/lereng.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Kondisi Tanah", "Lereng/Flat", f"Phi: {phi_tanah}°")
    c2.metric("Metode Analisa", "Rankine & Mayerhof", "SNI 8460:2017")
    c3.metric("Cost Standard", "SE PUPR 182", "Update 2025")

# 2. IMPORT BIM
with tab2:
    st.markdown('<p class="header-style">Import Model IFC (Revit/ArchiCAD)</p>', unsafe_allow_html=True)
    st.caption("Aplikasi akan membaca kolom (untuk beban pile) dan dinding (untuk beban balok).")
    
    uploaded_ifc = st.file_uploader("Upload .IFC File", type=["ifc"])
    if uploaded_ifc:
        try:
            with st.spinner("Membaca data BIM..."):
                engine_ifc = bim.IFC_Parser_Engine(uploaded_ifc)
                df_struk = engine_ifc.parse_structure()
                st.success(f"Terbaca {len(df_struk)} elemen struktur.")
                st.dataframe(df_struk.head())
                
                # Plot Denah
                fig, ax = plt.subplots()
                ax.scatter(df_struk['X'], df_struk['Y'], c='red', marker='x')
                ax.set_title("Denah Titik Kolom dari BIM")
                st.pyplot(fig)
                
                st.session_state['bim_data'] = df_struk
        except Exception as e:
            st.error(f"Error import: {e}")

# 3. GEOTEKNIK (TALUD)
with tab3:
    st.markdown('<p class="header-style">Analisa Dinding Penahan Tanah (Talud)</p>', unsafe_allow_html=True)
    
    col_t1, col_t2 = st.columns([1, 2])
    with col_t1:
        H_talud = st.number_input("Tinggi Talud (m)", 2.0, 10.0, 3.0)
        B_atas = st.number_input("Lebar Atas (m)", 0.3, 1.0, 0.4)
        B_bawah = st.number_input("Lebar Bawah (m)", 0.5, 5.0, 1.5)
        
        # Hitung
        res_talud = engine_geo.hitung_talud_batu_kali(H_talud, B_atas, B_bawah)
        
        st.write("---")
        if res_talud['Status'] == "AMAN":
            st.success(f"✅ Konstruksi AMAN")
        else:
            st.error(f"❌ BAHAYA (Perbesar Dimensi)")
            
        st.write(f"SF Guling: {res_talud['SF_Guling']:.2f} (Min 1.5)")
        st.write(f"SF Geser: {res_talud['SF_Geser']:.2f} (Min 1.5)")
        
        # Simpan volume untuk RAB
        st.session_state['vol_talud'] = res_talud['Vol_Per_M']

    with col_t2:
        # Visualisasi Penampang Talud
        fig, ax = plt.subplots()
        coords = res_talud['Coords']
        polygon = plt.Polygon(coords, closed=True, fill=True, edgecolor='black', facecolor='gray', alpha=0.5)
        ax.add_patch(polygon)
        
        # Gambar Tanah
        ax.fill_between([B_bawah, B_bawah+2], [0, 0], [H_talud, H_talud], color='brown', alpha=0.3, label='Tanah Urug')
        
        ax.set_xlim(-1, B_bawah+3)
        ax.set_ylim(-1, H_talud+1)
        ax.set_aspect('equal')
        ax.set_title("Cross Section Dinding Penahan")
        st.pyplot(fig)
        
        # Download DXF Button
        dxf_str = engine_geo.generate_shop_drawing_dxf("TALUD", res_talud)
        st.download_button("📥 Download Shop Drawing (.dxf)", dxf_str, "Detail_Talud.dxf")

# 4. STRUKTUR & PILE
with tab4:
    st.markdown('<p class="header-style">Pondasi Dalam (Bore Pile / Tiang Pancang)</p>', unsafe_allow_html=True)
    
    c_p1, c_p2 = st.columns(2)
    with c_p1:
        st.info("Input Beban")
        # Bisa ambil dari BIM atau Manual
        beban_pile = st.number_input("Beban Aksial per Titik (kN)", 100.0, 5000.0, 800.0)
        
        st.info("Dimensi Pile")
        dia_pile = st.selectbox("Diameter (cm)", [30, 40, 50, 60, 80, 100])
        depth_pile = st.number_input("Kedalaman Rencana (m)", 6.0, 30.0, 12.0)
        
    with c_p2:
        st.info("Data Tanah (N-SPT)")
        nspt = st.number_input("N-SPT Rata-rata sepanjang tiang", 5, 60, 20)
        
        # Hitung Kapasitas
        res_pile = engine_geo.hitung_bore_pile(dia_pile, depth_pile, nspt)
        
        st.metric("Daya Dukung Izin (Qall)", f"{res_pile['Q_allow']:.1f} kN")
        
        # Cek Status
        if res_pile['Q_allow'] >= beban_pile:
            st.success(f"✅ Pile Diameter {dia_pile}cm AMAN")
        else:
            st.error(f"❌ TIDAK KUAT. Perdalam atau Perbesar Diameter.")
            
        # Simpan volume
        st.session_state['vol_pile'] = res_pile['Vol_Beton']

# 5. RAB TOTAL
with tab5:
    st.markdown('<p class="header-style">RAB Terintegrasi (SE 182)</p>', unsafe_allow_html=True)
    
    # Input Panjang Talud & Jumlah Pile
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        L_talud = st.number_input("Panjang Total Talud (m')", 10.0, 1000.0, 50.0)
    with col_r2:
        n_pile = st.number_input("Jumlah Titik Bore Pile", 1, 500, 20)
        
    if 'vol_talud' in st.session_state and 'vol_pile' in st.session_state:
        # 1. Volume Total
        vol_batu_total = st.session_state['vol_talud'] * L_talud
        vol_pile_total = st.session_state['vol_pile'] * n_pile
        
        # 2. Harga Satuan (HSP)
        # Dictionary harga dasar (simplified)
        h_bahan = {'batu kali': p_batu, 'beton k300': p_beton_ready, 'semen': 1500, 'pasir': 250000}
        h_upah = {'pekerja': u_pekerja, 'tukang': u_pekerja*1.2, 'mandor': u_pekerja*1.3}
        
        hsp_talud = calc_biaya.hitung_hsp('pasangan_batu_kali', h_bahan, h_upah)
        hsp_pile = calc_biaya.hitung_hsp('bore_pile_k300', h_bahan, h_upah)
        
        # 3. Tabel RAB
        data_rab = [
            {"Item": "Pek. Dinding Penahan (Talud)", "Vol": vol_batu_total, "Sat": "m3", "Harga": hsp_talud, "Total": vol_batu_total*hsp_talud},
            {"Item": "Pek. Bore Pile", "Vol": vol_pile_total, "Sat": "m3", "Harga": hsp_pile, "Total": vol_pile_total*hsp_pile},
        ]
        
        df_rab = pd.DataFrame(data_rab)
        st.dataframe(df_rab.style.format({"Vol": "{:.2f}", "Harga": "{:,.0f}", "Total": "{:,.0f}"}), use_container_width=True)
        
        st.success(f"### Total Estimasi: Rp {df_rab['Total'].sum():,.0f}")
    else:
        st.warning("Silakan hitung Talud dan Pile terlebih dahulu di Tab Geoteknik.")
