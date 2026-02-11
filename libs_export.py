import pandas as pd
from io import BytesIO
import numpy as np

class Export_Engine:
    def __init__(self):
        pass

    def create_dxf(self, drawing_type, params):
        dxf = "0\nSECTION\n2\nENTITIES\n"
        
        def add_line(x1, y1, x2, y2, layer="STRUKTUR"):
            return f"0\nLINE\n8\n{layer}\n10\n{x1}\n20\n{y1}\n30\n0.0\n11\n{x2}\n21\n{y2}\n31\n0.0\n"
        
        def add_text(x, y, text, height=0.15, layer="TEXT"):
            return f"0\nTEXT\n8\n{layer}\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{height}\n1\n{text}\n"
        
        def add_circle(x, y, radius, layer="BESI"):
            return f"0\nCIRCLE\n8\n{layer}\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{radius}\n"

        if drawing_type == "BALOK":
            b = params['b'] / 1000; h = params['h'] / 1000; dia = params['dia'] / 1000
            # Beton
            dxf += add_line(0, 0, b, 0) + add_line(b, 0, b, h) + add_line(b, h, 0, h) + add_line(0, h, 0, 0)
            # Tulangan
            selimut = 0.04; y_pos = selimut + 0.01 + dia/2
            dxf += add_circle(selimut+0.01, y_pos, dia/2, "BESI") # Kiri
            dxf += add_circle(b-selimut-0.01, y_pos, dia/2, "BESI") # Kanan
            dxf += add_text(b/2-0.1, -0.2, f"{int(params['n'])} D{int(params['dia'])}")

        elif drawing_type == "FOOTPLATE":
            B = params['B']
            dxf += add_line(0, 0, B, 0) + add_line(B, 0, B, B) + add_line(B, B, 0, B) + add_line(0, B, 0, 0)
            dxf += add_text(B/2-0.2, -0.2, f"Pondasi {B}x{B}m")

        elif drawing_type == "TALUD":
            H = params['H']; Ba = params['Ba']; Bb = params['Bb']
            dxf += add_line(0, 0, Bb, 0) + add_line(Bb, 0, Bb, H) + add_line(Bb, H, Bb-Ba, H) + add_line(Bb-Ba, H, 0, 0)
            dxf += add_text(Bb/2, -0.5, f"Talud H={H}m")
            
        dxf += "0\nENDSEC\n0\nEOF"
        return dxf

    def create_excel_report(self, df_rab, session_data):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_rab.to_excel(writer, sheet_name='RAB Final', index=False)
            
            # Sheet Data Teknis
            tech_data = {'Parameter': ['Mutu Beton', 'Mutu Baja'], 'Nilai': [f"{session_data.get('fc',0)} MPa", f"{session_data.get('fy',0)} MPa"]}
            pd.DataFrame(tech_data).to_excel(writer, sheet_name='Data Teknis', index=False)
        return output.getvalue()
