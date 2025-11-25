# FILE: app/services/ai_service.py
import google.generativeai as genai
import json
import re
from app.config import settings
from app.prompts import *

if settings.GOOGLE_API_KEY:
    genai.configure(api_key=settings.GOOGLE_API_KEY)

def parse_json_garbage(text: str) -> dict | None:
    if not text: return None
    match = re.search(r"```(json)?\s*({.*})\s*```", text, re.DOTALL)
    json_str = match.group(2) if match else text
    if not match:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end != -1: json_str = text[start:end]
    try:
        return json.loads(json_str)
    except:
        return None

async def call_llm_for_json(prompt: str, system_instruction: str) -> dict | None:
    try:
        model = genai.GenerativeModel('gemini-2.0-flash', system_instruction=system_instruction)
        response = await model.generate_content_async(prompt, generation_config={"response_mime_type": "application/json"})
        return parse_json_garbage(response.text)
    except Exception as e:
        print(f"LLM Error: {e}")
        return None

async def analyze_user_requirements(user_prompt: str) -> dict:
    print(f"--> 🧠 Architect Agent Analyzing...")
    return await call_llm_for_json(user_prompt, REQUIREMENTS_SYSTEM_INSTRUCTION)

async def refine_requirements(original_analysis: dict, user_answers: list[str]) -> dict:
    print(f"--> 🧠 Chief Engineer Refining...")
    context = f"ANALYSIS:\n{json.dumps(original_analysis)}\nANSWERS:\n{json.dumps(user_answers)}"
    final_plan = await call_llm_for_json(context, CONSTRAINT_MERGER_INSTRUCTION)
    
    # --- THE FIX: Inject Topology back into plan ---
    if final_plan and original_analysis.get("topology"):
        final_plan["topology"] = original_analysis["topology"]
    
    return final_plan

async def generate_spec_sheet(build_plan: dict) -> dict:
    topology = build_plan.get("topology", {})
    print(f"--> 📋 Sourcing Agent working on: {topology.get('class')} ({topology.get('target_voltage')})...")
    return await call_llm_for_json(json.dumps(build_plan), SPEC_GENERATOR_INSTRUCTION)

async def generate_assembly_instructions(project_data: dict) -> dict:
    print("--> 📝 Generating Documentation...")
    return await call_llm_for_json(json.dumps(project_data), ASSEMBLY_GUIDE_INSTRUCTION)

async def optimize_specs(current_bom: list, physics_report: dict) -> dict:
    print("--> 🔧 Optimization Agent Analyzing...")
    context = {"bom": current_bom, "report": physics_report}
    return await call_llm_for_json(json.dumps(context), OPTIMIZATION_ENGINEER_INSTRUCTION)