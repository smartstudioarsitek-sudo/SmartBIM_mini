import pandas as pd

class AHSP_Engine:
    """
    Database Koefisien Analisa Harga Satuan Pekerjaan (AHSP)
    Mengacu pada Permen PUPR & SE Dirjen Cipta Karya Terbaru
    """
    def __init__(self):
        # Database Koefisien (Contoh sebagian item umum)
        self.koefisien = {
            "beton_k250": {
                "desc": "Membuat 1 m3 Beton Mutu f'c=21.7 MPa (K-250)",
                "bahan": {"Semen (kg)": 384, "Pasir (m3)": 0.494, "Split (m3)": 0.77},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },
            "beton_k175": {
                "desc": "Membuat 1 m3 Beton Mutu f'c=14.5 MPa (K-175)",
                "bahan": {"Semen (kg)": 326, "Pasir (m3)": 0.54, "Split (m3)": 0.76},
                "upah": {"Pekerja": 1.65, "Tukang": 0.275, "Mandor": 0.083}
            },
            "bekisting_balok": {
                "desc": "Pemasangan 1 m2 Bekisting Balok (Kayu)",
                "bahan": {"Kayu Kelas III (m3)": 0.04, "Paku (kg)": 0.4, "Minyak Bekisting (L)": 0.2},
                "upah": {"Pekerja": 0.66, "Tukang": 0.33, "Mandor": 0.033}
            },
            "pembesian_polos": {
                "desc": "Pembesian 10 kg dengan Besi Polos/Ulir",
                "bahan": {"Besi Beton (kg)": 10.5, "Kawat Beton (kg)": 0.15}, # 10.5 inc waste
                "upah": {"Pekerja": 0.07, "Tukang": 0.07, "Mandor": 0.004}
            }, # <--- KOMA DITAMBAHKAN DISINI
            "pasangan_batu_kali": {
                "desc": "Pasangan Batu Kali 1:4 (Talud)",
                "bahan": {"Batu Kali (m3)": 1.2, "Semen (kg)": 163, "Pasir (m3)": 0.52},
                "upah": {"Pekerja": 1.5, "Tukang": 0.75, "Mandor": 0.075}
            },
            "bore_pile_k300": {
                "desc": "Pengecoran Bore Pile K-300 (Site Mix/Ready Mix)",
                "bahan": {"Beton K300 (m3)": 1.05}, # Waste 5%
                "upah": {"Pekerja": 2.0, "Tukang": 0.5, "Mandor": 0.1} # Upah cor manual/alat bantu
            },
            "penulangan_pile": {
                "desc": "Pembesian Spiral & Utama Pile",
                "bahan": {"Besi Beton (kg)": 10.5, "Kawat Beton (kg)": 0.2},
                "upah": {"Pekerja": 0.07, "Tukang": 0.07, "Mandor": 0.004}
            }
        }

    def hitung_hsp(self, kode_analisa, harga_bahan_dasar, harga_upah_dasar):
        """
        Menghitung Harga Satuan Pekerjaan (HSP) berdasarkan input harga dasar user.
        """
        if kode_analisa not in self.koefisien:
            return 0
        
        data = self.koefisien[kode_analisa]
        total_bahan = 0
        total_upah = 0
        
        # Hitung Bahan
        for item, koef in data['bahan'].items():
            # Cari harga yang cocok dari input user (Simple matching)
            key_clean = item.split(" (")[0].lower() # misal "Semen" dari "Semen (kg)"
            
            # Logic pencocokan harga (Bisa dipercanggih)
            h_satuan = 0
            if "semen" in key_clean: h_satuan = harga_bahan_dasar.get('semen', 0)
            elif "pasir" in key_clean: h_satuan = harga_bahan_dasar.get('pasir', 0)
            elif "split" in key_clean: h_satuan = harga_bahan_dasar.get('split', 0)
            elif "kayu" in key_clean: h_satuan = harga_bahan_dasar.get('kayu', 0)
            elif "besi" in key_clean: h_satuan = harga_bahan_dasar.get('besi', 0)
            elif "batu kali" in key_clean: h_satuan = harga_bahan_dasar.get('batu kali', 0)
            elif "beton" in key_clean: h_satuan = harga_bahan_dasar.get('beton k300', 0) # Fallback for readymix
            
            total_bahan += koef * h_satuan
            
        # Hitung Upah
        for item, koef in data['upah'].items():
            item_lower = item.lower()
            h_upah = harga_upah_dasar.get(item_lower, 0)
            total_upah += koef * h_upah
            
        return total_bahan + total_upah
