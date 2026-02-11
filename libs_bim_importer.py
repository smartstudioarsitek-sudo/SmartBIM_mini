import ifcopenshell
import ifcopenshell.util.placement
import pandas as pd
import io

class IFC_Parser_Engine:
    def __init__(self):
        self.ifc_file = None

    def load_ifc_file(self, file_obj):
        """
        Memuat file IFC baik dari path string maupun object file (Streamlit upload).
        """
        try:
            if isinstance(file_obj, str):
                # Jika input adalah path file (string)
                self.ifc_file = ifcopenshell.open(file_obj)
            elif file_obj is not None:
                # Jika input adalah file object dari Streamlit (bytes)
                # Kita perlu membaca bytes tersebut ke string sementara
                file_bytes = file_obj.getvalue()
                # Mengubah bytes menjadi string utf-8 agar bisa dibaca ifcopenshell
                ifc_string = file_bytes.decode("utf-8")
                self.ifc_file = ifcopenshell.file.from_string(ifc_string)
            
            return True
        except Exception as e:
            print(f"Error loading IFC file: {e}")
            return False

    def get_element_properties(self, element):
        """
        Mengekstrak properti dari elemen IFC, termasuk KOORDINAT GLOBAL (X, Y, Z).
        """
        properties = {
            "GlobalId": element.GlobalId,
            "Name": element.Name if element.Name else "Unnamed",
            "Type": element.is_a(),
            "PredefinedType": getattr(element, "PredefinedType", "None"),
            # Default value koordinat
            "X": 0.0,
            "Y": 0.0,
            "Z": 0.0
        }

        # --- PERBAIKAN UTAMA: LOGIKA KOORDINAT ---
        # Menggunakan matrix transformasi untuk mendapatkan posisi absolut di dunia 3D
        if hasattr(element, "ObjectPlacement") and element.ObjectPlacement:
            try:
                # Fungsi ini menghitung posisi elemen relatif terhadap 0,0,0 dunia
                # meskipun elemen tersebut berada di dalam Group/Component bertingkat
                matrix = ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement)
                
                # Mengambil nilai X, Y, Z dari kolom terakhir matrix (index 3)
                properties["X"] = round(matrix[0][3], 4)
                properties["Y"] = round(matrix[1][3], 4)
                properties["Z"] = round(matrix[2][3], 4)
            except Exception as e:
                # Jika gagal hitung (jarang terjadi), biarkan 0.0
                print(f"Warning: Gagal hitung koordinat untuk {element.GlobalId}: {e}")

        # --- MENGEKSTRAK PROPERTY SETS (Pset) ---
        # Mengambil data Custom Attributes (misal: Pset_Irigasi, Material, dll)
        for definition in getattr(element, "IsDefinedBy", []):
            if definition.is_a("IfcRelDefinesByProperties"):
                property_set = definition.RelatingPropertyDefinition
                
                if property_set.is_a("IfcPropertySet"):
                    for prop in property_set.HasProperties:
                        # Menangani Single Value (Angka/Teks biasa)
                        if prop.is_a("IfcPropertySingleValue"):
                            val = prop.NominalValue
                            # Unwrapping value jika terbungkus class ifc
                            if hasattr(val, "wrappedValue"):
                                val = val.wrappedValue
                            properties[prop.Name] = val

        # --- MENGEKSTRAK QUANTITIES (Qto) ---
        # Mengambil data Volume, Luas, Panjang bawaan software
        for definition in getattr(element, "IsDefinedBy", []):
             if definition.is_a("IfcRelDefinesByProperties"):
                quantity_set = definition.RelatingPropertyDefinition
                
                if quantity_set.is_a("IfcElementQuantity"):
                    for quantity in quantity_set.Quantities:
                        if quantity.is_a("IfcQuantityLength"):
                            properties[quantity.Name] = quantity.LengthValue
                        elif quantity.is_a("IfcQuantityArea"):
                            properties[quantity.Name] = quantity.AreaValue
                        elif quantity.is_a("IfcQuantityVolume"):
                            properties[quantity.Name] = quantity.VolumeValue

        return properties

    def extract_data(self):
        """
        Mengambil semua elemen IfcProduct (fisik) dan mengubahnya menjadi DataFrame.
        """
        if not self.ifc_file:
            return pd.DataFrame()

        data = []
        # Kita ambil 'IfcProduct' agar mencakup semua elemen fisik (Wall, Beam, BuildingElementProxy, dll)
        elements = self.ifc_file.by_type("IfcProduct")

        for element in elements:
            # Lewati elemen abstrak seperti IfcSpace atau IfcOpeningElement jika tidak diperlukan
            if element.is_a("IfcOpeningElement") or element.is_a("IfcSpace"):
                continue
                
            props = self.get_element_properties(element)
            data.append(props)

        # Konversi ke Pandas DataFrame
        df = pd.DataFrame(data)
        
        # Membersihkan data NaN (kosong) agar rapi di tabel
        if not df.empty:
            df = df.fillna("")
        
        return df
