import google.generativeai as genai
import libs_tools as tools

class SmartBIM_Brain:
    def __init__(self, api_key, model_name, system_instruction):
        genai.configure(api_key=api_key)
        
        # === DAFTAR TOOLS LENGKAP (SEMUA LIBS) ===
        self.tools_list = [
            tools.tool_hitung_balok,       # libs_sni
            tools.tool_cek_baja_wf,        # libs_baja
            tools.tool_hitung_pondasi,     # libs_pondasi
            tools.tool_estimasi_biaya,     # libs_ahsp
            tools.tool_hitung_gempa_v,     # libs_gempa (BARU)
            tools.tool_cek_talud           # libs_geoteknik (BARU)
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
