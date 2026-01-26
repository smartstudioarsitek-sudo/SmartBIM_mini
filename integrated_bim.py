import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

# --- CONFIG ---
st.set_page_config(page_title="IndoBIM Integrated", layout="wide", page_icon="🏗️")

# --- SESSION STATE INITIALIZATION (Database Sementara) ---
if 'nodes' not in st.session_state:
    # Default: 4 Titik (Membentuk persegi 4x4 meter)
    st.session_state.nodes = pd.DataFrame([
        {"Node ID": 1, "X (m)": 0.0, "Y (m)": 0.0, "Z (m)": 0.0},
        {"Node ID": 2, "X (m)": 4.0, "Y (m)": 0.0, "Z (m)": 0.0},
        {"Node ID": 3, "X (m)": 4.0, "Y (m)": 4.0, "Z (m)": 0.0},
        {"Node ID": 4, "X (m)": 0.0, "Y (m)": 4.0, "Z (m)": 0.0},
        {"Node ID": 5, "X (m)": 0.0, "Y (m)": 0.0, "Z (m)": 3.5},
        {"Node ID": 6, "X (m)": 4.0, "Y (m)": 0.0, "Z (m)": 3.5},
        {"Node ID": 7, "X (m)": 4.0, "Y (m)": 4.0, "Z (m)": 3.5},
        {"Node ID": 8, "X (m)": 0.0, "Y (m)": 4.0, "Z (m)": 3.5},
    ])

if 'frames' not in st.session_state:
    # Default: Kolom dan Balok menghubungkan node di atas
    st.session_state.frames = pd.DataFrame([
        # Kolom (Vertical)
        {"Element ID": "K1-1", "Start Node": 1, "End Node": 5, "Type": "Kolom K1"},
        {"Element ID": "K1-2", "Start Node": 2, "End Node": 6, "Type": "Kolom K1"},
        {"Element ID": "K1-3", "Start Node": 3, "End Node": 7, "Type": "Kolom K1"},
        {"Element ID": "K1-4", "Start Node": 4, "End Node": 8, "Type": "Kolom K1"},
        # Balok (Horizontal di atas)
        {"Element ID": "B1-1", "Start Node": 5, "End Node": 6, "Type": "Balok B1"},
        {"Element ID": "B1-2", "Start Node": 6, "End Node": 7, "Type": "Balok B1"},
        {"Element ID": "B1-3", "Start Node": 7, "End Node": 8, "Type": "Balok B1"},
        {"Element ID": "B1-4", "Start Node": 8, "End Node": 5, "Type": "Balok B1"},
    ])

if 'profiles' not in st.session_state:
    # Database Profil (Revit Families)
    st.session_state.profiles = pd.DataFrame([
        {"Type": "Kolom K1", "b (mm)": 300, "h (mm)": 300, "Tulangan (kg/m3)": 150},
        {"Type": "Kolom K2", "b (mm)": 150, "h (mm)": 150, "Tulangan (kg/m3)": 120},
        {"Type": "Balok B1", "b (mm)": 200, "h (mm)": 400, "Tulangan (kg/m3)": 160},
        {"Type": "Balok B2", "b (mm)": 150, "h (mm)": 250, "Tulangan (kg/m3)": 130},
        {"Type": "Sloof S1", "b (mm)": 200, "h (mm)": 300, "Tulangan (kg/m3)": 140},
    ])

# --- HELPER FUNCTIONS ---
def get_node_coords(node_id, nodes_df):
    node = nodes_df[nodes_df["Node ID"] == node_id]
    if not node.empty:
        return node.iloc[0]["X (m)"], node.iloc[0]["Y (m)"], node.iloc[0]["Z (m)"]
    return 0, 0, 0

def calculate_length(row, nodes_df):
    x1, y1, z1 = get_node_coords(row["Start Node"], nodes_df)
    x2, y2, z2 = get_node_coords(row["End Node"], nodes_df)
    return np.sqrt((x2-x1)**2 + (y2-y1)**2 + (z2-z1)**2)

# --- SIDEBAR (Global Settings) ---
with st.sidebar:
    st.title("🏗️ IndoBIM Integrated")
    st.caption("SAP (Model) + Revit (Data) + PlanSwift (Cost)")
    st.divider()
    
    st.header("💰 Database Harga (HSD)")
    hsp_beton = st.number_input("Harga Beton (Rp/m3)", value=1100000)
    hsp_besi = st.number_input("Harga Besi Terpasang (Rp/kg)", value=18500)
    hsp_bekisting = st.number_input("Harga Bekisting (Rp/m2)", value=185000)
    
    st.divider()
    st.info("Tips: Gunakan Tab '1. Modeling' untuk mengubah koordinat dan sambungan batang.")

