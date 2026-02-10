import libs_sni as sni
import libs_ahsp as ahsp
import libs_pondasi as fdn
import libs_baja as steel
import libs_gempa as quake
import libs_geoteknik as geo
import libs_optimizer as opt  # <--- IMPORT BARU

# --- 1. TOOL STRUKTUR BETON (SNI 2847) ---
def tool_hitung_balok(b_mm, h_mm, fc, fy, mu_kNm):
    """
    [TOOL SATRIA] Menghitung tulangan balok beton.
    """
    engine = sni.SNI_Concrete_2847(fc, fy)
    as_req = engine.kebutuhan_tulangan(mu_kNm, b_mm, h_mm, 40)
    dia_tul = 16
    n_bars = int(as_req / (0.25 * 3.14 * dia_tul**2)) + 1
    return f"Balok {b_mm}x{h_mm} (Mu={mu_kNm}kNm) butuh tulangan: {as_req:.2f} mm2. Rekomendasi: {n_bars} D{dia_tul}."

# --- 2. TOOL STRUKTUR BAJA (SNI 1729) ---
def tool_cek_baja_wf(mu_kNm, bentang_m):
    """
    [TOOL SATRIA] Cek kapasitas profil baja WF 300x150 (Default).
    """
    wf_data = {'Zx': 481} # WF 300x150
    engine = steel.SNI_Steel_1729(240, 410)
    res = engine.cek_balok_lentur(mu_kNm, wf_data, bentang_m)
    return f"Analisa WF 300x150: Ratio {res['Ratio']:.2f}. Status: {res['Status']}."

# --- 3. TOOL PONDASI (DANGKAL) ---
def tool_hitung_pondasi(beban_pu, lebar_m):
    """
    [TOOL GEOTEKNIK] Cek keamanan pondasi telapak (Footplate).
    """
    engine = fdn.Foundation_Engine(150.0)
    res = engine.hitung_footplate(beban_pu, lebar_m, lebar_m, 300)
    return f"Pondasi {lebar_m}x{lebar_m}m (Pu={beban_pu}kN): {res['status']}. Safety Factor: {res['ratio_safety']:.2f}."

# --- 4. TOOL ESTIMASI BIAYA (AHSP) ---
def tool_estimasi_biaya(volume_beton):
    """
    [TOOL BUDI] Hitung biaya beton per m3 (K-250).
    """
    engine = ahsp.AHSP_Engine()
    h_dasar = {'semen': 1500, 'pasir': 250000, 'split': 300000, 'pekerja': 110000, 'tukang': 135000}
    hsp = engine.hitung_hsp('beton_k250', h_dasar, h_dasar)
    total = volume_beton * hsp
    return f"Harga Satuan Beton K-250: Rp {hsp:,.0f}/m3. Total ({volume_beton} m3): Rp {total:,.0f}"

# --- 5. TOOL GEMPA (SNI 1726) ---
def tool_hitung_gempa_v(berat_total_kn, lokasi_tanah):
    """
    [TOOL GEMPA] Hitung Gaya Geser Dasar (V) Gempa.
    lokasi_tanah: 'Lunak' (SE), 'Sedang' (SD), atau 'Keras' (SC).
    """
    site_map = {'lunak': 'SE', 'sedang': 'SD', 'keras': 'SC'}
    kode_site = site_map.get(lokasi_tanah.lower(), 'SD')
    
    engine = quake.SNI_Gempa_1726(0.8, 0.4, kode_site)
    V, sds, sd1 = engine.hitung_base_shear(berat_total_kn, 8.0)
    return f"Analisa Gempa (Tanah {kode_site}): Base Shear V = {V:.2f} kN (SDS={sds:.2f})."

# --- 6. TOOL TALUD (GEOTEKNIK) ---
def tool_cek_talud(tinggi_m):
    """
    [TOOL GEOTEKNIK] Cek kestabilan dinding penahan tanah (Talud Batu Kali).
    """
    engine = geo.Geotech_Engine(18.0, 30.0, 5.0)
    res = engine.hitung_talud_batu_kali(tinggi_m, 0.4, 1.5)
    return f"Talud Tinggi {tinggi_m}m: SF Guling={res['SF_Guling']:.2f}, SF Geser={res['SF_Geser']:.2f}. Status: {res['Status']}."

# --- 7. TOOL OPTIMASI STRUKTUR (BARU) ---
def tool_cari_dimensi_optimal(mu_kNm, bentang_m):
    """
    [TOOL SATRIA] Mencari dimensi balok termurah & aman untuk beban tertentu.
    """
    # Harga asumsi default AI
    harga = {'beton': 1100000, 'baja': 14000, 'bekisting': 150000}
    
    optimizer = opt.BeamOptimizer(25, 400, harga) # Mutu default fc25 fy400
    hasil = optimizer.cari_dimensi_optimal(mu_kNm, bentang_m)
    
    if not hasil:
        return "Tidak ditemukan dimensi yang cocok (Beban terlalu besar atau bentang terlalu panjang)."
    
    # Format Jawaban AI
    best = hasil[0]
    return (f"SOLUSI OPTIMAL:\n"
            f"1. Dimensi: {best['b']}x{best['h']} mm\n"
            f"2. Estimasi Biaya: Rp {best['Biaya']:,.0f} per meter\n"
            f"3. Tulangan Perlu: {best['As']:.0f} mm2\n"
            f"Opsi Alternatif: {hasil[1]['b']}x{hasil[1]['h']} mm (Rp {hasil[1]['Biaya']:,.0f})")
