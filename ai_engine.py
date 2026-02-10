import google.generativeai as genai
import libs_tools as tools
import os

# ==============================================================================
# FUNGSI BANTUAN: MENGUBAH DATA SESSION STATE MENJADI TEKS UNTUK AI
# ==============================================================================
def generate_context_from_state(session_state):
    """
    Fungsi ini membaca data dari Tab Manual (session_state) 
    dan merangkumnya menjadi teks agar AI tahu konteks proyek saat ini.
    """
    context_text = "--- [DATA PROYEK AKTIF DARI TAB MANUAL] ---\n"
    
    # 1. Data Geometri (Dari Tab Modeling)
    if 'geo' in session_state:
        g = session_state['geo']
        context_text += f"1. GEOMETRI: Bentang L={g.get('L',0)}m, Dimensi b={g.get('b',0)}mm, h={g.get('h',0)}mm\n"
        
    # 2. Data Struktur (Dari Tab Beton)
    if 'structure' in session_state:
        s = session_state['structure']
        # Cek apakah ada data report struktur
        if 'report_struk' in session_state:
            r = session_state['report_struk']
            context_text += f"2. STRUKTUR BETON: Mu={r.get('Mu',0)} kNm, Tulangan={r.get('Tulangan','-')}\n"
    
    # 3. Data Baja (Dari Tab Baja)
    if 'report_baja' in session_state:
        b = session_state['report_baja']
        if b: # Cek jika dictionary tidak kosong
            context_text += f"3. STRUKTUR BAJA: Profil={b.get('Profil','-')}, Ratio={b.get('Ratio',0)}, Status={b.get('Status','-')}\n"
            
    # 4. Data Gempa (Dari Tab Gempa)
    if 'report_gempa' in session_state:
        gm = session_state['report_gempa']
        if gm:
            context_text += f"4. GEMPA: V_base={gm.get('V_gempa',0)} kN, Site Class={gm.get('Site','-')}\n"
            
    # 5. Data Geoteknik (Dari Tab Geoteknik)
    if 'report_geo' in session_state:
        gt = session_state['report_geo']
        if gt:
            context_text += f"5. GEOTEKNIK: SF Talud={gt.get('Talud_SF','-')}, Pile Qall={gt.get('Pile_Qall','-')}\n"
            
    # 6. Data BIM (Jika ada upload IFC)
    if 'bim_loads' in session_state:
        context_text += f"6. DATA BIM (IFC): Terdeteksi beban tambahan dari BIM sebesar {session_state['bim_loads']} kN\n"

    context_text += "--- [AKHIR DATA PROYEK] ---\n"
    context_text += "INSTRUKSI: Gunakan data di atas sebagai referensi JIKA user bertanya tentang 'proyek ini' atau 'data saya'. Jika user bertanya umum, abaikan data ini.\n"
    
    return context_text

# ==============================================================================
# CLASS UTAMA AI (BRAIN)
# ==============================================================================
class SmartBIM_Brain:
    def __init__(self, api_key, model_name, system_instruction):
        # Konfigurasi API
        genai.configure(api_key=api_key)
        
        # === DAFTAR TOOLS LENGKAP ===
        self.tools_list = [
            tools.tool_hitung_balok,       # libs_sni
            tools.tool_cek_baja_wf,        # libs_baja
            tools.tool_hitung_pondasi,     # libs_pondasi
            tools.tool_estimasi_biaya,     # libs_ahsp
            tools.tool_hitung_gempa_v,     # libs_gempa 
            tools.tool_cek_talud           # libs_geoteknik 
        ]
        
        # Inisialisasi Model
        self.model = genai.GenerativeModel(
            model_name=model_name,
            tools=self.tools_list,
            system_instruction=system_instruction
        )
        
        # Mulai Chat Session
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def ask(self, user_prompt, context_data=""):
        """
        Fungsi untuk mengirim pesan ke AI.
        user_prompt: Pertanyaan user (misal: "Apakah balok saya aman?")
        context_data: Data proyek dari Tab Manual (otomatis disisipkan)
        """
        try:
            # Gabungkan Data Proyek + Pertanyaan User
            # Ini trik agar AI "membaca" data tanpa user mengetik ulang
            full_prompt = f"{context_data}\n\nPERTANYAAN USER:\n{user_prompt}"
            
            # Kirim pesan gabungan ke Gemini
            response = self.chat.send_message(full_prompt)
            return response.text
        except Exception as e:
            return f"⚠️ Maaf, terjadi kesalahan pada AI: {str(e)}. Coba ganti model ke versi 'Lite' atau periksa API Key."

# ==============================================================================
# DEFINISI PERSONA
# ==============================================================================
PERSONAS = {
    "🦁 The Grandmaster": """
        Anda adalah 'EnginEx Titan', AI Konstruksi level Grandmaster.
        Anda memiliki akses ke semua tools perhitungan dan DATA PROYEK USER yang diberikan di setiap pesan.
        Tugas Anda adalah menjawab pertanyaan user dengan data teknis yang akurat.
        Gaya bicara: Profesional, Cerdas, dan Solutif.
    """,
    "👷 Ir. Satria (Ahli Struktur)": """
        Anda adalah Ir. Satria, Insinyur Struktur Senior.
        Fokus utama Anda adalah KEKUATAN dan KESELAMATAN (SNI 2847 & SNI 1729).
        Gunakan data geometri yang tersedia untuk memverifikasi keamanan.
    """,
    "💰 Budi (Estimator Biaya)": """
        Anda adalah Budi, Quantity Surveyor (Ahli Biaya).
        Fokus utama Anda adalah EFISIENSI BUDGET dan HARGA (AHSP).
        Selalu tawarkan solusi hemat berdasarkan volume beton yang ada di data proyek.
    """,
    "🌋 Dr. Geo (Ahli Gempa & Geoteknik)": """
        Anda adalah Dr. Geo. Ahli Geoteknik dan Kegempaan.
        Fokus Anda adalah SNI 1726 (Gempa) dan Kestabilan Lereng/Pondasi.
    """
}
