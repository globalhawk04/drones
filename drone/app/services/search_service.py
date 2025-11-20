# FILE: app/services/search_service.py
import asyncio

# SAFETY PROTOCOL: Live Search disabled for public release.
# This Mock Service returns static data for demonstration purposes.

MOCK_DATABASE = {
    "motor": [
        {
            "title": "Demo Motor 2207 1750KV (Mock)",
            "price": "19.99",
            "source": "DemoStore",
            "link": "https://example.com/demo-motor",
            "image_url": "https://example.com/motor.jpg"
        }
    ],
    "fc": [
        {
            "title": "Demo F7 Flight Controller (Mock)",
            "price": "49.99",
            "source": "DemoStore",
            "link": "https://example.com/demo-fc",
            "image_url": "https://example.com/fc.jpg"
        }
    ]
    # ... (The system will default to generic mocks if not found)
}

def find_components(query: str, limit: int = 5) -> list[dict]:
    print(f"🔎 [MOCK SEARCH] Simulating search for: '{query}'")
    
    # Simple keyword matching to return safe mock data
    query_lower = query.lower()
    
    results = []
    if "motor" in query_lower:
        results = MOCK_DATABASE["motor"]
    elif "fc" in query_lower or "flight controller" in query_lower:
        results = MOCK_DATABASE["fc"]
    else:
        # Generic Fallback
        results = [{
            "title": f"Generic Component for '{query}'",
            "price": "9.99",
            "source": "DemoStore",
            "link": "https://example.com/demo-part",
            "image_url": ""
        }]
        
    return results
