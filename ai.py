"""AI provider and evidence-only outreach generation."""
import json,os,httpx
BASE_URL=os.getenv("OLLAMA_BASE_URL","https://ollama.com/api").rstrip("/");MODEL=os.getenv("OLLAMA_MODEL","gemma4")
async def ollama_generate(prompt):
 key=os.getenv("OLLAMA_API_KEY","").strip()
 if not key:raise RuntimeError("OLLAMA_API_KEY is not configured")
 async with httpx.AsyncClient(timeout=60) as c:
  r=await c.post(f"{BASE_URL}/generate",headers={"Authorization":f"Bearer {key}"},json={"model":MODEL,"prompt":prompt,"stream":False});r.raise_for_status();text=r.json().get("response")
  if not text:raise RuntimeError("AI returned no response text")
  return text.strip()
def _fallback_message(lead,research):
 problems=[str(x) for x in (research.get("problems") or []) if str(x).strip()]
 services=[str(x) for x in (lead.get("recommended_services") or []) if str(x).strip()]
 if not problems:return "Insufficient verified intelligence for a personalized pitch. Run or expand research before generating outreach."
 name=str(lead.get("name") or "there");service=", ".join(services[:2]) or "your online presence"
 return f"Hi {name}, I noticed {problems[0].lower()} We help businesses improve {service} with practical, measurable work. If useful, I can share a short audit with a few specific recommendations—no pressure."
async def generate_whatsapp_message(lead,research=None):
 r=research or {};facts={"business":lead.get("name"),"industry":lead.get("industry"),"city":lead.get("city"),"website":lead.get("website"),"recommended_services":lead.get("recommended_services"),"verified_problems":r.get("problems") or [],"research_contract":(r.get("meta") or {}).get("contract_version")}
 if not facts["verified_problems"]:return _fallback_message(lead,r)
 prompt="""Write a concise professional first-contact WhatsApp message. Use only supplied verified facts. Mention 1-2 observations only from verified_problems. Never invent rankings, reviews, customers, results or technical facts. No guarantees. 80-120 words. Return only the message.\nFACTS:\n"""+json.dumps(facts,ensure_ascii=False,default=str)
 try:return await ollama_generate(prompt)
 except Exception:return _fallback_message(lead,r)
