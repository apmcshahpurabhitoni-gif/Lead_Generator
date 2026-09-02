import json,os,httpx
BASE_URL=os.getenv("OLLAMA_BASE_URL","https://ollama.com/api").rstrip("/")
MODEL=os.getenv("OLLAMA_MODEL","gemma4")
async def ollama_generate(prompt:str)->str:
 key=os.getenv("OLLAMA_API_KEY","").strip()
 if not key: raise RuntimeError("OLLAMA_API_KEY is not configured")
 async with httpx.AsyncClient(timeout=60) as client:
  r=await client.post(f"{BASE_URL}/generate",headers={"Authorization":f"Bearer {key}"},json={"model":MODEL,"prompt":prompt,"stream":False}); r.raise_for_status(); text=r.json().get("response")
  if not text: raise RuntimeError("Ollama returned no response text")
  return text.strip()
async def generate_whatsapp_message(lead:dict,research:dict|None)->str:
 r=research or {}; g=r.get("google",{}); s=r.get("search",{}); score=lead.get("score"); facts={"business":lead.get("name"),"industry":lead.get("industry"),"city":lead.get("city"),"website":lead.get("website"),"phone":lead.get("phone"),"email":lead.get("email"),"opportunity_score":score,"google_local_rank":g.get("local_rank"),"google_query":s.get("query"),"rating":g.get("rating"),"reviews":g.get("review_count"),"recommended_services":lead.get("recommended_services"),"verified_problems":lead.get("problems"),"score_breakdown":r.get("score_breakdown")}
 prompt="""Write a professional, human first-contact WhatsApp message for a digital services agency. The recipient must immediately understand WHY we are contacting them. Use only the supplied facts. Mention 1-2 specific verified observations, such as a missing website, weak website SEO signal, or Google local position. Do not invent rankings, reviews, phone/email, customers, revenue or results. Do not promise a Google ranking or guaranteed outcome. Do not mention the internal opportunity score. Be respectful and concise (80-120 words). End with a low-pressure offer to share a short audit. Return only the message.\n\nFACTS:\n"""+json.dumps(facts,ensure_ascii=False,default=str)
 return await ollama_generate(prompt)
