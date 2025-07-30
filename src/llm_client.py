import requests
import json
from typing import Dict, Any, Optional
from src.config import config

class LLMClient:
    def __init__(self, api_url: str = None, model: str = None):
        self.api_url = api_url or config.llm_api_url
        self.model = model or config.llm_model
        
    def generate_response(self, prompt: str, max_length: int = None, temperature: float = None) -> str:
        """Generate response using open source LLM (Ollama by default)"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature or config.temperature,
                    "num_predict": max_length or config.max_response_length
                }
            }
            
            response = requests.post(self.api_url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "").strip()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"LLM API error: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test if LLM service is available"""
        try:
            test_response = self.generate_response("Hello", max_length=10)
            return len(test_response) > 0
        except:
            return False

# Alternative clients for different LLM services
class OpenRouterClient(LLMClient):
    def __init__(self, api_key: str, model: str = "anthropic/claude-3.5-sonnet"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        
    def generate_response(self, prompt: str, max_length: int = None, temperature: float = None) -> str:
        """Generate response using OpenRouter API"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/workday-agent",
                "X-Title": "Workday Desktop Agent"
            }
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": max_length or config.max_response_length,
                "temperature": temperature or config.temperature
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenRouter API error: {str(e)}")
        except (KeyError, IndexError) as e:
            raise Exception(f"Invalid OpenRouter response format: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test if OpenRouter service is available"""
        try:
            test_response = self.generate_response("Hello", max_length=10)
            return len(test_response) > 0
        except:
            return False

class HuggingFaceClient(LLMClient):
    def __init__(self, api_token: str, model: str = "microsoft/DialoGPT-medium"):
        self.api_token = api_token
        self.model = model
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"
    
    def generate_response(self, prompt: str, max_length: int = None, temperature: float = None) -> str:
        headers = {"Authorization": f"Bearer {self.api_token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_length": max_length or config.max_response_length,
                "temperature": temperature or config.temperature
            }
        }
        
        response = requests.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()
        
        result = response.json()
        if isinstance(result, list) and len(result) > 0:
            return result[0].get("generated_text", "").replace(prompt, "").strip()
        return ""