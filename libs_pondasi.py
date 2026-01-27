import pandas as pd
import numpy as np

class Foundation_Engine:
    def __init__(self, sigma_tanah):
        self.sigma_tanah = sigma_tanah # Daya dukung tanah (kN/m2)

    def hitung_footplate(self, beban_pu, lebar_B, lebar_L, tebal_mm):
        """
        Menghitung Keamanan & Volume Cakar Ayam
        """
        # 1. Cek Tegangan Tanah
        luas = lebar_B * lebar_L
        tegangan_terjadi = beban_pu / luas
        status = "AMAN" if tegangan_terjadi <= self.sigma_tanah else "BAHAYA (Perbesar Dimensi)"
        
        # 2. Hitung Volume
        vol_beton = luas * (tebal_mm / 1000)
        vol_galian = (lebar_B + 0.5) * (lebar_L + 0.5) * 1.5 # Asumsi kedalaman 1.5m + space kerja
        
        # 3. Estimasi Besi (Ratio 120 kg/m3 untuk pondasi)
        berat_besi = vol_beton * 120
        
        return {
            "status": status,
            "ratio_safety": self.sigma_tanah / tegangan_terjadi if tegangan_terjadi > 0 else 0,
            "vol_beton": vol_beton,
            "vol_galian": vol_galian,
            "berat_besi": berat_besi
        }

    def hitung_batu_kali(self, panjang_total, lebar_atas, lebar_bawah, tinggi):
        """
        Menghitung Volume Pondasi Menerus (Batu Kali)
        """
        # Luas Penampang Trapesium
        luas_penampang = ((lebar_atas + lebar_bawah) / 2) * tinggi
        
        # Volume Pasangan
        vol_pasangan = luas_penampang * panjang_total
        
        # Volume Galian (Lebar bawah + 20cm kiri kanan x Tinggi)
        vol_galian = (lebar_bawah + 0.4) * tinggi * panjang_total
        
        return {
            "vol_pasangan": vol_pasangan,
            "vol_galian": vol_galian
        }