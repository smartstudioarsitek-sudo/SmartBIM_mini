from fpdf import FPDF
import matplotlib.pyplot as plt
import io

class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Laporan Perhitungan SmartBIMMini', 0, 1, 'C')
        self.ln(5)

    def render_math_formula(self, latex_str):
        """
        Ubah string LaTeX jadi Gambar PNG transparan
        """
        fig = plt.figure(figsize=(4, 1)) # Ukuran kanvas kecil
        fig.text(0.5, 0.5, f"${latex_str}$", fontsize=15, ha='center', va='center')
        plt.axis('off')
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', transparent=True)
        buf.seek(0)
        plt.close(fig)
        return buf

    def add_calculation_step(self, title, formula_latex, result_text):
        self.set_font('Arial', 'B', 10)
        self.cell(0, 10, title, 0, 1)
        
        # Render Rumus
        img_buffer = self.render_math_formula(formula_latex)
        
        # Tempel Gambar ke PDF (Trick: FPDF bisa baca BytesIO)
        self.image(img_buffer, w=60) 
        self.ln(5)
        
        self.set_font('Arial', '', 10)
        self.multi_cell(0, 5, result_text)
        self.ln(5)

# Contoh Penggunaan Nanti:
# pdf = PDFReport()
# pdf.add_page()
# pdf.add_calculation_step("1. Cek Kapasitas Momen", r"M_n = A_s f_y (d - a/2)", "Hasil perhitungan menunjukkan Mn = 150 kNm > Mu.")
# pdf.output("Laporan.pdf")
