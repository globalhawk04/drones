# FILE: app/services/supply_service.py
from app.services.db_service import ArsenalDB
import difflib

class SupplyService:
    def __init__(self):
        self.db = ArsenalDB()

    def find_part(self, part_type, ideal_model_name):
        """
        Smart Inventory Lookup:
        1. Checks DB for exact match.
        2. Checks DB for fuzzy match (e.g. "Feetech SCS15" vs "Feetech SCS15 15kg").
        3. Returns a 'Generic Fallback' if the scraping failed, so the pipeline doesn't crash.
        """
        # 1. Exact/SQL Search
        candidate = self.db.find_component(part_type, ideal_model_name)
        if candidate:
            return candidate

        # 2. Broad Category Search (for fuzzy matching)
        # Note: In production, do this logic in SQL. For prototype, Python is fine.
        all_category_parts = self._get_all_by_type(part_type)
        
        if all_category_parts:
            # Fuzzy Match
            model_names = [p['product_name'] for p in all_category_parts]
            matches = difflib.get_close_matches(ideal_model_name, model_names, n=1, cutoff=0.4)
            
            if matches:
                # Return the fuzzy match
                return next(p for p in all_category_parts if p['product_name'] == matches[0])
            
            # If no fuzzy match but we have *something*, return the best verify part
            return all_category_parts[0]

        # 3. Fallback (The "Dummy Part")
        # Keeps the CAD/Physics engines running even if Google Search blocked us.
        return self._get_generic_fallback(part_type, ideal_model_name)

    def save_part(self, part_data):
        return self.db.add_component(part_data)

    def _get_all_by_type(self, part_type):
        # Helper to filter raw inventory
        # In real app, add a specific method to ArsenalDB
        inventory = self.db.get_all_inventory()
        return [p for p in inventory if p['part_type'] == part_type]

    def _get_generic_fallback(self, part_type, name):
        """Generates a dummy part based on library knowledge."""
        from app.services.library_service import infer_actuator_specs
        
        # Try to infer specs from the requested name, even if we couldn't buy it
        inferred_specs = {}
        if "actuator" in part_type.lower():
            inferred_specs = infer_actuator_specs(name)

        return {
            "part_type": part_type,
            "product_name": f"Generic {name}",
            "price": 0.0,
            "engineering_specs": inferred_specs,
            "visuals": {
                "primary_color_hex": "#888888",
                "material_type": "PLASTIC"
            },
            "source": "FALLBACK_GENERATOR"
        }