import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from streamlit_drawable_canvas import st_canvas
from io import BytesIO

# --- PAGE CONFIG ---
st.set_page_config(page_title="IndoBIM Integrated: SAP + Revit + PlanSwift", layout="wide", page_icon="🏗️")

# --- CSS CUSTOMIZATION (UI PRO) ---
st.markdown("""
    <style>
    .block-container {padding-top: 1rem;}
    div.stButton > button:first-child {background-color: #2E86C1; color: white;}
    </style>
""", unsafe_allow_html=True)

# --- CLASS: STRUCTURAL SOLVER (Si "SAP2000") ---
class StructureSolver:
    """
    Meniru logika SAP2000: Menerima input bentang & beban, 
    mengeluarkan Gaya Dalam (Momen, Geser).
    """
    def __init__(self, length_m, load_kN_m):
        self.L = length_m
        self.q = load_kN_m
    
    def analyze_beam(self):
        # Analisa Balok Sederhana (Sendi-Rol)
        # Reaksi Tumpuan
        Rv = (self.q * self.L) / 2
        
        # Momen Maksimum (1/8 qL^2)
        M_max = (1/8) * self.q * (self.L ** 2)
        
        # Generate Diagram Data
        x = np.linspace(0, self.L, 100)
        # Persamaan Momen: Mx = (qL/2)x - (q/2)x^2
        M_x = (Rv * x) - (0.5 * self.q * x**2)
        
        return {
            "Rv": Rv,
            "M_max": M_max,
            "x_coords": x,
            "moment_values": M_x
        }

    def recommend_section(self, M_max_kNm):
        # Rule of Thumb Engineer Sipil berbasis Momen
        # Asumsi Mu = 1.2DL + 1.6LL (Simplified factor 1.4)
        Mu = M_max_kNm * 1.4
        
        # Pendekatan kasar dimensi ekonomis (h = sqrt(Mu) * k)
        # Tapi kita pakai pendekatan L/12 untuk balok induk beton
        h_min = self.L / 12 * 100 # cm
        
        # Pembulatan ke kelipatan 5
        h_design = 5 * round(h_min/5)
        if h_design < 20: h_design = 20
        b_design = h_design * 0.6 # Lebar ~ 1/2 - 2/3 tinggi
        b_design = 5 * round(b_design/5)
        if b_design < 15: b_design = 15
        
        return f"{int(b_design)}/{int(h_design)}"

# --- SIDEBAR: KONFIGURASI PROYEK ---
with st.sidebar:
    st.title("🏗️ IndoBIM V1.0")
    st.caption("Integrated: QS | Structural | BIM")
    
    st.header("1. Parameter Gambar")
    scale = st.slider("Skala Pixel/Meter", 10, 50, 30)
    
    st.header("2. Parameter Beban (SAP)")
    beban_mati = st.number_input("Dead Load (kN/m2)", value=2.0, help="Berat sendiri + Finishing")
    beban_hidup = st.number_input("Live Load (kN/m2)", value=2.5, help="Hunian Rumah Tinggal")
    q_total = beban_mati + beban_hidup # kN/m2 (Disederhanakan jadi beban merata balok nanti)
    
    st.header("3. Database Harga (PlanSwift)")
    st.caption("Update Harga Satuan Dasar (HSD)")
    price_beton = st.number_input("Beton K-250 (Rp/m3)", value=1100000)
    price_besi = st.number_input("Besi Ulir (Rp/kg)", value=14500)
    price_bekisting = st.number_input("Bekisting (Rp/m2)", value=180000)
    price_upah_cor = st.number_input("Upah Cor (Rp/m3)", value=150000)

# --- MAIN TABS ---
tab_draw, tab_struct, tab_qs, tab_export = st.tabs([
    "📐 1. Drafting (Revit Lite)", 
    "⚙️ 2. Structure (Mini-SAP)", 
    "💰 3. Estimator (PlanSwift)",
    "📤 4. Export"
])

