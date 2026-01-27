import ifcopenshell
import pandas as pd
import numpy as np
import tempfile
import os

class IFC_Parser_Engine:
    def __init__(self, file_bytes):
        # Trik Streamlit: IFC perlu path file fisik, bukan bytes memory
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
        self.temp_file.write(file_bytes.read())
        self.temp_file.close()
        
        # Load IFC
        self.ifc_file = ifcopenshell.open(self.temp_file.name)
        
        # Hapus file temp
        os.unlink(self.temp_file.name)

    def parse_structure(self):
        """
        Mengambil Balok & Kolom untuk jadi Model Analisa
        """
        elements = []
        
        # 1. Ambil Kolom (IfcColumn)
        cols = self.ifc_file.by_type("IfcColumn")
        for col in cols:
            # Simplifikasi: Ambil koordinat pusat (Placement)
            coord = col.ObjectPlacement.RelativePlacement.Location.Coordinates
            # Ambil Property Sets (untuk dimensi jika ada)
            # Default fallback dimensions
            b, h = 0.3, 0.3 
            
            elements.append({
                "Type": "Kolom",
                "Name": col.Name,
                "X": float(coord[0]),
                "Y": float(coord[1]),
                "Z": float(coord[2]),
                "b": b, "h": h
            })

        # 2. Ambil Balok (IfcBeam)
        beams = self.ifc_file.by_type("IfcBeam")
        for beam in beams:
            coord = beam.ObjectPlacement.RelativePlacement.Location.Coordinates
            elements.append({
                "Type": "Balok",
                "Name": beam.Name,
                "X": float(coord[0]),
                "Y": float(coord[1]),
                "Z": float(coord[2]),
                "b": 0.25, "h": 0.5 # Default
            })
            
        return pd.DataFrame(elements)

    def calculate_architectural_loads(self):
        """
        Mengubah Dinding & Lantai Arsitek menjadi Beban (kN)
        Logika: Cari IfcWall -> Hitung Volume -> Kali Berat Jenis Bata
        """
        beban_arsitek = 0
        
        # Berat Jenis Material (Asumsi SNI 1727)
        bj_bata = 17.0 # kN/m3 (Dinding setengah bata)
        bj_finishing = 22.0 # kN/m3 (Keramik/Spesi)
        
        # 1. Dinding (IfcWall)
        walls = self.ifc_file.by_type("IfcWall")
        for w in walls:
            # Cara Cepat Hitung Volume di IFC (Quantity Sets)
            # Jika Quantities tidak diexport Revit, kita estimasi kasar
            # Disini kita pakai logic simpel: Asumsi 1 dinding rata2 3x3m tebal 0.15
            vol_est = 3.0 * 3.0 * 0.15 
            
            # Coba cari Quantities real jika ada (Advanced)
            for relDefines in w.IsDefinedBy:
                if relDefines.is_a("IfcRelDefinesByProperties"):
                    if hasattr(relDefines, "RelatingPropertyDefinition"):
                        props = relDefines.RelatingPropertyDefinition
                        if props.is_a("IfcElementQuantity"):
                            for q in props.Quantities:
                                if q.Name == "NetVolume":
                                    vol_est = q.VolumeValue
            
            berat_dinding = vol_est * bj_bata
            beban_arsitek += berat_dinding
            
        # 2. MEP (IfcPipeSegment, IfcDuctSegment)
        # Asumsi beban MEP rata-rata 10% dari beban arsitek
        beban_mep = beban_arsitek * 0.10
        
        return {
            "Total Beban Dinding (kN)": round(beban_arsitek, 2),
            "Estimasi Beban MEP (kN)": round(beban_mep, 2),
            "Total Load Tambahan (kN)": round(beban_arsitek + beban_mep, 2)
        }