import streamlit as st
import pandas as pd
import numpy as np
import math
from streamlit_drawable_canvas import st_canvas
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- CONFIG ---
st.set_page_config(page_title="Visual BIM Estimator", layout="wide")
st.title("🏠 Visual BIM: Gambar Denah → Hitung Struktur & Biaya")
st.caption("Konsep: User menggambar denah, Python menganalisa struktur & menghitung RAB.")

# --- SIDEBAR: KONFIGURASI SKALA ---
with st.sidebar:
    st.header("⚙️ Konfigurasi Gambar")
    st.info("Tentukan skala agar gambar pixel terbaca sebagai meter.")
    # Asumsi: 1 kotak grid (20px) = 1 meter
    scale_factor = st.slider("Skala (Pixel per Meter)", 10, 50, 20)
    st.caption(f"Saat ini: {scale_factor} pixel = 1 meter")
    
    st.divider()
    st.header("💰 Harga Satuan (HSD)")
    hsp_beton = st.number_input("Beton Struktur (Rp/m3)", 4500000)
    hsp_dinding = st.number_input("Dinding Bata (Rp/m2)", 250000)

# --- TAB NAVIGASI ---
tab_draw, tab_vis, tab_rab = st.tabs(["1️⃣ Gambar Denah", "2️⃣ Visualisasi Struktur", "3️⃣ RAB Otomatis"])

# ==============================================================================
# TAB 1: CANVAS GAMBAR (INPUT VISUAL)
# ==============================================================================
with tab_draw:
    st.markdown("""
    ### 🖱️ Area Gambar Denah
    **Cara Pakai:**
    1. Pilih tool **'Rect'** (Kotak) di menu kiri kanvas.
    2. Gambar kotak-kotak ruangan (Kamar, Ruang Tamu, dll).
    3. Python akan otomatis membaca dimensi ruangan Anda.
    """)
    
    # Inisialisasi Canvas
    # stroke_color: Warna garis, bg_color: Warna background grid
    canvas_result = st_canvas(
        fill_color="rgba(46, 134, 193, 0.3)",  # Warna isi kotak (biru transparan)
        stroke_width=2,
        stroke_color="#000000",
        background_color="#f0f2f6",
        background_image=None,
        update_streamlit=True,
        height=400,
        width=600,
        drawing_mode="rect", # Mode menggambar kotak
        key="canvas",
    )

    # PROSES DATA DARI GAMBAR
    rooms_data = []
    if canvas_result.json_data is not None:
        objects = canvas_result.json_data["objects"]
        
        for i, obj in enumerate(objects):
            # Ambil data pixel
            w_px = obj["width"]
            h_px = obj["height"]
            left = obj["left"]
            top = obj["top"]
            
            # Konversi Pixel ke Meter
            w_m = w_px / scale_factor
            h_m = h_px / scale_factor
            
            # Analisa Struktur Sederhana per Ruangan
            bentang = max(w_m, h_m)
            if bentang <= 3: 
                dim_balok = "15/20"
            elif bentang <= 5: 
                dim_balok = "20/30"
            else: 
                dim_balok = "25/40 (Butuh Perhatian!)"
            
            rooms_data.append({
                "ID": i+1,
                "Ruangan": f"Ruang-{i+1}",
                "P (m)": round(w_m, 2),
                "L (m)": round(h_m, 2),
                "Luas (m2)": round(w_m * h_m, 2),
                "Keliling (m')": round(2 * (w_m + h_m), 2),
                "Bentang Max": round(bentang, 2),
                "Rec. Balok": dim_balok,
                # Koordinat untuk Visualisasi nanti
                "x": left, "y": top, "w_px": w_px, "h_px": h_px
            })

    # Tampilkan Data Mentah di bawah Canvas
    if rooms_data:
        df_rooms = pd.DataFrame(rooms_data)
        st.dataframe(df_rooms[["ID", "Ruangan", "P (m)", "L (m)", "Luas (m2)", "Rec. Balok"]])
    else:
        st.info("Silakan gambar kotak di area canvas di atas.")