# ==============================================================================
# TAB 1: DRAFTING (LOGIKA REVIT/PLAN SWIFT)
# ==============================================================================
with tab_draw:
    st.subheader("📍 Digitasi Denah Ruangan")
    col1, col2 = st.columns([3, 1])
    
    with col1:
        canvas_result = st_canvas(
            fill_color="rgba(46, 134, 193, 0.3)",
            stroke_width=2,
            stroke_color="#000",
            background_color="#fff",
            update_streamlit=True,
            height=500,
            width=700,
            drawing_mode="rect",
            key="canvas",
            display_toolbar=True
        )
    
    with col2:
        st.info("Panduan:")
        st.markdown("""
        1. Pilih **Rect** tool.
        2. Gambar layout balok/ruangan.
        3. Sistem akan otomatis menghitung koordinat.
        """)
        
    # PROSES DATA DARI CANVAS
    elements = []
    if canvas_result.json_data is not None:
        for i, obj in enumerate(canvas_result.json_data["objects"]):
            w_m = obj["width"] / scale
            h_m = obj["height"] / scale
            
            # Logic: Sisi terpanjang dianggap bentang balok induk
            bentang = max(w_m, h_m)
            trib_width = min(w_m, h_m) / 2 # Lebar tributary area (asumsi amplop)
            
            # Beban merata pada balok (q = Luas * Beban / Panjang) 
            # Simplifikasi: q (kN/m') = Beban Area (kN/m2) * Lebar Tributary (m)
            q_line = q_total * (min(w_m, h_m) / 2) * 2 # Asumsi 2 sisi
            
            elements.append({
                "ID": f"B-{i+1}",
                "Type": "Balok Induk",
                "Bentang (m)": round(bentang, 2),
                "Load (kN/m)": round(q_line, 2),
                "W_px": obj["width"], "H_px": obj["height"],
                "Left": obj["left"], "Top": obj["top"],
                "Luas (m2)": round(w_m*h_m, 2)
            })
            
    df_elements = pd.DataFrame(elements)

# ==============================================================================
# TAB 2: ANALISA STRUKTUR (LOGIKA SAP2000)
# ==============================================================================
with tab_struct:
    st.subheader("⚙️ Analisa Mekanika & Desain Penampang")
    
    if not df_elements.empty:
        col_list, col_detail = st.columns([1, 2])
        
        with col_list:
            st.write("Pilih Elemen Struktur:")
            selected_id = st.selectbox("ID Balok", df_elements["ID"])
            
            # Get data selected
            data = df_elements[df_elements["ID"] == selected_id].iloc[0]
            st.metric("Bentang", f"{data['Bentang (m)']} m")
            st.metric("Beban Merata (q)", f"{data['Load (kN/m)']} kN/m'")
        
        with col_detail:
            # PANGGIL CLASS StructureSolver
            solver = StructureSolver(data['Bentang (m)'], data['Load (kN/m)'])
            res = solver.analyze_beam()
            rec_dim = solver.recommend_section(res['M_max'])
            
            # Plotting Matplotlib (Diagram Momen)
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(res['x_coords'], res['moment_values'], color='red', label='Bidang Momen (M)')
            ax.fill_between(res['x_coords'], res['moment_values'], color='red', alpha=0.1)
            ax.set_title(f"Diagram Momen Balok {selected_id} (M.max = {res['M_max']:.2f} kNm)")
            ax.set_xlabel("Jarak (m)")
            ax.set_ylabel("Momen (kNm)")
            ax.grid(True, linestyle='--')
            st.pyplot(fig)
            
            # Output Engineering
            st.success(f"✅ Rekomendasi Dimensi Penampang (SNI Rule of Thumb): **{rec_dim} cm**")
            
            # Simpan dimensi ke dataframe utama untuk dipakai QS
            idx = df_elements.index[df_elements['ID'] == selected_id].tolist()[0]
            # Parsing "25/40" menjadi angka
            b_dim = int(rec_dim.split("/")[0]) / 100 # convert to m
            h_dim = int(rec_dim.split("/")[1]) / 100 # convert to m
            
            # Update all rows (in reality, should be per row, but simple for now)
            df_elements["b (m)"] = b_dim
            df_elements["h (m)"] = h_dim
            
    else:
        st.warning("Gambar dulu di Tab 1!")

