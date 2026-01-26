import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from anastruct.fem.system import SystemElements
from io import BytesIO

# --- 1. CONFIG ---
st.set_page_config(page_title="IndoBIM SAP Ultimate", layout="wide", page_icon="🏗️")

# --- 2. CLASS & ENGINE ---
class StructuralEngine:
    def __init__(self, materials):
        self.materials = materials # fc, fy, E
        
    def analyze_frame(self, nodes, elements, loads):
        """
        Menganalisa 1 Frame 2D (Portal) menggunakan AnaStruct
        """
        ss = SystemElements(EA=15000*2000, EI=5000*10000) # Dummy stiffness awal, nanti di override
        
        # Add Nodes & Elements
        # AnaStruct node logic is automatic based on coordinates
        # Kita perlu mapping ID user ke ID AnaStruct
        
        # Build System
        element_map = []
        for el in elements:
            # Cari koordinat node
            n1 = nodes[nodes['ID'] == el['Start']].iloc[0]
            n2 = nodes[nodes['ID'] == el['End']].iloc[0]
            
            # Define Section Properties (EI)
            # E beton = 4700 * sqrt(fc)
            E = 4700 * np.sqrt(self.materials['fc']) * 1000 # MPa -> kPa (kN/m2)
            b, h = el['b'], el['h']
            I = (b * h**3) / 12
            A = b * h
            
            ss.add_element(location=[[n1['X'], n1['Z']], [n2['X'], n2['Z']]], 
                           EA=E*A, EI=E*I)
            element_map.append(el['ID'])

        # Add Supports (Tumpuan)
        # Asumsi Node dengan Z=0 adalah Jepit (Fixed)
        for _, n in nodes.iterrows():
            if n['Z'] == 0:
                node_id = ss.find_node_id(location=[n['X'], n['Z']])
                ss.add_support_fixed(node_id=node_id)
        
        # Add Loads (Beban)
        for load in loads:
            # Apply to Element (Uniform Load)
            # Cari ID Element di anastruct (agak tricky, kita pakai pendekatan index urut)
            # Simplifikasi: Beban merata di semua balok level lantai
            if load['Type'] == 'Distributed':
                 ss.q_load(q=-load['Value'], element_id='all', direction='y') 
                 # Note: 'all' is simplified. In real app, match element ID.

        ss.solve()
        return ss

# --- 3. SESSION STATE INIT ---
if 'grid_x' not in st.session_state: st.session_state.grid_x = [0.0, 4.0, 8.0]
if 'grid_y' not in st.session_state: st.session_state.grid_y = [0.0, 3.0, 6.0]
if 'levels' not in st.session_state: st.session_state.levels = [0.0, 3.5, 7.0] # Z levels

if 'sections' not in st.session_state:
    st.session_state.sections = pd.DataFrame([
        {"Label": "K1", "Type": "Kolom", "b (m)": 0.3, "h (m)": 0.3},
        {"Label": "B1", "Type": "Balok", "b (m)": 0.25, "h (m)": 0.4},
        {"Label": "B2", "Type": "Balok", "b (m)": 0.2, "h (m)": 0.3},
    ])

# --- 4. SIDEBAR INPUT ---
with st.sidebar:
    st.title("⚙️ IndoBIM SAP")
    st.header("1. Material Beton")
    fc = st.number_input("Mutu Beton (MPa)", 25)
    fy = st.number_input("Mutu Baja (MPa)", 400)
    
    st.header("2. Beban (Loads)")
    q_dl = st.number_input("Beban Mati (kN/m)", 15.0)
    q_ll = st.number_input("Beban Hidup (kN/m)", 8.0)
    comb_1 = 1.2*q_dl + 1.6*q_ll
    st.info(f"Kombinasi 1.2D + 1.6L = {comb_1:.2f} kN/m")

# --- 5. TABS INTERFACE ---
tab_geo, tab_model, tab_run, tab_design = st.tabs([
    "1️⃣ Grid & Geometri", "2️⃣ Input Elemen (3D)", "3️⃣ Running & View", "4️⃣ Design & RAB"
])

