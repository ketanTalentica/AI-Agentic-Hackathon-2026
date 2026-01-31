"""
LangGraph Agent Implementations
Converts existing agents to LangGraph-based event-driven system
"""
import asyncio
import json
import datetime
import time
from typing import Dict, Any
try:
    from .langgraph_system import BaseAgent
    from ..llm_client import LLMClient
    from ..utils.CommonLogger import CommonLogger
    from ..models.EmailContent import EmailContent
    from ..config import UTILS_LOG_DIR_PATH
except ImportError:
    # Fallback for direct execution
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from langgraph_agents.langgraph_system import BaseAgent
    from llm_client import LLMClient
    from utils.CommonLogger import CommonLogger
    from models.EmailContent import EmailContent
    from config import UTILS_LOG_DIR_PATH

class LangGraphInterpreterAgent(BaseAgent):
    """LangGraph version of interpreter agent"""
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.llm = LLMClient(agent_type="interpreter", debug=debug)
        self.log_path = UTILS_LOG_DIR_PATH + "interpreter_agent.log"
        
    async def _execute_impl(self) -> Dict[str, Any]:
        # Get user input from state
        user_input = await self.state_store.get("user_input", {})
        
        if isinstance(user_input, dict):
            user_text = user_input.get("user_input", str(user_input))
        else:
            user_text = str(user_input)
            
        # Create prompt for business requirement extraction
        prompt = (
            "Extract key business information from this user input for an email marketing campaign. "
            "Return ONLY a valid JSON object with these fields: "
            "- product_name (string): The product/service name"
            "- launch_date (string): Launch date in YYYY-MM-DD format"
            "- campaign_goal (string): Main marketing objective"
            "- frequency (string): How often to send emails (e.g., 'weekly')"
            "Do NOT include comments, markdown, or any preamble. "
            f"User input: {user_text}"
        )
        
        # Execute LLM call
        result = self.llm.generate(prompt, max_tokens=1024)
        
        # Parse and clean result
        cleaned = result.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[len('```json'):].strip()
        if cleaned.startswith('```'):
            cleaned = cleaned[len('```'):].strip()
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].strip()
            
        try:
            extracted = json.loads(cleaned)
            if not isinstance(extracted, dict):
                raise ValueError("Expected a JSON object with business requirements.")
                
            # Log the extraction
            CommonLogger.WriteLog(self.log_path, f"Extracted: {extracted}")
            
            return {
                "product_name": extracted.get("product_name", "Unknown Product"),
                "launch_date": extracted.get("launch_date", "Unknown Date"),
                "campaign_goal": extracted.get("campaign_goal", "General marketing"),
                "frequency": extracted.get("frequency", "weekly")
            }
            
        except Exception as e:
            if self.debug:
                print(f"[{self.agent_id}] Parse error: {e}, Raw result: {cleaned}")
            
            # Fallback extraction
            return {
                "product_name": "Unknown Product",
                "launch_date": "Unknown Date", 
                "campaign_goal": "General marketing",
                "frequency": "weekly"
            }

