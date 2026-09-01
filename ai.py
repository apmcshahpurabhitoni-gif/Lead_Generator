import json
import os

import httpx

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/api")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4")


async def ollama_generate(prompt: str) -> str:
    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY is not configured")

    payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    headers = {"Authorization": f"Bearer {api_key}"}

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/generate",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        text = data.get("response")
        if not text:
            raise RuntimeError("Ollama returned no response text")
        return text.strip()


async def generate_whatsapp_message(lead: dict, research: dict | None) -> str:
    research = research or {}
    facts = {
        "business_name": lead.get("name"),
        "industry": lead.get("industry"),
        "city": lead.get("city"),
        "website": lead.get("website"),
        "score": lead.get("score"),
        "recommended_services": lead.get("recommended_services"),
        "problems": lead.get("problems"),
        "research": research,
    }
    prompt = f"""
Write a short first-contact WhatsApp draft for a digital/technology services agency.
Use ONLY the supplied facts. Never invent rankings, reviews, revenue, customers,
technologies, or results.

FACTS:
{json.dumps(facts, ensure_ascii=False, default=str)}

Rules:
- 60-100 words.
- Friendly and natural.
- Mention only 1-2 genuine observations.
- Do not promise rankings or guaranteed results.
- No fake urgency.
- End by asking whether the business wants a short audit.
- Return only the message.
"""
    return await ollama_generate(prompt)
