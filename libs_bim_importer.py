import ifcopenshell
import ifcopenshell.util.placement # Library sakti untuk koordinat
import pandas as pd
import numpy as np
import tempfile
import os

class IFC_Parser_Engine:
    def __init__(self, file_bytes):
        # 1. Simpan file sementara agar bisa dibaca ifcopenshell
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
        self.temp_file.write(file_bytes.read())
        self.temp_file.close()
        
        try:
            self.ifc_file = ifcopenshell.open(self.temp_file.name)
        except Exception as e:
            os.unlink(self.temp_file.name)
            raise ValueError(f"File IFC rusak atau tidak valid: {e}")
        
        # Hapus file temp setelah di-load ke memori
        os.unlink(self.temp_file.name)

    def get_absolute_coordinates(self, element):
        """
        Mengambil koordinat GLOBAL (X, Y, Z) elemen.
        Menggunakan matrix transformation untuk akurasi tinggi.
        """
        try:
            # Cara Canggih: Menggunakan utilitas bawaan ifcopenshell
            # Ini menghitung posisi absolut elemen terhadap titik 0,0,0 proyek
            matrix = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
            
            # Matrix 4x4, kolom ke-4 (index 3) adalah posisi X, Y, Z
            x = matrix[0][3]
            y = matrix[1][3]
            z = matrix[2][3]
            return float(x), float(y), float(z)
            
        except:
            # Cara Manual (Fallback): Menjumlahkan offset secara hierarki
            # (Kolom -> Lantai -> Gedung -> Site)
            x, y, z = 0.0, 0.0, 0.0
            try:
                placement = element.ObjectPlacement
                while placement is not None:
                    if placement.is_a("IfcLocalPlacement"):
                        rel_pl = placement.RelativePlacement
                        if rel_pl.is_a("IfcAxis2Placement3D"):
                            loc = rel_pl.Location.Coordinates
                            x += float(loc[0])
                            y += float(loc[1])
                            z += float(loc[2])
                    
                    # Naik ke parent placement
                    if hasattr(placement, "PlacementRelTo"):
                        placement = placement.PlacementRelTo
                    else:
                        placement = None
                return x, y, z
            except:
                return 0.0, 0.0, 0.0

    def parse_structure(self):
        """
        Mengambil Elemen Struktur (Balok & Kolom)
        Support IFC2x3 dan IFC4
        """
        elements = []
        
        # 1. Kolom (IfcColumn)
        for col in self.ifc_file.by_type("IfcColumn"):
            x, y, z = self.get_absolute_coordinates(col)
            name = col.Name if col.Name else "Unnamed Column"
            elements.append({"Type": "Kolom", "Name": name, "X": x, "Y": y, "Z": z})
            
        # 2. Balok (IfcBeam)
        for beam in self.ifc_file.by_type("IfcBeam"):
            x, y, z = self.get_absolute_coordinates(beam)
            name = beam.Name if beam.Name else "Unnamed Beam"
            elements.append({"Type": "Balok", "Name": name, "X": x, "Y": y, "Z": z})
            
        return pd.DataFrame(elements)

    def parse_architectural_quantities(self):
        """
        Mengambil Volume Dinding, Pintu, Jendela
        """
        total_wall_area = 0
        
        # Ambil IfcWall dan IfcWallStandardCase
        walls = self.ifc_file.by_type("IfcWall") 
        
        for wall in walls:
            area_found = False
            
            # Coba cari di Property Sets (NetSideArea / Area)
            if hasattr(wall, "IsDefinedBy"):
                for rel in wall.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    if q.Name in ["NetSideArea", "GrossSideArea", "Area"]:
                                        val = 0
                                        if hasattr(q, "AreaValue"): val = q.AreaValue
                                        elif hasattr(q, "VolumeValue"): val = q.VolumeValue # Kadang salah label
                                        
                                        if val > 0:
                                            total_wall_area += val
                                            area_found = True
                                            break
                    if area_found: break
            
            # Fallback Estimasi jika Property kosong
            if not area_found:
                total_wall_area += 9.0 # Asumsi panel 3x3m

        doors = len(self.ifc_file.by_type("IfcDoor"))
        windows = len(self.ifc_file.by_type("IfcWindow"))
        
        return {
            "Luas Dinding (m2)": round(total_wall_area, 2),
            "Jumlah Pintu (Unit)": doors,
            "Jumlah Jendela (Unit)": windows
        }

    def parse_mep_quantities(self):
        """
        Mengambil Panjang Pipa & Ducting.
        Support IFC2x3 (IfcFlowSegment) dan IFC4 (IfcPipeSegment)
        """
        total_pipe_len = 0
        schema_version = self.ifc_file.schema 
        mep_elements = []
        
        # Deteksi tipe elemen berdasarkan versi IFC
        if schema_version == "IFC4":
            try: mep_elements = self.ifc_file.by_type("IfcPipeSegment")
            except: mep_elements = self.ifc_file.by_type("IfcFlowSegment")
        else:
            try: mep_elements = self.ifc_file.by_type("IfcFlowSegment")
            except: mep_elements = []

        for item in mep_elements:
            length = 0
            # Coba cari Length di Quantities
            if hasattr(item, "IsDefinedBy"):
                for rel in item.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    if q.Name in ["Length", "NominalLength", "GrossLength"] and hasattr(q, "LengthValue"):
                                        if q.LengthValue > 0:
                                            length = q.LengthValue
                                            break
            
            if length == 0: length = 4.0 # Fallback
            total_pipe_len += length
            
        return {
            "Panjang Pipa (m')": round(total_pipe_len, 2)
        }

    def calculate_architectural_loads(self):
        # Helper untuk beban struktur
        q = self.parse_architectural_quantities()
        beban_dinding = q["Luas Dinding (m2)"] * 2.55 # Asumsi 15cm x 17kN/m3
        return {"Total Load Tambahan (kN)": round(beban_dinding, 2)}
