import numpy as np
import pandas as pd

# ==========================================
# CLASS 1: BAJA BERAT (WF/H-BEAM) - SNI 1729
# ==========================================
class SNI_Steel_1729:
    def __init__(self, fy, fu):
        self.fy = fy # MPa
        self.fu = fu # MPa
        self.E = 200000 # MPa

    def cek_balok_lentur(self, Mu_kNm, profil_data, Lb_m):
        """
        Cek Kapasitas Lentur Balok I/WF (Phi_Mn)
        profil_data: Dictionary {'Zx': cm3}
        """
        phi_b = 0.9
        
        # Ambil data Zx
        Zx = profil_data['Zx'] * 1000 # cm3 -> mm3
        
        # 1. Momen Plastis (Mp) = Fy * Zx
        Mp = self.fy * Zx
        
        # 2. Cek Tekuk Torsi Lateral (LTB) - Simplifikasi
        # Rule of thumb: Jika bentang > 2 meter, mulai ada reduksi kekuatan
        faktor_tekuk = 1.0
        if Lb_m > 2.0:
            # Reduksi linear sederhana untuk warning awal
            penurunan = 0.1 * (Lb_m - 2.0)
            faktor_tekuk = max(0.6, 1.0 - penurunan)
            
        Mn = Mp * faktor_tekuk
        
        # Kapasitas Desain
        phi_Mn = phi_b * Mn / 1e6 # Nmm -> kNm
        
        ratio = Mu_kNm / phi_Mn if phi_Mn > 0 else 99
        
        return {
            "Phi_Mn": phi_Mn,
            "Ratio": ratio,
            "Status": "AMAN" if ratio <= 1.0 else "TIDAK AMAN (Bahaya Tekuk)",
            "Keterangan": f"Faktor Reduksi Tekuk LTB: {int(faktor_tekuk*100)}% (Lb={Lb_m}m)"
        }

# ==========================================
# CLASS 2: BAJA RINGAN (ATAP) - ESTIMASI
# ==========================================
class Baja_Ringan_Calc:
    def hitung_kebutuhan_atap(self, luas_atap_m2, jenis_genteng):
        # Koefisien per m2
        if "Metal" in jenis_genteng:
            k_c = 0.35; k_reng = 0.6 # Ringan
        else:
            k_c = 0.55; k_reng = 1.2 # Berat
            
        btg_c = np.ceil(luas_atap_m2 * k_c)
        btg_reng = np.ceil(luas_atap_m2 * k_reng)
        
        # Sekrup genteng (12/m2) + Sekrup truss (8/btg C + 4/btg Reng)
        sekrup_genteng = luas_atap_m2 * 12 
        sekrup_truss = (btg_c * 8) + (btg_reng * 4)
        total_sekrup = np.ceil(sekrup_genteng + sekrup_truss)
        
        return {
            "C75.75 (Btg)": int(btg_c),
            "Reng 30.45 (Btg)": int(btg_reng),
            "Sekrup (Box)": int(total_sekrup/1000) + 1
        }
