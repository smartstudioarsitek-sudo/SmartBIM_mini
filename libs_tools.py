import libs_sni as sni
import libs_ahsp as ahsp
import libs_pondasi as fdn
import libs_geoteknik as geo

# --- INITIALIZE ENGINES ---
# Kita inisialisasi dengan nilai default, nanti AI bisa override parameter ini
calc_ahsp = ahsp.AHSP_Engine()
# Harga dummy untuk Budi Estimator (Idealnya ambil dari database real-time)
h_dasar = {'semen': 1500, 'pasir': 250000, 'split': 300000, 'besi': 14000, 
           'kayu': 2500000, 'batu kali': 280000, 'pekerja': 110000, 'tukang': 135000}

def tool_hitung_balok(b_mm, h_mm, fc, fy, mu_kNm, l_m):
    """
    [TOOL IR. SATRIA]
    Menghitung kebutuhan tulangan balok beton berdasarkan SNI 2847:2019.
    Input: b (mm), h (mm), fc (MPa), fy (MPa), Mu (kNm), L (m)
    """
    engine = sni.SNI_Concrete_2847(fc, fy)
    # 1. Hitung Tulangan Perlu
    as_req = engine.kebutuhan_tulangan(mu_kNm, b, h, 40) # ds asumsi 40mm
    
    # 2. Cek Tulangan Minimum (Safety Check)
    # (Logika ini sudah ada di libs_sni, kita bungkus jadi report teks)
    
    # 3. Konversi ke Jumlah Batang (Misal D16)
    dia_tul = 16
    n_bars = int(as_req / (0.25 * 3.14 * dia_tul**2)) + 1
    
    status = "AMAN" if n_bars < 10 else "TIDAK EFISIEN (Tulangan terlalu padat)"
    
    return {
        "output_text": f"Analisa Balok {b}x{h}mm (fc'{fc}):\n- Momen Perlu: {mu_kNm} kNm\n- Tulangan Perlu: {as_req:.2f} mm2\n- Rekomendasi: {n_bars} D{dia_tul}\n- Status: {status}",
        "data_teknis": {"b": b, "h": h, "as": as_req, "n_bars": n_bars, "fc": fc}
    }

def tool_estimasi_biaya_struktur(volume_beton, berat_besi):
    """
    [TOOL BUDI ESTIMATOR]
    Menghitung biaya struktur beton (Beton + Besi + Bekisting estimasi).
    """
    # Hitung HSP Real-time
    hsp_beton = calc_ahsp.hitung_hsp('beton_k250', h_dasar, h_dasar)
    hsp_besi = calc_ahsp.hitung_hsp('pembesian_polos', h_dasar, h_dasar) / 10 # per kg
    
    biaya_beton = volume_beton * hsp_beton
    biaya_besi = berat_besi * hsp_besi
    total = biaya_beton + biaya_besi
    
    return {
        "output_text": f"Estimasi Biaya Konstruksi:\n- Beton ({volume_beton:.2f} m3): Rp {biaya_beton:,.0f}\n- Besi ({berat_besi:.2f} kg): Rp {biaya_besi:,.0f}\n- TOTAL: Rp {total:,.0f}",
        "total_biaya": total
    }

def tool_cek_pondasi(beban_pu, lebar_m, daya_dukung):
    """
    [TOOL IR. SATRIA & GEOTEK]
    Cek keamanan pondasi telapak.
    """
    engine = fdn.Foundation_Engine(daya_dukung)
    res = engine.hitung_footplate(beban_pu, lebar_m, lebar_m, 300)
    
    return {
        "output_text": f"Analisa Pondasi {lebar_m}x{lebar_m}m:\n- Tegangan Tanah: {res['ratio_safety']:.2f} (SF)\n- Status: {res['status']}\n- Volume Beton: {res['vol_beton']:.2f} m3",
        "data_teknis": res
    }
