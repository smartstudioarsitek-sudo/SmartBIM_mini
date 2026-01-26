import streamlit as st
import pandas as pd
import math

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Smart House Estimator", layout="wide")

# --- CSS CUSTOM UNTUK TAMPILAN MODERN ---
st.markdown("""
<style>
    .big-font { font-size:20px !important; font-weight: bold; color: #2E86C1; }
    .step-box { background-color: #F0F3F4; padding: 20px; border-radius: 10px; border-left: 5px solid #2E86C1; }
    .result-box { background-color: #D5F5E3; padding: 20px; border-radius: 10px; border-left: 5px solid #27AE60; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Smart House Estimator: Logic & Cost")
st.caption("Alur: Input Ruangan → Analisa Struktur Otomatis → RAB Keluar")

# --- INISIALISASI SESSION STATE (AGAR DATA TERSIMPAN SAAT PINDAH TAB) ---
if 'ruangan' not in st.session_state:
    st.session_state['ruangan'] = []
if 'total_luas' not in st.session_state:
    st.session_state['total_luas'] = 0

# --- FUNGSI LOGIKA STRUKTUR (MOMEN & DIMENSI) ---
def analisa_struktur_balok(bentang_terpanjang):
    # Rule of Thumb Struktur Beton (SNI Sederhana)
    # Tinggi Balok (h) = 1/12 s.d 1/10 Bentang
    # Lebar Balok (b) = 1/2 s.d 2/3 Tinggi Balok
    
    h_perlu = bentang_terpanjang / 12 
    h_rekom = math.ceil(h_perlu * 100) # cm
    
    # Standarisasi Dimensi (misal kelipatan 5cm)
    if h_rekom < 20: h_rekom = 20
    
    b_rekom = math.ceil((h_rekom / 2))
    
    # Analisa Besi (Pendekatan Momen Sederhana ql^2/8)
    # Asumsi beban 2 ton/m (tembok + plat)
    q = 2000 # kg/m
    L = bentang_terpanjang
    Mu = (1/8) * q * (L**2) # kg.m
    
    # Rekomendasi Besi Utama
    if L <= 3: besi = "4 D10"
    elif L <= 4: besi = "4 D12"
    elif L <= 5: besi = "6 D12"
    else: besi = "6 D16 (Perlu Hitungan Detail!)"
    
    return h_rekom, b_rekom, Mu, besi

# --- TAB NAVIGASI ---
tab1, tab2, tab3 = st.tabs(["1️⃣ Denah & Ruang", "2️⃣ Cek Struktur", "3️⃣ RAB Final"])

# ==============================================================================
# TAB 1: INPUT DENAH (USER FRIENDLY)
# ==============================================================================
with tab1:
    st.markdown('<div class="step-box">Langkah 1: Masukkan daftar ruangan yang akan dibangun. Sistem akan menghitung luas & keliling otomatis.</div>', unsafe_allow_html=True)
    
    col_in1, col_in2, col_in3 = st.columns([2, 1, 1])
    with col_in1:
        nama_ruang = st.text_input("Nama Ruangan", placeholder="Contoh: Kamar Tidur Utama")
    with col_in2:
        panjang = st.number_input("Panjang (m)", min_value=1.0, value=3.0, step=0.5)
    with col_in3:
        lebar = st.number_input("Lebar (m)", min_value=1.0, value=3.0, step=0.5)
        
    if st.button("➕ Tambah Ruangan"):
        luas = panjang * lebar
        keliling = 2 * (panjang + lebar)
        # Simpan ke Session State
        st.session_state['ruangan'].append({
            "Nama": nama_ruang,
            "P": panjang,
            "L": lebar,
            "Luas (m2)": luas,
            "Keliling (m')": keliling
        })
        st.success(f"Ruangan '{nama_ruang}' ditambahkan!")

    # Tampilkan Tabel Ruangan
    if len(st.session_state['ruangan']) > 0:
        st.divider()
        df_ruang = pd.DataFrame(st.session_state['ruangan'])
        st.dataframe(df_ruang, use_container_width=True)
        
        # --- PERBAIKAN DI SINI ---
        # Hitung dulu di luar f-string agar tidak SyntaxError
        total_l = df_ruang["Luas (m2)"].sum()
        total_k = df_ruang["Keliling (m')"].sum() # Hitung keliling di variabel terpisah
        max_bentang = df_ruang[["P", "L"]].max().max()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Luas Lantai", f"{total_l} m2")
        c2.metric("Total Panjang Dinding (Kotor)", f"{total_k} m'") # Panggil variabelnya saja
        c3.metric("Bentang Ruang Terlebar", f"{max_bentang} m")
# ==============================================================================
# TAB 2: ANALISA STRUKTUR (THE LOGIC)
# ==============================================================================
with tab2:
    if len(st.session_state['ruangan']) == 0:
        st.warning("⚠️ Harap isi Data Ruangan di Tab 1 terlebih dahulu.")
    else:
        st.markdown('<div class="step-box">Langkah 2: Berdasarkan denah di Tab 1, sistem menganalisa kebutuhan struktur agar rumah aman namun efisien.</div>', unsafe_allow_html=True)
        
        # Ambil data dari Tab 1
        df_ruang = pd.DataFrame(st.session_state['ruangan'])
        bentang_max = df_ruang[["P", "L"]].max().max()
        
        # Panggil Fungsi Analisa
        h_balok, b_balok, Momen, Tulangan = analisa_struktur_balok(bentang_max)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.subheader("🔍 Analisa Beban")
            st.info(f"Bentang Terpanjang: **{bentang_max} meter**")
            st.write(f"Estimasi Momen Lentur (Mu): **{Momen/1000:.2f} Ton.m**")
            
            if bentang_max > 5:
                st.error("⚠️ Peringatan: Ada ruangan dengan bentang > 5 meter. Wajib pakai kolom praktis tambahan atau konsultasi sipil.")
            else:
                st.success("✅ Bentang aman untuk struktur rumah tinggal standar.")
                
        with col_s2:
            st.subheader("🛠️ Rekomendasi Dimensi")
            st.markdown(f"""
            Untuk menahan beban di atas, sistem merekomendasikan:
            * **Dimensi Balok Gantung:** {b_balok} x {h_balok} cm
            * **Dimensi Kolom Utama:** {b_balok} x {b_balok} cm
            * **Penulangan Utama:** {Tulangan}
            * **Begel/Sengkang:** Ø8 - 150 mm
            """)
            
        st.divider()
        st.caption("User Override (Jika ingin mengubah rekomendasi):")
        c_ov1, c_ov2 = st.columns(2)
        final_b = c_ov1.number_input("Lebar Beton (cm)", value=int(b_balok))
        final_h = c_ov2.number_input("Tinggi Beton (cm)", value=int(h_balok))

# ==============================================================================
# TAB 3: RAB FINAL (OUTPUT)
# ==============================================================================
with tab3:
    if len(st.session_state['ruangan']) == 0:
        st.warning("⚠️ Data kosong.")
    else:
        st.markdown('<div class="result-box">Langkah 3: Berikut adalah estimasi biaya berdasarkan Volume Ruangan & Dimensi Struktur.</div>', unsafe_allow_html=True)
        
        # INPUT HARGA CEPAT
        with st.expander("💰 Update Harga Satuan (HSD)", expanded=False):
            h_beton = st.number_input("HSP Beton Struktur /m3", value=4500000)
            h_dinding = st.number_input("HSP Pas. Bata + Plester /m2", value=250000)
            h_lantai = st.number_input("HSP Keramik /m2", value=180000)
            h_plafon = st.number_input("HSP Plafon /m2", value=120000)
            
        # HITUNG VOLUME OTOMATIS
        # 1. Volume Struktur (Kolom + Balok)
        # Asumsi panjang balok = total keliling dinding
        # Asumsi kolom = setiap 3 meter ada kolom (Keliling / 3)
        total_keliling = df_ruang["Keliling (m')"].sum()
        total_luas = df_ruang["Luas (m2)"].sum()
        
        vol_balok = total_keliling * (final_b/100) * (final_h/100)
        
        jml_kolom = math.ceil(total_keliling / 3.0)
        vol_kolom = jml_kolom * 3.5 * (final_b/100) * (final_b/100) # Tinggi kolom 3.5m
        
        vol_beton_total = vol_balok + vol_kolom
        
        # 2. Volume Arsitek
        luas_dinding_kotor = total_keliling * 3.5 # Tinggi 3.5m
        luas_pintu_jendela = luas_dinding_kotor * 0.15 # Asumsi 15% bukaan
        luas_dinding_net = luas_dinding_kotor - luas_pintu_jendela
        
        # TABULASI RAB
        data_rab = [
            ["1", "Pekerjaan Struktur (Beton Bertulang)", f"{vol_beton_total:.2f}", "m3", h_beton],
            ["2", "Pekerjaan Dinding (Bata, Plester, Cat)", f"{luas_dinding_net:.2f}", "m2", h_dinding],
            ["3", "Pekerjaan Lantai (Keramik)", f"{total_luas:.2f}", "m2", h_lantai],
            ["4", "Pekerjaan Plafon & Atap", f"{total_luas:.2f}", "m2", h_plafon]
        ]
        
        df_rab = pd.DataFrame(data_rab, columns=["No", "Uraian", "Volume", "Satuan", "Harga Satuan"])
        df_rab["Volume"] = df_rab["Volume"].astype(float)
        df_rab["Total Harga"] = df_rab["Volume"] * df_rab["Harga Satuan"]
        
        st.dataframe(df_rab.style.format({"Total Harga": "{:,.0f}", "Harga Satuan": "{:,.0f}"}), use_container_width=True)
        
        grand_total = df_rab["Total Harga"].sum()
        st.success(f"### 🏷️ Estimasi Biaya Fisik: Rp {grand_total:,.0f}")
        st.caption(f"Harga per m2 Bangunan: Rp {grand_total/total_luas:,.0f} /m2")

