import pandas as pd
from io import BytesIO
import numpy as np

class Export_Engine:
    def __init__(self):
        pass

    # ==========================================
    # 1. CORE DXF GENERATOR (LOW LEVEL)
    # ==========================================
    def create_dxf(self, drawing_type, params):
        # Header DXF Standar
        dxf = "0\nSECTION\n2\nENTITIES\n"
        
        # --- Helper Functions ---
        def add_line(x1, y1, x2, y2, layer="STRUKTUR"):
            return f"0\nLINE\n8\n{layer}\n10\n{x1}\n20\n{y1}\n30\n0.0\n11\n{x2}\n21\n{y2}\n31\n0.0\n"
        
        def add_text(x, y, text, height=0.15, layer="TEXT"):
            return f"0\nTEXT\n8\n{layer}\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{height}\n1\n{text}\n"
        
        def add_circle(x, y, radius, layer="BESI"):
            return f"0\nCIRCLE\n8\n{layer}\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{radius}\n"

        def add_dim_linear(x1, y1, x2, y2, text_offset=0.3):
            # Simple manual dimension lines
            mid_x, mid_y = (x1+x2)/2, (y1+y2)/2
            dist = np.sqrt((x2-x1)**2 + (y2-y1)**2)
            dxf_code = add_line(x1, y1, x1, y1+text_offset, "DIM") # Kaki 1
            dxf_code += add_line(x2, y2, x2, y2+text_offset, "DIM") # Kaki 2
            dxf_code += add_line(x1, y1+text_offset*0.8, x2, y2+text_offset*0.8, "DIM") # Garis Dim
            dxf_code += add_text(mid_x-0.1, mid_y+text_offset, f"{dist*1000:.0f}", 0.1) # Text mm
            return dxf_code

        # --- LOGIKA GAMBAR KOMPLEKS ---
        
        if drawing_type == "BALOK":
            # Params: b, h, dia_tul (mm), n_tul (int), pjg (m)
            b = params['b'] / 1000
            h = params['h'] / 1000
            dia = params['dia'] / 1000 # convert mm to m
            n = int(params['n'])
            selimut = 0.04 # 40mm
            
            # 1. POTONGAN MELINTANG (CROSS SECTION) @ X=0
            # Beton
            dxf += add_line(0, 0, b, 0)
            dxf += add_line(b, 0, b, h)
            dxf += add_line(b, h, 0, h)
            dxf += add_line(0, h, 0, 0)
            
            # Sengkang (Stirrup) - Offset selimut
            s_w = b - 2*selimut
            s_h = h - 2*selimut
            dxf += add_line(selimut, selimut, selimut+s_w, selimut, "SENGKANG")
            dxf += add_line(selimut+s_w, selimut, selimut+s_w, selimut+s_h, "SENGKANG")
            dxf += add_line(selimut+s_w, selimut+s_h, selimut, selimut+s_h, "SENGKANG")
            dxf += add_line(selimut, selimut+s_h, selimut, selimut, "SENGKANG")
            
            # Tulangan Utama (Main Bars)
            # Distribusi besi secara merata di sisi bawah (Tarik)
            y_pos = selimut + 0.01 + dia/2 # Posisi Y (bawah + sengkang)
            
            if n > 1:
                spacing = (b - 2*selimut - 2*0.01 - dia) / (n - 1)
                for i in range(n):
                    x_pos = selimut + 0.01 + dia/2 + (i * spacing)
                    dxf += add_circle(x_pos, y_pos, dia/2, "BESI_ULIR")
            else:
                # Minimal 2 besi sudut
                dxf += add_circle(selimut+0.015, y_pos, dia/2, "BESI_ULIR")
                dxf += add_circle(b-selimut-0.015, y_pos, dia/2, "BESI_ULIR")

            # Besi Pinggang/Atas (Dummy 2 buah diameter 10)
            dxf += add_circle(selimut+0.015, h-y_pos, 0.005, "BESI_POLOS")
            dxf += add_circle(b-selimut-0.015, h-y_pos, 0.005, "BESI_POLOS")
            
            # Judul
            dxf += add_text(b/2 - 0.2, -0.3, "POTONGAN A-A", 0.15)
            dxf += add_text(b/2 - 0.2, -0.5, f"{int(params['b'])} x {int(params['h'])} mm")
            
            # Notasi Besi
            dxf += add_line(b/2, y_pos, b/2, -0.15, "LEADER") # Garis penunjuk
            dxf += add_text(b/2 + 0.05, -0.15, f"{n} D{int(params['dia'])}")
            
            # 2. POTONGAN MEMANJANG (LONG SECTION) @ X = b + 1.0
            start_x = b + 1.0
            L = 3.0 # Gambar potongan sepanjang 3m saja sbg representasi
            
            # Garis Beton
            dxf += add_line(start_x, 0, start_x+L, 0) # Bawah
            dxf += add_line(start_x, h, start_x+L, h) # Atas
            # Garis Putus (Cut line)
            dxf += add_line(start_x, -0.1, start_x, h+0.1)
            dxf += add_line(start_x+L, -0.1, start_x+L, h+0.1)
            
            # Garis Tulangan Utama (Memanjang)
            dxf += add_line(start_x, y_pos, start_x+L, y_pos, "BESI_ULIR") # Bawah
            dxf += add_line(start_x, h-y_pos, start_x+L, h-y_pos, "BESI_POLOS") # Atas
            
            # Sengkang (Jarak 150mm / 0.15m)
            sengkang_dist = 0.15
            num_sengkang = int(L / sengkang_dist)
            for i in range(num_sengkang):
                x_s = start_x + (i * sengkang_dist) + 0.05
                dxf += add_line(x_s, selimut, x_s, h-selimut, "SENGKANG")
                
            dxf += add_dim_linear(start_x, h+0.1, start_x+sengkang_dist, h+0.1, 0.2)
            dxf += add_text(start_x + sengkang_dist/2, h+0.4, "Ø8-150")
            
            dxf += add_text(start_x + L/2 - 0.5, -0.5, "POTONGAN MEMANJANG")

        elif drawing_type == "FOOTPLATE":
            B = params['B'] # Lebar Pondasi (m)
            H = 0.3 # Tebal plat
            k = 0.3 # Lebar kolom
            
            # 1. DENAH (PLAN VIEW)
            # Kotak Luar
            dxf += add_line(0, 0, B, 0)
            dxf += add_line(B, 0, B, B)
            dxf += add_line(B, B, 0, B)
            dxf += add_line(0, B, 0, 0)
            
            # Grid Pembesian (Jarak 15cm)
            spc = 0.15
            num_bar = int(B / spc)
            for i in range(num_bar + 1):
                pos = i * spc
                if pos > B: break
                # Horizontal bars
                dxf += add_line(0, pos, B, pos, "BESI")
                # Vertical bars
                dxf += add_line(pos, 0, pos, B, "BESI")
            
            # Kolom Tengah
            c1 = (B - k)/2
            dxf += add_line(c1, c1, c1+k, c1, "KOLOM")
            dxf += add_line(c1+k, c1, c1+k, c1+k, "KOLOM")
            dxf += add_line(c1+k, c1+k, c1, c1+k, "KOLOM")
            dxf += add_line(c1, c1+k, c1, c1, "KOLOM")
            
            dxf += add_text(B/2 - 0.2, -0.3, f"DENAH PONDASI {B}x{B}m")
            dxf += add_text(B/2 - 0.2, -0.5, "Tulangan: D13-150")

            # 2. POTONGAN (SECTION) @ X = B + 1.0
            sx = B + 1.0
            # Bentuk Trapesium Pondasi
            dxf += add_line(sx, 0, sx+B, 0) # Bawah
            dxf += add_line(sx, 0, sx, H) # Kiri Tegak
            dxf += add_line(sx+B, 0, sx+B, H) # Kanan Tegak
            dxf += add_line(sx, H, sx+c1, H+0.2) # Miring Kiri
            dxf += add_line(sx+B, H, sx+c1+k, H+0.2) # Miring Kanan
            dxf += add_line(sx+c1, H+0.2, sx+c1+k, H+0.2) # Atas (Leher Kolom)
            
            # Besi Bawah
            selimut = 0.05
            dxf += add_line(sx+selimut, selimut, sx+B-selimut, selimut, "BESI_UTAMA")
            # Kaki Besi (Hook)
            dxf += add_line(sx+selimut, selimut, sx+selimut, H-selimut, "BESI_UTAMA")
            dxf += add_line(sx+B-selimut, selimut, sx+B-selimut, H-selimut, "BESI_UTAMA")
            
            # Stek Kolom
            dxf += add_line(sx+c1+0.05, selimut, sx+c1+0.05, H+1.0, "STEK")
            dxf += add_line(sx+c1+k-0.05, selimut, sx+c1+k-0.05, H+1.0, "STEK")
            
            dxf += add_text(sx + B/2 - 0.2, -0.3, "POTONGAN PONDASI")

        elif drawing_type == "TALUD":
            H = params['H']
            Ba = params['Ba']
            Bb = params['Bb']
            
            # Gambar Trapesium Batu Kali
            dxf += add_line(0, 0, Bb, 0)
            dxf += add_line(Bb, 0, Bb, H)
            dxf += add_line(Bb, H, Bb-Ba, H)
            dxf += add_line(Bb-Ba, H, 0, 0)
            
            # Pipa Sulingan (Drainase)
            for h_pipe in range(1, int(H)):
                y_p = h_pipe
                x_p = (y_p / H) * (Bb-Ba) # Interpolasi kemiringan
                dxf += add_circle(x_p + 0.3, y_p, 0.05, "PIPA")
                dxf += add_text(x_p + 0.4, y_p, "Pipa PVC 2''")

            dxf += add_text(Bb/2, -0.5, f"DETAIL TALUD BATU KALI H={H}m")
            
        # Footer DXF
        dxf += "0\nENDSEC\n0\nEOF"
        return dxf

    # ==========================================
    # 2. EXCEL REPORT (SAMA SEPERTI SEBELUMNYA)
    # ==========================================
    def create_excel_report(self, df_rab, session_data):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_rab.to_excel(writer, sheet_name='RAB Final', index=False)
            workbook = writer.book
            worksheet = writer.sheets['RAB Final']
            money_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
            worksheet.set_column('A:A', 30)
            worksheet.set_column('B:D', 15, money_fmt)
            
            tech_data = {'Parameter': ['Mutu Beton', 'Mutu Baja', 'Dimensi Balok', 'Daya Dukung Tanah'],
                         'Nilai': [f"fc {session_data.get('fc',0)} MPa", f"fy {session_data.get('fy',0)} MPa",
                                   f"{session_data.get('b',0)}x{session_data.get('h',0)} mm", f"{session_data.get('sigma',0)} kN/m2"]}
            pd.DataFrame(tech_data).to_excel(writer, sheet_name='Data Teknis', index=False)
        return output.getvalue()
