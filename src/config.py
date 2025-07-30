from pydantic import BaseModel
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Config(BaseModel):
    # LLM Configuration
    llm_api_url: str = os.getenv("LLM_API_URL", "http://localhost:11434/api/generate")
    llm_model: str = os.getenv("LLM_MODEL", "llama2")
    
    # Application settings
    max_response_length: int = 500
    temperature: float = 0.7
    
    # Automation settings
    typing_delay: float = 0.1  # Delay between keystrokes
    action_delay: float = 1.0  # Delay between actions
    screenshot_dir: str = "screenshots"
    
    # Browser settings
    browser_timeout: int = 30
    implicit_wait: int = 10
    
    # OCR settings
    tesseract_path: Optional[str] = os.getenv("TESSERACT_PATH")  # Set if not in PATH

config = Config()