# Orchestrator Agent for LangGraph Workflow

from workflow_definition import WORKFLOW_STEPS
from agents import (
    interpreter_agent,
    content_generator,
    schedule_calculator,
    plan_presenter,
    user_confirmation,
    api_caller,
    progress_reporter
)


class Orchestrator:
    def __init__(self, workflow_steps):
        self.workflow = workflow_steps
        self.agents = {
            "interpreter_agent": interpreter_agent.InterpreterAgent(),
            # "content_generator": content_generator.ContentGeneratorWorker(),
            # "schedule_calculator": schedule_calculator.ScheduleCalculatorWorker(),
            # "plan_presenter": plan_presenter.PlanPresenterWorker(),
            # "user_confirmation": user_confirmation.UserConfirmationWorker(),
            # "api_caller": api_caller.APICallerWorker(),
            # "progress_reporter": progress_reporter.ProgressReporterWorker()
        }
        self.state = {}

    def run(self, input_data):
        self.state = input_data
        # Step 1: Interpreter agent
        self.state = self.agents["interpreter_agent"].execute(self.state)
        # Step 2: Content generator
        self.state = self.agents["content_generator"].execute(self.state)
        # Step 3: Schedule calculator
        self.state = self.agents["schedule_calculator"].execute(self.state)
        # Step 4: Plan presenter
        self.state = self.agents["plan_presenter"].execute(self.state)
        # Present plan to user and ask for confirmation
        print("\n--- PLAN SUMMARY ---")
        print(self.state.get("plan_summary", "No summary available."))
        confirm = input("\nDo you want to proceed? (Y/N): ").strip().lower()
        if confirm != "y":
            print("Workflow cancelled by user.")
            return self.state
        # Step 5: User confirmation
        self.state = self.agents["user_confirmation"].execute(self.state)
        # Step 6: API caller
        self.state = self.agents["api_caller"].execute(self.state)
        # Step 7: Progress reporter
        self.state = self.agents["progress_reporter"].execute(self.state)
        return self.state

if __name__ == "__main__":
    print("Enter your workflow request (e.g., product launch details, schedule, etc.):")
    user_input = input()
    orchestrator = Orchestrator(WORKFLOW_STEPS)
    orchestrator.run({"user_input": user_input})