# ==============================================================================
# TAB 2: VISUALISASI TEKNIS (CEK GAMBAR)
# ==============================================================================
with tab_vis:
    st.header("🏗️ Digital Twin: Analisa Struktur")
    
    if not rooms_data:
        st.warning("Belum ada gambar. Silakan gambar di Tab 1.")
    else:
        col_v1, col_v2 = st.columns([3, 1])
        
        with col_v1:
            # MEMBUAT PLOT BLUEPRINT
            fig, ax = plt.subplots(figsize=(8, 6))
            
            # Loop data ruangan untuk digambar ulang di Matplotlib
            for room in rooms_data:
                # Gambar Ruangan
                rect = patches.Rectangle(
                    (room["x"], 400 - room["y"] - room["h_px"]), # Matplotlib y-axis is inverted vs Screen
                    room["w_px"], room["h_px"], 
                    linewidth=2, edgecolor='black', facecolor='none'
                )
                ax.add_patch(rect)
                
                # Gambar Kolom di 4 Sudut
                # Asumsi kolom praktis di setiap sudut ruangan
                corners = [
                    (room["x"], 400 - room["y"]), 
                    (room["x"] + room["w_px"], 400 - room["y"]),
                    (room["x"], 400 - room["y"] - room["h_px"]),
                    (room["x"] + room["w_px"], 400 - room["y"] - room["h_px"])
                ]
                for cx, cy in corners:
                    col_rect = patches.Rectangle((cx-2, cy-2), 4, 4, color='red') # Kolom merah
                    ax.add_patch(col_rect)
                
                # Label Bentang
                cx = room["x"] + room["w_px"]/2
                cy = 400 - room["y"] - room["h_px"]/2
                ax.text(cx, cy, f"{room['P (m)']}x{room['L (m)']}m\n{room['Rec. Balok']}", 
                        ha='center', va='center', fontsize=8, color='blue')

            ax.set_xlim(0, 600)
            ax.set_ylim(0, 400)
            ax.set_aspect('equal')
            ax.axis('off') # Hilangkan axis angka
            ax.set_title("Blueprint Struktur (Merah = Titik Kolom)", fontsize=10)
            st.pyplot(fig)
            
            
            
        with col_v2:
            st.markdown("### 🔍 Cek Struktur")
            total_luas = df_rooms["Luas (m2)"].sum()
            max_b = df_rooms["Bentang Max"].max()
            
            st.metric("Total Luas Bangunan", f"{total_luas} m2")
            st.metric("Bentang Terlebar", f"{max_b} m")
            
            if max_b > 4.5:
                st.error("⚠️ Perhatian: Ada bentang > 4.5m. Sistem merekomendasikan Balok Struktural Besar.")
            else:
                st.success("✅ Struktur Aman (Standar Rumah Tinggal).")

# ==============================================================================
# TAB 3: RAB OTOMATIS
# ==============================================================================
with tab_rab:
    st.header("💰 Estimasi Biaya (RAB)")
    
    if rooms_data:
        # LOGIKA PERHITUNGAN VOLUME (BIM LOGIC)
        # 1. Total Keliling Dinding
        keliling_total = df_rooms["Keliling (m')"].sum()
        
        # 2. Volume Beton (Sloof + Kolom + Ring Balok)
        # Asumsi rata-rata dimensi struktur 15x20 cm sepanjang keliling dinding (Sloof & Ringbalok)
        # Ditambah kolom setinggi 3.5m setiap sudut (Estimasi kasar)
        vol_beton_m3 = (keliling_total * 0.15 * 0.20 * 2) + (len(rooms_data) * 4 * 3.5 * 0.15 * 0.15)
        
        # 3. Luas Dinding
        # Tinggi dinding 3.5m, dikurangi pintu/jendela (20%)
        luas_dinding_m2 = (keliling_total * 3.5) * 0.8
        
        # TABEL RAB
        data_rab = {
            "Uraian Pekerjaan": ["Pekerjaan Beton Bertulang (Struktur)", "Pekerjaan Dinding Bata (Arsitek)"],
            "Volume": [vol_beton_m3, luas_dinding_m2],
            "Satuan": ["m3", "m2"],
            "Harga Satuan (Rp)": [hsp_beton, hsp_dinding],
            "Total (Rp)": [vol_beton_m3*hsp_beton, luas_dinding_m2*hsp_dinding]
        }
        
        df_rab = pd.DataFrame(data_rab)
        st.dataframe(df_rab.style.format({"Volume": "{:.2f}", "Harga Satuan (Rp)": "{:,.0f}", "Total (Rp)": "{:,.0f}"}), use_container_width=True)
        
        st.success(f"### Total Estimasi: Rp {df_rab['Total (Rp)'].sum():,.0f}")
    else:
        st.warning("Silakan gambar denah dulu.")
