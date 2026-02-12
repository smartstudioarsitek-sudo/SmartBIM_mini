import ifcopenshell
import pandas as pd
import numpy as np
import tempfile
import os
import math

class IFC_Parser_Engine:
    def __init__(self, file_bytes):
        # 1. Simpan file sementara agar bisa dibaca ifcopenshell
        # Kita menggunakan delete=False agar file ada saat dibuka, lalu dihapus manual
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ifc")
        self.temp_file.write(file_bytes.read())
        self.temp_file.close()
        
        try:
            self.ifc_file = ifcopenshell.open(self.temp_file.name)
        except Exception as e:
            # Bersihkan file jika gagal load
            if os.path.exists(self.temp_file.name):
                os.unlink(self.temp_file.name)
            raise ValueError(f"File IFC rusak atau tidak valid: {e}")
        
        # Hapus file temp setelah load ke memori selesai
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def _create_matrix(self, placement):
        """
        Helper Internal: Mengubah IfcLocalPlacement menjadi Matrix 4x4 (NumPy).
        Ini menangani Rotasi (Axis, RefDirection) dan Translasi (Location).
        """
        # Matriks Identitas Default (Tidak ada perubahan posisi)
        matrix = np.identity(4)
        
        if not placement or not hasattr(placement, "RelativePlacement"):
            return matrix
            
        rel_pl = placement.RelativePlacement
        
        # 1. AMBIL LOKASI (TRANSLATION)
        x, y, z = 0.0, 0.0, 0.0
        if hasattr(rel_pl, "Location") and rel_pl.Location:
            coords = rel_pl.Location.Coordinates
            x = float(coords[0])
            y = float(coords[1])
            z = float(coords[2]) if len(coords) > 2 else 0.0
            
        # 2. AMBIL SUMBU PUTAR (ROTATION)
        # Default Sumbu
        ref_x = np.array([1.0, 0.0, 0.0])
        ref_y = np.array([0.0, 1.0, 0.0])
        ref_z = np.array([0.0, 0.0, 1.0])
        
        # Cek apakah placement 3D
        if rel_pl.is_a("IfcAxis2Placement3D"):
            # A. Sumbu Z (Axis)
            if hasattr(rel_pl, "Axis") and rel_pl.Axis:
                axis_vals = rel_pl.Axis.DirectionRatios
                ref_z = np.array([float(v) for v in axis_vals])
                # Normalisasi vektor (biar panjangnya = 1)
                norm = np.linalg.norm(ref_z)
                if norm > 0: ref_z /= norm
                
            # B. Sumbu X (RefDirection)
            if hasattr(rel_pl, "RefDirection") and rel_pl.RefDirection:
                ref_vals = rel_pl.RefDirection.DirectionRatios
                ref_x = np.array([float(v) for v in ref_vals])
                norm = np.linalg.norm(ref_x)
                if norm > 0: ref_x /= norm
            
            # C. Hitung Sumbu Y (Cross Product Z * X)
            # Ini memastikan sumbu Y tegak lurus terhadap Z dan X
            ref_y = np.cross(ref_z, ref_x)
            norm = np.linalg.norm(ref_y)
            if norm > 0: ref_y /= norm
            
            # D. Koreksi Sumbu X (Cross Product Y * Z)
            # Memastikan X benar-benar tegak lurus (Orthogonal)
            ref_x = np.cross(ref_y, ref_z)
            norm = np.linalg.norm(ref_x)
            if norm > 0: ref_x /= norm
            
        # 3. MASUKKAN KE MATRIX 4x4
        # Format Matrix Transformasi Homogen:
        # [Rx Ry Rz Tx]
        # [Rx Ry Rz Ty]
        # [Rx Ry Rz Tz]
        # [ 0  0  0  1]
        
        # Kolom 0 (Sumbu X)
        matrix[0,0] = ref_x[0]
        matrix[1,0] = ref_x[1]
        matrix[2,0] = ref_x[2]
        
        # Kolom 1 (Sumbu Y)
        matrix[0,1] = ref_y[0]
        matrix[1,1] = ref_y[1]
        matrix[2,1] = ref_y[2]
        
        # Kolom 2 (Sumbu Z)
        matrix[0,2] = ref_z[0]
        matrix[1,2] = ref_z[1]
        matrix[2,2] = ref_z[2]
        
        # Kolom 3 (Translasi / Lokasi)
        matrix[0,3] = x
        matrix[1,3] = y
        matrix[2,3] = z
        
        return matrix

    def get_absolute_coordinates(self, element):
        """
        Menghitung Koordinat Global (Absolute World Coordinate).
        Melakukan perkalian matrix dari elemen -> parents -> world.
        """
        try:
            current_placement = element.ObjectPlacement
            # Mulai dengan Matrix Identitas (Posisi 0,0,0)
            final_matrix = np.identity(4)
            
            # Loop naik ke atas (Element -> Level -> Building -> Site)
            # Kita kumpulkan semua matrix transformasi dari anak ke induk
            matrices = []
            while current_placement is not None:
                # 1. Hitung Matrix Lokal level ini
                local_mat = self._create_matrix(current_placement)
                matrices.append(local_mat)
                
                # 2. Naik ke Parent
                if hasattr(current_placement, "PlacementRelTo"):
                    current_placement = current_placement.PlacementRelTo
                else:
                    current_placement = None
            
            # 3. Kalikan Matrix dari INDUK TERATAS (Site) ke ANAK TERBAWAH (Element)
            # Urutan perkalian matrix: Global = Parent * Child
            # List `matrices` isinya [Element, Level, Building, Site]
            # Kita perlu balik urutannya jadi [Site, Building, Level, Element]
            for mat in reversed(matrices):
                final_matrix = np.matmul(final_matrix, mat)
            
            # Ambil kolom terakhir (Translasi X, Y, Z) dari Matrix Final
            x_final = float(final_matrix[0][3])
            y_final = float(final_matrix[1][3])
            z_final = float(final_matrix[2][3])
            
            return x_final, y_final, z_final
            
        except Exception as e:
            # Fallback Terakhir: Coba baca langsung attribute local jika matrix gagal
            # print(f"Matrix Calc Error for {element.GlobalId}: {e}")
            return 0.0, 0.0, 0.0

    def parse_structure(self):
        """
        Mengambil Elemen Struktur (Balok, Kolom, Member, Plate, CurtainWall, dll)
        Support IFC2x3 dan IFC4
        """
        elements = []
        # Tipe elemen yang dicari (termasuk IfcMember untuk facade/baja)
        # Kita perluas jangkauan pencarian agar fasade terbaca
        target_types = [
            "IfcColumn", 
            "IfcBeam", 
            "IfcMember", 
            "IfcPlate", 
            "IfcCurtainWall", 
            "IfcWall", 
            "IfcWallStandardCase"
        ]
        
        for e_type in target_types:
            try:
                # Ambil semua elemen tipe tersebut
                items = self.ifc_file.by_type(e_type)
                
                for item in items:
                    # Lewati elemen yang tidak punya geometri (misal Type Object)
                    if not hasattr(item, "ObjectPlacement") or not item.ObjectPlacement:
                        continue
                        
                    x, y, z = self.get_absolute_coordinates(item)
                    
                    # Bersihkan nama
                    name = item.Name if item.Name else f"Unnamed {e_type.replace('Ifc', '')}"
                    
                    # Simpan data
                    elements.append({
                        "Type": e_type.replace("Ifc", ""), # Hapus prefix Ifc
                        "Name": name, 
                        "X": round(x, 2), 
                        "Y": round(y, 2), 
                        "Z": round(z, 2),
                        "GUID": item.GlobalId # Berguna untuk referensi unik
                    })
            except Exception:
                continue # Skip jika tipe tidak ada di file
            
        return pd.DataFrame(elements)

    def parse_architectural_quantities(self):
        """
        Mengambil Volume Dinding, Pintu, Jendela
        """
        total_wall_area = 0
        
        # Ambil dinding
        walls = []
        try: walls.extend(self.ifc_file.by_type("IfcWall"))
        except: pass
        try: walls.extend(self.ifc_file.by_type("IfcWallStandardCase"))
        except: pass
        
        # Hapus duplikat jika ada (walaupun by_type biasanya unik per kelas)
        walls = list(set(walls))
        
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
                                    # Prioritas nama quantity untuk luas dinding
                                    if q.Name in ["NetSideArea", "GrossSideArea", "Area", "NetArea"]:
                                        val = 0.0
                                        if hasattr(q, "AreaValue"): val = q.AreaValue
                                        elif hasattr(q, "VolumeValue"): 
                                            # Kadang software BIM salah taruh value di Volume padahal Area
                                            # Cek kewajaran angka (misal < 100m2 dinding per piece)
                                            if q.VolumeValue < 200: val = q.VolumeValue 
                                        
                                        if val > 0:
                                            total_wall_area += val
                                            area_found = True
                                            break
                    if area_found: break
            
            # Fallback jika property kosong: Estimasi dari dimensi bounding box (jika bisa)
            # Untuk simplifikasi saat ini kita pakai nilai default kecil jika gagal total
            if not area_found:
                total_wall_area += 9.0 # Asumsi panel default 3x3

        # Hitung Pintu & Jendela
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
        Cerdas mendeteksi IFC2x3 (FlowSegment) vs IFC4 (PipeSegment)
        """
        total_pipe_len = 0
        schema_version = self.ifc_file.schema 
        mep_elements = []
        
        # Strategi Deteksi Versi
        if schema_version == "IFC4":
            try: mep_elements.extend(self.ifc_file.by_type("IfcPipeSegment"))
            except: pass
            try: mep_elements.extend(self.ifc_file.by_type("IfcDuctSegment"))
            except: pass
        
        # Jika kosong atau IFC2x3, ambil FlowSegment (Induk umum)
        if not mep_elements:
            try: mep_elements = self.ifc_file.by_type("IfcFlowSegment")
            except: mep_elements = []

        for item in mep_elements:
            length = 0.0
            # Coba cari Length di Quantities
            if hasattr(item, "IsDefinedBy"):
                for rel in item.IsDefinedBy:
                    if rel.is_a("IfcRelDefinesByProperties"):
                        if hasattr(rel, "RelatingPropertyDefinition"):
                            props = rel.RelatingPropertyDefinition
                            if props.is_a("IfcElementQuantity"):
                                for q in props.Quantities:
                                    if q.Name in ["Length", "NominalLength", "GrossLength", "NetLength"] and hasattr(q, "LengthValue"):
                                        if q.LengthValue > 0:
                                            length = q.LengthValue
                                            break
            
            if length == 0: length = 4.0 # Fallback 4m per batang pipa/duct
            total_pipe_len += length
            
        return {
            "Panjang Pipa/Duct (m')": round(total_pipe_len, 2)
        }

    def calculate_architectural_loads(self):
        """Menghitung beban struktur dari elemen arsitek"""
        q = self.parse_architectural_quantities()
        # Asumsi beban dinding bata ringan (hebel) + plester = 1.5 - 2.5 kN/m2
        beban_dinding = q["Luas Dinding (m2)"] * 2.55 
        return {"Total Load Tambahan (kN)": round(beban_dinding, 2)}
