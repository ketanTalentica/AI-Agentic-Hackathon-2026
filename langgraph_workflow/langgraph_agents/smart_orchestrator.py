"""
AI-Driven Dynamic Workflow Orchestrator
Uses LLM to analyze prompts and select optimal agents
"""
import json
import asyncio
import os
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
try:
    from .langgraph_system import EventBus, StateStore, WorkflowMonitor, EventType, AgentEvent
    from ..llm_client import LLMClient
    from ..utils.CommonLogger import CommonLogger
    from ..config import UTILS_LOG_DIR_PATH
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from langgraph_agents.langgraph_system import EventBus, StateStore, WorkflowMonitor, EventType, AgentEvent
    from llm_client import LLMClient
    from utils.CommonLogger import CommonLogger
    from config import UTILS_LOG_DIR_PATH

@dataclass
class WorkflowPlan:
    selected_agents: List[str]
    execution_order: List[str]
    dependencies: Dict[str, List[str]]
    reasoning: str
    estimated_time: str
    estimated_cost: str

class AgentRegistry:
    """Manages agent definitions and capabilities"""
    
    def __init__(self, registry_path: str = None):
        if registry_path is None:
            # Default to agent_registry.json in the same directory as this file
            import os
            registry_path = os.path.join(os.path.dirname(__file__), "agent_registry.json")
        with open(registry_path, 'r') as f:
            self.registry_data = json.load(f)
            
    def get_all_agents(self) -> Dict[str, Any]:
        return self.registry_data["agents"]
        
    def get_agent_info(self, agent_id: str) -> Dict[str, Any]:
        return self.registry_data["agents"].get(agent_id, {})
        
    def get_workflow_templates(self) -> Dict[str, Any]:
        return self.registry_data.get("workflow_templates", {})
        
    def search_agents_by_capability(self, capability: str) -> List[str]:
        matching_agents = []
        for agent_id, agent_info in self.registry_data["agents"].items():
            if capability in agent_info.get("capabilities", []):
                matching_agents.append(agent_id)
        return matching_agents

class SmartOrchestrator:
    """AI-driven orchestrator that analyzes prompts and creates dynamic workflows"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.event_bus = EventBus()
        self.state_store = StateStore()
        self.monitor = WorkflowMonitor(self.event_bus)
        self.registry = AgentRegistry()
        self.llm = LLMClient(agent_type="content_generator", debug=debug)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.log_path = os.path.join(UTILS_LOG_DIR_PATH, f"smart_orchestrator_{timestamp}.jsonl")

    def _log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "payload": payload
        }
        CommonLogger.WriteLog(self.log_path, json.dumps(record, ensure_ascii=False))
        
    async def analyze_prompt(self, user_prompt: str) -> WorkflowPlan:
        """Analyze user prompt and create workflow plan"""
        self._log_event("input_received", {"user_prompt": user_prompt})
        
        # Get available agents and templates
        agents_info = self.registry.get_all_agents()
        templates = self.registry.get_workflow_templates()
        
        # Create analysis prompt for LLM
        analysis_prompt = self._build_analysis_prompt(user_prompt, agents_info, templates)
        
        try:
            # Get LLM analysis
            response = self.llm.generate(analysis_prompt, max_tokens=1500, temperature=0.3)
            
            # Parse response
            workflow_plan = self._parse_workflow_response(response)

            self._log_event("plan_created", {
                "selected_agents": workflow_plan.selected_agents,
                "execution_order": workflow_plan.execution_order,
                "dependencies": workflow_plan.dependencies,
                "reasoning": workflow_plan.reasoning,
                "estimated_time": workflow_plan.estimated_time,
                "estimated_cost": workflow_plan.estimated_cost
            })
            
            if self.debug:
                print(f"[SmartOrchestrator] Generated workflow plan:")
                print(f"  Agents: {workflow_plan.selected_agents}")
                print(f"  Order: {workflow_plan.execution_order}")
                print(f"  Reasoning: {workflow_plan.reasoning}")
                
            return workflow_plan
            
        except Exception as e:
            if self.debug:
                print(f"[SmartOrchestrator] Error analyzing prompt: {e}")
            self._log_event("plan_failed", {"error": str(e)})
            # Fallback to default workflow
            return self._create_default_workflow()
            
    def _build_analysis_prompt(self, user_prompt: str, agents_info: Dict, templates: Dict) -> str:
        """Build prompt for LLM to analyze user request"""
        
        agent_descriptions = []
        for agent_id, info in agents_info.items():
            agent_descriptions.append(
                f"- {agent_id}: {info['description']} "
                f"(capabilities: {', '.join(info['capabilities'])}, "
                f"dependencies: {info['dependencies']}, "
                f"cost: {info['cost_tier']})"
            )
            
        template_descriptions = []
        for template_id, info in templates.items():
            template_descriptions.append(
                f"- {template_id}: {info['description']} "
                f"(typical agents: {', '.join(info['typical_agents'])}, "
                f"keywords: {', '.join(info['keywords'])})"
            )
            
        prompt = f"""Analyze this user request and design an optimal workflow:

