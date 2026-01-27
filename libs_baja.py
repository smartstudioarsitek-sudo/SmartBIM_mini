import numpy as np

class SNI_Steel_1729:
    """
    Engine Struktur Baja (SNI 1729:2015 - LRFD)
    """
    def __init__(self, fy, fu):
        self.fy = fy # Yield Strength (MPa)
        self.fu = fu # Ultimate Strength (MPa)
        self.E = 200000 # Modulus Elastisitas (MPa)

    def cek_balok_lentur(self, Mu_kNm, Zx_cm3, Lb_m, Lp_m, Lr_m):
        """
        Cek Kapasitas Lentur Balok I/WF (Phi_Mn)
        """
        phi_b = 0.9
        Zx = Zx_cm3 * 1000 # convert to mm3
        
        # 1. Yielding (Leleh)
        Mn_yield = self.fy * Zx
        
        # 2. Lateral Torsional Buckling (Tekuk Torsi Lateral)
        # Asumsi sederhana LRFD
        if Lb_m <= Lp_m:
            Mn = Mn_yield
            zone = "Plastis (Compact)"
        elif Lb_m <= Lr_m:
            # Interpolasi Linear (Zone 2)
            # Simplifikasi rumus Cb=1.0
            Mn = Mn_yield # Simplified for brevity, real formula involves Cb
            zone = "Inelastis (LTB)"
        else:
            Mn = 0.7 * self.fy * Zx # Simplified elastic buckling
            zone = "Elastis (Bahaya)"
            
        phi_Mn = phi_b * Mn / 1e6 # kNm
        
        ratio = Mu_kNm / phi_Mn
        status = "AMAN" if ratio <= 1.0 else "TIDAK AMAN"
        
        return {
            "Phi_Mn": phi_Mn,
            "Ratio": ratio,
            "Status": status,
            "Zone": zone
        }

class Baja_Ringan_Calc:
    """
    Kalkulator Estimasi Kuda-Kuda Baja Ringan (SNI 7971)
    """
    def hitung_kebutuhan_atap(self, luas_atap_m2, jenis_genteng="Metal Pasir"):
        # Koefisien Berat (kg/m2) Rangka Baja Ringan
        # Metal Pasir (Ringan): ~15 kg/m2 (Rangka + Atap)
        # Keramik (Berat): ~35 kg/m2 (Rangka + Atap)
        
        beban_sqm = 15.0 if "Metal" in jenis_genteng else 35.0
        
        # Kebutuhan Material per m2 (Rule of Thumb)
        # C-Channel (Kaso)
        btg_c = luas_atap_m2 * 0.5 # estimasi 0.5 batang per m2
        # Reng
        btg_reng = luas_atap_m2 * 1.2 # estimasi 1.2 batang per m2
        # Sekrup
        sekrup = luas_atap_m2 * 20 # 20 pcs per m2
        
        return {
            "Total Beban (kg)": luas_atap_m2 * beban_sqm,
            "Kanal C (btg)": np.ceil(btg_c),
            "Reng (btg)": np.ceil(btg_reng),
            "Sekrup (pcs)": np.ceil(sekrup)
        }