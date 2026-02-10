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
    
    # 1. Data Geometri
    if 'geo' in session_state:
        g = session_state['geo']
        context_text += f"1. GEOMETRI: Bentang L={g.get('L',0)}m, Dimensi b={g.get('b',0)}mm, h={g.get('h',0)}mm\n"
        
    # 2. Data Struktur
    if 'structure' in session_state:
        s = session_state['structure']
        if 'report_struk' in session_state:
            r = session_state['report_struk']
            context_text += f"2. STRUKTUR BETON: Mu={r.get('Mu',0)} kNm, Tulangan={r.get('Tulangan','-')}\n"
    
    # 3. Data Baja
    if 'report_baja' in session_state:
        b = session_state['report_baja']
        if b: 
            context_text += f"3. STRUKTUR BAJA: Profil={b.get('Profil','-')}, Ratio={b.get('Ratio',0)}, Status={b.get('Status','-')}\n"
            
    # 4. Data Gempa
    if 'report_gempa' in session_state:
        gm = session_state['report_gempa']
        if gm:
            context_text += f"4. GEMPA: V_base={gm.get('V_gempa',0)} kN, Site Class={gm.get('Site','-')}\n"
            
    # 5. Data Geoteknik
    if 'report_geo' in session_state:
        gt = session_state['report_geo']
        if gt:
            context_text += f"5. GEOTEKNIK: SF Talud={gt.get('Talud_SF','-')}, Pile Qall={gt.get('Pile_Qall','-')}\n"
            
    # 6. Data BIM
    if 'bim_loads' in session_state:
        context_text += f"6. DATA BIM (IFC): Terdeteksi beban tambahan dari BIM sebesar {session_state['bim_loads']} kN\n"

    context_text += "--- [AKHIR DATA PROYEK] ---\n"
    context_text += "INSTRUKSI: Gunakan data di atas sebagai referensi JIKA user bertanya tentang 'proyek ini' atau 'data saya'.\n"
    
    return context_text

# ==============================================================================
# CLASS UTAMA AI (BRAIN)
# ==============================================================================
class SmartBIM_Brain:
    def __init__(self, api_key, model_name, system_instruction):
        genai.configure(api_key=api_key)
        
        # === DAFTAR TOOLS LENGKAP ===
        # Pastikan tidak ada koma yang hilang di sini
        self.tools_list = [
            tools.tool_hitung_balok,       
            tools.tool_cek_baja_wf,        
            tools.tool_hitung_pondasi,     
            tools.tool_estimasi_biaya,     
            tools.tool_hitung_gempa_v,     
            tools.tool_cek_talud,
            tools.tool_cari_dimensi_optimal # <--- TOOL BARU
        ]
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            tools=self.tools_list,
            system_instruction=system_instruction
        )
        
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def ask(self, user_prompt, context_data=""):
        try:
            full_prompt = f"{context_data}\n\nPERTANYAAN USER:\n{user_prompt}"
            response = self.chat.send_message(full_prompt)
            return response.text
        except Exception as e:
            return f"⚠️ Maaf, terjadi kesalahan pada AI: {str(e)}. Coba ganti model ke versi 'Lite' atau periksa API Key."

# ==============================================================================
# DEFINISI PERSONA
# ==============================================================================
PERSONAS = {
    "🦁 The Grandmaster": """
        Anda adalah 'EnginEx Titan'. Jawab teknis & hitung menggunakan tools.
        Jika user minta desain hemat, gunakan tool_cari_dimensi_optimal.
    """,
    "👷 Ir. Satria (Ahli Struktur)": """
        Anda adalah Ir. Satria. Fokus kekuatan struktur & SNI.
    """,
    "💰 Budi (Estimator Biaya)": """
        Anda adalah Budi. Fokus efisiensi biaya & RAB.
    """,
    "🌋 Dr. Geo (Ahli Gempa & Geoteknik)": """
        Anda adalah Dr. Geo. Fokus Gempa & Geoteknik.
    """
}
