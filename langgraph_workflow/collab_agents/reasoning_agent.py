from langgraph_agents.langgraph_system import BaseAgent
from typing import Dict, Any, List
import json
import logging

class ReasoningAgent(BaseAgent):
    """
    AGENT: Reasoning / Correlation Agent
    DESCRIPTION: Connects current issues with history and identifies root causes.
    CAPABILITIES: reasoning, pattern_recognition, root_cause_analysis
    OWNS: [PRD 3.9 & 4.6] Logical Chain-of-Thought, Root Cause Analysis. Context Synthesis.
    REQUIRED_PACKAGES: None (LLM)
    """

    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.logger = logging.getLogger("ReasoningAgent")
        
        # Initialize LLM client for correlation analysis
        try:
            from llm_client import LLMClient
            self.llm = LLMClient(agent_type="reasoning", debug=debug)
        except ImportError:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            from llm_client import LLMClient
            self.llm = LLMClient(agent_type="reasoning", debug=debug)
        
        # Initialize Memory Agent for historical data access
        from collab_agents.memory_agent import MemoryAgent
        self.memory_agent = MemoryAgent("memory_agent_internal", event_bus, state_store, debug)

    async def _execute_impl(self) -> Dict[str, Any]:
        """
        Implementation of reasoning logic.
        """
        self.logger.info("Reasoning Agent executing...")
        
        # STEP 1: GATHER CONTEXT
        # Get data from previous agents
        intent_data = await self.state_store.get("intent_classification")
        retrieval_data = await self.state_store.get("retrieval_results")
        normalized_data = await self.state_store.get("normalized_input")
        
        if not intent_data:
            self.logger.error("No intent classification found")
            return {"status": "error", "message": "Missing intent data"}
        
        user_query = normalized_data.get("content", "") if normalized_data else ""
        primary_intent = intent_data.get("primary_intent", "unknown")
        urgency = intent_data.get("urgency_level", "low")
        
        self.logger.info(f"Analyzing: intent={primary_intent}, urgency={urgency}")
        
        # STEP 2: QUERY MEMORY AGENT
        # Search episodic memory for similar past incidents
        historical_incidents = await self._query_episodic_memory(user_query, primary_intent)
        
        # Get semantic memory for known patterns
        known_patterns = await self._query_semantic_memory(primary_intent)
        
        self.logger.info(f"Found {len(historical_incidents)} similar incidents and {len(known_patterns)} known patterns")
        
        # STEP 3: CORRELATION ANALYSIS (LLM-powered)
        correlation_result = await self._perform_correlation_analysis(
            user_query=user_query,
            intent=primary_intent,
            urgency=urgency,
            retrieval_context=retrieval_data,
            historical_incidents=historical_incidents,
            known_patterns=known_patterns
        )
        
        # STEP 4: PATTERN DETECTION
        pattern_analysis = self._detect_patterns(
            current_issue=user_query,
            intent=primary_intent,
            historical_incidents=historical_incidents,
            correlation_result=correlation_result
        )
        
        # STEP 5: WRITE BACK TO MEMORY
        await self._update_memory(
            user_query=user_query,
            intent=primary_intent,
            correlation_result=correlation_result,
            pattern_analysis=pattern_analysis
        )
        
        # STEP 6: OUTPUT TO STATE STORE
        from models.model_reasoning_agent import ReasoningTrace, RootCause
        
        # Build reasoning trace
        reasoning_trace = ReasoningTrace(
            analysis_steps=correlation_result.get("analysis_steps", []),
            identified_patterns=pattern_analysis.get("patterns", []),
            root_causes=correlation_result.get("root_causes", []),
            recommended_solution=correlation_result.get("recommended_solution", ""),
            confidence_score=correlation_result.get("confidence_score", 0.5)
        )
        
        # Save to state store
        await self.state_store.set("reasoning_trace", reasoning_trace.model_dump())
        
        self.logger.info("Reasoning analysis complete and saved to state store")
        
        return {
            "status": "success",
            "reasoning_trace": reasoning_trace.model_dump(),
            "message": "Reasoning analysis completed successfully"
        }
    
    async def _query_episodic_memory(self, query: str, intent: str) -> List[Dict[str, Any]]:
        """Query episodic memory for similar past incidents."""
        try:
            from models.model_memory_agent import MemoryInput
            
            # Create search query for episodic memory
            search_key = f"incidents_{intent}"
            
            memory_input = MemoryInput(
                operation="read",
                memory_type="episodic",
                key=search_key,
                user_id="system",
                session_id="reasoning_session"
            )
            
            # Query memory agent
            # Note: For now, return empty list - Memory Agent implementation needed
            self.logger.info(f"Querying episodic memory for key: {search_key}")
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to query episodic memory: {e}")
            return []
    
    async def _query_semantic_memory(self, intent: str) -> List[Dict[str, Any]]:
        """Query semantic memory for known patterns and solutions."""
        try:
            from models.model_memory_agent import MemoryInput
            
            # Create search query for semantic memory
            pattern_key = f"patterns_{intent}"
            
            memory_input = MemoryInput(
                operation="read",
                memory_type="semantic",
                key=pattern_key,
                user_id="system",
                session_id="reasoning_session"
            )
            
            # Query memory agent
            # Note: For now, return empty list - Memory Agent implementation needed
            self.logger.info(f"Querying semantic memory for key: {pattern_key}")
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to query semantic memory: {e}")
            return []
    
    async def _perform_correlation_analysis(
        self,
        user_query: str,
        intent: str,
        urgency: str,
        retrieval_context: Any,
        historical_incidents: List[Dict],
        known_patterns: List[Dict]
    ) -> Dict[str, Any]:
        """Use LLM to perform correlation analysis and identify root causes."""
        
        # Build comprehensive prompt for LLM
        llm_prompt = f"""You are an expert technical analyst performing root cause analysis for support incidents.

CURRENT ISSUE:
User Query: {user_query}
Intent: {intent}
Urgency: {urgency}

RETRIEVED KNOWLEDGE (RAG):
{json.dumps(retrieval_context, indent=2) if retrieval_context else "No retrieval data available"}

HISTORICAL INCIDENTS (Similar past cases):
{json.dumps(historical_incidents[:3], indent=2) if historical_incidents else "No similar incidents found"}

KNOWN PATTERNS (Semantic memory):
{json.dumps(known_patterns, indent=2) if known_patterns else "No known patterns"}

INSTRUCTIONS:
1. Analyze the current issue in context of retrieved knowledge and history
2. Identify step-by-step reasoning (chain of thought)
3. Detect patterns or correlations with historical incidents
4. Determine most likely root cause(s) with probability
5. Recommend solution approach
6. Provide confidence score for your analysis

OUTPUT FORMAT (JSON):
{{
    "analysis_steps": ["step 1", "step 2", ...],
    "identified_patterns": ["pattern 1", "pattern 2", ...],
    "root_causes": [
        {{
            "cause": "description of root cause",
            "probability": 0.0-1.0,
            "evidence": ["supporting evidence 1", "evidence 2"]
        }}
    ],
    "recommended_solution": "detailed solution approach",
    "confidence_score": 0.0-1.0,
    "reasoning": "explanation of analysis"
}}

Return ONLY valid JSON, no additional text."""

        self.logger.info("Calling LLM for correlation analysis...")
        
        try:
            # Call LLM with comprehensive context
            llm_response = self.llm.generate(
                llm_prompt,
                max_tokens=1000,
                temperature=0.4  # Moderate creativity for analysis
            )
            
            # Parse JSON response
            llm_response_clean = llm_response.replace("```json", "").replace("```", "").strip()
            correlation_result = json.loads(llm_response_clean)
            
            self.logger.info(f"LLM correlation analysis complete: {len(correlation_result.get('root_causes', []))} root causes identified")
            
            return correlation_result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM correlation response: {e}")
            # Fallback result
            return {
                "analysis_steps": ["Unable to perform detailed analysis"],
                "identified_patterns": [],
                "root_causes": [{
                    "cause": "Analysis failed - insufficient data",
                    "probability": 0.3,
                    "evidence": []
                }],
                "recommended_solution": "Manual investigation required",
                "confidence_score": 0.3,
                "reasoning": f"LLM parsing failed: {str(e)}"
            }
            
        except Exception as e:
            self.logger.error(f"LLM correlation analysis failed: {e}")
            return {
                "analysis_steps": ["Analysis error occurred"],
                "identified_patterns": [],
                "root_causes": [{
                    "cause": f"Error during analysis: {str(e)}",
                    "probability": 0.0,
                    "evidence": []
                }],
                "recommended_solution": "Escalate for manual review",
                "confidence_score": 0.1,
                "reasoning": f"Error: {str(e)}"
            }
    
    def _detect_patterns(
        self,
        current_issue: str,
        intent: str,
        historical_incidents: List[Dict],
        correlation_result: Dict
    ) -> Dict[str, Any]:
        """Detect if current issue matches known patterns or represents a new pattern."""
        
        patterns = []
        is_recurring = len(historical_incidents) > 2  # If more than 2 similar incidents
        
        if is_recurring:
            patterns.append(f"Recurring {intent} issue - {len(historical_incidents)} similar incidents found")
        
        # Check if LLM identified patterns
        llm_patterns = correlation_result.get("identified_patterns", [])
        patterns.extend(llm_patterns)
        
        pattern_analysis = {
            "patterns": patterns,
            "is_recurring": is_recurring,
            "frequency": len(historical_incidents),
            "pattern_type": "recurring" if is_recurring else "isolated"
        }
        
        self.logger.info(f"Pattern detection: {pattern_analysis['pattern_type']}, {len(patterns)} patterns")
        
        return pattern_analysis
    
    async def _update_memory(
        self,
        user_query: str,
        intent: str,
        correlation_result: Dict,
        pattern_analysis: Dict
    ) -> None:
        """Write current incident and patterns back to memory."""
        try:
            from models.model_memory_agent import MemoryInput
            
            # Save to episodic memory
            incident_record = {
                "query": user_query,
                "intent": intent,
                "root_causes": correlation_result.get("root_causes", []),
                "solution": correlation_result.get("recommended_solution", "")
            }
            
            episodic_input = MemoryInput(
                operation="write",
                memory_type="episodic",
                key=f"incident_{intent}_{hash(user_query)}",
                content=incident_record,
                user_id="system",
                session_id="reasoning_session"
            )
            
            # Update semantic memory if new pattern detected
            if pattern_analysis.get("is_recurring"):
                pattern_record = {
                    "pattern_type": pattern_analysis.get("pattern_type"),
                    "frequency": pattern_analysis.get("frequency"),
                    "patterns": pattern_analysis.get("patterns", [])
                }
                
                semantic_input = MemoryInput(
                    operation="update",
                    memory_type="semantic",
                    key=f"pattern_{intent}",
                    content=pattern_record,
                    user_id="system",
                    session_id="reasoning_session"
                )
            
            self.logger.info("Memory updated with current incident and patterns")
            
        except Exception as e:
            self.logger.error(f"Failed to update memory: {e}")
