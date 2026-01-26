import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO

# --- CONFIG ---
st.set_page_config(page_title="IndoBIM Foundation Ultimate", layout="wide", page_icon="🏗️")

# --- CSS PRO ---
st.markdown("""
    <style>
    div.stButton > button:first-child {background-color: #2E86C1; color: white; width: 100%;}
    .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE (DATABASE PROYEK) ---
if 'project_data' not in st.session_state:
    st.session_state.project_data = {
        "grids_x": [0.0, 3.0, 6.0], # Default Grid X
        "grids_y": [0.0, 4.0],      # Default Grid Y
        "nodes": [],                # Generated Joints
        "footplates": [],           # Data Cakar Ayam (Point)
        "rubbles": []               # Data Batu Belah (Line)
    }

# --- CLASS & FUNGSI LOGIKA ---

def generate_nodes(gx, gy):
    """Membuat titik snapping otomatis dari perpotongan Grid"""
    nodes = []
    id_counter = 1
    for y in gy:
        for x in gx:
            nodes.append({"ID": id_counter, "X": x, "Y": y})
            id_counter += 1
    return pd.DataFrame(nodes)

def check_punching_shear(Pu_kN, fc, h_mm, c_mm):
    """Cek Geser Pons Sederhana (SNI 2847)"""
    # d = tebal efektif (tebal - selimut)
    d = h_mm - 75 
    # Keliling kritis (bo) = keliling kolom + d
    bo = 4 * (c_mm + d)
    # Kuat Geser Beton (Vc) = 0.33 * sqrt(fc) * bo * d
    Vc_N = 0.33 * np.sqrt(fc) * bo * d
    phi_Vc = 0.75 * Vc_N / 1000 # ke kN
    
    status = "✅ Aman" if phi_Vc > Pu_kN else "❌ Gagal Geser"
    return status, round(phi_Vc, 2)

# --- SIDEBAR (SETTINGS) ---
with st.sidebar:
    st.title("🏗️ Foundation Engine")
    st.caption("Integrated: SAP Grid + Revit Props + QS AHSP")
    
    st.header("1. Parameter Tanah & Material")
    sigma_tanah = st.number_input("Daya Dukung Tanah (kN/m2)", value=150.0, help="Hasil Sondir/Soil Test")
    depth_tanah = st.number_input("Kedalaman Galian (m)", value=1.5)
    
    st.divider()
    st.header("2. Database Harga (HSD)")
    hsp_galian = st.number_input("Upah Galian (Rp/m3)", 85000)
    hsp_batu = st.number_input("Pas. Batu Kali (Rp/m3)", 950000)
    hsp_beton = st.number_input("Beton K-250 (Rp/m3)", 1200000)
    hsp_besi = st.number_input("Besi Terpasang (Rp/kg)", 18500)

# --- TABS ---
tab_grid, tab_props, tab_model, tab_analisa, tab_rab = st.tabs([
    "1️⃣ Grid System", "2️⃣ Properties (Section)", "3️⃣ Modeling (Draw)", "4️⃣ Structural Analysis", "5️⃣ RAB / QS"
])

# ==============================================================================
# TAB 1: GRID SYSTEM (SAP STYLE)
# ==============================================================================
with tab_grid:
    col_g1, col_g2 = st.columns([1, 2])
    with col_g1:
        st.subheader("📍 Atur Grid (As Bangunan)")
        # Input Text untuk Grid (misal: 0, 3, 6)
        gx_str = st.text_input("Grid X (pisahkan koma)", value="0, 3.0, 6.0")
        gy_str = st.text_input("Grid Y (pisahkan koma)", value="0, 4.0, 7.0")
        
        # Update Session State
        try:
            st.session_state.project_data['grids_x'] = sorted([float(x.strip()) for x in gx_str.split(',')])
            st.session_state.project_data['grids_y'] = sorted([float(y.strip()) for y in gy_str.split(',')])
            st.success("Grid Updated!")
        except:
            st.error("Format salah. Gunakan angka dipisah koma (cth: 0, 3, 4.5)")
            
    with col_g2:
        # Visualisasi Grid
        fig, ax = plt.subplots(figsize=(6, 6))
        
        # Draw Grid Lines
        gx = st.session_state.project_data['grids_x']
        gy = st.session_state.project_data['grids_y']
        
        for x in gx:
            ax.axvline(x, color='gray', linestyle='--', alpha=0.5)
        for y in gy:
            ax.axhline(y, color='gray', linestyle='--', alpha=0.5)
            
        # Generate & Draw Nodes
        df_nodes = generate_nodes(gx, gy)
        ax.scatter(df_nodes['X'], df_nodes['Y'], color='red', zorder=5)
        
        # Label Nodes
        for idx, row in df_nodes.iterrows():
            ax.text(row['X']+0.1, row['Y']+0.1, f"J{int(row['ID'])}", fontsize=9, color='red', fontweight='bold')
            
        ax.set_title("Grid & Snapping Points (Joints)")
        ax.set_aspect('equal')
        st.pyplot(fig)
        
        st.caption(f"Total Snapping Points: {len(df_nodes)}")

# ==============================================================================
# TAB 2: PROPERTIES (REVIT STYLE)
# ==============================================================================
with tab_props:
    st.subheader("📦 Define Sections (Family Types)")
    
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.markdown("### A. Tipe Cakar Ayam (Footplate)")
        # Default Data
        data_fp = pd.DataFrame([
            {"Type": "P1", "L (m)": 1.0, "B (m)": 1.0, "Tebal (mm)": 250, "Kolom (mm)": 300},
            {"Type": "P2", "L (m)": 1.2, "B (m)": 1.2, "Tebal (mm)": 300, "Kolom (mm)": 400},
        ])
        edited_fp = st.data_editor(data_fp, num_rows="dynamic", key="editor_fp")
        
    with col_p2:
        st.markdown("### B. Tipe Batu Belah (Strip)")
        data_batu = pd.DataFrame([
            {"Type": "TB-1", "Lebar Atas (m)": 0.3, "Lebar Bawah (m)": 0.6, "Tinggi (m)": 0.8},
            {"Type": "TB-2", "Lebar Atas (m)": 0.25, "Lebar Bawah (m)": 0.5, "Tinggi (m)": 0.6},
        ])
        edited_batu = st.data_editor(data_batu, num_rows="dynamic", key="editor_batu")

# ==============================================================================
# TAB 3: MODELING (ASSIGNMENTS)
# ==============================================================================
with tab_model:
    st.subheader("🏗️ Assign Struktur ke Grid")
    
    c_mod1, c_mod2 = st.columns([1, 2])
    
    with c_mod1:
        st.info("Input Data Model")
        
        # 1. Assign Footplate (Ke Titik)
        st.markdown("#### 1. Tambah Cakar Ayam")
        fp_type = st.selectbox("Pilih Tipe P", edited_fp["Type"].unique())
        node_select = st.multiselect("Pilih Joint (Titik)", df_nodes["ID"])
        beban_p = st.number_input("Beban Aksial (kN)", value=100.0, step=10.0)
        
        if st.button("➕ Pasang Footplate"):
            for nid in node_select:
                # Cek duplikasi
                existing = [x for x in st.session_state.project_data['footplates'] if x['Node'] == nid]
                if not existing:
                    st.session_state.project_data['footplates'].append({
                        "Node": nid, "Type": fp_type, "Load (kN)": beban_p
                    })
            st.success(f"Terpasang di {len(node_select)} titik.")
            
        st.divider()
        
        # 2. Assign Batu Belah (Antar Titik)
        st.markdown("#### 2. Tambah Batu Belah (Sloof)")
        batu_type = st.selectbox("Pilih Tipe TB", edited_batu["Type"].unique())
        start_node = st.selectbox("Dari Joint", df_nodes["ID"], key="s_node")
        end_node = st.selectbox("Ke Joint", df_nodes["ID"], key="e_node")
        
        if st.button("➕ Pasang Batu Belah"):
            if start_node != end_node:
                st.session_state.project_data['rubbles'].append({
                    "Start": start_node, "End": end_node, "Type": batu_type
                })
                st.success("Pondasi jalur terpasang.")
            else:
                st.error("Titik awal dan akhir tidak boleh sama.")

        if st.button("🗑️ Reset Model"):
            st.session_state.project_data['footplates'] = []
            st.session_state.project_data['rubbles'] = []
            st.rerun()

    with c_mod2:
        # VISUALISASI HASIL MODELING
        fig2, ax2 = plt.subplots(figsize=(8, 8))
        
        # Draw Grid & Nodes (Background)
        for x in gx: ax2.axvline(x, color='#ddd', zorder=1)
        for y in gy: ax2.axhline(y, color='#ddd', zorder=1)
        
        # Draw Batu Belah (Lines)
        for r in st.session_state.project_data['rubbles']:
            n1 = df_nodes[df_nodes["ID"] == r["Start"]].iloc[0]
            n2 = df_nodes[df_nodes["ID"] == r["End"]].iloc[0]
            # Plot line
            ax2.plot([n1["X"], n2["X"]], [n1["Y"], n2["Y"]], color='gray', linewidth=5, alpha=0.7, zorder=2)
            # Label
            mx, my = (n1["X"]+n2["X"])/2, (n1["Y"]+n2["Y"])/2
            ax2.text(mx, my, r["Type"], fontsize=7, ha='center', color='black', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

        # Draw Footplates (Squares)
        for fp in st.session_state.project_data['footplates']:
            node = df_nodes[df_nodes["ID"] == fp["Node"]].iloc[0]
            # Get dimensions
            props = edited_fp[edited_fp["Type"] == fp["Type"]].iloc[0]
            w, h = props["B (m)"], props["L (m)"]
            
            # Rectangle (Center anchor)
            rect = patches.Rectangle((node["X"] - w/2, node["Y"] - h/2), w, h, linewidth=1, edgecolor='blue', facecolor='rgba(0,0,255,0.3)', zorder=3)
            ax2.add_patch(rect)
            ax2.text(node["X"], node["Y"], f"{fp['Type']}\nP={fp['Load (kN)']}", ha='center', va='center', fontsize=7, color='white', fontweight='bold')

        ax2.set_aspect('equal')
        ax2.set_title("3D Blueprint View (Top)")
        st.pyplot(fig2)

# ==============================================================================
# TAB 4: ANALISA STRUKTUR
# ==============================================================================
with tab_analisa:
    st.subheader("⚙️ Structural Check (Safety)")
    
    if st.session_state.project_data['footplates']:
        res_fp = []
        for fp in st.session_state.project_data['footplates']:
            # Ambil Data
            props = edited_fp[edited_fp["Type"] == fp["Type"]].iloc[0]
            Area = props["B (m)"] * props["L (m)"]
            Pu = fp["Load (kN)"]
            
            # 1. Cek Tegangan Tanah (Bearing Capacity)
            sigma_act = Pu / Area
            status_bearing = "✅ Aman" if sigma_act <= sigma_tanah else "❌ Bahaya"
            
            # 2. Cek Geser Pons (Punching Shear)
            status_pons, cap_pons = check_punching_shear(Pu, 25, props["Tebal (mm)"], props["Kolom (mm)"])
            
            res_fp.append({
                "Node": fp["Node"], "Type": fp["Type"],
                "Beban (kN)": Pu,
                "Tegangan (kN/m2)": round(sigma_act, 1),
                "Izin Tanah": sigma_tanah,
                "Status Bearing": status_bearing,
                "Geser Pons (kN)": cap_pons,
                "Status Geser": status_pons
            })
            
        st.markdown("#### Analisa Pondasi Telapak (Footplate)")
        df_res_fp = pd.DataFrame(res_fp)
        st.dataframe(df_res_fp.style.applymap(lambda v: 'color: red;' if 'Bahaya' in str(v) or 'Gagal' in str(v) else 'color: green;', subset=['Status Bearing', 'Status Geser']))
    else:
        st.info("Belum ada Footplate yang dimodelkan.")

# ==============================================================================
# TAB 5: RAB & BOQ (AHSP SE 182)
# ==============================================================================
with tab_rab:
    st.subheader("💰 Bill of Quantities & Cost Estimate")
    
    # --- HITUNG VOLUME ---
    boq_data = []
    
    # 1. Volume Footplate
    vol_beton_fp = 0
    vol_galian_fp = 0
    berat_besi_fp = 0
    
    for fp in st.session_state.project_data['footplates']:
        props = edited_fp[edited_fp["Type"] == fp["Type"]].iloc[0]
        # Vol Beton
        v_conc = props["B (m)"] * props["L (m)"] * (props["Tebal (mm)"]/1000)
        vol_beton_fp += v_conc
        
        # Vol Galian (Simplifikasi: Tegak lurus + space kerja 20cm)
        v_dig = (props["B (m)"]+0.4) * (props["L (m)"]+0.4) * depth_tanah
        vol_galian_fp += v_dig
        
        # Besi (Asumsi rasio 120 kg/m3 untuk pondasi)
        berat_besi_fp += v_conc * 120 
    
    # 2. Volume Batu Belah
    vol_pas_batu = 0
    vol_galian_batu = 0
    
    for r in st.session_state.project_data['rubbles']:
        props = edited_batu[edited_batu["Type"] == r["Type"]].iloc[0]
        # Panjang elemen
        n1 = df_nodes[df_nodes["ID"] == r["Start"]].iloc[0]
        n2 = df_nodes[df_nodes["ID"] == r["End"]].iloc[0]
        length = np.sqrt((n2["X"]-n1["X"])**2 + (n2["Y"]-n1["Y"])**2)
        
        # Luas Penampang Trapesium
        area_sect = (props["Lebar Atas (m)"] + props["Lebar Bawah (m)"]) / 2 * props["Tinggi (m)"]
        vol_pas_batu += area_sect * length
        
        # Galian Batu (Lebar Bawah + kerja * Dalam)
        vol_galian_batu += (props["Lebar Bawah (m)"] + 0.2) * depth_tanah * length

    # --- REKAPITULASI ---
    total_galian = vol_galian_fp + vol_galian_batu
    
    # Create Table
    rab_items = [
        {"Item": "Galian Tanah Pondasi", "Vol": total_galian, "Sat": "m3", "Harga": hsp_galian},
        {"Item": "Pasangan Batu Kali (1:4)", "Vol": vol_pas_batu, "Sat": "m3", "Harga": hsp_batu},
        {"Item": "Beton Bertulang (Footplate)", "Vol": vol_beton_fp, "Sat": "m3", "Harga": hsp_beton},
        {"Item": "Pembesian (Ulir)", "Vol": berat_besi_fp, "Sat": "kg", "Harga": hsp_besi},
    ]
    
    df_rab = pd.DataFrame(rab_items)
    df_rab["Total (Rp)"] = df_rab["Vol"] * df_rab["Harga"]
    
    st.dataframe(df_rab.style.format({
        "Vol": "{:.2f}", "Harga": "{:,.0f}", "Total (Rp)": "{:,.0f}"
    }), use_container_width=True)
    
    grand_total = df_rab["Total (Rp)"].sum()
    st.success(f"### Total Estimasi Biaya Pondasi: Rp {grand_total:,.0f}")
    
    # Download Button
    def to_excel(df):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, sheet_name='RAB', index=False)
        return output.getvalue()
        
    st.download_button("📥 Download RAB Excel", to_excel(df_rab), "RAB_Pondasi.xlsx")
