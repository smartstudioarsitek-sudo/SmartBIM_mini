import libs_tools as tools
import re

class SmartBIM_Agent:
    def __init__(self):
        self.history = []
        
    def process_query(self, user_input):
        """
        [ROUTER SEDERHANA - PENGGANTI LLM SEMENTARA]
        Mendeteksi niat user dan memanggil Persona yang tepat.
        """
        user_input_lower = user_input.lower()
        response = {"text": "", "persona": "", "data": None}
        
        # --- LOGIKA ROUTING ---
        
        # 1. DETEKSI: PERHITUNGAN BALOK (Ir. Satria)
        if "balok" in user_input_lower and ("hitung" in user_input_lower or "cek" in user_input_lower):
            # Ekstraksi parameter sederhana (Regex)
            # Contoh input: "Hitung balok 300x500 beban 50"
            try:
                dims = re.findall(r'(\d+)x(\d+)', user_input_lower)
                beban = re.findall(r'beban (\d+)', user_input_lower)
                
                b = int(dims[0][0]) if dims else 250
                h = int(dims[0][1]) if dims else 400
                mu = float(beban[0]) if beban else 40.0
                
                # CALL TOOL (Mencegah Halusinasi)
                result = tools.tool_hitung_balok(b, h, 25, 400, mu, 6.0)
                
                response["persona"] = "Ir. Satria (Ahli Struktur)"
                response["text"] = f"Baik, saya akan analisa keamanan strukturnya.\n\n{result['output_text']}\n\nSaran: Pastikan panjang penyaluran tulangan memenuhi SNI Pasal 25.4."
                response["data"] = {"type": "balok", "val": result['data_teknis']}
                
            except:
                response["persona"] = "Ir. Satria"
                response["text"] = "Saya perlu data dimensi balok (b x h) dan Beban (kNm). Contoh: 'Hitung balok 300x600 beban 80'."

        # 2. DETEKSI: BIAYA / HARGA (Budi Estimator)
        elif "biaya" in user_input_lower or "rab" in user_input_lower or "harga" in user_input_lower:
            # Asumsi user minta hitung biaya dari perhitungan terakhir (Context Aware)
            # Mock data volume
            result = tools.tool_estimasi_biaya_struktur(2.5, 300) # 2.5 m3 beton, 300 kg besi
            
            response["persona"] = "Budi Estimator (QS & Biaya)"
            response["text"] = f"Siap Bos. Saya hitung pakai harga pasar hari ini (AHSP Update).\n\n{result['output_text']}\n\nTips: Kalau pakai Fly Ash bisa hemat semen 15% loh."
            
        # 3. DETEKSI: PONDASI
        elif "pondasi" in user_input_lower or "cakar ayam" in user_input_lower:
            try:
                lebar = re.findall(r'lebar (\d+)', user_input_lower)
                b = float(lebar[0]) if lebar else 1.0
                result = tools.tool_cek_pondasi(100, b, 150)
                
                response["persona"] = "Ir. Satria x Geoteknik"
                response["text"] = result['output_text']
            except:
                response["text"] = "Input kurang jelas."

        # 4. CHAT UMUM
        else:
            response["persona"] = "Smart Engine Assistant"
            response["text"] = "Halo! Saya Sistem Multi-Agen Smart BIM. Anda bisa meminta saya:\n1. Menghitung Struktur (Tanya Ir. Satria)\n2. Estimasi Biaya (Tanya Budi)\n3. Cek Pondasi\n\nSilakan ketik perintah teknis Anda."

        return response
