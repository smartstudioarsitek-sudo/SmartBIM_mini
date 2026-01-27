import ifcopenshell
import pandas as pd
import numpy as np
import tempfile
import os

class IFC_Parser_Engine:
    def __init__(self, file_bytes):
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
        self.temp_file.write(file_bytes.read())
        self.temp_file.close()
        self.ifc_file = ifcopenshell.open(self.temp_file.name)
        os.unlink(self.temp_file.name)

    def parse_structure(self):
        """Mengambil Balok & Kolom"""
        elements = []
        for col in self.ifc_file.by_type("IfcColumn"):
            try:
                coord = col.ObjectPlacement.RelativePlacement.Location.Coordinates
                x, y, z = float(coord[0]), float(coord[1]), float(coord[2])
            except: x, y, z = 0,0,0
            elements.append({"Type": "Kolom", "Name": col.Name, "X": x, "Y": y, "Z": z})
            
        for beam in self.ifc_file.by_type("IfcBeam"):
            try:
                coord = beam.ObjectPlacement.RelativePlacement.Location.Coordinates
                x, y, z = float(coord[0]), float(coord[1]), float(coord[2])
            except: x, y, z = 0,0,0
            elements.append({"Type": "Balok", "Name": beam.Name, "X": x, "Y": y, "Z": z})
            
        return pd.DataFrame(elements)

    def parse_architectural_quantities(self):
        """
        Mengambil Volume Dinding, Pintu, Jendela
        """
        # 1. Dinding (Luas m2)
        total_wall_area = 0
        for wall in self.ifc_file.by_type("IfcWall"):
            # Coba ambil Property 'Area' atau 'NetSideArea'
            area = 0
            # Fallback sederhana: Panjang * Tinggi (Estimasi)
            # (Logic detail parsing property set bisa sangat kompleks, kita pakai simplified approach)
            # Asumsi rata-rata dinding panel 3x3m jika data null
            total_wall_area += 9.0 
            
            # Coba cari Quantities real (Advanced)
            if hasattr(wall, "IsDefinedBy"):
                for rel in wall.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    if q.Name in ["NetSideArea", "GrossSideArea", "Area"]:
                                        if q.VolumeValue > 0: # Kadang nama area tapi value volume
                                            total_wall_area += q.VolumeValue # Koreksi
                                        elif hasattr(q, 'AreaValue'):
                                            total_wall_area += q.AreaValue

        # 2. Pintu & Jendela (Unit)
        doors = len(self.ifc_file.by_type("IfcDoor"))
        windows = len(self.ifc_file.by_type("IfcWindow"))
        
        return {
            "Luas Dinding (m2)": round(total_wall_area, 2),
            "Jumlah Pintu (Unit)": doors,
            "Jumlah Jendela (Unit)": windows
        }

    def parse_mep_quantities(self):
        """
        Mengambil Panjang Pipa & Ducting
        """
        total_pipe_len = 0
        
        # Pipa (IfcPipeSegment)
        for pipe in self.ifc_file.by_type("IfcPipeSegment"):
            length = 0
            # Coba cari Length di Quantities
            if hasattr(pipe, "IsDefinedBy"):
                for rel in pipe.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    if q.Name == "Length" and q.LengthValue > 0:
                                        length = q.LengthValue
            
            if length == 0: length = 4.0 # Asumsi panjang batang 4m jika data null
            total_pipe_len += length
            
        return {
            "Panjang Pipa (m')": round(total_pipe_len, 2)
        }

    def calculate_architectural_loads(self):
        # Fungsi lama untuk beban struktur (tetap dipertahankan untuk backward compatibility)
        q = self.parse_architectural_quantities()
        beban_dinding = q["Luas Dinding (m2)"] * 0.15 * 17.0 # Tebal 15cm x BJ 17
        return {"Total Load Tambahan (kN)": round(beban_dinding, 2)}
