import ifcopenshell
import ifcopenshell.util.placement # Wajib ada untuk Matrix
import pandas as pd
import numpy as np
import tempfile
import os
import math

class IFC_Parser_Engine:
    def __init__(self, file_bytes):
        # 1. Simpan file sementara agar bisa dibaca ifcopenshell
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
        self.temp_file.write(file_bytes.read())
        self.temp_file.close()
        
        try:
            # Load file IFC
            self.ifc_file = ifcopenshell.open(self.temp_file.name)
        except Exception as e:
            if os.path.exists(self.temp_file.name):
                os.unlink(self.temp_file.name)
            raise ValueError(f"File IFC rusak atau tidak valid: {e}")
        
        # Hapus file temp setelah load ke memori
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def get_global_coordinates(self, element):
        """
        [ULTIMATE FIX] Menghitung Koordinat Global (Absolute World Coordinate).
        Melakukan perkalian matrix dari Site -> Building -> Storey -> Element.
        """
        try:
            placement = element.ObjectPlacement
            if not placement:
                return 0.0, 0.0, 0.0
            
            # 1. Kumpulkan semua hierarki placement (Anak -> Bapak -> Kakek -> Buyut)
            placements = []
            current = placement
            while current:
                placements.append(current)
                if hasattr(current, "PlacementRelTo"):
                    current = current.PlacementRelTo
                else:
                    current = None
            
            # 2. Mulai dengan Matrix Identitas (0,0,0)
            global_matrix = np.eye(4)
            
            # 3. Kalikan Matrix dari ATAS (Site) ke BAWAH (Element)
            # Urutan Matematika: Global = Parent * Child
            for p in reversed(placements):
                # Ubah placement object menjadi Matrix 4x4
                local_matrix = ifcopenshell.util.placement.get_local_placement(p)
                
                # Kalikan Akumulasi
                global_matrix = np.matmul(global_matrix, local_matrix)
            
            # 4. Ambil Kolom Terakhir (Translasi X, Y, Z)
            x_final = float(global_matrix[0][3])
            y_final = float(global_matrix[1][3])
            z_final = float(global_matrix[2][3])
            
            return x_final, y_final, z_final
            
        except Exception as e:
            # Fallback jika terjadi error matematika (Sangat jarang)
            return 0.0, 0.0, 0.0

    def parse_structure(self):
        """
        Mengambil Elemen Struktur Utama dengan Koordinat Global.
        """
        elements = []
        
        # Daftar Tipe Elemen Struktur
        target_types = [
            "IfcColumn",          # Kolom
            "IfcBeam",            # Balok
            "IfcMember",          # Rangka Baja / Facade
            "IfcPlate",           # Pelat Lantai
            "IfcFooting",         # Pondasi
            "IfcPile",            # Tiang Pancang
            "IfcWall",            # Dinding
            "IfcWallStandardCase",
            "IfcSlab"             # Tambahan untuk lantai
        ]
        
        for e_type in target_types:
            try:
                # Ambil semua elemen berdasarkan tipe
                items = self.ifc_file.by_type(e_type)
                
                for item in items:
                    # Lewati elemen tanpa geometri placement
                    if not hasattr(item, "ObjectPlacement"):
                        continue
                        
                    # HITUNG KOORDINAT GLOBAL (Logic Baru)
                    x, y, z = self.get_global_coordinates(item)
                    
                    # Ambil Nama yang bersih
                    name = item.Name if item.Name else f"Unnamed {e_type.replace('Ifc', '')}"
                    
                    # Simpan data ke list
                    elements.append({
                        "Type": e_type.replace("Ifc", ""), 
                        "Name": name, 
                        "X": round(x, 2), 
                        "Y": round(y, 2), 
                        "Z": round(z, 2),
                        "GUID": item.GlobalId
                    })
            except Exception:
                continue # Skip jika tipe tersebut tidak ada di file
            
        return pd.DataFrame(elements)

    def parse_architectural_quantities(self):
        """
        Mengambil Volume Dinding, Jumlah Pintu, dan Jendela.
        """
        total_wall_area = 0.0
        
        # --- 1. HITUNG DINDING ---
        walls = []
        try: walls.extend(self.ifc_file.by_type("IfcWall"))
        except: pass
        try: walls.extend(self.ifc_file.by_type("IfcWallStandardCase"))
        except: pass
        
        # Hapus duplikat
        walls = list(set(walls))
        
        for wall in walls:
            area_found = False
            # Strategi 1: Cek Property Sets (BaseQuantities)
            if hasattr(wall, "IsDefinedBy"):
                for rel in wall.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    # Cari parameter Area yang valid
                                    if q.Name in ["NetSideArea", "GrossSideArea", "Area", "NetArea"]:
                                        val = 0.0
                                        if hasattr(q, "AreaValue"): val = q.AreaValue
                                        # Kadang Revit salah taruh di VolumeValue
                                        elif hasattr(q, "VolumeValue") and q.VolumeValue < 200: 
                                            val = q.VolumeValue 
                                        
                                        if val > 0:
                                            total_wall_area += val
                                            area_found = True
                                            break
                    if area_found: break
            
            # Strategi 2: Jika Property kosong, estimasi kasar
            if not area_found:
                # Asumsi default kecil agar tidak 0
                total_wall_area += 10.0

        # --- 2. HITUNG PINTU & JENDELA ---
        try: doors = len(self.ifc_file.by_type("IfcDoor"))
        except: doors = 0
        
        try: windows = len(self.ifc_file.by_type("IfcWindow"))
        except: windows = 0
        
        return {
            "Luas Dinding (m2)": round(total_wall_area, 2),
            "Jumlah Pintu (Unit)": doors,
            "Jumlah Jendela (Unit)": windows
        }

    def parse_mep_quantities(self):
        """
        Mengambil Panjang Pipa & Ducting.
        """
        total_len = 0.0
        mep_elements = []
        
        # Deteksi Versi Schema IFC
        schema = self.ifc_file.schema
        
        # Ambil elemen berdasarkan versi
        if schema == "IFC4":
            try: mep_elements.extend(self.ifc_file.by_type("IfcPipeSegment"))
            except: pass
            try: mep_elements.extend(self.ifc_file.by_type("IfcDuctSegment"))
            except: pass
        
        # Fallback untuk IFC2x3 atau jika kosong
        if not mep_elements:
            try: mep_elements.extend(self.ifc_file.by_type("IfcFlowSegment"))
            except: pass

        for item in mep_elements:
            length = 0.0
            # Cari property Length
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
            # Fallback jika tidak ada data length
            if length == 0: length = 1.0 
            total_len += length
            
        return {
            "Panjang Pipa/Duct (m')": round(total_len, 2)
        }

    def calculate_architectural_loads(self):
        """
        Estimasi Beban Struktur dari Elemen Arsitek.
        """
        q = self.parse_architectural_quantities()
        beban_dinding = q["Luas Dinding (m2)"] * 2.0
        return {"Total Load Tambahan (kN)": round(beban_dinding, 2)}
