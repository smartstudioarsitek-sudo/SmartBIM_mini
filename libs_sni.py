import numpy as np

class SNI_Concrete_2847:
    """
    Engine perhitungan Struktur Beton Bertulang berdasarkan SNI 2847:2019
    """
    def __init__(self, fc, fy):
        self.fc = fc # MPa
        self.fy = fy # MPa
        self.beta1 = 0.85 if fc <= 28 else max(0.85 - 0.05 * (fc - 28) / 7, 0.65)

    def hitung_momen_nominal(self, b, h, As, ds):
        """
        Menghitung Kapasitas Momen (Phi Mn) balok persegi.
        b, h, ds dalam mm. As dalam mm2.
        Output: Phi_Mn (kNm)
        """
        # Kedalaman blok tekan (a)
        # a = (As * fy) / (0.85 * fc * b)
        a = (As * self.fy) / (0.85 * self.fc * b)
        
        # Momen Nominal (Mn) -> Nmm
        # Mn = As * fy * (d - a/2)
        d = h - ds
        Mn = As * self.fy * (d - a / 2)
        
        # Faktor Reduksi Kekuatan (Phi) - SNI 2847 Tabel 21.2.1
        # Asumsi terkendali tarik (Tension Controlled) untuk balok
        phi = 0.9 
        
        return (phi * Mn) / 1e6 # Convert ke kNm

    def kebutuhan_tulangan(self, Mu_kNm, b, h, ds):
        """
        Desain Tulangan Perlu (As_req) berdasarkan Mu.
        """
        phi = 0.9
        d = h - ds
        Mu = Mu_kNm * 1e6 # Nmm
        
        # Rumus Pendekatan (Simplified Design)
        # As = Mu / (phi * fy * 0.875 * d)
        As_perlu = Mu / (phi * self.fy * 0.875 * d)
        
        # Cek Minimum Reinforcement (SNI 2847 Pasal 9.6.1.2)
        As_min1 = (0.25 * np.sqrt(self.fc) / self.fy) * b * d
        As_min2 = (1.4 / self.fy) * b * d
        As_min = max(As_min1, As_min2)
        
        return max(As_perlu, As_min)

class SNI_Load_1727:
    """
    Kombinasi Pembebanan SNI 1727:2020
    """
    @staticmethod
    def komb_pembebanan(D, L):
        """
        Mengembalikan Envelope beban terbesar (kNm atau kN)
        K1: 1.4D
        K2: 1.2D + 1.6L
        """
        k1 = 1.4 * D
        k2 = 1.2 * D + 1.6 * L
        return max(k1, k2)
