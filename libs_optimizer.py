import pandas as pd
import numpy as np
import libs_sni as sni

class BeamOptimizer:
    def __init__(self, fc, fy, harga_satuan):
        self.fc = fc
        self.fy = fy
        # Harga Satuan (Default jika user tidak input)
        self.h_beton = harga_satuan.get('beton', 1100000) # per m3
        self.h_baja = harga_satuan.get('baja', 14000)     # per kg
        self.h_bekisting = harga_satuan.get('bekisting', 150000) # per m2

    def cari_dimensi_optimal(self, Mu_kNm, bentang_m):
        """
        Mencari dimensi b x h yang paling murah namun Aman (Phi Mn >= Mu)
        """
        options = []
        
        # 1. Tentukan Range Pencarian (Grid Search)
        # Lebar (b): 200mm s/d 600mm (interval 50mm)
        range_b = range(200, 650, 50)
        
        # Tinggi (h): 300mm s/d 1000mm (interval 50mm)
        # Rule of thumb: h minimal 1/12 sampai 1/10 bentang
        h_min_rec = int(bentang_m * 1000 / 15) 
        range_h = range(max(300, h_min_rec), 1050, 50)
        
        engine_sni = sni.SNI_Concrete_2847(self.fc, self.fy)

        # 2. Iterasi Semua Kemungkinan
        for b in range_b:
            for h in range_h:
                # Rule Geometri: Tinggi harus >= Lebar (umumnya)
                if h < b: continue
                if h > 3 * b: continue # Jangan terlalu pipih (Stabilitas)
                
                # Hitung Kebutuhan Tulangan (As)
                ds = 40 + 10 + 6 # Selimut + Sengkang + 1/2 D13
                try:
                    As_req = engine_sni.kebutuhan_tulangan(Mu_kNm, b, h, ds)
                except:
                    continue # Skip jika error matematika
                
                # Cek Rasio Tulangan (Rho)
                d = h - ds
                rho = As_req / (b * d)
                rho_max = 0.025 # Limit praktis agar tidak macet saat cor
                
                if rho > rho_max: continue # Skip, tulangan terlalu padat
                
                # 3. Hitung Biaya per Meter Lari
                vol_beton = (b/1000) * (h/1000) * 1.0
                berat_baja = (As_req * 1.0 * 7850) / 1e6 # Konversi mm2 ke m3 ke kg
                # Asumsi tulangan sengkang & susut 30% dari utama
                berat_baja_total = berat_baja * 1.3 
                luas_bekisting = (2 * (h/1000)) + (b/1000) # Kiri + Kanan + Bawah
                
                biaya = (vol_beton * self.h_beton) + \
                        (berat_baja_total * self.h_baja) + \
                        (luas_bekisting * self.h_bekisting)
                        
                options.append({
                    'b': b, 'h': h, 'As': As_req, 
                    'Biaya': biaya,
                    'Rho': rho * 100
                })
        
        # 4. Urutkan dari yang Termurah
        if not options:
            return None
            
        df_opt = pd.DataFrame(options)
        df_opt = df_opt.sort_values(by='Biaya', ascending=True)
        
        # Ambil Top 3 Solusi
        return df_opt.head(3).to_dict('records')
