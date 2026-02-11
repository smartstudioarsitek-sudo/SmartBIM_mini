import ifcopenshell
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
            self.ifc_file = ifcopenshell.open(self.temp_file.name)
        except Exception as e:
            os.unlink(self.temp_file.name)
            raise ValueError(f"File IFC rusak atau tidak valid: {e}")
        
        # Hapus file temp setelah load ke memori
        os.unlink(self.temp_file.name)

    def _create_matrix(self, placement):
        """
        Helper Internal: Membuat Matrix Transformasi 4x4 dari IfcLocalPlacement
        Menangani Rotasi dan Translasi secara manual (Math Only)
        """
        # Default Identity Matrix
        matrix = np.identity(4)
        
        if not placement or not hasattr(placement, "RelativePlacement"):
            return matrix
            
        rel_pl = placement.RelativePlacement
        
        # 1. Ambil Lokasi (Translation)
        x, y, z = 0.0, 0.0, 0.0
        if hasattr(rel_pl, "Location") and rel_pl.Location:
            coords = rel_pl.Location.Coordinates
            x = float(coords[0])
            y = float(coords[1])
            z = float(coords[2]) if len(coords) > 2 else 0.0
            
        # 2. Ambil Sumbu (Rotation) - Jika 3D
        # Default Axis
        ref_x = np.array([1.0, 0.0, 0.0])
        ref_y = np.array([0.0, 1.0, 0.0])
        ref_z = np.array([0.0, 0.0, 1.0])
        
        if rel_pl.is_a("IfcAxis2Placement3D"):
            # Axis (Z-Axis)
            if hasattr(rel_pl, "Axis") and rel_pl.Axis:
                axis_vals = rel_pl.Axis.DirectionRatios
                ref_z = np.array([float(v) for v in axis_vals])
                # Normalize
                norm = np.linalg.norm(ref_z)
                if norm > 0: ref_z /= norm
                
            # RefDirection (X-Axis)
            if hasattr(rel_pl, "RefDirection") and rel_pl.RefDirection:
                ref_vals = rel_pl.RefDirection.DirectionRatios
                ref_x = np.array([float(v) for v in ref_vals])
                norm = np.linalg.norm(ref_x)
                if norm > 0: ref_x /= norm
            
            # Hitung Y-Axis (Cross Product Z * X)
            ref_y = np.cross(ref_z, ref_x)
            # Re-orthogonalize X (Cross Product Y * Z)
            ref_x = np.cross(ref_y, ref_z)
            
        # 3. Masukkan ke Matrix 4x4
        # [Rx Ry Rz Tx]
        # [Rx Ry Rz Ty]
        # [Rx Ry Rz Tz]
        # [ 0  0  0  1]
        
        matrix[0,0] = ref_x[0]; matrix[0,1] = ref_y[0]; matrix[0,2] = ref_z[0]; matrix[0,3] = x
        matrix[1,0] = ref_x[1]; matrix[1,1] = ref_y[1]; matrix[1,2] = ref_z[1]; matrix[1,3] = y
        matrix[2,0] = ref_x[2]; matrix[2,1] = ref_y[2]; matrix[2,2] = ref_z[2]; matrix[2,3] = z
        
        return matrix

    def get_absolute_coordinates(self, element):
        """
        Menghitung Koordinat Global (Absolute World Coordinate).
        Melakukan perkalian matrix dari elemen -> parents -> world.
        """
        try:
            current_placement = element.ObjectPlacement
            final_matrix = np.identity(4)
            
            # Loop naik ke atas (Element -> Level -> Building -> Site)
            while current_placement is not None:
                # 1. Hitung Matrix Lokal level ini
                local_mat = self._create_matrix(current_placement)
                
                # 2. Kalikan: Parent * Child (Order matters!)
                # Di sini kita tumpuk transformasi: Final = Local * Final_Previous
                # Tapi urutan traverse kita dari Child ke Parent.
                # Jadi: Global = ParentMat * ... * ChildMat
                # Kita perlu mengalikan di sebelah KIRI.
                final_matrix = np.matmul(local_mat, final_matrix)
                
                # 3. Naik ke Parent
                if hasattr(current_placement, "PlacementRelTo"):
                    current_placement = current_placement.PlacementRelTo
                else:
                    current_placement = None
            
            # Ambil kolom terakhir (Translasi X, Y, Z)
            return float(final_matrix[0][3]), float(final_matrix[1][3]), float(final_matrix[2][3])
            
        except Exception as e:
            # Fallback Terakhir: Coba baca langsung attribute local
            print(f"Matrix Calc Error: {e}")
            return 0.0, 0.0, 0.0

    def parse_structure(self):
        """
        Mengambil Elemen Struktur (Balok, Kolom, Member, Plate)
        Support IFC2x3 dan IFC4
        """
        elements = []
        # Tipe elemen yang dicari (termasuk IfcMember untuk facade/baja)
        target_types = ["IfcColumn", "IfcBeam", "IfcMember", "IfcPlate", "IfcCurtainWall"]
        
        for e_type in target_types:
            try:
                for item in self.ifc_file.by_type(e_type):
                    x, y, z = self.get_absolute_coordinates(item)
                    
                    # Bersihkan nama
                    name = item.Name if item.Name else f"Unnamed {e_type[3:]}"
                    
                    # Filter elemen di 0,0,0 jika mencurigakan (opsional), tapi kita simpan saja
                    elements.append({
                        "Type": e_type.replace("Ifc", ""), # Hapus prefix Ifc
                        "Name": name, 
                        "X": round(x, 2), 
                        "Y": round(y, 2), 
                        "Z": round(z, 2)
                    })
            except:
                continue # Skip jika tipe tidak ada di file
            
        return pd.DataFrame(elements)

    def parse_architectural_quantities(self):
        """Mengambil Volume Dinding, Pintu, Jendela"""
        total_wall_area = 0
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
                                        elif hasattr(q, "VolumeValue"): val = q.VolumeValue
                                        if val > 0:
                                            total_wall_area += val
                                            area_found = True
                                            break
                    if area_found: break
            
            if not area_found:
                total_wall_area += 9.0 # Asumsi panel default

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
            try: mep_elements = self.ifc_file.by_type("IfcPipeSegment")
            except: mep_elements = []
        
        # Jika IFC4 kosong atau IFC2x3, coba FlowSegment (Induk dari Pipa di IFC2x3)
        if not mep_elements:
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
                                    if q.Name in ["Length", "NominalLength"] and hasattr(q, "LengthValue"):
                                        if q.LengthValue > 0:
                                            length = q.LengthValue
                                            break
            
            if length == 0: length = 4.0 # Fallback 4m per batang
            total_pipe_len += length
            
        return {
            "Panjang Pipa (m')": round(total_pipe_len, 2)
        }

    def calculate_architectural_loads(self):
        q = self.parse_architectural_quantities()
        beban_dinding = q["Luas Dinding (m2)"] * 2.55 
        return {"Total Load Tambahan (kN)": round(beban_dinding, 2)}
