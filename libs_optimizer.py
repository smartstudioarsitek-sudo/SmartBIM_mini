import numpy as np
from scipy.optimize import minimize

class StructuralOptimizer:
    def __init__(self, fc, fy, harga_satuan):
        self.fc = fc  # MPa
        self.fy = fy  # MPa
        self.harga = harga_satuan # Dict {beton: Rp/m3, baja: Rp/kg, bekisting: Rp/m2}

    def objective_function(self, x):
        """
        Fungsi Biaya Total (Cost Function)
        x[0] = b (lebar), x[1] = h (tinggi), x[2] = As (luas tulangan)
        """
        b, h, As = x
        rho_baja = 7850 # kg/m3
        
        # Volume per 1 meter panjang
        vol_beton = b * h
        berat_baja = As * rho_baja 
        luas_bekisting = 2*h + b # Sisi kiri + kanan + bawah
        
        cost = (vol_beton * self.harga['beton']) + \
               (berat_baja * self.harga['baja']) + \
               (luas_bekisting * self.harga['bekisting'])
        return cost

    def constraint_capacity(self, x, Mu):
        """
        Batasan Kekuatan: phi * Mn >= Mu
        Mengembalikan nilai non-negatif jika syarat terpenuhi
        """
        b, h, As = x
        phi = 0.9
        
        # Hitung a (tinggi blok tekan)
        a = (As * self.fy) / (0.85 * self.fc * b)
        d = h - 0.04 # Asumsi selimut 40mm
        
        # Momen Nominal
        Mn = As * self.fy * (d - a/2)
        
        # Constraint: Kapasitas - Beban >= 0
        return (phi * Mn) - (Mu * 1e6) # Mu konversi ke Nmm

    def optimize_beam(self, Mu_kNm):
        # Initial Guess (Tebakan awal) [b=0.3, h=0.5, As=0.001]
        x0 = [0.3, 0.5, 0.0015] 
        
        # Batasan (Bounds)
        # b min 200mm, h min 300mm
        bounds = ((0.2, 0.8), (0.3, 1.0), (0.0005, 0.01)) 
        
        # Constraints Dictionary
        cons = ({'type': 'ineq', 'fun': self.constraint_capacity, 'args': (Mu_kNm,)})
        
        # Eksekusi SLSQP
        res = minimize(self.objective_function, x0, method='SLSQP', bounds=bounds, constraints=cons)
        
        if res.success:
            return {
                "b_opt": round(res.x[0] * 1000, 0), # mm
                "h_opt": round(res.x[1] * 1000, 0), # mm
                "As_opt": round(res.x[2] * 1e6, 2), # mm2
                "Cost": round(res.fun, 0)
            }
        else:
            return "Optimasi Gagal"