# ==============================================================================
# TAB 3: ESTIMASI BIAYA / QS (LOGIKA PLANSWIFT)
# ==============================================================================
with tab_qs:
    st.subheader("💰 Bill of Quantities (BoQ) & RAB")
    
    if not df_elements.empty and "h (m)" in df_elements.columns:
        # 1. HITUNG VOLUME REAL (Logic BIM: Geometry -> Volume)
        # Volume Beton = Panjang x Lebar x Tinggi
        df_elements["Vol. Beton (m3)"] = df_elements["Bentang (m)"] * df_elements["b (m)"] * df_elements["h (m)"]
        
        # Luas Bekisting = (2 x Tinggi + Lebar Bawah) x Panjang
        df_elements["Luas Bekisting (m2)"] = (2 * df_elements["h (m)"] + df_elements["b (m)"]) * df_elements["Bentang (m)"]
        
        # Berat Besi (Logic Engineer: Asumsi rasio penulangan 150kg/m3 beton untuk balok tahan gempa)
        ratio_besi = 150 # kg/m3
        df_elements["Berat Besi (kg)"] = df_elements["Vol. Beton (m3)"] * ratio_besi
        
        st.dataframe(df_elements[["ID", "Bentang (m)", "b (m)", "h (m)", "Vol. Beton (m3)", "Berat Besi (kg)"]])
        
        st.divider()
        
        # 2. ANALISA HARGA SATUAN (AHS)
        st.markdown("### 📋 Rekapitulasi Biaya")
        
        vol_beton_total = df_elements["Vol. Beton (m3)"].sum()
        luas_bekisting_total = df_elements["Luas Bekisting (m2)"].sum()
        berat_besi_total = df_elements["Berat Besi (kg)"].sum()
        
        # Breakdown Costs
        cost_beton = vol_beton_total * (price_beton + price_upah_cor) # Material + Upah
        cost_besi = berat_besi_total * (price_besi + 2500) # Material + Upah rakit (2500)
        cost_bekisting = luas_bekisting_total * (price_bekisting + 50000) # Material + Upah pasang
        
        rab_data = {
            "Item Pekerjaan": ["Pekerjaan Beton (Cor + Upah)", "Pekerjaan Pembesian (Ulir)", "Pekerjaan Bekisting"],
            "Volume": [vol_beton_total, berat_besi_total, luas_bekisting_total],
            "Satuan": ["m3", "kg", "m2"],
            "Harga Satuan (Est)": [price_beton+price_upah_cor, price_besi+2500, price_bekisting+50000],
            "Total Harga": [cost_beton, cost_besi, cost_bekisting]
        }
        df_rab = pd.DataFrame(rab_data)
        
        st.table(df_rab.style.format({"Volume": "{:.2f}", "Harga Satuan (Est)": "{:,.0f}", "Total Harga": "{:,.0f}"}))
        
        grand_total = df_rab["Total Harga"].sum()
        ppn = grand_total * 0.11
        st.success(f"### Grand Total (Inc. PPN 11%): Rp {grand_total + ppn:,.0f}")
        
    else:
        st.warning("Lakukan Analisa Struktur di Tab 2 terlebih dahulu untuk mendapatkan dimensi balok!")

# ==============================================================================
# TAB 4: EXPORT & LAPORAN
# ==============================================================================
with tab_export:
    st.subheader("📤 Export Data")
    col_ex1, col_ex2 = st.columns(2)
    
    with col_ex1:
        st.markdown("#### Export Excel (Untuk QS)")
        if 'df_rab' in locals():
            # Convert to Excel in memory
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_rab.to_excel(writer, sheet_name='RAB', index=False)
                df_elements.to_excel(writer, sheet_name='Backup Volume', index=False)
            
            st.download_button(
                label="📥 Download RAB (.xlsx)",
                data=output.getvalue(),
                file_name="RAB_Project_IndoBIM.xlsx",
                mime="application/vnd.ms-excel"
            )
            
    with col_ex2:
        st.markdown("#### Export Koordinat (Untuk Drafter)")
        # Simulasi Text File untuk Script AutoCAD
        if not df_elements.empty:
            script_cad = ";; Script AutoCAD Generated by IndoBIM\n"
            for index, row in df_elements.iterrows():
                # Simple rectangle command script
                script_cad += f"RECTANG {row['Left']},{row['Top']} @{row['W_px']},{row['H_px']}\n"
                script_cad += f"TEXT {row['Left'] + 10},{row['Top'] + 10} 20 0 {row['ID']}\n"
            
            st.download_button(
                label="📥 Download Script AutoCAD (.scr)",
                data=script_cad,
                file_name="draw_layout.scr",
                mime="text/plain"
            )
            st.caption("Cara pakai: Buka AutoCAD -> Ketik 'SCRIPT' -> Pilih file ini.")