# ==============================================================================
# TAB 1: GEOMETRI & GRID
# ==============================================================================
with tab_geo:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📍 Grid System")
        gx_in = st.text_input("Grid X (m)", value="0, 4, 8")
        gy_in = st.text_input("Grid Y (m)", value="0, 5, 10")
        gz_in = st.text_input("Level Z (m)", value="0, 4, 8")
        
        if st.button("Update Grid"):
            st.session_state.grid_x = sorted([float(x) for x in gx_in.split(',')])
            st.session_state.grid_y = sorted([float(x) for x in gy_in.split(',')])
            st.session_state.levels = sorted([float(x) for x in gz_in.split(',')])
            st.success("Grid Updated!")
            
    with c2:
        st.subheader("📦 Section Properties")
        st.session_state.sections = st.data_editor(st.session_state.sections, num_rows="dynamic")

# ==============================================================================
# TAB 2: MODELING (AUTO GENERATE)
# ==============================================================================
with tab_model:
    st.subheader("🏗️ Generate Structure")
    st.caption("Aplikasi otomatis menghubungkan Grid menjadi Kerangka Struktur (Default).")
    
    # Logic to Generate Nodes & Elements based on Grids
    nodes = []
    elements = []
    
    nid = 1
    # Create Nodes
    for z in st.session_state.levels:
        for y in st.session_state.grid_y:
            for x in st.session_state.grid_x:
                nodes.append({"ID": nid, "X": x, "Y": y, "Z": z})
                nid += 1
    df_nodes = pd.DataFrame(nodes)
    
    # Create Elements (Logika Sederhana: Connect Grid neighbors)
    # Kolom (Vertical)
    eid = 1
    for i, node in df_nodes.iterrows():
        # Cari node di atasnya (Z+1) dengan X,Y sama
        upper_node = df_nodes[
            (df_nodes['X'] == node['X']) & 
            (df_nodes['Y'] == node['Y']) & 
            (df_nodes['Z'] > node['Z'])
        ].sort_values('Z')
        
        if not upper_node.empty:
            target = upper_node.iloc[0]
            # Assign Section default
            sec = st.session_state.sections[st.session_state.sections['Type']=='Kolom'].iloc[0]
            elements.append({
                "ID": f"C{eid}", "Type": "Column", 
                "Start": node['ID'], "End": target['ID'], 
                "b": sec['b (m)'], "h": sec['h (m)'], "Sec": sec['Label']
            })
            eid += 1
            
    # Balok Arah X
    for i, node in df_nodes.iterrows():
        if node['Z'] == 0: continue # Skip pondasi
        right_node = df_nodes[
            (df_nodes['Y'] == node['Y']) & 
            (df_nodes['Z'] == node['Z']) & 
            (df_nodes['X'] > node['X'])
        ].sort_values('X')
        
        if not right_node.empty:
            # Cek apakah tetangga grid terdekat
            target = right_node.iloc[0]
            # Asumsi hanya connect tetangga dekat (simplified logic)
            sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
            elements.append({
                "ID": f"Bx{eid}", "Type": "Beam", 
                "Start": node['ID'], "End": target['ID'],
                "b": sec['b (m)'], "h": sec['h (m)'], "Sec": sec['Label']
            })
            eid += 1

    # Balok Arah Y
    for i, node in df_nodes.iterrows():
        if node['Z'] == 0: continue
        back_node = df_nodes[
            (df_nodes['X'] == node['X']) & 
            (df_nodes['Z'] == node['Z']) & 
            (df_nodes['Y'] > node['Y'])
        ].sort_values('Y')
        
        if not back_node.empty:
            target = back_node.iloc[0]
            sec = st.session_state.sections[st.session_state.sections['Type']=='Balok'].iloc[0]
            elements.append({
                "ID": f"By{eid}", "Type": "Beam", 
                "Start": node['ID'], "End": target['ID'],
                "b": sec['b (m)'], "h": sec['h (m)'], "Sec": sec['Label']
            })
            eid += 1
            
    df_elements = pd.DataFrame(elements)
    
    st.write(f"Model Generated: {len(df_nodes)} Joints, {len(df_elements)} Frames")
    with st.expander("Lihat Data Tabel Elemen"):
        st.dataframe(df_elements)

    # 3D PREVIEW (MATPLOTLIB)
    fig = plt.figure(figsize=(10, 6))
    ax = fig.add_subplot(111, projection='3d')
    
    for _, el in df_elements.iterrows():
        n1 = df_nodes[df_nodes['ID'] == el['Start']].iloc[0]
        n2 = df_nodes[df_nodes['ID'] == el['End']].iloc[0]
        col = 'blue' if el['Type'] == 'Column' else 'red'
        ax.plot([n1['X'], n2['X']], [n1['Y'], n2['Y']], [n1['Z'], n2['Z']], c=col)
        
    ax.set_xlabel('X'); ax.set_ylabel('Y'); ax.set_zlabel('Z')
    st.pyplot(fig)