USER REQUEST: {user_prompt}

AVAILABLE AGENTS:
{chr(10).join(agent_descriptions)}

WORKFLOW TEMPLATES:
{chr(10).join(template_descriptions)}

Please return ONLY a valid JSON response with this structure:
{{
  "selected_agents": ["agent1", "agent2", "agent3"],
  "execution_order": ["agent1", "agent2", "agent3"],  
  "dependencies": {{"agent2": ["agent1"], "agent3": ["agent2"]}},
  "reasoning": "Brief explanation of why these agents were chosen",
  "estimated_time": "10-20 seconds",
  "estimated_cost": "low/medium/high"
}}

RULES:
1. Select 2-5 agents that best match the user's needs
2. Ensure dependencies are respected in execution_order
3. Consider cost-effectiveness (prefer lower cost agents when possible)
4. Include brief reasoning for your choices
5. Return ONLY valid JSON, no markdown or explanations"""

        return prompt
        
    def _parse_workflow_response(self, response: str) -> WorkflowPlan:
        """Parse LLM response into WorkflowPlan"""
        
        # Clean response
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        
        try:
            data = json.loads(cleaned)
            return WorkflowPlan(
                selected_agents=data.get("selected_agents", []),
                execution_order=data.get("execution_order", []), 
                dependencies=data.get("dependencies", {}),
                reasoning=data.get("reasoning", "No reasoning provided"),
                estimated_time=data.get("estimated_time", "Unknown"),
                estimated_cost=data.get("estimated_cost", "Unknown")
            )
        except json.JSONDecodeError as e:
            if self.debug:
                print(f"[SmartOrchestrator] JSON parse error: {e}")
                print(f"Response was: {cleaned}")
            return self._create_default_workflow()
            
    def _create_default_workflow(self) -> WorkflowPlan:
        """Create default workflow as fallback"""
        return WorkflowPlan(
            selected_agents=["interpreter_agent", "content_generator", "plan_presenter"],
            execution_order=["interpreter_agent", "content_generator", "plan_presenter"],
            dependencies={
                "content_generator": ["interpreter_agent"],
                "plan_presenter": ["content_generator"]
            },
            reasoning="Default email campaign workflow",
            estimated_time="15-25 seconds",
            estimated_cost="medium"
        )
        
    def present_plan_to_user(self, plan: WorkflowPlan) -> bool:
        """Present workflow plan to user for approval"""
        self._log_event("plan_presented", {
            "selected_agents": plan.selected_agents,
            "execution_order": plan.execution_order,
            "dependencies": plan.dependencies,
            "reasoning": plan.reasoning,
            "estimated_time": plan.estimated_time,
            "estimated_cost": plan.estimated_cost
        })
        
        print("\\n" + "="*50)
        print("🤖 PROPOSED WORKFLOW PLAN")
        print("="*50)
        print(f"📋 Selected Agents: {', '.join(plan.selected_agents)}")
        print(f"⚡ Execution Order: {' → '.join(plan.execution_order)}")  
        print(f"💭 Reasoning: {plan.reasoning}")
        print(f"⏱️  Estimated Time: {plan.estimated_time}")
        print(f"💰 Estimated Cost: {plan.estimated_cost}")
        
        if plan.dependencies:
            print(f"🔗 Dependencies:")
            for agent, deps in plan.dependencies.items():
                if deps:
                    print(f"   {agent} depends on: {', '.join(deps)}")
        
        print("="*50)
        
        while True:
            choice = input("Do you approve this workflow plan? (Y/N/D for details): ").strip().lower()
            
            if choice == 'y':
                self._log_event("plan_approved", {"approved": True})
                return True
            elif choice == 'n':
                self._log_event("plan_approved", {"approved": False})
                return False
            elif choice == 'd':
                self._show_detailed_plan(plan)
            else:
                print("Please enter Y (yes), N (no), or D (details)")
                
    def _show_detailed_plan(self, plan: WorkflowPlan):
        """Show detailed information about each agent in the plan"""
        
        print("\\n" + "="*60)
        print("📊 DETAILED WORKFLOW PLAN")
        print("="*60)
        
        for agent_id in plan.selected_agents:
            agent_info = self.registry.get_agent_info(agent_id)
            print(f"\\n🔧 {agent_id.upper()}")
            print(f"   Description: {agent_info.get('description', 'No description')}")
            print(f"   Capabilities: {', '.join(agent_info.get('capabilities', []))}")
            print(f"   Execution Time: {agent_info.get('execution_time_estimate', 'Unknown')}")
            print(f"   Cost Tier: {agent_info.get('cost_tier', 'Unknown')}")
            
            inputs = agent_info.get('input_schema', {})
            if inputs:
                print(f"   Inputs: {', '.join(inputs.keys())}")
                
            outputs = agent_info.get('output_schema', {})  
            if outputs:
                print(f"   Outputs: {', '.join(outputs.keys())}")
                
        print("="*60)
        
    async def execute_workflow(self, plan: WorkflowPlan, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the approved workflow plan"""
        
        print(f"\\n🚀 Starting workflow execution...")
        
        # Initialize state with user input
        await self.state_store.set("user_input", user_input)
        self._log_event("state_initialized", {"user_input": user_input})
        
        # Import and create agent instances
        agent_instances = {}
        for agent_id in plan.selected_agents:
            agent_instances[agent_id] = await self._create_agent_instance(agent_id)
            
        # Set up dependencies
        for agent_id, agent in agent_instances.items():
            agent.dependencies = plan.dependencies.get(agent_id, [])
            
        # Execute workflow
        try:
            # Execute agents in dependency order
            for agent_id in plan.execution_order:
                agent = agent_instances[agent_id]
                
                # Wait for dependencies to complete first
                for dep in agent.dependencies:
                    if dep in agent_instances:
                        await agent_instances[dep].wait_for_completion()
                        
                # Now execute this agent
                self._log_event("agent_start", {
                    "agent_id": agent_id,
                    "input_state": self.state_store.get_all()
                })
                await agent.execute_async()
                output = await self.state_store.get(f"{agent_id}_output")
                self._log_event("agent_complete", {
                    "agent_id": agent_id,
                    "output": output
                })
                
            # Collect final results
            results = {}
            for agent_id in plan.selected_agents:
                agent_output = await self.state_store.get(f"{agent_id}_output")
                if agent_output:
                    results[agent_id] = agent_output
                    
            # Print execution summary
            if self.debug:
                self.monitor.print_summary()
            self._log_event("workflow_complete", {"status": "completed", "results": results})
                
            return results
            
        except Exception as e:
            print(f"❌ Workflow execution failed: {e}")
            self._log_event("workflow_failed", {"error": str(e)})
            raise
            
    async def _create_agent_instance(self, agent_id: str):
        """Dynamically create agent instance"""
        
        agent_info = self.registry.get_agent_info(agent_id)
        agent_class_name = agent_info.get("agent_class")
        
        # Import the appropriate agent class
        try:
            if agent_class_name == "InterpreterAgent":
                from .agent_implementations import LangGraphInterpreterAgent
                return LangGraphInterpreterAgent(agent_id, self.event_bus, self.state_store, self.debug)
                
            elif agent_class_name == "ContentGeneratorWorker":
                from .agent_implementations import LangGraphContentGenerator  
                return LangGraphContentGenerator(agent_id, self.event_bus, self.state_store, self.debug)
                
            elif agent_class_name == "PlanPresenterWorker":
                from .agent_implementations import LangGraphPlanPresenter
                return LangGraphPlanPresenter(agent_id, self.event_bus, self.state_store, self.debug)
                
            elif agent_class_name == "EmailValidator":
                from .agent_implementations import LangGraphEmailValidator
                return LangGraphEmailValidator(agent_id, self.event_bus, self.state_store, self.debug)
                
            elif agent_class_name == "ScheduleOptimizer":
                from .agent_implementations import LangGraphScheduleOptimizer
                return LangGraphScheduleOptimizer(agent_id, self.event_bus, self.state_store, self.debug)

            # --- Collab Agents Support (Package Mode) ---
            elif agent_class_name == "IngestionAgent":
                from ..collab_agents.ingestion_agent import IngestionAgent
                return IngestionAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "IntentAgent":
                from ..collab_agents.intent_agent import IntentAgent
                return IntentAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "PlannerAgent":
                from ..collab_agents.planner_agent import PlannerAgent
                return PlannerAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "MemoryAgent":
                from ..collab_agents.memory_agent import MemoryAgent
                return MemoryAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "ReasoningAgent":
                from ..collab_agents.reasoning_agent import ReasoningAgent
                return ReasoningAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "ResponseSynthesisAgent":
                from ..collab_agents.response_synthesis_agent import ResponseSynthesisAgent
                return ResponseSynthesisAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "GuardrailsAgent":
                from ..collab_agents.guardrails_agent import GuardrailsAgent
                return GuardrailsAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "RetrievalAgent":
                from ..collab_agents.retrieval_agent import RetrievalAgent
                return RetrievalAgent(agent_id, self.event_bus, self.state_store, self.debug)

        except ImportError:
            # Fallback for direct execution
            if agent_class_name == "InterpreterAgent":
                from agent_implementations import LangGraphInterpreterAgent
                return LangGraphInterpreterAgent(agent_id, self.event_bus, self.state_store, self.debug)
            
            elif agent_class_name == "ContentGeneratorWorker":
                from agent_implementations import LangGraphContentGenerator  
                return LangGraphContentGenerator(agent_id, self.event_bus, self.state_store, self.debug)
            
            elif agent_class_name == "PlanPresenterWorker":
                from agent_implementations import LangGraphPlanPresenter
                return LangGraphPlanPresenter(agent_id, self.event_bus, self.state_store, self.debug)
            
            elif agent_class_name == "EmailValidator":
                from agent_implementations import LangGraphEmailValidator
                return LangGraphEmailValidator(agent_id, self.event_bus, self.state_store, self.debug)
            
            elif agent_class_name == "ScheduleOptimizer":
                from agent_implementations import LangGraphScheduleOptimizer
                return LangGraphScheduleOptimizer(agent_id, self.event_bus, self.state_store, self.debug)

            # --- Collab Agents Support (Direct Mode) ---
            elif agent_class_name == "IngestionAgent":
                from collab_agents.ingestion_agent import IngestionAgent
                return IngestionAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "IntentAgent":
                from collab_agents.intent_agent import IntentAgent
                return IntentAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "PlannerAgent":
                from collab_agents.planner_agent import PlannerAgent
                return PlannerAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "MemoryAgent":
                from collab_agents.memory_agent import MemoryAgent
                return MemoryAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "ReasoningAgent":
                from collab_agents.reasoning_agent import ReasoningAgent
                return ReasoningAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "ResponseSynthesisAgent":
                from collab_agents.response_synthesis_agent import ResponseSynthesisAgent
                return ResponseSynthesisAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "GuardrailsAgent":
                from collab_agents.guardrails_agent import GuardrailsAgent
                return GuardrailsAgent(agent_id, self.event_bus, self.state_store, self.debug)
            elif agent_class_name == "RetrievalAgent":
                from collab_agents.retrieval_agent import RetrievalAgent
                return RetrievalAgent(agent_id, self.event_bus, self.state_store, self.debug)
            
        else:
            raise ValueError(f"Unknown agent class: {agent_class_name}")
            
    async def run_intelligent_workflow(self, user_prompt: str) -> Dict[str, Any]:
        """Complete intelligent workflow: analyze -> plan -> confirm -> execute"""
        
        try:
            # Step 1: Analyze user prompt
            print("🔍 Analyzing your request...")
            workflow_plan = await self.analyze_prompt(user_prompt)
            
            # Step 2: Present plan to user
            approved = self.present_plan_to_user(workflow_plan)
            
            if not approved:
                print("❌ Workflow cancelled by user.")
                self._log_event("workflow_cancelled", {"reason": "user_declined_plan"})
                return {"status": "cancelled"}
                
            # Step 3: Execute approved workflow
            user_input = {"user_input": user_prompt}
            results = await self.execute_workflow(workflow_plan, user_input)
            
            print("✅ Workflow completed successfully!")
            return {"status": "completed", "results": results}
            
        except Exception as e:
            print(f"💥 Workflow failed: {e}")
            self._log_event("workflow_failed", {"error": str(e)})
            return {"status": "failed", "error": str(e)}