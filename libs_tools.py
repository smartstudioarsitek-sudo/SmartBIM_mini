import libs_sni as sni
import libs_ahsp as ahsp
import libs_pondasi as fdn
import libs_baja as steel

# --- WRAPPER FUNCTION AGAR BISA DIPANGGIL AI ---

def tool_hitung_balok(b_mm, h_mm, fc, fy, mu_kNm, l_m):
    """
    [TOOL IR. SATRIA] Menghitung tulangan balok beton (SNI 2847).
    """
    # Panggil Logic Lama Anda
    engine = sni.SNI_Concrete_2847(fc, fy)
    as_req = engine.kebutuhan_tulangan(mu_kNm, b_mm, h_mm, 40)
    
    # Hitung Rekomendasi Tulangan
    dia_tul = 16
    n_bars = int(as_req / (0.25 * 3.14 * dia_tul**2)) + 1
    
    return {
        "output_text": f"Analisa Balok {b_mm}x{h_mm}mm (fc'{fc}):\n- Momen Perlu: {mu_kNm} kNm\n- Tulangan Perlu: {as_req:.2f} mm2\n- Rekomendasi: {n_bars} D{dia_tul}",
        "data_teknis": {"as": as_req, "n": n_bars}
    }

def tool_cek_baja_wf(mu_kNm, bentang_m):
    """
    [TOOL IR. SATRIA] Cek kapasitas profil baja WF 300x150 standar.
    """
    # Panggil Logic Lama Anda
    wf_data = {'Zx': 481} # WF 300x150
    engine = steel.SNI_Steel_1729(240, 410) # BJ 37
    res = engine.cek_balok_lentur(mu_kNm, wf_data, bentang_m)
    return res

def tool_hitung_pondasi(beban_pu, lebar_m):
    """
    [TOOL GEOTEKNIK] Cek keamanan pondasi telapak.
    """
    # Panggil Logic Lama Anda
    engine = fdn.Foundation_Engine(150.0) # Daya dukung asumsi 150
    res = engine.hitung_footplate(beban_pu, lebar_m, lebar_m, 300)
    return res

def tool_estimasi_biaya(volume_beton):
    """
    [TOOL BUDI ESTIMATOR] Hitung biaya beton per m3.
    """
    engine = ahsp.AHSP_Engine()
    # Harga Dasar Dummy (Karena AI tidak baca sidebar)
    h_dasar = {'semen': 1500, 'pasir': 250000, 'split': 300000, 'pekerja': 110000, 'tukang': 135000}
    hsp = engine.hitung_hsp('beton_k250', h_dasar, h_dasar)
    total = volume_beton * hsp
    return {"HSP_Beton": hsp, "Total_Biaya": total}