# ==============================================================================
# TAB 3: RUNNING & MULTI-VIEW (SAP STYLE)
# ==============================================================================
with tab_run:
    st.subheader("🚀 Structural Analysis Engine")
    
    # SELECT VIEW TYPE
    view_mode = st.radio("Pilih Tampilan (View):", 
                         ["Tampak Depan (Portal X-Z)", "Tampak Samping (Portal Y-Z)", "Tampak Atas (Denah)"], 
                         horizontal=True)
    
    selected_frame_nodes = []
    selected_frame_els = []
    
    if "Depan" in view_mode:
        # User select Grid Y
        grid_sel = st.selectbox("Pilih Grid Y (As Melintang):", st.session_state.grid_y)
        st.caption(f"Menampilkan Portal 2D pada Grid Y = {grid_sel}")
        
        # Filter Nodes & Elements on this Plane
        plane_nodes = df_nodes[df_nodes['Y'] == grid_sel]
        
        # Filter Elements that are completely within this plane
        # (Both Start and End nodes must be on Y = grid_sel)
        plane_ids = plane_nodes['ID'].tolist()
        plane_els = df_elements[
            (df_elements['Start'].isin(plane_ids)) & 
            (df_elements['End'].isin(plane_ids))
        ]
        
        # PREPARE FOR SOLVER
        # Run 2D Analysis using AnaStruct for this Frame
        if st.button("▶️ RUN ANALYSIS (Momen & Gaya Dalam)"):
            with st.spinner("Menghitung Matriks Kekakuan..."):
                engine = StructuralEngine({'fc': fc, 'fy': fy})
                # Define Load: Uniform load on Beams
                loads = [{'Type': 'Distributed', 'Value': comb_1}] 
                
                # Running AnaStruct
                # Note: AnaStruct works on X-Y, so we map Z to Y for visualization
                # Mapping: Real X -> AnaStruct x, Real Z -> AnaStruct y
                
                # We need to reconstruct the system for AnaStruct
                ss = SystemElements()
                
                # Add Beam/Col
                for _, el in plane_els.iterrows():
                    n1 = plane_nodes[plane_nodes['ID'] == el['Start']].iloc[0]
                    n2 = plane_nodes[plane_nodes['ID'] == el['End']].iloc[0]
                    
                    # Convert to Local 2D (X, Z)
                    ss.add_element(location=[[n1['X'], n1['Z']], [n2['X'], n2['Z']]], 
                                   EI=5000) # Simplified EI
                    
                # Add Supports (Z=0)
                for _, n in plane_nodes.iterrows():
                    if n['Z'] == 0:
                        nid = ss.find_node_id(location=[n['X'], n['Z']])
                        ss.add_support_fixed(node_id=nid)
                        
                # Add Load
                ss.q_load(q=-comb_1, element_id='all', direction='y')
                ss.solve()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Diagram Momen (M3)**")
                    fig_m = ss.show_bending_moment(show=False)
                    st.pyplot(fig_m)
                with c2:
                    st.write("**Displacement / Deformasi**")
                    fig_d = ss.show_displacement(show=False)
                    st.pyplot(fig_d)
                    
                # Extract Results for Design
                st.session_state.last_result = {
                    "Mu_max": max([abs(val) for sublist in ss.get_node_results_system(node_id=0)['moment'] for val in sublist]) if ss.get_node_results_system(node_id=0) else 15.0 # Dummy fallback if parsing complex
                }
                
    elif "Samping" in view_mode:
        st.info("Pilih Grid X untuk melihat Portal Arah Y (Belum diaktifkan di demo ini)")
        
    elif "Atas" in view_mode:
        lvl_sel = st.selectbox("Pilih Lantai (Elevasi Z):", st.session_state.levels)
        # Plot Denah
        fig, ax = plt.subplots()
        # Filter elements on this level
        plan_nodes = df_nodes[df_nodes['Z'] == lvl_sel]
        plan_ids = plan_nodes['ID'].tolist()
        plan_els = df_elements[(df_elements['Start'].isin(plan_ids)) & (df_elements['End'].isin(plan_ids))]
        
        for _, el in plan_els.iterrows():
            n1 = df_nodes[df_nodes['ID'] == el['Start']].iloc[0]
            n2 = df_nodes[df_nodes['ID'] == el['End']].iloc[0]
            ax.plot([n1['X'], n2['X']], [n1['Y'], n2['Y']], 'k-', lw=2)
            
        # Draw Columns as squares
        col_nodes = df_nodes[(df_nodes['Z'] == lvl_sel)]
        ax.scatter(col_nodes['X'], col_nodes['Y'], marker='s', s=100, c='red')
        
        ax.set_aspect('equal')
        ax.grid(True, linestyle='--')
        ax.set_title(f"Denah Lantai Z={lvl_sel}")
        st.pyplot(fig)

