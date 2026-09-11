import os
import json
import httpx

# REAL: queries Groq completions endpoint directly
async def chat(system_prompt: str, user_prompt: str) -> str:
    """
    Calls Groq API with system and user prompt.
    Returns plain text or raises error if API fails.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured in environment.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    model_name = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [])[0].get("message", {}).get("content", "")

# REAL: queries Groq completions endpoint requesting JSON object output
async def chat_json(system_prompt: str, user_prompt: str) -> dict:
    """
    Calls Groq API requesting JSON format.
    Returns dict or raises error if API fails.
    """
    api_key = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured in environment.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }
    model_name = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    payload = {
        "model": model_name,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        text_response = data.get("choices", [])[0].get("message", {}).get("content", "{}")
        return json.loads(text_response)

