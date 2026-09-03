"""AI provider and safe outreach copy generation."""
import json
import os
import httpx
from config import APP_VERSION

BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/api").rstrip("/")
MODEL = os.getenv("OLLAMA_MODEL", "gemma4")

async def ollama_generate(prompt: str) -> str:
    key = os.getenv("OLLAMA_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OLLAMA_API_KEY is not configured")
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{BASE_URL}/generate",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": MODEL, "prompt": prompt, "stream": False},
        )
        r.raise_for_status()
        text = r.json().get("response")
        if not text:
            raise RuntimeError("Ollama returned no response text")
        return text.strip()

def _fallback_message(lead: dict, research: dict) -> str:
    name = str(lead.get("name") or "your business").strip()
    city = str(lead.get("city") or "").strip()
    problems = [str(x) for x in (research.get("problems") or [])[:2]]
    services = [str(x) for x in (lead.get("recommended_services") or [])[:2]]
    observation = problems[0] if problems else "we noticed an opportunity to strengthen your online presence"
    service = ", ".join(services) if services else "your online presence"
    return (
        f"Hi {name}, I’m reaching out because {observation.lower()}. "
        f"We help businesses improve {service}"
        f"{(' in ' + city) if city else ''}. "
        "I’d be happy to share a short, no-pressure audit with a few practical recommendations. "
        "Would that be useful?"
    )

async def generate_whatsapp_message(lead: dict, research: dict | None) -> str:
    r = research or {}
    g = r.get("google") or {}
    facts = {
        "business": lead.get("name"), "industry": lead.get("industry"), "city": lead.get("city"),
        "website": lead.get("website"), "phone": lead.get("phone"), "email": lead.get("email"),
        "rating": g.get("rating"), "review_count": g.get("review_count"),
        "recommended_services": lead.get("recommended_services"),
        "verified_problems": lead.get("problems"),
        "research_status": r.get("research_status"),
        "research_confidence": r.get("confidence"),
    }
    prompt = """Write a professional, human first-contact WhatsApp message for a digital services agency.
Use only the supplied facts. Mention 1-2 specific observations only when they are explicitly present in verified_problems.
Do not invent rankings, reviews, phone/email, customers, revenue, results, listings or technical facts.
Do not mention internal scores or research confidence. Do not promise a ranking or guaranteed outcome.
Be respectful and concise (80-120 words). End with a low-pressure offer to share a short audit.
Return only the message.

FACTS:
""" + json.dumps(facts, ensure_ascii=False, default=str)
    try:
        return await ollama_generate(prompt)
    except Exception:
        return _fallback_message(lead, r)
