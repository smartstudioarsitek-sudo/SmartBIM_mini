import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

class Geotech_Engine:
    def __init__(self, gamma_tanah, phi, c):
        self.gamma = gamma_tanah 
        self.phi = phi           
        self.c = c               
        
    def hitung_talud_batu_kali(self, H, b_atas, b_bawah, beban_atas_q=0):
        # 1. Tekanan Tanah Aktif (Rankine)
        Ka = np.tan(np.radians(45 - self.phi/2))**2
        Pa = 0.5 * self.gamma * (H**2) * Ka
        Pq = beban_atas_q * H * Ka
        Total_Dorong_H = Pa + Pq
        Momen_Guling = (Pa * H/3) + (Pq * H/2)
        
        # 2. Berat Sendiri
        gamma_batu = 22.0
        W1 = b_atas * H * gamma_batu
        W2 = 0.5 * (b_bawah - b_atas) * H * gamma_batu
        Total_Berat_V = W1 + W2
        
        # Momen Tahan
        L1 = b_bawah - (b_atas / 2) 
        L2 = (b_bawah - b_atas) * (2/3) 
        Momen_Tahan = (W1 * L1) + (W2 * L2)
        
        # 3. SF
        SF_Guling = Momen_Tahan / Momen_Guling if Momen_Guling > 0 else 99
        mu = np.tan(np.radians(2/3 * self.phi))
        Gaya_Geser_Tahan = (Total_Berat_V * mu) + (self.c * b_bawah)
        SF_Geser = Gaya_Geser_Tahan / Total_Dorong_H if Total_Dorong_H > 0 else 99
        
        coords = [(0, 0), (b_bawah, 0), (b_bawah, H), (b_bawah - b_atas, H), (0, 0)]
        
        return {
            "SF_Guling": SF_Guling,
            "SF_Geser": SF_Geser,
            "Vol_Per_M": (b_atas + b_bawah)/2 * H,
            "Coords": coords, # Kapital
            "Status": "AMAN" if SF_Guling >= 1.5 and SF_Geser >= 1.5 else "TIDAK AMAN"
        }

    def hitung_bore_pile(self, diameter_cm, kedalaman_m, N_spt_rata):
        D = diameter_cm / 100
        Ap = 0.25 * np.pi * D**2
        Keliling = np.pi * D
        
        qp = min(40 * N_spt_rata, 400) * 10
        Qp = qp * Ap
        fs = 5 * N_spt_rata
        Qs = fs * Keliling * kedalaman_m
        
        Q_ult = Qp + Qs
        Q_allow = Q_ult / 3.0
        
        return {"Q_allow": Q_allow, "Vol_Beton": Ap * kedalaman_m}

    def generate_shop_drawing_dxf(self, type_str, params):
        dxf_content = "0\nSECTION\n2\nENTITIES\n"
        if type_str == "TALUD":
            coords = params['Coords'] # Panggil dengan Kapital
            for i in range(len(coords)-1):
                p1 = coords[i]; p2 = coords[i+1]
                dxf_content += f"0\nLINE\n8\nSTRUKTUR\n10\n{p1[0]}\n20\n{p1[1]}\n30\n0.0\n11\n{p2[0]}\n21\n{p2[1]}\n31\n0.0\n"
        dxf_content += "0\nENDSEC\n0\nEOF"
        return dxf_content
