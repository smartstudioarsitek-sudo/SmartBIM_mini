import ifcopenshell
import pandas as pd
import numpy as np
import tempfile
import os

class IFC_Parser_Engine:
    def __init__(self, file_bytes):
        # Simpan file sementara agar bisa dibaca ifcopenshell
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
        self.temp_file.write(file_bytes.read())
        self.temp_file.close()
        try:
            self.ifc_file = ifcopenshell.open(self.temp_file.name)
        except Exception as e:
            os.unlink(self.temp_file.name)
            raise ValueError(f"File tidak valid atau rusak: {e}")
        
        os.unlink(self.temp_file.name)

    def parse_structure(self):
        """
        Mengambil Elemen Struktur (Balok & Kolom)
        Support IFC2x3 dan IFC4
        """
        elements = []
        
        # 1. Kolom (IfcColumn) - Tersedia di semua versi IFC
        for col in self.ifc_file.by_type("IfcColumn"):
            x, y, z = 0, 0, 0
            try:
                # Coba ambil koordinat placement
                if col.ObjectPlacement and col.ObjectPlacement.RelativePlacement:
                    loc = col.ObjectPlacement.RelativePlacement.Location
                    if hasattr(loc, "Coordinates"):
                        coord = loc.Coordinates
                        x, y, z = float(coord[0]), float(coord[1]), float(coord[2])
            except:
                pass # Default 0,0,0 jika gagal parsing geo
                
            elements.append({"Type": "Kolom", "Name": col.Name if col.Name else "Unnamed Column", "X": x, "Y": y, "Z": z})
            
        # 2. Balok (IfcBeam) - Tersedia di semua versi IFC
        for beam in self.ifc_file.by_type("IfcBeam"):
            x, y, z = 0, 0, 0
            try:
                if beam.ObjectPlacement and beam.ObjectPlacement.RelativePlacement:
                    loc = beam.ObjectPlacement.RelativePlacement.Location
                    if hasattr(loc, "Coordinates"):
                        coord = loc.Coordinates
                        x, y, z = float(coord[0]), float(coord[1]), float(coord[2])
            except:
                pass
            elements.append({"Type": "Balok", "Name": beam.Name if beam.Name else "Unnamed Beam", "X": x, "Y": y, "Z": z})
            
        return pd.DataFrame(elements)

    def parse_architectural_quantities(self):
        """
        Mengambil Volume Dinding, Pintu, Jendela
        """
        # 1. Dinding (Luas m2)
        total_wall_area = 0
        walls = self.ifc_file.by_type("IfcWall") # Mengambil IfcWall dan IfcWallStandardCase
        
        for wall in walls:
            area_found = False
            
            # Metode 1: Cari di Property Sets (Qto_WallBaseQuantities)
            if hasattr(wall, "IsDefinedBy"):
                for rel in wall.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    # Prioritaskan NetSideArea (Luas Bersih) atau Area
                                    if q.Name in ["NetSideArea", "GrossSideArea", "Area"]:
                                        val = 0
                                        if hasattr(q, "AreaValue"): val = q.AreaValue
                                        elif hasattr(q, "VolumeValue") and q.VolumeValue < 100: val = q.VolumeValue # Kadang salah label
                                        
                                        if val > 0:
                                            total_wall_area += val
                                            area_found = True
                                            break
                    if area_found: break
            
            # Metode 2: Fallback jika tidak ada Quantity Sets (Estimasi Kasar)
            if not area_found:
                # Asumsi panel dinding standar 3x3m = 9m2 per item
                total_wall_area += 9.0 

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
        Mengambil Panjang Pipa & Ducting.
        FIX: Support IFC2x3 (IfcFlowSegment) dan IFC4 (IfcPipeSegment)
        """
        total_pipe_len = 0
        
        # --- DETEKSI SCHEMA ---
        schema_version = self.ifc_file.schema # Return string misal 'IFC2X3' atau 'IFC4'
        
        mep_elements = []
        
        # --- STRATEGI PENGAMBILAN DATA ---
        if schema_version == "IFC4":
            # Di IFC4, Pipa sudah punya entity sendiri
            try:
                mep_elements = self.ifc_file.by_type("IfcPipeSegment")
            except:
                mep_elements = self.ifc_file.by_type("IfcFlowSegment") # Fallback
        else:
            # Di IFC2x3, Pipa, Duct, CableTray semua adalah IfcFlowSegment
            # Kita ambil semua FlowSegment sebagai estimasi MEP
            try:
                mep_elements = self.ifc_file.by_type("IfcFlowSegment")
            except:
                mep_elements = []

        # --- HITUNG PANJANG ---
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
            
            # Fallback jika length 0 (Asumsi panjang per batang standar 4m)
            if length == 0: length = 4.0 
            
            total_pipe_len += length
            
        return {
            "Panjang Pipa (m')": round(total_pipe_len, 2)
        }

    def calculate_architectural_loads(self):
        # Helper untuk menghitung beban struktur dari arsitek
        q = self.parse_architectural_quantities()
        # Asumsi Dinding Bata Ringan/Merah: Tebal 15cm, BJ 17 kN/m3 -> ~2.55 kN/m2
        beban_dinding = q["Luas Dinding (m2)"] * 2.55 
        return {"Total Load Tambahan (kN)": round(beban_dinding, 2)}
