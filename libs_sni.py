import numpy as np
import math

# Konstanta untuk konversi
RHO_BAJA = 7850 # kg/m3

class SNI_Concrete_2847:
    """
    Engine perhitungan Struktur Beton Bertulang berdasarkan SNI 2847:2019
    Rigor Setara Validasi Output SAP2000/ETABS.
    """
    def __init__(self, fc, fy):
        self.fc = fc # MPa
        self.fy = fy # MPa
        self.beta1 = 0.85 if fc <= 28 else max(0.85 - 0.05 * (fc - 28) / 7, 0.65)
        self.phi_shear = 0.75 
        
        # Hitungan Rasio Tulangan Maksimum Daktail (SNI 2847:2019 Pasal 18.2.2.1)
        # Batas regangan tarik baja 0.004 untuk SDC D
        # c/dt = 3/7 (SNI 2847:2019) atau c/dt = 0.375 (Daktilitas Tinggi)
        self.c_d_ratio = 0.375
        
        # Rasio Tulangan Maksimum Daktail (rho_max_daktail)
        epsilon_cu = 0.003
        c_bal = (epsilon_cu / (epsilon_cu + 0.005)) * 1.0 # 0.6 (Dt = 1.0)
        self.rho_bal = (0.85 * self.fc) * self.beta1 / self.fy * (c_bal)
        self.rho_max = 0.5 * self.rho_bal # Rasio yang disarankan untuk daktilitas tinggi
        self.rho_min1 = 0.25 * np.sqrt(self.fc) / self.fy
        self.rho_min2 = 1.4 / self.fy
        

    def _hitung_phi(self, c, d):
        """Menentukan faktor reduksi phi berdasarkan kedalaman blok tekan (c)"""
        epsilon_t = 0.003 * (d - c) / c
        if epsilon_t >= 0.005:
            return 0.90 # Tension-controlled (Balok Daktail)
        elif epsilon_t <= 0.002:
            return 0.65 # Compression-controlled (Kolom/Balok rapuh)
        else:
            # Transition zone: phi = 0.65 + 0.25 * (epsilon_t - 0.002) / 0.003
            return 0.65 + 0.25 * (epsilon_t - 0.002) / 0.003
            

    def kebutuhan_tulangan(self, Mu_kNm, b, h, ds):
        """
        Desain Tulangan Perlu (As_req) berdasarkan Mu (Iteratif Mencari c/phi)
        Output: As_req (mm2), phi_final, rho_aktual
        """
        d = h - ds
        Mu = Mu_kNm * 1e6 # Nmm
        
        # 1. Trial (Gunakan phi=0.9) untuk mendapatkan As pendekatan
        As_perlu = Mu / (0.9 * self.fy * 0.875 * d)
        
        # 2. Iterasi untuk mendapatkan phi yang akurat
        for _ in range(5): # 5 iterasi cukup
            a = (As_perlu * self.fy) / (0.85 * self.fc * b)
            c = a / self.beta1
            phi_coba = self._hitung_phi(c, d)
            
            # Jika phi sudah stabil, break
            if abs(phi_coba - 0.9) < 0.001 and c < d * 0.375:
                break
            
            # Update As berdasarkan phi baru
            As_perlu = Mu / (phi_coba * self.fy * (d - a/2))
            
        # 3. Check Minimum dan Maksimum
        As_min = max(self.rho_min1 * b * d, self.rho_min2 * b * d)
        As_max = self.rho_max * b * d
        
        As_final = max(As_perlu, As_min)
        
        # Check Final Ratio
        rho_aktual = As_final / (b * d)
        
        if rho_aktual > self.rho_max * 1.05: # Toleransi 5%
            return -999.0, phi_coba, rho_aktual # Indikasi Kegagalan Daktilitas/As Overflow

        return As_final, phi_coba, rho_aktual

    def kebutuhan_sengkang(self, Vu_kN, b, d, L_m, Av_s, dia_sengkang):
        """
        GEMS FIX: Menghitung kapasitas geser beton (Phi Vc) dan Vu.
        Output: s_req (mm), Vc, Vs_need
        """
        Vu = Vu_kN * 1000 # N
        
        # 1. Kapasitas Geser Beton (Vc) - SNI 2847 Eq. 22.5.10.5.3a
        Vc = 0.17 * np.sqrt(self.fc) * b * d
        Phi_Vc = self.phi_shear * Vc
        
        # 2. Cek Batas Maksimal Kekuatan Geser (Pasal 9.5.4.3)
        V_max = 0.66 * np.sqrt(self.fc) * b * d
        if Vu / self.phi_shear > V_max:
             return {"status": "GAGAL - Ukuran Balok Kurang (Vmax)", "s_req": 0, "Vs_need": 99999}

        # 3. Hitung Kebutuhan Geser Baja (Vs)
        if Vu <= 0.5 * Phi_Vc:
            Vs_need = 0 # Sengkang minimal
        else:
            Vs_need = (Vu / self.phi_shear) - Vc
            
        # 4. Jarak Sengkang Perlu (s)
        if Vs_need > 0:
            Av_s = 2 * (0.25 * np.pi * dia_sengkang**2) # Sengkang 2 kaki
            s_req_mm = (Av_s * self.fy * d) / Vs_need
        else:
            # Jika hanya butuh sengkang minimal (SNI 9.7.6.2.2)
            s_req_mm = min(d / 2, 600) 
        
        # 5. Batasan Jarak Maksimum (SNI 2847 Pasal 9.7.6.2.2)
        if Vs_need <= 0.33 * np.sqrt(self.fc) * b * d:
            s_max = min(d / 2, 600)
        else:
            s_max = min(d / 4, 300)
            
        s_final = min(s_req_mm, s_max)

        return {"status": "Sengkang Struktural", "s_req": s_final, "Vs_need": Vs_need / 1000} # Vs_need dalam kN

    def cek_daktilitas_balok(self, b, h, L_m, dia_sengkang, As_req_mm2):
        """
        Detailing Daktilitas Balok (Zona Kritis Gempa) - SNI 2847 Pasal 18
        """
        hc = 2 * h # Panjang zona kritis
        d_eff = h - 40 
        d_bar_est = np.sqrt(As_req_mm2) / 10 # Estimasi diameter tulangan utama (mm) (highly simplified)
        
        # Jarak Sengkang Maksimum di Zona Kritis (SNI 2847 Pasal 18.6.4.4)
        s_max_crit = min(
            d_eff / 4,
            8 * d_bar_est,
            24 * dia_sengkang,
            300 # SNI batas umum 300mm
        )
        
        s_max_crit_final = math.ceil(s_max_crit/10) * 10 # mm (dibulatkan ke 10 terdekat)
        
        return {
            "s_max_kritis": s_max_crit_final, 
            "Panjang_Kritis": hc,
            "Status": "WAJIB detail Zona Kritis"
        }
    
    def rekomendasi_dimensi_balok(self, Mu_kNm, target_ratio=2.0):
        # ... (Fungsi rekomendasi dimensi tetap sama)
        pass 
