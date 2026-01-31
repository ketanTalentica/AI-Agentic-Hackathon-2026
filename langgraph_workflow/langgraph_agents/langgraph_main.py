"""
LangGraph Multi-Agent Workflow System
Main entry point for AI-driven dynamic workflows
"""
import asyncio
import sys
from smart_orchestrator import SmartOrchestrator

async def main():
    """Main function to run the intelligent workflow system"""
    
    # Check for debug mode and input args
    debug = "1" in sys.argv
    
    # Parse potential input from args (simple catch-all for now)
    cli_prompt = None
    if len(sys.argv) > 1:
        # iterate to find non-flag args
        args = [a for a in sys.argv[1:] if a != "1"]
        if args:
            cli_prompt = " ".join(args)

    if debug:
        print("🐛 Debug mode enabled")
        
    # Create smart orchestrator
    orchestrator = SmartOrchestrator(debug=debug)
    
    print("🤖 Welcome to the LangGraph Multi-Agent Workflow System!")
    print("📝 This system will analyze your request and automatically select the best agents.")
    
    if not cli_prompt:
        print("✨ Enter your workflow request below:\\n")
        user_prompt = input("Your Request: ")
    else:
        print(f"✨ Processing request: {cli_prompt}\\n")
        user_prompt = cli_prompt
    
    if not user_prompt.strip():
        print("❌ No input provided. Exiting.")
        return
        
    try:
        # Run intelligent workflow
        results = await orchestrator.run_intelligent_workflow(user_prompt)
        
        # Display results
        if results["status"] == "completed":
            print("\\n" + "="*60)
            print("🎉 WORKFLOW RESULTS")
            print("="*60)
            
            for agent_id, agent_results in results["results"].items():
                print(f"\\n📊 {agent_id.replace('_', ' ').title()}:")
                
                # Display key results
                if isinstance(agent_results, dict):
                    for key, value in agent_results.items():
                        if key == "email_content":
                            try:
                                import json
                                emails = json.loads(value) if isinstance(value, str) else value
                                print(f"   Generated {len(emails)} emails")
                            except:
                                print(f"   {key}: {str(value)[:100]}...")
                        elif key == "plan_summary":
                            print(f"   Plan created with formatted schedule")
                        else:
                            print(f"   {key}: {value}")
                else:
                    print(f"   Result: {str(agent_results)[:200]}...")
                    
            print("\\n✅ All workflow steps completed successfully!")
            
        elif results["status"] == "cancelled":
            print("\\n🚫 Workflow was cancelled by user.")
            
        elif results["status"] == "failed":
            print(f"\\n💥 Workflow failed: {results.get('error', 'Unknown error')}")
            
    except KeyboardInterrupt:
        print("\\n\\n🛑 Workflow interrupted by user.")
        
    except Exception as e:
        print(f"\\n💥 Unexpected error: {e}")
        if debug:
            import traceback
            traceback.print_exc()

def run_legacy_workflow():
    """Fallback to run legacy workflow if needed"""
    print("🔄 Falling back to legacy workflow system...")
    
    try:
        from state_machine_orchestrator import StatefulOrchestrator
        from workflow_definition import WORKFLOW_STEPS
        
        print("Enter your workflow request (e.g., product launch details, schedule, etc.):")
        user_input = input()
        debug = len(sys.argv) > 1 and sys.argv[1] == "1"
        
        orchestrator = StatefulOrchestrator(WORKFLOW_STEPS, debug=debug)
        orchestrator.run({"user_input": user_input})
        
    except Exception as e:
        print(f"❌ Legacy workflow also failed: {e}")

if __name__ == "__main__":
    try:
        # Try to run the new LangGraph system
        asyncio.run(main())
    except ImportError as e:
        print(f"⚠️  LangGraph system not available: {e}")
        run_legacy_workflow()
    except Exception as e:
        print(f"💥 LangGraph system failed: {e}")
        if len(sys.argv) > 1 and sys.argv[1] == "1":
            import traceback
            traceback.print_exc()
        print("\\n🔄 Would you like to try the legacy system? (Y/N)")
        if input().strip().lower() == 'y':
            run_legacy_workflow()