# --- TABS ---
tab_model, tab_data, tab_check, tab_rab = st.tabs([
    "1️⃣ Modeling (SAP Style)", 
    "2️⃣ Properties (Revit Style)", 
    "3️⃣ Analysis Check", 
    "4️⃣ PlanSwift / RAB"
])

# ==============================================================================
# TAB 1: MODELING (INPUT GRID & KOORDINAT)
# ==============================================================================
with tab_model:
    col_m1, col_m2 = st.columns([1, 2])
    
    with col_m1:
        st.subheader("📍 Step 1: Input Titik (Nodes)")
        st.caption("Definisikan titik pertemuan (Joints) seperti di SAP2000.")
        
        # Editor Nodes
        edited_nodes = st.data_editor(st.session_state.nodes, num_rows="dynamic", key="editor_nodes")
        st.session_state.nodes = edited_nodes # Save state
        
        st.subheader("🔗 Step 2: Input Batang (Frames)")
        st.caption("Hubungkan titik-titik tersebut menjadi elemen struktur.")
        
        # Dropdown options for Types based on Profile DB
        frame_config = {
            "Type": st.column_config.SelectboxColumn(
                "Profil / Family",
                options=st.session_state.profiles["Type"].unique().tolist(),
                required=True
            ),
            "Start Node": st.column_config.NumberColumn("Start Node", step=1),
            "End Node": st.column_config.NumberColumn("End Node", step=1)
        }
        
        edited_frames = st.data_editor(st.session_state.frames, num_rows="dynamic", column_config=frame_config, key="editor_frames")
        st.session_state.frames = edited_frames # Save state
        
    with col_m2:
        st.subheader("👁️ 3D Wireframe View")
        
        # Visualization Logic
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot Nodes
        nodes = st.session_state.nodes
        ax.scatter(nodes["X (m)"], nodes["Y (m)"], nodes["Z (m)"], c='red', marker='o', s=50, label='Joints')
        
        # Label Nodes
        for _, row in nodes.iterrows():
            ax.text(row["X (m)"], row["Y (m)"], row["Z (m)"], f" {int(row['Node ID'])}", fontsize=8)
            
        # Plot Frames
        frames = st.session_state.frames
        for _, row in frames.iterrows():
            x1, y1, z1 = get_node_coords(row["Start Node"], nodes)
            x2, y2, z2 = get_node_coords(row["End Node"], nodes)
            
            # Warna beda untuk Kolom vs Balok
            color = 'blue' if "Balok" in row["Type"] else 'green'
            line_width = 2 if "Balok" in row["Type"] else 3
            
            ax.plot([x1, x2], [y1, y2], [z1, z2], c=color, linewidth=line_width)
            
            # Label Element di tengah batang
            mx, my, mz = (x1+x2)/2, (y1+y2)/2, (z1+z2)/2
            ax.text(mx, my, mz, row["Type"], fontsize=6, color='grey')

        ax.set_xlabel('X (Meter)')
        ax.set_ylabel('Y (Meter)')
        ax.set_zlabel('Z (Meter)')
        ax.set_title("Visualisasi Struktur Wireframe")
        st.pyplot(fig)
        st.caption("Hijau: Kolom/Vertikal | Biru: Balok/Horizontal")

# ==============================================================================
# TAB 2: PROPERTIES (DATABASE PROFIL)
# ==============================================================================
with tab_model: # Saya gabung di tab model biar flow-nya enak, tapi logikanya "Revit"
    st.divider()
with tab_data:
    st.subheader("📚 Family & Type Manager (Revit Logic)")
    st.markdown("""
    Di sini kita mendefinisikan **"Apa itu K1?"** atau **"Apa itu B1?"**. 
    Ubah dimensi di sini, maka seluruh perhitungan RAB akan berubah otomatis (Parametrik).
    """)
    
    edited_profiles = st.data_editor(st.session_state.profiles, num_rows="dynamic", key="editor_profiles")
    st.session_state.profiles = edited_profiles
    
    st.info("Tips: 'Tulangan (kg/m3)' adalah estimasi rasio berat besi per m3 beton. Untuk rumah tinggal, kolom biasanya 150-200 kg/m3.")

