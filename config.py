import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "raw"
OUTPUT_DIR = BASE_DIR / "output"
WIKI_DIR = BASE_DIR / "wiki"
PROMPTS_DIR = BASE_DIR / "prompts"

# Load environment variables using python-dotenv
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DART_API_KEY = os.getenv("DART_API_KEY")

# Model Configuration
GEMINI_MODEL = "gemini-3.5-flash"  # Active stable model in 2026

# API Call Limits and Control (For LLMClient)
LLM_REQUEST_DELAY = 4.0      # Delay between calls (seconds)
LLM_MAX_RETRIES = 3         # Max retries
LLM_RETRY_BASE_DELAY = 2.0  # Base delay for backoff (seconds)

def validate():
    """Validates that necessary configuration and keys are loaded."""
    if not GEMINI_API_KEY or GEMINI_API_KEY.strip() == "" or GEMINI_API_KEY == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY is not set. Please update the .env file with your actual Gemini API key."
        )
