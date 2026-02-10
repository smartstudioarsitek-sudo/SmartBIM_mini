import google.generativeai as genai
import libs_tools as tools

class SmartBIM_Brain:
    def __init__(self, api_key, model_name, system_instruction):
        genai.configure(api_key=api_key)
        
        # Daftarkan Tools diatas
        self.tools_list = [
            tools.tool_hitung_balok,
            tools.tool_cek_baja_wf,
            tools.tool_hitung_pondasi,
            tools.tool_estimasi_biaya
        ]
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            tools=self.tools_list,
            system_instruction=system_instruction
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def ask(self, prompt):
        try:
            response = self.chat.send_message(prompt)
            return response.text
        except Exception as e:
            return f"Error AI: {str(e)}"

# PERSONA
PERSONAS = {
    "🦁 The Grandmaster": "Anda adalah AI Konstruksi Ahli. Jawab teknis & hitung menggunakan tools.",
    "👷 Ir. Satria (Struktur)": "Anda Ahli Struktur kaku & tegas. Fokus SNI.",
    "💰 Budi (Estimator)": "Anda Ahli Biaya. Fokus efisiensi budget."
}
