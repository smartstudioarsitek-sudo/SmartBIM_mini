class SNI_Gempa_1726:
    def __init__(self, Ss, S1, Kelas_Situs):
        """
        Ss: Percepatan batuan dasar perioda pendek
        S1: Percepatan batuan dasar perioda 1 det
        Kelas_Situs: 'SA' (Keras), 'SD' (Sedang), 'SE' (Lunak)
        """
        self.Ss = Ss
        self.S1 = S1
        self.Site = Kelas_Situs
        
    def get_fa_fv(self):
        # Tabel Fa (Simplifikasi SNI 1726)
        if self.Site == 'SE': # Tanah Lunak
            Fa = 2.5 if self.Ss <= 0.25 else 0.9 # Simplified lookup
            Fv = 3.5 if self.S1 <= 0.1 else 2.4
        elif self.Site == 'SD': # Tanah Sedang
            Fa = 1.6 if self.Ss <= 0.25 else 1.0
            Fv = 2.4 if self.S1 <= 0.1 else 1.5
        else: # SA/SB Tanah Keras
            Fa = 1.0
            Fv = 1.0
        return Fa, Fv

    def hitung_respon_spektrum(self):
        Fa, Fv = self.get_fa_fv()
        
        # Parameter Desain
        Sds = (2/3) * Fa * self.Ss
        Sd1 = (2/3) * Fv * self.S1
        
        To = 0.2 * (Sd1 / Sds)
        Ts = Sd1 / Sds
        
        return {"Sds": Sds, "Sd1": Sd1, "To": To, "Ts": Ts}

    def hitung_gaya_geser_dasar(self, Berat_Struktur_W, R=8.0, Ie=1.0):
        """
        Menghitung Base Shear (V)
        V = Cs * W
        """
        params = self.hitung_respon_spektrum()
        Sds = params['Sds']
        Sd1 = params['Sd1']
        
        # Koefisien Cs
        Cs_max = Sds / (R / Ie)
        Cs_min = 0.044 * Sds * Ie
        
        # Gaya Geser (V)
        V = Cs_max * Berat_Struktur_W
        
        return V, params