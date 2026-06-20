import os
import re
import json
import time
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import httpx
from zomato_recsys.data.ingestion import load_app_config

logger = logging.getLogger(__name__)

def load_groq_settings(repo_root: Path) -> Dict[str, Any]:
    """
    Load Groq API settings from config/app.toml, environment variables, 
    supporting fallback to LLM_API_KEY.
    """
    config_path = repo_root / "config" / "app.toml"
    config = {}
    if config_path.exists():
        try:
            config = load_app_config(config_path).get("groq", {})
        except Exception as e:
            logger.warning(f"Failed to load app config: {e}")
            
    # Read environment variables (take precedence)
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("LLM_API_KEY") or config.get("api_key", "")
    model = os.environ.get("GROQ_MODEL") or config.get("model", "llama-3.3-70b-specdec")
    base_url = os.environ.get("GROQ_BASE_URL") or config.get("base_url", "https://api.groq.com/openai/v1")
    
    use_json_object = True
    if "GROQ_JSON_OBJECT" in os.environ:
        use_json_object = os.environ["GROQ_JSON_OBJECT"].lower() in ("true", "1", "yes")
    else:
        use_json_object = config.get("use_json_object", True)
        
    timeout = float(config.get("timeout_seconds", 30.0))
    
    return {
        "api_key": api_key,
        "model": model,
        "base_url": base_url,
        "use_json_object": use_json_object,
        "timeout": timeout
    }

class LLMResult(object):
    def __init__(self, content: str, latency_ms: float, error: Optional[str] = None):
        self.content = content
        self.latency_ms = latency_ms
        self.error = error

class GroqChatClient:
    def __init__(self, settings: Dict[str, Any], client: Optional[httpx.Client] = None):
        self.api_key = settings.get("api_key", "")
        self.model = settings.get("model", "llama-3.3-70b-specdec")
        self.base_url = settings.get("base_url", "https://api.groq.com/openai/v1").rstrip("/")
        self.use_json_object = settings.get("use_json_object", True)
        self.timeout = settings.get("timeout", 30.0)
        self.client = client or httpx.Client()
        
    def complete(self, messages: List[Dict[str, str]]) -> LLMResult:
        """Call Groq Chat Completions API with retries and exponential backoff."""
        if not self.api_key:
            return LLMResult(
                content="",
                latency_ms=0.0,
                error="GROQ_API_KEY or LLM_API_KEY is not set. Please configure it in your environment or .env file."
            )
            
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1 # Low temperature for factual ranking
        }
        
        if self.use_json_object:
            payload["response_format"] = {"type": "json_object"}
            
        max_retries = 3
        backoff_factor = 2.0
        
        start_time = time.time()
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Sending LLM request to Groq (attempt {attempt + 1}/{max_retries})")
                response = self.client.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                
                # Check rate limit (429) or server errors (5xx)
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        sleep_time = backoff_factor ** attempt
                        logger.warning(f"Rate limited (429). Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        latency = (time.time() - start_time) * 1000.0
                        return LLMResult("", latency, f"Rate limit exceeded (429) after {max_retries} attempts.")
                        
                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        sleep_time = backoff_factor ** attempt
                        logger.warning(f"Server error ({response.status_code}). Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        latency = (time.time() - start_time) * 1000.0
                        return LLMResult("", latency, f"Server error ({response.status_code}) after {max_retries} attempts.")
                
                # Raise for other error status codes (e.g. 401, 403, 400)
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                latency = (time.time() - start_time) * 1000.0
                return LLMResult(content, latency)
                
            except httpx.HTTPStatusError as e:
                latency = (time.time() - start_time) * 1000.0
                err_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
                logger.error(err_msg)
                return LLMResult("", latency, err_msg)
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    sleep_time = backoff_factor ** attempt
                    logger.warning(f"Request error {e}. Retrying in {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                else:
                    latency = (time.time() - start_time) * 1000.0
                    err_msg = f"Failed to connect to Groq API: {e}"
                    logger.error(err_msg)
                    return LLMResult("", latency, err_msg)
                    
        latency = (time.time() - start_time) * 1000.0
        return LLMResult("", latency, "Unknown error during LLM request.")

def clean_json_fences(raw_content: str) -> str:
    """Strip optional ```json ... ``` fences if the model wraps the payload."""
    cleaned = raw_content.strip()
    if cleaned.startswith("```"):
        # Match ```json or ``` and strip the headers/footers
        match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
    return cleaned
