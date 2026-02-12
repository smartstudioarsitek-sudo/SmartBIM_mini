import pandas as pd
from io import BytesIO
import numpy as np

class Export_Engine:
    def __init__(self):
        pass

    def _dxf_header(self):
        return "0\nSECTION\n2\nENTITIES\n"

    def _dxf_footer(self):
        return "0\nENDSEC\n0\nEOF"

    def _dxf_line(self, x1, y1, x2, y2, layer="STRUKTUR"):
        return f"0\nLINE\n8\n{layer}\n10\n{x1}\n20\n{y1}\n30\n0.0\n11\n{x2}\n21\n{y2}\n31\n0.0\n"

    def _dxf_rect(self, cx, cy, b, h, layer="KOLOM"):
        # cx, cy adalah titik tengah
        # b, h dalam meter
        dx = b/2
        dy = h/2
        p1 = (cx - dx, cy - dy)
        p2 = (cx + dx, cy - dy)
        p3 = (cx + dx, cy + dy)
        p4 = (cx - dx, cy + dy)
        
        s = ""
        s += self._dxf_line(p1[0], p1[1], p2[0], p2[1], layer)
        s += self._dxf_line(p2[0], p2[1], p3[0], p3[1], layer)
        s += self._dxf_line(p3[0], p3[1], p4[0], p4[1], layer)
        s += self._dxf_line(p4[0], p4[1], p1[0], p1[1], layer)
        return s

    def _dxf_text(self, x, y, text, height=0.2, layer="TEXT"):
        return f"0\nTEXT\n8\n{layer}\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{height}\n1\n{text}\n"

    def _dxf_circle(self, x, y, radius, layer="BESI"):
        return f"0\nCIRCLE\n8\n{layer}\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{radius}\n"

    def generate_bim_dxf(self, df_structure):
        """
        [NEW] Generate Denah Struktur dari Data BIM (IFC)
        df_structure: DataFrame hasil parsing libs_bim_importer
        """
        content = self._dxf_header()
        
        if df_structure is not None and not df_structure.empty:
            count = 0
            for idx, row in df_structure.iterrows():
                try:
                    tipe = row['Type']
                    x = row['X']
                    y = row['Y']
                    # Z tidak dipakai untuk denah 2D
                    
                    if "Column" in tipe:
                        # Gambar Kolom sebagai Kotak 40x40cm (Default jika dimensi tidak terbaca)
                        # Idealnya dimensi dibaca dari properti, tapi untuk visualisasi cepat kita standarisasi
                        content += self._dxf_rect(x, y, 0.4, 0.4, layer="S-KOLOM")
                        content += self._dxf_text(x, y, "K1", height=0.15, layer="S-TAG")
                        
                    elif "Beam" in tipe:
                        # Balok agak susah digambar tanpa koordinat start/end yang jelas (saat ini kita cuma punya titik tengah)
                        # Kita beri tanda cross (+) saja sebagai indikasi balok
                        content += self._dxf_line(x-0.2, y, x+0.2, y, layer="S-BALOK")
                        content += self._dxf_line(x, y-0.2, x, y+0.2, layer="S-BALOK")
                    
                    elif "Wall" in tipe:
                        # Dinding sebagai garis panjang (Estimasi)
                        # Diplot sebagai titik kecil memanjang
                        content += self._dxf_circle(x, y, 0.05, layer="A-DINDING")
                        
                    count += 1
                except:
                    continue
                    
        content += self._dxf_footer()
        return content

    # --- FUNGSI LAMA (TETAP DIPERTAHANKAN UNTUK KOMPATIBILITAS) ---
    def create_dxf(self, drawing_type, params):
        dxf = self._dxf_header()

        if drawing_type == "BALOK":
            b = params['b'] / 1000; h = params['h'] / 1000; dia = params['dia'] / 1000
            # Beton
            dxf += self._dxf_line(0, 0, b, 0) + self._dxf_line(b, 0, b, h) + self._dxf_line(b, h, 0, h) + self._dxf_line(0, h, 0, 0)
            # Tulangan
            selimut = 0.04; y_pos = selimut + 0.01 + dia/2
            dxf += self._dxf_circle(selimut+0.01, y_pos, dia/2, "BESI") # Kiri
            dxf += self._dxf_circle(b-selimut-0.01, y_pos, dia/2, "BESI") # Kanan
            dxf += self._dxf_text(b/2-0.1, -0.2, f"{int(params['n'])} D{int(params['dia'])}")

        elif drawing_type == "FOOTPLATE":
            B = params['B']
            dxf += self._dxf_line(0, 0, B, 0) + self._dxf_line(B, 0, B, B) + self._dxf_line(B, B, 0, B) + self._dxf_line(0, B, 0, 0)
            dxf += self._dxf_text(B/2-0.2, -0.2, f"Pondasi {B}x{B}m")

        elif drawing_type == "TALUD":
            H = params['H']; Ba = params['Ba']; Bb = params['Bb']
            dxf += self._dxf_line(0, 0, Bb, 0) + self._dxf_line(Bb, 0, Bb, H) + self._dxf_line(Bb, H, Bb-Ba, H) + self._dxf_line(Bb-Ba, H, 0, 0)
            dxf += self._dxf_text(Bb/2, -0.5, f"Talud H={H}m")
            
        dxf += self._dxf_footer()
        return dxf

    def create_excel_report(self, df_rab, session_data):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_rab.to_excel(writer, sheet_name='RAB Final', index=False)
            
            # Sheet Data Teknis
            tech_data = {'Parameter': ['Mutu Beton', 'Mutu Baja'], 'Nilai': [f"{session_data.get('fc',0)} MPa", f"{session_data.get('fy',0)} MPa"]}
            pd.DataFrame(tech_data).to_excel(writer, sheet_name='Data Teknis', index=False)
        return output.getvalue()
