class CarbonCalculator:
    def __init__(self):
        # Emission Factors (kgCO2e per Unit)
        # Sumber: Inventory Data (ICE) atau Lokal
        self.ef = {
            'beton_k300': 350.0, # kgCO2e/m3
            'baja': 2.2,         # kgCO2e/kg
            'bekisting': 15.0    # kgCO2e/m2
        }

    def calculate_gwp(self, vol_beton, berat_baja):
        """
        Hitung Global Warming Potential
        """
        co2_beton = vol_beton * self.ef['beton_k300']
        co2_baja = berat_baja * self.ef['baja']
        
        total_co2 = co2_beton + co2_baja
        return total_co2

class GreenshipChecker:
    def check_mrc_credits(self, materials_list, project_location, factory_location):
        points = 0
        report = []
        
        # MRC 2: Material Ramah Lingkungan
        # Logic: Cek apakah ada sertifikat ISO 14001
        certified_cost = sum([m['cost'] for m in materials_list if m['iso_14001']])
        total_cost = sum([m['cost'] for m in materials_list])
        
        if (certified_cost / total_cost) > 0.3:
            points += 2
            report.append("MRC 2: Lulus (2 Poin) - Material bersertifikat > 30%")
            
        # MRC 6: Material Regional (Hitung Jarak)
        from geopy.distance import geodesic
        dist = geodesic(project_location, factory_location).km
        
        if dist < 1000:
            points += 1
            report.append(f"MRC 6: Lulus (1 Poin) - Jarak pabrik {int(dist)} km (< 1000km)")
            
        return points, report
