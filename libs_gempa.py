import numpy as np

class SNI_Gempa_1726:
    def __init__(self, Ss, S1, Kelas_Situs):
        self.Ss = Ss
        self.S1 = S1
        self.Site = Kelas_Situs
        
    def hitung_base_shear(self, Berat_W_kN, R_redaman):
        # 1. Tentukan Fa Fv (Tabel SNI)
        if self.Site == 'SE': # Tanah Lunak
            Fa = 0.9 if self.Ss >= 1.0 else 2.5
            Fv = 2.4 if self.S1 >= 0.5 else 3.5
        elif self.Site == 'SD': # Tanah Sedang
            Fa = 1.1 if self.Ss >= 1.0 else 1.6
            Fv = 1.6 if self.S1 >= 0.5 else 2.4
        else: # SC (Tanah Keras)
            Fa = 1.0; Fv = 1.0
            
        # 2. Hitung SMS, SDS
        Sms = Fa * self.Ss
        Sm1 = Fv * self.S1
        Sds = (2/3) * Sms
        Sd1 = (2/3) * Sm1
        
        # 3. Hitung Koefisien Cs
        Ie = 1.0
        Cs = Sds / (R_redaman / Ie)
        
        # 4. Gaya Geser Dasar (V)
        V = Cs * Berat_W_kN
        
        return V, Sds, Sd1
