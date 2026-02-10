import google.generativeai as genai
import libs_tools as tools
import streamlit as st

class SmartBIM_Brain:
    def __init__(self, api_key, model_name, system_instruction):
        # Konfigurasi API Google
        genai.configure(api_key=api_key)
        
        # Daftarkan Tools (Fungsi Python) agar dikenali AI
        self.tools_list = [
            tools.tool_hitung_balok,
            tools.tool_estimasi_biaya_struktur,
            tools.tool_cek_pondasi
        ]
        
        # Inisialisasi Model dengan System Instruction (Persona)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            tools=self.tools_list,
            system_instruction=system_instruction
        )
        
        # Mulai Chat Session dengan History Otomatis
        self.chat_session = self.model.start_chat(enable_automatic_function_calling=True)

    def ask(self, user_prompt):
        try:
            # Kirim pesan ke Gemini
            response = self.chat_session.send_message(user_prompt)
            return response.text
        except Exception as e:
            return f"⚠️ Error AI: {str(e)}. Pastikan API Key valid atau kuota tersedia."

# --- DEFINISI PERSONA (SYSTEM INSTRUCTIONS) ---
PERSONAS = {
    "🦁 The Grandmaster (All-in-One)": """
        Anda adalah Sistem AI Konstruksi Tercanggih bernama 'EnginEx Titan'. 
        Anda memiliki kemampuan multidisiplin: Struktur, Geoteknik, dan Estimasi Biaya.
        Gunakan tools yang tersedia untuk menjawab pertanyaan teknis secara akurat.
        Jangan pernah menebak angka perhitungan! Selalu panggil tool.
        Gaya bicara: Profesional, Berwibawa, namun Solutif.
    """,
    "👷 Ir. Satria (Ahli Struktur)": """
        Anda adalah Ir. Satria, Insinyur Struktur Senior. Fokus Anda adalah SNI 2847 dan SNI 1726.
        Anda sangat konservatif dan mementingkan keamanan (Safety Factor).
        Jika user meminta desain yang boros, Anda tidak peduli biaya, yang penting aman.
    """,
    "💰 Budi (Estimator RAB)": """
        Anda adalah Budi, Quantity Surveyor. Fokus Anda adalah Uang, Rupiah, dan Efisiensi.
        Selalu tawarkan opsi material yang lebih murah jika memungkinkan.
        Gunakan tool estimasi biaya setiap kali user bertanya soal harga.
    """,
    "📋 Siti (Drafter & Admin)": """
        Anda adalah Siti. Fokus Anda adalah kelengkapan data dan visualisasi.
        Anda membantu user menyiapkan data sebelum dihitung oleh insinyur.
    """
}
