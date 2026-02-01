from langgraph_agents.langgraph_system import BaseAgent
from typing import Dict, Any
import json
import os
import logging
import re
import ast
from utils.CommonLogger import CommonLogger

class IntentAgent(BaseAgent):
    """
    AGENT: Intent & Classification Agent
    DESCRIPTION: Detects intent, urgency, and SLA risk from normalized input.
    CAPABILITIES: intent_classification, urgency_detection, sla_monitoring
    OWNS: [PRD 4.3] Urgency scoring, Intent/Tagging logic.
    REQUIRED_PACKAGES: scikit-learn, nltk
    """

    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.logger = logging.getLogger("IntentAgent")
        self.intent_rules = self._load_config("intent_config.json")
        self.safety_rules = self._load_config("safety_policy.json")
        
        # Initialize LLM client for smart layer analysis
        try:
            from llm_client import LLMClient
            self.llm = LLMClient(agent_type="intent_classifier", debug=debug)
        except ImportError:
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from llm_client import LLMClient
            self.llm = LLMClient(agent_type="intent_classifier", debug=debug)

    def _load_config(self, filename: str) -> Dict[str, Any]:
        """Load JSON config files from policies folder."""
        try:
            path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "policies", filename)
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config {filename}: {e}")
            return {}

    async def _execute_impl(self) -> Dict[str, Any]:
        """
        Implementation of intent classification logic.
        """
        # TODO: Refactor this agent to use the "Configurable Policy" and "Hybrid Guardrail" patterns.
        # Reference Configs: 
        #   - policies/intent_config.json (Categories, SLA rules)
        #   - policies/safety_policy.json (Regex patterns, Semantic guidelines)

        # STEP 1: LOAD CONFIGURATIONS (Already loaded in __init__)
        # self.intent_rules - Loaded from intent_config.json
        # self.safety_rules - Loaded from safety_policy.json

        # Get user query from state store (written by Ingestion Agent)
        raw_state = self.state_store.get_all()
        CommonLogger.WriteLog("logs/intent_agent_debug.log", f"Raw state from state store in intent_agent: {json.dumps(raw_state, indent=2)}")
        ingestion_output = raw_state.get("ingestion_agent_output")
        if not ingestion_output:
            self.logger.error("No ingestion_agent_output found in state store")
            return {"status": "error", "message": "Missing ingestion agent output"}
        
        normalized_data = ingestion_output.get("normalized_payload")
        if not normalized_data:
            self.logger.error("No normalized_payload found in ingestion_agent_output")
            return {"status": "error", "message": "Missing normalized payload"}
        
        user_query = normalized_data.get("cleaned_text", "")
        self.logger.info(f"Processing query: {user_query[:100]}...")

        # STEP 2: FAST LAYER GUARDRAIL (REGEX)
        # Check user query against 'regex_patterns' from safety_policy.json.
        # If match found -> Mark as unsafe immediately, skipping LLM cost.
        regex_patterns = self.safety_rules.get("regex_patterns", [])
        is_safe = True
        safety_violation = None
        
        for pattern in regex_patterns:
            try:
                if re.search(pattern, user_query, re.IGNORECASE):
                    is_safe = False
                    safety_violation = f"Regex pattern matched: {pattern}"
                    self.logger.warning(f"Safety violation detected: {safety_violation}")
                    break
            except re.error as e:
                self.logger.error(f"Invalid regex pattern '{pattern}': {e}")
        
        # If unsafe, return immediately without LLM call
        if not is_safe:
            from models.model_intent_agent import IntentClassification
            unsafe_result = IntentClassification(
                primary_intent="safety_violation",
                confidence_score=1.0,
                urgency_level="critical",
                sla_risk_score=1.0,
                reasoning=safety_violation
            )
            await self.state_store.set("intent_classification", unsafe_result.model_dump())
            return {
                "status": "blocked",
                "classification": unsafe_result.model_dump(),
                "message": "Content violates safety policy"
            }


        # STEP 2.5: KEYWORD HEURISTICS (SIGNAL BOOSTING)
        # Check query against 'heuristic_keywords' in intent_config.json.
        # NOTE: Keywords are NOT enough! "My server is down" (Outage) vs "Put a down payment" (Billing).
        # We need NLP to distinguish context.
        heuristic_keywords = self.intent_rules.get("heuristic_keywords", {})
        keyword_hints = []
        urgency_boost = "low"  # Default urgency
        
        user_query_lower = user_query.lower()
        
        for category, keywords in heuristic_keywords.items():
            for keyword in keywords:
                if keyword.lower() in user_query_lower:
                    keyword_hints.append({
                        "category": category,
                        "keyword": keyword
                    })
                    self.logger.info(f"Keyword hint detected: '{keyword}' suggests '{category}'")
                    
                    # Immediately escalate urgency if outage keywords are present
                    if category == "outage_report":
                        urgency_boost = "critical"
                        self.logger.warning(f"Urgency escalated to CRITICAL due to outage keyword: '{keyword}'")
        
        # Store keyword hints for LLM context in STEP 3
        keyword_context = {
            "hints": keyword_hints,
            "urgency_boost": urgency_boost,
            "suggested_categories": list(set([h["category"] for h in keyword_hints]))
        }
        self.logger.info(f"Keyword analysis complete: {len(keyword_hints)} hints detected")

        # STEP 3: SMART LAYER (LLM-AS-A-JUDGE)
        # Construct a prompt for the LLM that includes context from configs and keyword hints
        semantic_guidelines = self.safety_rules.get("semantic_guidelines", {})
        category_definitions = self.intent_rules.get("category_definitions", {})
        valid_categories = self.intent_rules.get("categories", [])
        
        # Build comprehensive prompt for LLM
        llm_prompt = f"""You are an AI intent classifier analyzing user support queries.

USER QUERY:
{user_query}

VALID INTENT CATEGORIES:
{json.dumps(category_definitions, indent=2)}

SAFETY GUIDELINES (Forbidden Topics):
{json.dumps(semantic_guidelines, indent=2)}

KEYWORD HINTS (From heuristic analysis):
- Suggested categories: {keyword_context['suggested_categories']}
- Urgency boost recommendation: {keyword_context['urgency_boost']}
- Detected keywords: {[h['keyword'] for h in keyword_hints]}

INSTRUCTIONS:
1. Analyze the user query for safety violations based on semantic guidelines
2. Classify the primary intent using the category definitions (context is critical!)
3. Determine urgency level: "low", "medium", "high", or "critical"
4. Provide clear reasoning for your classification

OUTPUT FORMAT (JSON):
{{
    "is_safe": true/false,
    "primary_intent": "one of {valid_categories}",
    "urgency": "low|medium|high|critical",
    "reasoning": "explanation of your analysis"
}}

Return ONLY valid JSON, no additional text."""

        self.logger.info("Calling LLM for intent classification...")
        
        try:
            # Call LLM with structured prompt
            llm_response = self.llm.generate(
                llm_prompt,
                max_tokens=500,
                temperature=0.3  # Lower temperature for consistent classification
            )
            
            # Parse JSON response - handle escaped newlines in LLM response
            try:
                # Try to evaluate as Python string literal first (handles escaped \n)
                actual_response = ast.literal_eval(llm_response)
            except (ValueError, SyntaxError):
                actual_response = llm_response
            
            # Remove markdown code fences
            actual_response = actual_response.replace("```json", "").replace("```", "").strip()
            
            # Extract JSON object
            json_match = re.search(r'\{.*\}', actual_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                # Escape all newlines for valid JSON, then selectively unescape structural ones
                json_str = json_str.replace('\n', '\\n').replace('\r', '\\r')
                # Unescape newlines that are part of JSON structure (after commas, braces)
                json_str = json_str.replace(',\\n', ',\n').replace('{\\n', '{\n').replace('\\n}', '\n}')
                llm_result = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON object found in response", actual_response, 0)
            
            CommonLogger.WriteLog("logs/intent_agent_llm_classification.log", f"LLM classification: {llm_result.get('primary_intent')}, urgency: {llm_result.get('urgency')}")
        
            
            # Validate LLM output
            if not llm_result.get("is_safe", True):
                self.logger.warning(f"LLM detected safety violation: {llm_result.get('reasoning')}")
            
            # Extract classification results
            primary_intent = llm_result.get("primary_intent", "unknown")
            urgency = llm_result.get("urgency", "low")
            reasoning = llm_result.get("reasoning", "LLM classification completed")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM JSON response: {e}")
            self.logger.error(f"Raw LLM response: {llm_response[:200]}")
            CommonLogger.WriteLog("logs/intent_agent_llm_response.log", f"LLM response in intent_agent: {json.dumps(llm_response, indent=2)}")
            # Fallback to keyword hints
            primary_intent = keyword_context['suggested_categories'][0] if keyword_context['suggested_categories'] else "technical_issue"
            urgency = keyword_context['urgency_boost']
            reasoning = f"LLM parsing failed, used keyword heuristics. Error: {str(e)}"
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            # Fallback to keyword hints
            primary_intent = keyword_context['suggested_categories'][0] if keyword_context['suggested_categories'] else "technical_issue"
            urgency = keyword_context['urgency_boost']
            reasoning = f"LLM call failed, used keyword heuristics. Error: {str(e)}"

        # STEP 4: SLA & RISK CALCULATION
        # Match 'primary_intent' to 'sla_thresholds_hours' in intent_config.json.
        sla_thresholds = self.intent_rules.get("sla_thresholds_hours", {})
        sla_hours = sla_thresholds.get(primary_intent, sla_thresholds.get("default", 8))
        
        # Calculate sla_risk_score (0.0 - 1.0) based on urgency and SLA window
        # Logic: Shorter SLA window + Higher urgency = Higher risk
        urgency_weights = {
            "critical": 1.0,
            "high": 0.75,
            "medium": 0.5,
            "low": 0.25
        }
        
        # Base risk from urgency
        urgency_risk = urgency_weights.get(urgency, 0.5)
        
        # Adjust risk based on SLA window (shorter window = higher base risk)
        # Normalize SLA hours: 1 hour (highest risk) to 72 hours (lowest risk)
        if sla_hours <= 1:
            sla_factor = 0.9
        elif sla_hours <= 4:
            sla_factor = 0.7
        elif sla_hours <= 8:
            sla_factor = 0.5
        elif sla_hours <= 24:
            sla_factor = 0.3
        else:
            sla_factor = 0.1
        
        # Combine urgency and SLA factors
        # Weight: 60% urgency, 40% SLA window
        sla_risk_score = (urgency_risk * 0.6) + (sla_factor * 0.4)
        
        # Ensure within bounds
        sla_risk_score = max(0.0, min(1.0, sla_risk_score))
        
        self.logger.info(f"SLA calculation: intent={primary_intent}, threshold={sla_hours}h, urgency={urgency}, risk_score={sla_risk_score:.2f}")

        # STEP 5: OUTPUT TO STATE STORE
        # Create 'IntentClassification' Pydantic model with all calculated data
        from models.model_intent_agent import IntentClassification
        
        # Calculate confidence score
        # High confidence if LLM succeeded, lower if we fell back to keywords
        if 'llm_result' in locals() and isinstance(llm_result, dict):
            confidence_score = 0.85  # LLM-based classification
        else:
            confidence_score = 0.6  # Keyword-based fallback
        
        # Collect secondary intents from keyword hints (excluding primary)
        secondary_intents = [
            cat for cat in keyword_context['suggested_categories'] 
            if cat != primary_intent
        ]
        
        # Create the IntentClassification model
        intent_classification = IntentClassification(
            primary_intent=primary_intent,
            confidence_score=confidence_score,
            urgency_level=urgency,
            sla_risk_score=sla_risk_score,
            secondary_intents=secondary_intents,
            reasoning=reasoning
        )
        
        # Save to state store for downstream agents
        await self.state_store.set("intent_classification", intent_classification.model_dump())
        
        self.logger.info(f"Intent classification complete and saved to state store")
        self.logger.info(f"Final result: intent={primary_intent}, urgency={urgency}, sla_risk={sla_risk_score:.2f}, confidence={confidence_score:.2f}")
        
        # Return success with classification details
        return {
            "status": "success",
            "classification": intent_classification.model_dump(),
            "message": "Intent classification completed successfully"
        }
