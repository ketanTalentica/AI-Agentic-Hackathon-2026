# Configuration for LLM and API endpoints

LLM_PROVIDER = "mistral"
LLM_API_KEY = "your_mistral_api_key_here"
LLM_API_URL = "https://api.mistral.ai/v1"

# Multi-model configuration for different agents
LLM_MODELS = {
    "interpreter": "mistral-medium-2508",    # Cheaper model for simple extraction
    "content_generator": "mistral-large-2512", # More powerful model for creative content
    "default": "mistral-medium-2508"             # Fallback model
}

# Backward compatibility
LLM_MODEL = LLM_MODELS["default"]
# For Mistral chat models, endpoint used in llm_client.py is /chat/completions

UTILS_LOG_DIR_PATH = "D:\\AI Native Assignments\\AI-Agentic-Hackathon-2026\\langgraph_workflow\\logs\\"