# ==============================================================================
# TAB 3: ANALYSIS CHECK (SIMPLE SAFETY)
# ==============================================================================
with tab_check:
    st.subheader("⚙️ Preliminary Structural Check")
    st.write("Mengecek apakah dimensi balok/kolom masuk akal terhadap bentangnya (Rule of Thumb SNI).")
    
    # Merge Frame Data with Node Coordinates to calculate Length
    df_calc = st.session_state.frames.copy()
    df_calc["Panjang (m)"] = df_calc.apply(lambda x: calculate_length(x, st.session_state.nodes), axis=1)
    
    # Merge with Profile Data to get Dimensions
    df_calc = pd.merge(df_calc, st.session_state.profiles, on="Type", how="left")
    
    # Logic Cek
    checks = []
    for index, row in df_calc.iterrows():
        status = "✅ OK"
        note = "Aman"
        
        # Cek Balok (Tinggi min L/12)
        if "Balok" in row["Type"]:
            min_h = (row["Panjang (m)"] * 1000) / 12 # dalam mm
            if row["h (mm)"] < min_h:
                status = "⚠️ Warning"
                note = f"Terlalu Tipis (Min h={min_h:.0f}mm)"
        
        # Cek Kolom (Langsing < 4m biasanya aman untuk 30x30)
        if "Kolom" in row["Type"]:
            if row["Panjang (m)"] > 4.0 and row["b (mm)"] < 200:
                status = "⚠️ Warning"
                note = "Bahaya Tekuk (Slenderness)"

        checks.append({"ID": row["Element ID"], "Type": row["Type"], "Panjang": f"{row['Panjang (m)']:.2f} m", "Dimensi": f"{row['b (mm)']}x{row['h (mm)']}", "Status": status, "Catatan": note})
    
    st.dataframe(pd.DataFrame(checks))

# ==============================================================================
# TAB 4: PLANSWIFT / RAB (ESTIMATOR)
# ==============================================================================
with tab_rab:
    st.subheader("💰 Automated Bill of Quantities (BoQ)")
    
    if df_calc.empty:
        st.warning("Data struktur belum lengkap.")
    else:
        # 1. Hitung Volume
        # Vol Beton (m3) = b * h * L
        df_calc["Vol Beton (m3)"] = (df_calc["b (mm)"]/1000) * (df_calc["h (mm)"]/1000) * df_calc["Panjang (m)"]
        
        # Berat Besi (kg) = Vol Beton * Rasio
        df_calc["Berat Besi (kg)"] = df_calc["Vol Beton (m3)"] * df_calc["Tulangan (kg/m3)"]
        
        # Luas Bekisting (m2)
        # Balok = (2h + b) * L (Sisi bawah + 2 sisi samping) -> Asumsi sederhana
        # Kolom = (2h + 2b) * L (4 sisi)
        def calc_bekisting(row):
            if "Kolom" in row["Type"]:
                keliling = 2 * (row["b (mm)"] + row["h (mm)"]) / 1000
                return keliling * row["Panjang (m)"]
            else: # Balok
                keliling = (2 * row["h (mm)"] + row["b (mm)"]) / 1000 # Atas tidak dibekisting
                return keliling * row["Panjang (m)"]
                
        df_calc["Luas Bekisting (m2)"] = df_calc.apply(calc_bekisting, axis=1)
        
        # Tampilkan Tabel Detail
        st.markdown("#### Detail Volume per Elemen")
        st.dataframe(df_calc[["Element ID", "Type", "Panjang (m)", "Vol Beton (m3)", "Berat Besi (kg)", "Luas Bekisting (m2)"]])
        
        st.divider()
        
        # 2. Rekapitulasi & Biaya
        st.markdown("#### 📊 Rekapitulasi Biaya (RAB)")
        
        total_beton = df_calc["Vol Beton (m3)"].sum()
        total_besi = df_calc["Berat Besi (kg)"].sum()
        total_bek = df_calc["Luas Bekisting (m2)"].sum()
        
        biaya_beton = total_beton * hsp_beton
        biaya_besi = total_besi * hsp_besi
        biaya_bek = total_bek * hsp_bekisting
        
        summary_data = {
            "Uraian Pekerjaan": ["Pekerjaan Beton Struktur", "Pekerjaan Pembesian", "Pekerjaan Bekisting"],
            "Volume": [total_beton, total_besi, total_bek],
            "Satuan": ["m3", "kg", "m2"],
            "Harga Satuan": [hsp_beton, hsp_besi, hsp_bekisting],
            "Total Harga": [biaya_beton, biaya_besi, biaya_bek]
        }
        
        df_sum = pd.DataFrame(summary_data)
        st.dataframe(df_sum.style.format({
            "Volume": "{:.2f}", 
            "Harga Satuan": "Rp {:,.0f}", 
            "Total Harga": "Rp {:,.0f}"
        }), use_container_width=True)
        
        grand_total = df_sum["Total Harga"].sum()
        st.success(f"### Total Estimasi Struktur: Rp {grand_total:,.0f}")
        
        # Export Button
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='RAB')
            return output.getvalue()
            
        st.download_button("📥 Download RAB Excel", to_excel(df_sum), "RAB_IndoBIM.xlsx")
