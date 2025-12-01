# FILE: app/services/fusion_service.py
import asyncio
import json
from app.services.recon_service import Scraper
from app.services.vision_service import analyze_specs_multimodal
from app.services.library_service import infer_actuator_specs, extract_chassis_size
from app.services.search_service import find_components
from app.services.ai_service import generate_vision_prompt 

DOMAIN_BLOCKLIST = [
    "reddit.com", "facebook.com", "youtube.com", "twitter.com", 
    "instagram.com", "forum", "pinterest", "thingiverse", "mdpi.com", 
    "blog", "news", "wikipedia"
]

GENERIC_TITLE_BLOCKLIST = [
    "collections", "products", "category", "browse", "shop", 
    "accessories", "parts", "review"
]

def validate_critical_specs(part_type, specs):
    """
    Quality Gate: Determines if the extracted data is sufficient for engineering.
    Updated for ROBOTICS.
    """
    if not specs: return False
    pt = part_type.lower()
    
    # --- ROBOTICS VALIDATION LOGIC ---
    if "actuator" in pt or "servo" in pt:
        # We need Torque (Strength) to calculate physics viability
        # We need Voltage to ensure we don't burn it out
        has_torque = any(k in specs for k in ["torque", "stall_torque", "est_torque_kgcm"])
        has_voltage = any(k in specs for k in ["voltage", "voltage_rating", "operating_voltage"])
        if not has_torque: return False 
        
    elif "chassis" in pt or "frame" in pt:
        # We need dimensions to generate the CAD
        has_dims = any(k in specs for k in ["length_mm", "width_mm", "dimensions", "femur_length_mm"])
        if not has_dims: return False
        
    elif "controller" in pt or "driver" in pt:
        # We need to know if it can drive 12 servos
        has_channels = any(k in specs for k in ["channels", "channel_count"])
        has_proto = any(k in specs for k in ["protocol", "interface", "bus_type"])
        if not has_channels and not has_proto: return False
        
    elif "battery" in pt:
        # Standard checks
        if not specs.get("capacity_mah"): return False
        if not specs.get("voltage") and not specs.get("cell_count_s"): return False

    return True

async def process_single_candidate(scraper, item, part_type, vision_prompt_object, min_confidence):
    link = item.get('link')
    title = item.get('title')
    
    if not link or not title: return None
    if any(bad_domain in link for bad_domain in DOMAIN_BLOCKLIST): return None
    if any(bad_word in title.lower() for bad_word in GENERIC_TITLE_BLOCKLIST): return None

    print(f"   Trying: {title[:50]}...")
    
    # 1. Deep Scrape
    scraped_data = await scraper.scrape_product_page(link)
    if not scraped_data: return None

    final_price = scraped_data.get('price')
    if not final_price or final_price <= 1.00: # Filter out screws/accessories
        return None

    # 2. Multimodal Vision Analysis
    validated_specs = {}
    
    # Combine text context
    text_context = f"{scraped_data.get('structured_tables', '')}\n{scraped_data.get('text', '')[:2000]}"
    
    if vision_prompt_object:
        raw_vision_result = await analyze_specs_multimodal(
            text_context, 
            scraped_data.get('images', []), 
            part_type, 
            vision_prompt_object
        )
        
        if raw_vision_result and not raw_vision_result.get("error"):
            # Filter low confidence data
            for key, data in raw_vision_result.items():
                if isinstance(data, dict):
                    if data.get("value") is not None and data.get("confidence", 0) >= min_confidence:
                        validated_specs[key] = data.get("value")
                elif data is not None:
                     validated_specs[key] = data

            if validated_specs:
                 validated_specs["source"] = "multimodal_fusion"

    # 3. Fallback / Augmentation (Library Service)
    # If Vision missed the torque, maybe the model name (e.g. "MG996R") tells us?
    if "actuator" in part_type.lower():
        inferred = infer_actuator_specs(title)
        # Only overwrite if missing
        if "est_torque_kgcm" not in validated_specs and "est_torque_kgcm" in inferred:
            validated_specs["est_torque_kgcm"] = inferred["est_torque_kgcm"]
            validated_specs["source_augmentation"] = "library_inference"
            
    if "chassis" in part_type.lower() and "length_mm" not in validated_specs:
        size = extract_chassis_size(title)
        if size:
            validated_specs["length_mm"] = size

    # 4. Critical Validation
    if not validate_critical_specs(part_type, validated_specs):
        return None

    return {
        "product_name": title, 
        "price": final_price, 
        "source_url": link,
        "image_url": scraped_data.get('image_url'),
        "engineering_specs": validated_specs,
        "data_quality_score": len(validated_specs)
    }

async def fuse_component_data(part_type: str, search_query: str, search_limit: int = 5, min_confidence: float = 0.6):
    """
    Main entry point for sourcing a specific part.
    """
    vision_prompt = await generate_vision_prompt(part_type)
    if not vision_prompt: return None

    results = find_components(search_query, limit=search_limit)
    if not results: return None

    async with Scraper() as scraper:
        tasks = [process_single_candidate(scraper, res, part_type, vision_prompt, min_confidence) for res in results]
        candidates = await asyncio.gather(*tasks)
        
    valid_candidates = [c for c in candidates if c is not None]
    if not valid_candidates: return None

    # Rank by Data Quality (Specs Found) + Price Reality Check
    # We want the part with the most complete engineering data.
    valid_candidates.sort(key=lambda x: x['data_quality_score'], reverse=True)
    
    return {
        "part_type": part_type,
        "product_name": valid_candidates[0]['product_name'],
        "price": valid_candidates[0]['price'],
        "source_url": valid_candidates[0]['source_url'],
        "engineering_specs": valid_candidates[0]['engineering_specs'],
        "reference_image": valid_candidates[0]['image_url']
    }