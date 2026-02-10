import pandas as pd
import numpy as np
import libs_sni as sni

class BeamOptimizer:
    def __init__(self, fc, fy, harga_satuan):
        self.fc = fc
        self.fy = fy
        self.h_beton = harga_satuan.get('beton', 1100000)
        self.h_baja = harga_satuan.get('baja', 14000)
        self.h_bekisting = harga_satuan.get('bekisting', 150000)

    def cari_dimensi_optimal(self, Mu_kNm, bentang_m):
        """Mencari dimensi b x h yang paling murah namun Aman"""
        options = []
        range_b = range(200, 650, 50)
        h_min_rec = int(bentang_m * 1000 / 15) 
        range_h = range(max(300, h_min_rec), 1050, 50)
        
        engine_sni = sni.SNI_Concrete_2847(self.fc, self.fy)

        for b in range_b:
            for h in range_h:
                if h < b: continue
                if h > 3 * b: continue 
                
                ds = 40 + 10 + 6
                try:
                    As_req = engine_sni.kebutuhan_tulangan(Mu_kNm, b, h, ds)
                except: continue
                
                d = h - ds
                rho = As_req / (b * d)
                if rho > 0.025: continue 
                
                vol_beton = (b/1000) * (h/1000) * 1.0
                berat_baja = (As_req * 1.0 * 7850) / 1e6 * 1.3
                luas_bekisting = (2 * (h/1000)) + (b/1000)
                
                biaya = (vol_beton * self.h_beton) + (berat_baja * self.h_baja) + (luas_bekisting * self.h_bekisting)
                        
                options.append({'b': b, 'h': h, 'As': As_req, 'Biaya': biaya, 'Rho': rho * 100})
        
        if not options: return None
        df_opt = pd.DataFrame(options).sort_values(by='Biaya', ascending=True)
        return df_opt.head(3).to_dict('records')
