import os
from typing import Optional
from pydantic import BaseModel
from pathlib import Path
from dotenv import load_dotenv


workspace_env = Path(__file__).resolve().parent.parent / ".env"
if workspace_env.exists():
    try:
        load_dotenv(dotenv_path=workspace_env)
    except Exception:
        pass

class Settings(BaseModel):
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # LLM Provider Configuration
    # Supported: "gemini", "openai", "groq", "auto", "rule_only"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")
    
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "8.0"))
    NUMERIC_TOLERANCE: float = 0.01

settings = Settings()
