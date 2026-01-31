import json
import os
import re
from typing import Any, Dict, List, Optional

from llm_client import LLMClient
from models.model_intent_agent import IntentClassification

try:
    from utils.toon_converter import JsonToToonConverter
except Exception:
    # fallback when running from repo root
    from toon_converter import JsonToToonConverter


class NLPService:
    """
    Shared NLP service for intent classification, safety checks, and entity extraction.
    Uses LLMClient and policy configs under /policies.
    """

    def __init__(self, agent_type: str = "intent", debug: bool = False, policies_dir: Optional[str] = None):
        self.debug = debug
        self.llm = LLMClient(agent_type=agent_type, debug=debug)
        self.policies_dir = policies_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies")
        self.intent_config = self._load_json("intent_config.json")
        self.safety_policy = self._load_json("safety_policy.json")
        # No static mapping file needed; we generate on fly or rely on context
        self.toon_mapping = None

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.policies_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            if self.debug:
                print(f"[NLPService] Failed to load {filename}: {e}")
            return {}

    def _extract_json(self, text: str) -> Dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return {}
        return {}

    def _call_llm_json(self, prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> Dict[str, Any]:
        response = self.llm.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        return self._extract_json(response)

    def _call_llm_toon_aware(self, prompt: str, max_tokens: int = 512, temperature: float = 0.0) -> Dict[str, Any]:
        """
        Call LLM and accept either JSON or TOON responses. If JSON parse fails,
        attempt to decode as TOON using JsonToToonConverter and the loaded mapping.
        """
        response = self.llm.generate(prompt, max_tokens=max_tokens, temperature=temperature)
        # Try JSON first
        parsed = self._extract_json(response)
        if parsed:
            return parsed
        # Try TOON decode
        try:
            decoded = JsonToToonConverter.decode(response, mapping=self.toon_mapping)
            if isinstance(decoded, dict):
                return decoded
        except Exception:
            pass
        # Fallback empty
        return {}

    def _keyword_intent_hint(self, text: str) -> Optional[str]:
        keywords = self.intent_config.get("heuristic_keywords", {})
        lowered = text.lower()
        for intent, words in keywords.items():
            if any(word.lower() in lowered for word in words):
                return intent
        return None

    def _calculate_sla_risk(self, primary_intent: str, urgency: str) -> float:
        thresholds = self.intent_config.get("sla_thresholds_hours", {})
        hours = thresholds.get(primary_intent, thresholds.get("default", 8))

        if urgency == "critical":
            return 0.95
        if urgency == "high":
            return 0.8
        if hours <= 2:
            return 0.7
        if hours <= 4:
            return 0.6
        if hours <= 8:
            return 0.4
        return 0.2

    def safety_check(self, text: str) -> Dict[str, Any]:
        patterns = self.safety_policy.get("regex_patterns", [])
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return {
                    "is_safe": False,
                    "severity": "high",
                    "reason": "Matched disallowed regex pattern",
                    "action": self.safety_policy.get("actions", {}).get("high_severity", "block_and_escalate")
                }

        guidelines = self.safety_policy.get("semantic_guidelines", {})
        forbidden = self.safety_policy.get("forbidden_topics", [])

        prompt = (
            "You are a safety classifier for a support assistant. "
            "Decide if the user query is allowed. Output ONLY JSON.\n\n"
            f"Forbidden topics: {forbidden}\n"
            f"Semantic guidelines: {guidelines}\n\n"
            f"Query: {text}\n\n"
            "Return JSON with keys: is_safe (bool), severity (low|medium|high), reason (string)."
        )

        result = self._call_llm_json(prompt)
        is_safe = bool(result.get("is_safe", True))
        severity = result.get("severity", "low")
        action_map = self.safety_policy.get("actions", {})

        return {
            "is_safe": is_safe,
            "severity": severity,
            "reason": result.get("reason", "No reason provided"),
            "action": action_map.get(f"{severity}_severity", action_map.get("low_severity", "log_warning"))
        }

    def analyze_intent(self, text: str) -> IntentClassification:
        categories = self.intent_config.get("categories", [])
        definitions = self.intent_config.get("category_definitions", {})
        hint = self._keyword_intent_hint(text)
        # Build a compact TOON context payload to reduce token usage when communicating with the LLM.
        context_payload = {
            "categories": categories,
            "definitions": definitions,
            "hint": hint
        }

        toon_context = JsonToToonConverter.encode(context_payload, mapping=self.toon_mapping)

        prompt = (
            "You are an intent classifier for a support system. "
            "The context is provided in a compact TOON encoding below. You MAY use it to answer. "
            "Prefer returning structured JSON, but if you return TOON, it will be decoded.\n\n"
            f"TOON_CONTEXT: {toon_context}\n\n"
            f"Query: {text}\n\n"
            "Return JSON with keys: primary_intent (string), secondary_intents (array), "
            "urgency_level (low|medium|high|critical), confidence_score (0-1), reasoning (string)."
        )

        result = self._call_llm_toon_aware(prompt)
        primary_intent = result.get("primary_intent", hint or "faq")
        urgency = result.get("urgency_level", "low")
        confidence = float(result.get("confidence_score", 0.4))
        secondary = result.get("secondary_intents", []) or []
        reasoning = result.get("reasoning")

        sla_risk = self._calculate_sla_risk(primary_intent, urgency)

        try:
            return IntentClassification(
                primary_intent=primary_intent,
                confidence_score=confidence,
                urgency_level=urgency,
                sla_risk_score=sla_risk,
                secondary_intents=secondary,
                reasoning=reasoning
            )
        except Exception:
            return IntentClassification(
                primary_intent=hint or "faq",
                confidence_score=0.3,
                urgency_level="low",
                sla_risk_score=0.2,
                secondary_intents=[],
                reasoning="Fallback intent due to parsing error."
            )

    def extract_entities(self, text: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Extract entities from the query based on the provided schema. "
            "Output ONLY JSON matching the schema.\n\n"
            f"Schema: {schema}\n\n"
            f"Query: {text}"
        )
        return self._call_llm_json(prompt, max_tokens=512, temperature=0.0)
