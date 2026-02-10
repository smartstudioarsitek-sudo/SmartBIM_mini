from fpdf import FPDF
import matplotlib.pyplot as plt
import io
import datetime

# Setting Matplotlib agar aman di Server (Non-GUI)
plt.switch_backend('Agg')

class PDFReport(FPDF):
    def header(self):
        # 1. Judul / Kop Surat
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'ENGINEX TITAN - REPORT', 0, 1, 'C')
        
        self.set_font('Arial', 'I', 10)
        self.cell(0, 5, 'Laporan Perhitungan Struktur & Estimasi Biaya', 0, 1, 'C')
        
        # Garis Bawah Kop
        self.line(10, 25, 200, 25)
        self.ln(15)

    def footer(self):
        # Posisi 1.5 cm dari bawah
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Halaman {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, label):
        # Judul Bab (misal: "I. Analisa Struktur")
        self.set_font('Arial', 'B', 12)
        self.set_fill_color(230, 230, 230) # Abu-abu muda
        self.cell(0, 10, f"{label}", 0, 1, 'L', True)
        self.ln(5)

    def chapter_body(self, text):
        # Isi Paragraf
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 6, text)
        self.ln(5)

    def render_math_formula(self, latex_str):
        """
        Trik: Mengubah string LaTeX menjadi Gambar PNG Transparan
        menggunakan Matplotlib, lalu ditempel ke PDF.
        """
        # Buat Kanvas Kosong
        fig = plt.figure(figsize=(6, 1.5))
        # Tulis Rumus LaTeX di tengah
        fig.text(0.5, 0.5, f"${latex_str}$", fontsize=16, ha='center', va='center')
        plt.axis('off') # Hilangkan sumbu X/Y
        
        # Simpan ke Buffer Memori (bukan file fisik)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', transparent=True)
        buf.seek(0)
        plt.close(fig)
        
        return buf

    def add_math_block(self, title, formula, result):
        """
        Blok khusus untuk menampilkan: Judul -> Rumus Matematika -> Hasil
        """
        self.set_font('Arial', 'B', 10)
        self.cell(0, 8, title, 0, 1)
        
        # Render Rumus jadi Gambar
        img_buf = self.render_math_formula(formula)
        
        # Tempel Gambar ke PDF (Trik FPDF baca BytesIO)
        # x=None (center), w=0 (auto width scale)
        self.image(img_buf, x=20, w=100) 
        
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, f"Hasil: {result}")
        self.ln(5)

# ==============================================================================
# FUNGSI UTAMA GENERATE PDF DARI SESSION STATE
# ==============================================================================
def create_professional_report(session_state):
    pdf = PDFReport()
    pdf.add_page()
    
    # --- BAGIAN 1: INFORMASI PROYEK ---
    pdf.chapter_title("I. DATA PROYEK & INPUT")
    
    # Ambil data aman (pakai .get biar tidak error jika kosong)
    geo = session_state.get('geo', {})
    
    tgl = datetime.datetime.now().strftime("%d %B %Y")
    
    info_text = (
        f"Tanggal Laporan : {tgl}\n"
        f"Standar Desain  : SNI 2847:2019 (Beton), SNI 1726:2019 (Gempa)\n"
        f"Metode Analisa  : Analisa Statik Ekuivalen & Desain Kapasitas\n"
        f"Dimensi Balok   : {geo.get('b', 0)} x {geo.get('h', 0)} mm\n"
        f"Panjang Bentang : {geo.get('L', 0)} meter"
    )
    pdf.chapter_body(info_text)
    
    # --- BAGIAN 2: ANALISA STRUKTUR BETON (BALOK) ---
    pdf.chapter_title("II. ANALISA STRUKTUR BETON (BALOK)")
    
    struk = session_state.get('report_struk', {})
    
    if struk:
        pdf.chapter_body(f"Elemen Balok dianalisis terhadap kombinasi beban terfaktor (1.2DL + 1.6LL).")
        
        # 1. Momen Ultimate
        mu_val = struk.get('Mu', 0)
        pdf.add_math_block(
            "1. Momen Terfaktor (Mu)",
            r"M_u = \frac{1}{8} q_u L^2", 
            f"{mu_val} kNm"
        )
        
        # 2. Kapasitas Tulangan
        tul = struk.get('Tulangan', '-')
        pdf.add_math_block(
            "2. Kebutuhan Tulangan (As)",
            r"A_s = \frac{M_u}{\phi \cdot f_y \cdot (d - a/2)}", 
            f"Didesain menggunakan tulangan: {tul}"
        )
    else:
        pdf.chapter_body("Belum ada data analisa struktur yang dilakukan.")

    # --- BAGIAN 3: ANALISA BAJA & GEMPA ---
    pdf.chapter_title("III. ANALISA LANJUTAN (BAJA & GEMPA)")
    
    # Baja
    baja = session_state.get('report_baja', {})
    if baja:
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(0, 8, f"Analisa Baja Profil {baja.get('Profil')}", 0, 1)
        pdf.set_font('Arial', '', 10)
        pdf.cell(0, 6, f"Momen Beban: {baja.get('Mu')} kNm", 0, 1)
        pdf.cell(0, 6, f"Kapasitas Momen (Phi Mn): {baja.get('Phi_Mn')} kNm", 0, 1)
        pdf.cell(0, 6, f"Rasio Tegangan (DCR): {baja.get('Ratio')}", 0, 1)
        pdf.cell(0, 6, f"Status: {baja.get('Status')}", 0, 1)
        pdf.ln(5)
    
    # Gempa
    gempa = session_state.get('report_gempa', {})
    if gempa:
        pdf.add_math_block(
            "Gaya Geser Dasar Gempa (Base Shear)",
            r"V = C_s \cdot W = \frac{S_{DS}}{(R/I_e)} \cdot W",
            f"V = {gempa.get('V_gempa')} kN (Tanah {gempa.get('Site')})"
        )

    # --- BAGIAN 4: REKAPITULASI BIAYA (RAB) ---
    pdf.add_page()
    pdf.chapter_title("IV. ESTIMASI BIAYA KONSTRUKSI (RAB)")
    
    pdf.chapter_body("Berikut adalah ringkasan estimasi volume utama:")
    
    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(100, 10, "Uraian Pekerjaan", 1, 0, 'C', True)
    pdf.cell(40, 10, "Volume", 1, 0, 'C', True)
    pdf.cell(50, 10, "Satuan", 1, 1, 'C', True)
    
    s_vol = session_state.get('structure', {}).get('vol_beton', 0)
    p_vol = session_state.get('pondasi', {}).get('fp_beton', 0)
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(100, 8, "Pek. Beton Struktur Atas", 1, 0)
    pdf.cell(40, 8, f"{s_vol:.2f}", 1, 0, 'C')
    pdf.cell(50, 8, "m3", 1, 1, 'R')
    
    pdf.cell(100, 8, "Pek. Beton Pondasi", 1, 0)
    pdf.cell(40, 8, f"{p_vol:.2f}", 1, 0, 'C')
    pdf.cell(50, 8, "m3", 1, 1, 'R')
    
    pdf.ln(10)
    pdf.set_font('Arial', 'I', 10)
    pdf.multi_cell(0, 6, "Catatan: Harga total detail dapat dilihat pada lampiran Excel RAB yang terpisah.")

    # Output ke Bytes (Fixed for FPDF2)
    return bytes(pdf.output())
