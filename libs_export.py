import pandas as pd
from io import BytesIO

class Export_Engine:
    def __init__(self):
        pass

    # ==========================================
    # 1. ENGINE PEMBUAT GAMBAR CAD (.DXF)
    # ==========================================
    def create_dxf(self, drawing_type, params):
        """
        Membuat script DXF sederhana (Text Based)
        Support: BALOK, FOOTPLATE, TALUD
        """
        # Header DXF Standar
        dxf = "0\nSECTION\n2\nENTITIES\n"
        
        def add_line(x1, y1, x2, y2, layer="STRUKTUR"):
            return f"0\nLINE\n8\n{layer}\n10\n{x1}\n20\n{y1}\n30\n0.0\n11\n{x2}\n21\n{y2}\n31\n0.0\n"
        
        def add_text(x, y, text, height=0.2):
            return f"0\nTEXT\n8\nTEXT\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{height}\n1\n{text}\n"

        # --- LOGIKA GAMBAR SESUAI TIPE ---
        
        if drawing_type == "BALOK":
            # Params: b (mm), h (mm), dia_tul, n_tul
            b = params['b'] / 1000 # convert to m
            h = params['h'] / 1000
            
            # Gambar Kotak Beton
            dxf += add_line(0, 0, b, 0)
            dxf += add_line(b, 0, b, h)
            dxf += add_line(b, h, 0, h)
            dxf += add_line(0, h, 0, 0)
            
            # Gambar Tulangan (Simbolis Kotak Kecil di Sudut)
            selimut = 0.04
            dxf += add_line(selimut, selimut, b-selimut, selimut, "TULANGAN") # Sengkang Bawah
            dxf += add_line(b-selimut, selimut, b-selimut, h-selimut, "TULANGAN")
            dxf += add_line(b-selimut, h-selimut, selimut, h-selimut, "TULANGAN")
            dxf += add_line(selimut, h-selimut, selimut, selimut, "TULANGAN")
            
            dxf += add_text(0, -0.2, f"DETAIL BALOK {int(params['b'])}x{int(params['h'])}")
            dxf += add_text(0, -0.5, f"Tulangan: {int(params['n'])} D{params['dia']}")

        elif drawing_type == "FOOTPLATE":
            # Params: B (m)
            B = params['B']
            
            # Gambar Denah (Atas)
            dxf += add_line(0, 0, B, 0)
            dxf += add_line(B, 0, B, B)
            dxf += add_line(B, B, 0, B)
            dxf += add_line(0, B, 0, 0)
            
            # Kolom Pedestal di Tengah
            k = 0.3 # Asumsi kolom 30cm
            x1, y1 = (B-k)/2, (B-k)/2
            dxf += add_line(x1, y1, x1+k, y1)
            dxf += add_line(x1+k, y1, x1+k, y1+k)
            dxf += add_line(x1+k, y1+k, x1, y1+k)
            dxf += add_line(x1, y1+k, x1, y1)
            
            dxf += add_text(0, -0.3, f"DENAH PONDASI {B}x{B}m")

        elif drawing_type == "TALUD":
            # Params: H, B_atas, B_bawah
            H = params['H']
            Ba = params['Ba']
            Bb = params['Bb']
            
            # Gambar Trapesium
            dxf += add_line(0, 0, Bb, 0)         # Bawah
            dxf += add_line(Bb, 0, Bb, H)        # Belakang Tegak
            dxf += add_line(Bb, H, Bb-Ba, H)     # Atas
            dxf += add_line(Bb-Ba, H, 0, 0)      # Miring Depan
            
            dxf += add_text(0, -0.3, f"POTONGAN TALUD H={H}m")
            
        # Footer DXF
        dxf += "0\nENDSEC\n0\nEOF"
        return dxf

    # ==========================================
    # 2. ENGINE PEMBUAT EXCEL (XLSX)
    # ==========================================
    def create_excel_report(self, df_rab, session_data):
        """
        Membuat Laporan Excel Multi-Sheet:
        Sheet 1: Rekap RAB
        Sheet 2: Detail Struktur
        Sheet 3: Detail Pondasi
        """
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # --- SHEET 1: RAB ---
            df_rab.to_excel(writer, sheet_name='RAB Final', index=False)
            
            # Formatting Sheet RAB
            workbook = writer.book
            worksheet = writer.sheets['RAB Final']
            money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1})
            
            worksheet.set_column('A:A', 30) # Lebar kolom Pek
            worksheet.set_column('B:D', 15, money_fmt)
            
            # --- SHEET 2: DATA TEKNIS ---
            # Mengambil data dari session_state yang dilempar
            tech_data = {
                'Parameter': ['Mutu Beton', 'Mutu Baja', 'Dimensi Balok', 'Daya Dukung Tanah'],
                'Nilai': [
                    f"fc {session_data.get('fc',0)} MPa", 
                    f"fy {session_data.get('fy',0)} MPa",
                    f"{session_data.get('b',0)}x{session_data.get('h',0)} mm",
                    f"{session_data.get('sigma',0)} kN/m2"
                ]
            }
            pd.DataFrame(tech_data).to_excel(writer, sheet_name='Data Teknis', index=False)
            
        return output.getvalue()