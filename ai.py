import json
import os

import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/api")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")


async def ollama_generate(prompt: str) -> str:
    key = os.getenv("OLLAMA_API_KEY")
    if not key: raise RuntimeError("OLLAMA_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{OLLAMA_BASE_URL.rstrip('/')}/generate", headers={"Authorization": f"Bearer {key}"}, json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False})
        response.raise_for_status()
        text = response.json().get("response")
        if not text: raise RuntimeError("Ollama returned no response text")
        return text.strip()


async def generate_whatsapp_message(lead: dict, research: dict | None) -> str:
    facts = {"business_name": lead.get("name"), "industry": lead.get("industry"), "city": lead.get("city"), "website": lead.get("website"), "recommended_services": lead.get("recommended_services"), "problems": lead.get("problems"), "research": research or {}}
    prompt = f"""
Write a short first-contact WhatsApp draft for a digital/technology services agency.
Use ONLY the supplied facts. Never invent rankings, reviews, revenue, customers,
technologies, or results.

FACTS:
{json.dumps(facts, ensure_ascii=False, default=str)}

Rules:
- 60-100 words.
- Friendly, natural, and specific.
- Mention only 1-2 genuine observations.
- Do not promise rankings or guaranteed results.
- No fake urgency.
- End by asking whether they want a short audit.
- Return only the draft message.
"""
    return await ollama_generate(prompt)
