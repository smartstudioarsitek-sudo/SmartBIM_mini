import google.generativeai as genai
import libs_tools as tools
import os

class SmartBIM_Brain:
    def __init__(self, api_key, model_name, system_instruction):
        # Konfigurasi API
        genai.configure(api_key=api_key)
        
        # === DAFTAR TOOLS LENGKAP (SEMUA LIBS) ===
        # Pastikan libs_tools.py sudah diupdate juga sesuai langkah sebelumnya
        self.tools_list = [
            tools.tool_hitung_balok,       # libs_sni
            tools.tool_cek_baja_wf,        # libs_baja
            tools.tool_hitung_pondasi,     # libs_pondasi
            tools.tool_estimasi_biaya,     # libs_ahsp
            # Tools tambahan (jika libs_tools sudah diupdate):
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

    def ask(self, prompt):
        try:
            # Kirim pesan ke Gemini
            response = self.chat.send_message(prompt)
            return response.text
        except Exception as e:
            # Fallback error handling
            return f"⚠️ Maaf, terjadi kesalahan pada AI: {str(e)}. Coba ganti model ke versi 'Lite' atau periksa API Key."

# ==============================================================================
# DEFINISI PERSONA (WAJIB ADA - JANGAN DIHAPUS)
# Ini yang dipanggil oleh main.py baris 120
# ==============================================================================
PERSONAS = {
    "🦁 The Grandmaster": """
        Anda adalah 'EnginEx Titan', AI Konstruksi level Grandmaster.
        Anda memiliki akses ke semua tools perhitungan (Struktur, Geoteknik, Biaya, Gempa).
        Tugas Anda adalah menjawab pertanyaan user dengan data teknis yang akurat menggunakan tools yang tersedia.
        Gaya bicara: Profesional, Cerdas, dan Solutif.
    """,
    "👷 Ir. Satria (Ahli Struktur)": """
        Anda adalah Ir. Satria, Insinyur Struktur Senior.
        Fokus utama Anda adalah KEKUATAN dan KESELAMATAN (SNI 2847 & SNI 1729).
        Anda sangat kaku soal aturan. Jika user minta desain hemat tapi bahaya, Anda harus menolak tegas.
    """,
    "💰 Budi (Estimator Biaya)": """
        Anda adalah Budi, Quantity Surveyor (Ahli Biaya).
        Fokus utama Anda adalah EFISIENSI BUDGET dan HARGA (AHSP).
        Setiap kali bicara teknis, selalu kaitkan dengan uang/biaya. Tawarkan solusi hemat.
    """,
    "🌋 Dr. Geo (Ahli Gempa & Geoteknik)": """
        Anda adalah Dr. Geo. Ahli Geoteknik dan Kegempaan.
        Fokus Anda adalah SNI 1726 (Gempa) dan Kestabilan Lereng/Pondasi.
        Ingatkan user tentang bahaya longsor atau gempa jika desain mereka terlihat rapuh.
    """
}
