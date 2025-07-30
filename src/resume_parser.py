import PyPDF2
import docx
import re
from typing import Dict, List, Optional
from dataclasses import dataclass
from src.llm_client import LLMClient

@dataclass
class ParsedResume:
    """Structured resume data"""
    name: str = ""
    email: str = ""
    phone: str = ""
    address: str = ""
    summary: str = ""
    skills: List[str] = None
    experience: List[Dict] = None
    education: List[Dict] = None
    raw_text: str = ""
    
    def __post_init__(self):
        if self.skills is None:
            self.skills = []
        if self.experience is None:
            self.experience = []
        if self.education is None:
            self.education = []

class ResumeParser:
    def __init__(self, llm_client: LLMClient = None):
        self.llm_client = llm_client or LLMClient()
    
    def parse_resume(self, file_path: str) -> ParsedResume:
        """Parse resume from PDF or DOCX file"""
        if file_path.lower().endswith('.pdf'):
            text = self._extract_pdf_text(file_path)
        elif file_path.lower().endswith('.docx'):
            text = self._extract_docx_text(file_path)
        else:
            raise ValueError("Unsupported file format. Use PDF or DOCX.")
        
        return self._parse_text_with_llm(text)
    
    def _extract_pdf_text(self, file_path: str) -> str:
        """Extract text from PDF"""
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    
    def _extract_docx_text(self, file_path: str) -> str:
        """Extract text from DOCX"""
        doc = docx.Document(file_path)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    
    def _parse_text_with_llm(self, text: str) -> ParsedResume:
        """Use LLM to extract structured data from resume text"""
        prompt = f"""
Extract the following information from this resume text and format as JSON:

Resume Text:
{text}

Extract:
1. name (full name)
2. email 
3. phone (phone number)
4. address (location/address)
5. summary (professional summary/objective)
6. skills (array of technical skills)
7. experience (array of objects with: company, title, duration, description)
8. education (array of objects with: school, degree, year)

Return ONLY valid JSON format:
{{
  "name": "...",
  "email": "...",
  "phone": "...",
  "address": "...",
  "summary": "...",
  "skills": ["skill1", "skill2"],
  "experience": [{{"company": "...", "title": "...", "duration": "...", "description": "..."}}],
  "education": [{{"school": "...", "degree": "...", "year": "..."}}]
}}
"""
        
        try:
            response = self.llm_client.generate_response(prompt, max_length=1000)
            # Try to extract JSON from response
            import json
            
            # Find JSON in response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                resume = ParsedResume(
                    name=data.get('name', ''),
                    email=data.get('email', ''),
                    phone=data.get('phone', ''),
                    address=data.get('address', ''),
                    summary=data.get('summary', ''),
                    skills=data.get('skills', []),
                    experience=data.get('experience', []),
                    education=data.get('education', []),
                    raw_text=text
                )
                return resume
            else:
                # Fallback to regex parsing
                return self._parse_text_with_regex(text)
                
        except Exception as e:
            print(f"LLM parsing failed: {e}, falling back to regex")
            return self._parse_text_with_regex(text)
    
    def _parse_text_with_regex(self, text: str) -> ParsedResume:
        """Fallback regex-based parsing"""
        resume = ParsedResume(raw_text=text)
        
        # Extract email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, text)
        if email_match:
            resume.email = email_match.group()
        
        # Extract phone
        phone_pattern = r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            resume.phone = phone_match.group()
        
        # Extract name (first line that looks like a name)
        lines = text.split('\n')
        for line in lines[:5]:  # Check first 5 lines
            line = line.strip()
            if len(line.split()) >= 2 and not '@' in line and not any(char.isdigit() for char in line):
                resume.name = line
                break
        
        # Extract skills (look for skills section)
        skills_pattern = r'(?i)skills?[:\s]*(.*?)(?=\n\s*\n|\n[A-Z]|$)'
        skills_match = re.search(skills_pattern, text, re.DOTALL)
        if skills_match:
            skills_text = skills_match.group(1)
            # Split by common delimiters
            skills = re.split(r'[,•·\n\t]+', skills_text)
            resume.skills = [skill.strip() for skill in skills if skill.strip()]
        
        return resume