import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import ai_engine as ai  # Import otak AI kita

# --- CONFIG PAGE ---
st.set_page_config(page_title="Smart Engine X - Agentic BIM", layout="wide", page_icon="🏗️")

# --- CSS KHUSUS CHAT ---
st.markdown("""
<style>
    .stChatMessage {background-color: #f0f2f6; border-radius: 10px; padding: 10px;}
    .user-msg {background-color: #e8f0fe;}
    .persona-badge {font-size: 12px; font-weight: bold; color: white; padding: 2px 8px; border-radius: 4px;}
    .satria {background-color: #2E86C1;}
    .budi {background-color: #27AE60;}
    .siti {background-color: #8E44AD;}
</style>
""", unsafe_allow_html=True)

# --- INIT SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = ai.SmartBIM_Agent()
if "last_data" not in st.session_state:
    st.session_state.last_data = None # Untuk menampilkan visual di Canvas kanan

# --- HEADER ---
st.title("🏗️ Smart Engine X: Autonomous Engineering Firm")
st.caption("Powered by Multi-Agent System: Ir. Satria (Struktur) • Budi (Estimator) • Siti (Drafter)")

# --- LAYOUT HYBRID (50% Chat, 50% Canvas Visual) ---
col_chat, col_canvas = st.columns([1, 1], gap="medium")

# ==========================================================
# KOLOM KIRI: INTERFACE CHAT (HORIZON 1: FRICTIONLESS UI)
# ==========================================================
with col_chat:
    st.subheader("💬 Diskusi Teknis")
    
    # Tampilkan History Chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if "persona" in message:
                # Warna badge sesuai persona
                color = "satria" if "Satria" in message["persona"] else "budi" if "Budi" in message["persona"] else "gray"
                st.markdown(f'<span class="persona-badge {color}">{message["persona"]}</span>', unsafe_allow_html=True)
            st.markdown(message["content"])

    # Input User
    if prompt := st.chat_input("Contoh: 'Hitung balok 300x600 beban 80 kNm' atau 'Berapa biayanya?'"):
        # 1. Simpan pesan user
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Proses di AI Engine (Routing ke Tools)
        with st.spinner("Sedang memanggil tenaga ahli..."):
            response = st.session_state.agent.process_query(prompt)
            
        # 3. Tampilkan Balasan AI
        st.session_state.messages.append({"role": "assistant", "content": response["text"], "persona": response["persona"]})
        
        # 4. Update State Data untuk Canvas Kanan
        if response["data"]:
            st.session_state.last_data = response["data"]
            
        # Rerun untuk update tampilan
        st.rerun()

# ==========================================================
# KOLOM KANAN: DIGITAL CANVAS (VISUALISASI REAL-TIME)
# ==========================================================
with col_canvas:
    st.subheader("📐 Canvas Kerja & Visualisasi")
    
    data = st.session_state.last_data
    
    if data is None:
        st.info("👋 Belum ada data teknis. Silakan mulai diskusi di kolom chat sebelah kiri.")
        st.markdown("""
        **Coba perintah ini:**
        - *"Tolong cek balok ukuran 300x500 dengan beban 60 kNm"*
        - *"Hitung pondasi telapak lebar 1.5 meter"*
        - *"Berapa estimasi biaya struktur tersebut?"*
        """)
    
    else:
        # VISUALISASI DINAMIS BERDASARKAN KONTEKS
        if data['type'] == 'balok':
            val = data['val']
            st.success(f"📌 Detail Desain: Balok {val['b']} x {val['h']} mm")
            
            # Tabulasi Data
            metric1, metric2, metric3 = st.columns(3)
            metric1.metric("Mutu Beton", f"fc {val['fc']}")
            metric2.metric("Tulangan Perlu", f"{val['as']:.0f} mm2")
            metric3.metric("Jumlah Batang", f"{val['n_bars']} bh")
            
            # Gambar Penampang Sederhana (Matplotlib)
            fig, ax = plt.subplots(figsize=(4, 4))
            # Beton
            rect = plt.Rectangle((0, 0), val['b'], val['h'], linewidth=2, edgecolor='black', facecolor='#D6EAF8')
            ax.add_patch(rect)
            # Tulangan (Lingkaran merah)
            spacing = (val['b'] - 80) / (val['n_bars'] + 1)
            for i in range(val['n_bars']):
                circle = plt.Circle((40 + (i+1)*spacing, 40), 10, color='red') # Asumsi tulangan tarik bawah
                ax.add_patch(circle)
                
            ax.set_xlim(-50, val['b']+50)
            ax.set_ylim(-50, val['h']+50)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(f"Visualisasi Penampang {val['b']}x{val['h']}")
            st.pyplot(fig)
            
            st.download_button("📥 Download Laporan PDF (Mock)", "Data PDF", "Laporan_Struktur.pdf")
            
        elif data['type'] == 'pondasi':
            st.info("Visualisasi Pondasi sedang digenerate...")
            # (Tambahkan kode plot pondasi disini)

# --- SIDEBAR: KONTROL MANUAL (FALLBACK) ---
with st.sidebar:
    st.header("⚙️ Panel Kontrol")
    st.write("Jika AI ragu, Anda bisa override parameter di sini.")
    override_fc = st.number_input("Override fc' (MPa)", 20, 50, 25)
    if st.button("Reset Chat"):
        st.session_state.messages = []
        st.session_state.last_data = None
        st.rerun()
