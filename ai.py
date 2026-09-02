import json, os
import httpx

BASE_URL=os.getenv("OLLAMA_BASE_URL","https://ollama.com/api").rstrip("/")
MODEL=os.getenv("OLLAMA_MODEL","gemma4")

async def ollama_generate(prompt:str)->str:
    key=os.getenv("OLLAMA_API_KEY","").strip()
    if not key: raise RuntimeError("OLLAMA_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=60) as client:
        r=await client.post(f"{BASE_URL}/generate",headers={"Authorization":f"Bearer {key}"},json={"model":MODEL,"prompt":prompt,"stream":False}); r.raise_for_status()
        text=r.json().get("response")
        if not text: raise RuntimeError("Ollama returned no response text")
        return text.strip()

async def generate_whatsapp_message(lead:dict,research:dict|None)->str:
    facts={"business_name":lead.get("name"),"industry":lead.get("industry"),"city":lead.get("city"),"website":lead.get("website"),"recommended_services":lead.get("recommended_services"),"problems":lead.get("problems"),"research":research or {}}
    prompt="""Write a short first-contact WhatsApp draft for a digital/technology services agency. Use ONLY the supplied facts. Never invent rankings, reviews, revenue, customers, technologies, or results. Mention only 1-2 genuine observations. Do not promise rankings or guaranteed results. No fake urgency. 60-100 words. End by asking whether they want a short audit. Return only the message.\n\nFACTS:\n"""+json.dumps(facts,ensure_ascii=False,default=str)
    return await ollama_generate(prompt)
