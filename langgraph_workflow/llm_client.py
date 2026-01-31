# LLM Client Abstraction Layer
# Supports Mistral AI, easily swappable for other providers
# Enhanced with JSON length and token usage logging

import requests
import json
import re
from config import LLM_PROVIDER, LLM_API_KEY, LLM_API_URL, LLM_MODEL

try:
    from utils.toon_converter import JsonToToonConverter
except ImportError:
    # Handle case where utils is not in path or circular import
    JsonToToonConverter = None

class LLMClient:
    def __init__(self, agent_type="default", debug=False):
        self.provider = LLM_PROVIDER
        self.api_key = LLM_API_KEY
        self.api_url = LLM_API_URL
        self.debug = debug
        self.agent_type = agent_type
        # Select model based on agent type
        from config import LLM_MODELS
        self.model = LLM_MODELS.get(agent_type, LLM_MODELS["default"])
        if self.debug:
            print(f"[DEBUG] LLMClient initialized for agent '{agent_type}' with model '{self.model}'")
    
    def _estimate_tokens(self, text):

        """Estimate token count for text"""
        # More accurate token estimation
        words = len(re.findall(r'\b\w+\b', text))
        punctuation = len(re.findall(r'[{}[\](),.;:"\'\\]', text))
        whitespace = len(re.findall(r'\s', text))
        # Approximate: words ~1 token, punctuation ~0.5 token, whitespace ~0.2 token
        return int(words + (punctuation * 0.5) + (whitespace * 0.2))
    
    def _log_usage_stats(self, prompt, response, request_tokens, response_tokens):
        """Log detailed usage statistics for each LLM call"""
        prompt_length = len(prompt)
        response_length = len(response)
        total_tokens = request_tokens + response_tokens
        
        print(f"[LLM-STATS] Agent: {self.agent_type}")
        print(f"[LLM-STATS] Model: {self.model}")
        print(f"[LLM-STATS] Request - JSON Length: {prompt_length} chars, Estimated Tokens: {request_tokens}")
        print(f"[LLM-STATS] Response - JSON Length: {response_length} chars, Estimated Tokens: {response_tokens}")
        print(f"[LLM-STATS] Total Tokens Used: {total_tokens}")
        print(f"[LLM-STATS] ---")

    def generate(self, prompt, **kwargs):
        # Calculate input tokens
        request_tokens = self._estimate_tokens(prompt)
        
        if self.provider == "mistral":
            response = self._call_mistral(prompt, **kwargs)
            
            # Calculate response tokens
            response_tokens = self._estimate_tokens(response)
            
            # Log usage statistics
            self._log_usage_stats(prompt, response, request_tokens, response_tokens)
            
            return response
        # Add other providers here
        raise NotImplementedError("Provider not supported")

    def generate_structured(self, system_prompt, input_payload, response_schema_hint=None, **kwargs):
        """
        Optimized generation using TOON (Token-Oriented Object Notation).
        1. Encodes input_payload to TOON to save request tokens.
        2. Asks LLM to respond in TOON (or JSON) to save response tokens.
        3. Decodes response back to Python dict.
        """
        if not JsonToToonConverter:
            # Fallback to standard JSON if converter not available
            json_str = json.dumps(input_payload, ensure_ascii=False)
            full_prompt = f"{system_prompt}\n\nContext Data (JSON):\n{json_str}"
            response = self.generate(full_prompt, **kwargs)
            try:
                return json.loads(response)
            except:
                return {"raw_response": response}

        # 1. Encode Input
        # Auto-generate mapping on the fly for this payload
        mapping = JsonToToonConverter._generate_auto_mapping(input_payload)
        toon_input = JsonToToonConverter.encode(input_payload, mapping=mapping)
        
        # 2. Construct Prompt
        # We instruct the LLM about the format.
        prompt = (
            f"{system_prompt}\n\n"
            f"DATA_CONTEXT (compact format): {toon_input}\n\n"
            f"INSTRUCTION: Return the response in compatible compact format (or valid JSON)."
        )
        if response_schema_hint:
             prompt += f"\nEXPECTED OUTPUT FIELDS: {response_schema_hint}"

        # 3. Call LLM
        response_text = self.generate(prompt, **kwargs)

        # 4. Decode Output
        # We try to decode using the same mapping (assuming LLM respects keys) 
        # OR fallback to standard parsing if LLM outputted standard keys.
        try:
            # Try TOON decode with mapping
            decoded = JsonToToonConverter.decode(response_text, mapping=mapping)
            if isinstance(decoded, dict) or isinstance(decoded, list):
                return decoded
        except Exception:
            pass
            
        # Try JSON decode
        try:
            # Clean potential markdown code blocks
            clean = response_text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)
        except:
             # Last ditch: return raw
             return {"raw_response": response_text}

    def _call_mistral(self, prompt, **kwargs):

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,  # Use agent-specific model
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": kwargs.get("max_tokens", 1024),
            "temperature": kwargs.get("temperature", 0.7)
        }
        # Add top_p if provided
        if "top_p" in kwargs:
            payload["top_p"] = kwargs["top_p"]
        if self.debug:
            print("[DEBUG] Sending payload to Mistral:", payload)
        response = requests.post(f"{self.api_url}/chat/completions", json=payload, headers=headers)
        if self.debug:
            print("[DEBUG] Response status:", response.status_code)
            print("[DEBUG] Response text:", response.text)
        try:
            response.raise_for_status()
        except Exception as e:
            if self.debug:
                print("[ERROR] Mistral API error:", e)
            raise
        return response.json()["choices"][0]["message"]["content"]
