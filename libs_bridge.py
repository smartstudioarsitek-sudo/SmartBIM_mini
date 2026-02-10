import numpy as np
import pandas as pd

class SNI_Bridge_Loader:
    """
    Engine Pembebanan Jembatan berdasarkan SNI 1725:2016
    Fokus: Beban Lajur "D" (TD) untuk Gelagar Utama
    """
    def __init__(self, bentang_L):
        self.L = bentang_L # Panjang bentang (meter)

    def hitung_beban_lajur_D(self):
        """
        Menghitung Intensitas Beban Lajur "D"
        1. Beban Terbagi Rata (BTR/q) - kPa
        2. Beban Garis Terpusat (BGT/p) - kN/m
        """
        # 1. Hitung BTR (q) - SNI 1725 Pasal 8.3.1
        if self.L <= 30:
            q_btr = 9.0 # kPa
        else:
            q_btr = 9.0 * (0.5 + (15 / self.L)) # kPa (turun seiring panjang bentang)
            
        # 2. Hitung BGT (p) - SNI 1725 Pasal 8.3.1
        p_bgt = 49.0 # kN/m
        
        return {"q_btr": round(q_btr, 2), "p_bgt": p_bgt}

    def hitung_faktor_beban_dinamis(self):
        """
        Faktor Beban Dinamis (FBD/DLA) untuk BGT
        SNI 1725 Gambar 26
        """
        le = self.L # Untuk bentang sederhana
        
        if le <= 50:
            dla = 0.40 # 40%
        elif le >= 90:
            dla = 0.30 # 30%
        else:
            # Interpolasi linier 50 s/d 90
            dla = 0.40 - 0.0025 * (le - 50)
            
        return round(dla, 3)

    def analisis_momen_gelagar(self, jarak_gelagar, beban_mati_tambahan_kpa=0):
        """
        Menghitung Momen Ultimate (Mu) pada 1 Gelagar Interior
        Asumsi: Jembatan Simple Beam (Sendi-Rol)
        """
        # Load Data Beban
        beban = self.hitung_beban_lajur_D()
        dla = self.hitung_faktor_beban_dinamis()
        
        # --- 1. BEBAN HIDUP (LL) ---
        # Distribusi beban lajur ke gelagar (sederhana: lebar tributari)
        # q_LL = q_btr * jarak_gelagar
        q_LL = beban['q_btr'] * jarak_gelagar
        
        # P_LL = p_bgt * jarak_gelagar * (1 + DLA)
        P_LL = beban['p_bgt'] * jarak_gelagar * (1 + dla)
        
        # Momen Maksimum Beban Hidup (Di tengah bentang)
        # M = 1/8*q*L^2 + 1/4*P*L
        M_LL = (1/8 * q_LL * self.L**2) + (1/4 * P_LL * self.L)
        
        # --- 2. BEBAN MATI (DL) ---
        # Estimasi Berat Sendiri Profil Baja (Asumsi awal 200 kg/m -> 2 kN/m)
        q_sw_baja = 2.0 
        
        # Beban Pelat Lantai (Tebal 20cm beton) + Aspal (5cm)
        # Beton: 24 kN/m3 * 0.2m = 4.8 kPa
        # Aspal: 22 kN/m3 * 0.05m = 1.1 kPa
        # Total SDL = 5.9 kPa
        q_sdl = (5.9 + beban_mati_tambahan_kpa) * jarak_gelagar
        
        q_total_DL = q_sw_baja + q_sdl
        M_DL = 1/8 * q_total_DL * self.L**2
        
        # --- 3. KOMBINASI PEMBEBANAN (KUAT I) ---
        # SNI 1725 Tabel 1 (Faktor Beban)
        # U = 1.1*DL_profil + 1.3*DL_SDL + 1.8*LL
        # Untuk simplifikasi di aplikasi ini, kita pukul rata DL faktor 1.3
        
        Mu_Total = (1.3 * M_DL) + (1.8 * M_LL)
        
        return {
            "M_DL": M_DL,
            "M_LL": M_LL,
            "Mu_Total": Mu_Total,
            "DLA": dla,
            "Detail": {
                "q_btr": beban['q_btr'],
                "p_bgt": beban['p_bgt'],
                "q_distribusi_LL": q_LL,
                "P_distribusi_LL": P_LL
            }
        }

class Bridge_Profile_DB:
    """
    Database Profil Baja Jembatan (Welded Beam Ukuran Besar)
    Standard Pabrik Indonesia (Gunung Garuda / Krakatau Steel)
    """
    @staticmethod
    def get_profiles():
        return {
            "WB 600x300 (151 kg/m)": {'h': 600, 'b': 300, 'tw': 12, 'tf': 20, 'Zx': 3980, 'Ix': 118000, 'Iy': 9020},
            "WB 700x300 (185 kg/m)": {'h': 700, 'b': 300, 'tw': 13, 'tf': 24, 'Zx': 5760, 'Ix': 201000, 'Iy': 10800},
            "WB 800x300 (210 kg/m)": {'h': 800, 'b': 300, 'tw': 14, 'tf': 26, 'Zx': 7290, 'Ix': 292000, 'Iy': 11700},
            "WB 900x300 (243 kg/m)": {'h': 900, 'b': 300, 'tw': 16, 'tf': 28, 'Zx': 9170, 'Ix': 411000, 'Iy': 12600},
            "WB 1000x350 (298 kg/m)":{'h':1000, 'b': 350, 'tw': 16, 'tf': 32, 'Zx':11900, 'Ix': 624000, 'Iy': 21400},
            "WB 1200x400 (430 kg/m)":{'h':1200, 'b': 400, 'tw': 18, 'tf': 36, 'Zx':18500, 'Ix': 980000, 'Iy': 32000}
        }
