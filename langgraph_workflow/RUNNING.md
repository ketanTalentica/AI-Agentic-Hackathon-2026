# How to Run the LangGraph Workflow System

## 1. Install Dependencies
```bash
pip install -r requirements.txt
```

## 2. Configure LLM/API Keys
- Edit `config.py` and set your Mistral AI API key and endpoint.

## 3. Run the Orchestrator
```bash
python orchestrator.py
```

## 4. Input Data
- The orchestrator now expects an input dictionary with a key `user_input` containing your natural language prompt (e.g., product launch details, schedule, etc.).
- The interpreter agent will parse this input and extract all necessary fields for the workflow.
- You can modify `orchestrator.py` to accept input from CLI, file, or API as needed.

## 5. Logs
- Each agent writes logs to its own `.log` file and to the console.

## 6. Extending
- Add new worker agents in the `agents/` folder.
- Update `workflow_definition.py` to change the workflow steps.
- The interpreter agent ensures flexible, domain-agnostic input parsing for all workflows.

---
This system is modular, robust, and ready for integration with .NET/Angular backends.