class LangGraphContentGenerator(BaseAgent):
    """LangGraph version of content generator"""
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.llm = LLMClient(agent_type="content_generator", debug=debug)
        self.log_path = UTILS_LOG_DIR_PATH + "content_generator.log"
        
    async def _execute_impl(self) -> Dict[str, Any]:
        # Get interpreter output
        interpreter_output = await self.state_store.wait_for("interpreter_agent_output")
        
        product_name = interpreter_output.get("product_name", "Unknown Product")
        launch_date = interpreter_output.get("launch_date", "Unknown Date")
        
        # Generate weekly dates
        weekly_dates = self._generate_weekly_dates(launch_date)
        
        # Create variability elements
        run_count = len(self.event_bus.event_history) + 1
        timestamp = str(int(time.time()))[-6:]
        
        creative_angles = [
            "focus on emotional connection", "emphasize technical innovation",
            "highlight lifestyle benefits", "create mystery and intrigue",
            "use humor and personality", "stress exclusivity and status"
        ]
        angle = creative_angles[(run_count - 1) % len(creative_angles)]
        
        # Build prompt
        field_map = {
            "ScheduleDate": "ScheduleDate (date for this email)",
            "SubjectLine": "SubjectLine (max 15 words, creative, use emojis)",
            "TextContent": "TextContent (max 35 words, creative, use emojis)",
            "PreviewMessage": "PreviewMessage (short preview for inbox, optional)"
        }
        field_list = list(field_map.values())
        
        prompt = (
            f"Return ONLY a valid, indented JSON array for an email drip campaign. "
            f"Each element must be an object with these fields: {', '.join(field_list)}.\\n"
            f"Use EXACTLY these ScheduleDate values in order: {weekly_dates}\\n"
            f"Create {len(weekly_dates)} emails, one for each date provided above.\\n"
            f"CREATIVE BRIEF (Run #{run_count}, Session {timestamp}): {angle}.\\n"
            f"Make this completely different from previous attempts. Avoid typical marketing language.\\n"
            f"Output the emails in ascending order by ScheduleDate.\\n"
            f"Do NOT include any preamble, markdown, or explanation—just the JSON array.\\n"
            f"Be creative, use emojis where appropriate. All text must be plain (no HTML, no markdown, no code blocks).\\n"
            f"Product: {product_name}\\n"
            f"Launch Date: {launch_date}\\n"
        )
        
        # Execute LLM call
        content = self.llm.generate(prompt, max_tokens=1200, temperature=1.2, top_p=0.85)
        
        # Parse and clean result
        try:
            cleaned = content.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[len('```json'):].strip()
            if cleaned.startswith('```'):
                cleaned = cleaned[len('```'):].strip() 
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3].strip()
                
            parsed = json.loads(cleaned)
            if not isinstance(parsed, list):
                raise ValueError("Expected a JSON array of email objects.")
                
            # Sort emails by ScheduleDate
            parsed.sort(key=lambda x: x.get('ScheduleDate', ''))
            formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
            
            # Log the result
            CommonLogger.WriteLog(self.log_path, formatted)
            
            return {"email_content": formatted}
            
        except Exception as e:
            if self.debug:
                print(f"[{self.agent_id}] Content generation error: {e}")
            
            # Log raw content for debugging
            CommonLogger.WriteLog(self.log_path, f"Raw LLM output: {content}")
            return {"email_content": content}
            
    def _generate_weekly_dates(self, launch_date_str: str) -> list:
        """Generate weekly Saturday/Sunday dates"""
        dates = []
        try:
            if launch_date_str is None or launch_date_str == "Unknown Date":
                raise ValueError("Invalid launch date")
            end_date = datetime.datetime.strptime(launch_date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            # Fallback to 4 weeks from today
            end_date = datetime.date.today() + datetime.timedelta(weeks=4)
            
        current = datetime.date.today()
        while current <= end_date:
            if current.weekday() == 5:  # Saturday
                dates.append(current.strftime("%Y-%m-%dT09:00:00Z"))
                current += datetime.timedelta(days=7)
            elif current.weekday() == 6:  # Sunday
                dates.append(current.strftime("%Y-%m-%dT09:00:00Z"))
                current += datetime.timedelta(days=7)
            else:
                # Move to next Saturday
                days_until_saturday = (5 - current.weekday()) % 7
                if days_until_saturday == 0:
                    days_until_saturday = 7
                current += datetime.timedelta(days=days_until_saturday)
        return dates

class LangGraphPlanPresenter(BaseAgent):
    """LangGraph version of plan presenter"""
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.log_path = UTILS_LOG_DIR_PATH + "plan_presenter.log"
        
    async def _execute_impl(self) -> Dict[str, Any]:
        # Get content generator output
        content_output = await self.state_store.wait_for("content_generator_output")
        email_content = content_output.get('email_content', '')
        
        try:
            content_list = json.loads(email_content) if isinstance(email_content, str) else email_content
        except Exception:
            content_list = []
            
        # Create plan summary
        plan = {}
        for idx, email_obj in enumerate(content_list):
            schedule_date = email_obj.get('ScheduleDate', f'Email {idx+1}')
            date_key = schedule_date if schedule_date else f"Email {idx+1}"
            
            # Only include fields from EmailContent model
            day_info = {k: email_obj.get(k, None) for k in vars(EmailContent()) if not k.startswith('_')}
            plan[date_key] = day_info
            
        summary = json.dumps(plan, ensure_ascii=False, indent=2)
        
        # Log the result
        CommonLogger.WriteLog(self.log_path, f"Presented plan summary: {summary}")
        
        if self.debug:
            print("\\n=== PLAN SUMMARY (By Day) ===")
            print(summary)
            print("============================\\n")
            
        return {"plan_summary": summary}

class LangGraphEmailValidator(BaseAgent):
    """Email validation agent"""
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.llm = LLMClient(agent_type="interpreter", debug=debug)
        
    async def _execute_impl(self) -> Dict[str, Any]:
        # Get email content
        content_output = await self.state_store.wait_for("content_generator_output") 
        email_content = content_output.get('email_content', '')
        
        # Simple validation rules
        validation_results = {
            "is_valid": True,
            "warnings": [],
            "recommendations": []
        }
        
        try:
            emails = json.loads(email_content) if isinstance(email_content, str) else email_content
            
            for i, email in enumerate(emails):
                # Check subject line length
                subject = email.get('SubjectLine', '')
                if len(subject) > 78:
                    validation_results["warnings"].append(f"Email {i+1}: Subject line too long ({len(subject)} chars)")
                    
                # Check for spam trigger words
                spam_words = ['FREE', 'URGENT', 'ACT NOW', '!!!']
                for word in spam_words:
                    if word in subject.upper():
                        validation_results["warnings"].append(f"Email {i+1}: Potential spam word '{word}'")
                        
            if not validation_results["warnings"]:
                validation_results["recommendations"].append("All emails pass basic validation checks")
                
        except Exception as e:
            validation_results["is_valid"] = False
            validation_results["warnings"].append(f"JSON parsing error: {e}")
            
        return {"validation_results": validation_results}

class LangGraphScheduleOptimizer(BaseAgent):
    """Schedule optimization agent"""
    
    def __init__(self, agent_id: str, event_bus, state_store, debug: bool = False):
        super().__init__(agent_id, event_bus, state_store, debug)
        self.llm = LLMClient(agent_type="content_generator", debug=debug)
        
    async def _execute_impl(self) -> Dict[str, Any]:
        # Get inputs
        interpreter_output = await self.state_store.wait_for("interpreter_agent_output")
        content_output = await self.state_store.wait_for("content_generator_output")
        
        # Simple optimization: adjust times based on best practices
        email_content = content_output.get('email_content', '')
        
        try:
            emails = json.loads(email_content) if isinstance(email_content, str) else email_content
            
            # Optimal times by day of week (hour in 24h format)
            optimal_times = {
                5: 10,  # Saturday 10 AM
                6: 14,  # Sunday 2 PM
            }
            
            optimized_emails = []
            for email in emails:
                schedule_date = email.get('ScheduleDate', '')
                if schedule_date:
                    # Parse date and optimize time
                    try:
                        dt = datetime.datetime.fromisoformat(schedule_date.replace('Z', '+00:00'))
                        weekday = dt.weekday()
                        optimal_hour = optimal_times.get(weekday, 9)  # Default 9 AM
                        
                        # Update to optimal time
                        new_dt = dt.replace(hour=optimal_hour, minute=0, second=0)
                        email['ScheduleDate'] = new_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                        
                    except Exception:
                        pass  # Keep original if parsing fails
                        
                optimized_emails.append(email)
                
            optimized_schedule = json.dumps(optimized_emails, ensure_ascii=False, indent=2)
            
            return {
                "optimized_schedule": optimized_schedule,
                "optimization_notes": "Adjusted send times for optimal engagement"
            }
            
        except Exception as e:
            return {
                "optimized_schedule": email_content,
                "optimization_notes": f"Optimization failed: {e}"
            }