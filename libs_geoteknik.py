import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO

class Geotech_Engine:
    def __init__(self, gamma_tanah, phi, c):
        self.gamma = gamma_tanah # Berat isi tanah (kN/m3)
        self.phi = phi           # Sudut geser dalam (derajat)
        self.c = c               # Kohesi (kN/m2)
        
    def hitung_talud_batu_kali(self, H, b_atas, b_bawah, beban_atas_q=0):
        """
        Analisa Stabilitas Dinding Penahan Tanah (Gravity Wall)
        Metode Rankine & Stabilitas Guling/Geser
        """
        # 1. Tekanan Tanah Aktif (Rankine)
        # Ka = tan^2(45 - phi/2)
        Ka = np.tan(np.radians(45 - self.phi/2))**2
        
        # Gaya Dorong Tanah (Pa) = 0.5 * gamma * H^2 * Ka
        Pa = 0.5 * self.gamma * (H**2) * Ka
        # Gaya akibat beban merata di atas (Surcharge q)
        Pq = beban_atas_q * H * Ka
        
        Total_Dorong_H = Pa + Pq
        Momen_Guling = (Pa * H/3) + (Pq * H/2)
        
        # 2. Berat Sendiri Dinding (W) - Trapesium
        # Asumsi Berat Jenis Batu Kali = 22 kN/m3
        gamma_batu = 22.0
        W1 = b_atas * H * gamma_batu # Bagian persegi
        W2 = 0.5 * (b_bawah - b_atas) * H * gamma_batu # Bagian segitiga
        Total_Berat_V = W1 + W2
        
        # Momen Penahan (Tahan Guling) -> Titik putar di ujung kaki depan (Toe)
        # Lengan W1 (Persegi di sisi belakang)
        L1 = b_bawah - (b_atas / 2) 
        # Lengan W2 (Segitiga di sisi depan)
        L2 = (b_bawah - b_atas) * (2/3) 
        Momen_Tahan = (W1 * L1) + (W2 * L2)
        
        # 3. Cek Safety Factor (SF)
        SF_Guling = Momen_Tahan / Momen_Guling if Momen_Guling > 0 else 99
        
        # Gaya Geser Penahan (Friction) = V * tan(delta) + c*B
        # delta asumsi 2/3 phi
        mu = np.tan(np.radians(2/3 * self.phi))
        Gaya_Geser_Tahan = (Total_Berat_V * mu) + (self.c * b_bawah)
        SF_Geser = Gaya_Geser_Tahan / Total_Dorong_H if Total_Dorong_H > 0 else 99
        
        # Output Geometri untuk Gambar
        coords = [
            (0, 0), (b_bawah, 0), (b_bawah, H), # Sisi belakang tegak
            (b_bawah - b_atas, H), (0, 0)
        ]
        
        return {
            "SF_Guling": SF_Guling,
            "SF_Geser": SF_Geser,
            "Vol_Per_M": (b_atas + b_bawah)/2 * H,
            "Coords": coords, # Pastikan 'C' Besar agar konsisten dengan main.py
            "Status": "AMAN" if SF_Guling >= 1.5 and SF_Geser >= 1.5 else "TIDAK AMAN"
        }

    def hitung_bore_pile(self, diameter_cm, kedalaman_m, N_spt_rata):
        """
        Kapasitas Dukung Pondasi Dalam (Bore Pile)
        Metode Reese & Wright (Simplifikasi N-SPT)
        """
        D = diameter_cm / 100 # m
        Ap = 0.25 * np.pi * D**2 # Luas Penampang
        Keliling = np.pi * D
        
        # 1. Tahanan Ujung (End Bearing) - Qp
        # Qp = qp * Ap. Untuk tanah pasir/umum: qp = 40 * N_spt (ton/m2) -> approx 400 * N (kN/m2)
        # Batas max qp biasanya 4000 ton/m2
        qp = min(40 * N_spt_rata, 400) * 10 # convert ton to kN
        Qp = qp * Ap
        
        # 2. Tahanan Selimut (Friction) - Qs
        # fs = N_spt / 2 (ton/m2) -> 5 * N_spt (kN/m2) untuk Bored Pile
        fs = 5 * N_spt_rata
        Qs = fs * Keliling * kedalaman_m
        
        # Daya Dukung Izin (Q_allow) -> SF = 2.5 atau 3
        Q_ult = Qp + Qs
        SF = 3.0
        Q_allow = Q_ult / SF
        
        # Volume Beton
        Vol_Beton = Ap * kedalaman_m
        
        return {
            "Q_ult": Q_ult,
            "Q_allow": Q_allow,
            "Vol_Beton": Vol_Beton,
            "Qp": Qp,
            "Qs": Qs
        }

    def generate_shop_drawing_dxf(self, type_str, params):
        """
        Generates simple DXF script (text based) for AutoCAD
        """
        dxf_content = "0\nSECTION\n2\nENTITIES\n"
        
        if type_str == "TALUD":
            # Draw Polyline of Talud
            # FIX: Gunakan 'Coords' (C Besar) sesuai return dict diatas
            coords = params['Coords'] 
            for i in range(len(coords)-1):
                p1 = coords[i]
                p2 = coords[i+1]
                dxf_content += "0\nLINE\n8\nSTRUKTUR\n" # Layer
                dxf_content += f"10\n{p1[0]}\n20\n{p1[1]}\n30\n0.0\n" # Start Point
                dxf_content += f"11\n{p2[0]}\n21\n{p2[1]}\n31\n0.0\n" # End Point
                
        dxf_content += "0\nENDSEC\n0\nEOF"
        return dxf_content