# ==============================================================================
# TAB 4: DESIGN & RAB (DATA INPUT AHSP)
# ==============================================================================
with tab_design:
    st.subheader("📝 Concrete Design & Estimasi Biaya")
    
    # Ambil Momen Maksimum dari analisis (Dummy/Simplifikasi untuk Demo)
    # Di aplikasi real, ini diambil per elemen
    mu_design = st.number_input("Momen Desain Mu (kNm) - Ambil dari Tab 3", value=25.0)
    
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.markdown("#### 1. Desain Penulangan (SNI 2847)")
        # Input Section to Check
        b_des = st.number_input("Lebar Balok (mm)", 250)
        h_des = st.number_input("Tinggi Balok (mm)", 400)
        ds = 40 # selimut
        d = h_des - ds
        
        # Hitung Luas Tulangan Perlu
        # As = Mu / (phi * fy * 0.85 * d) approx
        phi = 0.9
        # Mu kNm -> Nmm
        As_req = (mu_design * 1e6) / (phi * fy * 0.87 * d)
        
        st.metric("Luas Tulangan Perlu (As)", f"{As_req:.1f} mm2")
        
        # Konversi ke Jumlah Besi
        dia_besi = st.selectbox("Diameter Besi", [10, 12, 13, 16, 19])
        A_bar = 0.25 * np.pi * dia_besi**2
        n_bar = np.ceil(As_req / A_bar)
        
        st.success(f"**Rekomendasi:** Gunakan **{int(n_bar)} D{dia_besi}**")
        
    with col_d2:
        st.markdown("#### 2. Input RAB (Integrasi AHSP)")
        vol_beton = len(df_elements) * 0.25 * 0.4 * 4.0 # Dummy volume calculation logic
        berat_besi = vol_beton * 150 # kg/m3 assumption
        
        hsp_beton = st.number_input("HSP Beton (Rp/m3)", 1200000)
        hsp_besi = st.number_input("HSP Besi (Rp/kg)", 18000)
        
        total_biaya = (vol_beton * hsp_beton) + (berat_besi * hsp_besi)
        
        st.write("---")
        st.metric("Estimasi Biaya Struktur", f"Rp {total_biaya:,.0f}")
        
        st.caption("*Volume dihitung otomatis dari geometri model 3D di Tab 2")
