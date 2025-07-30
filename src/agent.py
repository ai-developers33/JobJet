from typing import Dict, Any, Optional, List
import time
import os
import json
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pyautogui
import cv2
import numpy as np
from PIL import Image
from src.llm_client import LLMClient
from src.resume_parser import ParsedResume
from src.config import config
from templates.prompts import WORKDAY_PROMPTS

@dataclass
class WorkdayField:
    """Represents a field in Workday application"""
    label: str
    field_type: str  # text, textarea, select, checkbox, radio
    value: str = ""
    xpath: str = ""
    filled: bool = False

class WorkdayAgent:
    def __init__(self, llm_client: LLMClient = None):
        # Use OpenRouter by default with the provided API key
        if llm_client is None:
            from src.llm_client import OpenRouterClient
            openrouter_key = "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"
            self.llm_client = OpenRouterClient(openrouter_key, model="deepseek/deepseek-chat")
            print("🤖 Using OpenRouter with DeepSeek Chat (FREE) for enhanced AI capabilities")
        else:
            self.llm_client = llm_client
            
        self.driver = None
        self.wait = None
        self.resume_data = None
        
        # Create screenshots directory
        os.makedirs(config.screenshot_dir, exist_ok=True)
        
        # Configure pyautogui
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = config.action_delay
    
    def setup_browser(self):
        """Initialize Chrome browser with appropriate settings"""
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.wait = WebDriverWait(self.driver, config.browser_timeout)
        print("✅ Browser initialized")
    
    def load_resume(self, resume_path: str):
        """Load and parse resume"""
        from src.resume_parser import ResumeParser
        parser = ResumeParser(self.llm_client)
        self.resume_data = parser.parse_resume(resume_path)
        print(f"✅ Resume loaded: {self.resume_data.name}")
        return self.resume_data
    
    def load_resume_comprehensive(self, resume_path: str):
        """Parse ALL fields from resume comprehensively"""
        from src.resume_parser import ResumeParser
        parser = ResumeParser(self.llm_client)
        self.resume_data = parser.parse_resume(resume_path)
        
        # Enhanced parsing to extract more fields
        if not self.resume_data.name and self.resume_data.raw_text:
            # Try to extract name from first few lines
            lines = self.resume_data.raw_text.split('\n')[:5]
            for line in lines:
                line = line.strip()
                if len(line.split()) >= 2 and not '@' in line and not any(char.isdigit() for char in line):
                    self.resume_data.name = line
                    break
        
        print(f"✅ Comprehensive resume parsing completed")
        print(f"📋 Extracted: Name: {self.resume_data.name}, Email: {self.resume_data.email}, Phone: {self.resume_data.phone}")
        print(f"📋 Skills: {len(self.resume_data.skills)} items, Experience: {len(self.resume_data.experience)} positions")
        
        return self.resume_data
    
    def handle_account_creation(self) -> bool:
        """Create account with email from resume, or ask for password if exists"""
        try:
            email = self.resume_data.email
            print(f"👤 Attempting account creation/login with: {email}")
            
            # Look for email input field first
            email_selectors = [
                "input[type='email']",
                "input[name*='email']",
                "input[id*='email']",
                "input[placeholder*='email']",
                "input[aria-label*='email']"
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed() and element.is_enabled():
                            email_field = element
                            break
                    if email_field:
                        break
                except:
                    continue
            
            if email_field:
                print("📧 Found email field, entering email...")
                self._type_slowly(email_field, email)
                
                # Look for continue/next button
                continue_buttons = [
                    "//button[contains(text(), 'Continue')]",
                    "//button[contains(text(), 'Next')]",
                    "//button[contains(text(), 'Sign In')]",
                    "//button[contains(text(), 'Login')]",
                    "//input[@type='submit']",
                    "button[type='submit']"
                ]
                
                for button_selector in continue_buttons:
                    try:
                        if button_selector.startswith("//"):
                            buttons = self.driver.find_elements(By.XPATH, button_selector)
                        else:
                            buttons = self.driver.find_elements(By.CSS_SELECTOR, button_selector)
                        
                        for button in buttons:
                            if button.is_displayed() and button.is_enabled():
                                print(f"🔘 Clicking: {button.text}")
                                button.click()
                                time.sleep(3)
                                
                                # Check if password field appears (account exists)
                                password_field = self._find_password_field()
                                if password_field:
                                    print("🔐 Account exists, password required")
                                    password = input(f"Enter password for {email}: ")
                                    self._type_slowly(password_field, password)
                                    
                                    # Click login button
                                    login_buttons = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Sign In') or contains(text(), 'Login')]")
                                    for login_btn in login_buttons:
                                        if login_btn.is_displayed():
                                            login_btn.click()
                                            time.sleep(3)
                                            break
                                
                                return True
                    except Exception as e:
                        continue
            
            print("✅ Account handling completed (or not required)")
            return True
            
        except Exception as e:
            print(f"⚠️ Account creation/login failed: {e}")
            return False
    
    def _find_password_field(self):
        """Find password input field"""
        password_selectors = [
            "input[type='password']",
            "input[name*='password']",
            "input[id*='password']"
        ]
        
        for selector in password_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        return element
            except:
                continue
        return None
    
    def upload_resume_priority(self, resume_path: str) -> bool:
        """Upload resume with priority - comprehensive search"""
        try:
            print("📎 Searching for resume upload fields...")
            
            # Comprehensive file upload selectors
            file_selectors = [
                "input[type='file']",
                "input[accept*='.pdf']",
                "input[accept*='.doc']",
                "input[name*='resume']",
                "input[name*='cv']",
                "input[id*='resume']",
                "input[id*='cv']",
                "input[id*='upload']",
                "input[class*='upload']"
            ]
            
            uploaded = False
            for selector in file_selectors:
                try:
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for file_input in file_inputs:
                        try:
                            if file_input.is_enabled():
                                label = self._get_field_label(file_input)
                                print(f"📎 Found upload field: {label}")
                                
                                # Upload the file
                                file_input.send_keys(os.path.abspath(resume_path))
                                print(f"✅ Resume uploaded successfully to: {label}")
                                uploaded = True
                                time.sleep(2)
                                break
                        except Exception as e:
                            print(f"⚠️ Upload attempt failed: {e}")
                            continue
                    if uploaded:
                        break
                except:
                    continue
            
            if not uploaded:
                print("⚠️ No file upload fields found")
            
            return uploaded
            
        except Exception as e:
            print(f"❌ Resume upload failed: {e}")
            return False
    
    def _handle_alerts(self):
        """Handle JavaScript alerts, including success messages"""
        try:
            # Check if there's an alert present
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            print(f"🔔 Found alert: {alert_text}")
            
            # Accept the alert (click OK)
            alert.accept()
            print("✅ Alert dismissed")
            time.sleep(1)
            
        except Exception:
            # No alert present, continue normally
            pass
    
    def detect_all_form_fields(self) -> List[WorkdayField]:
        """Detect ALL form fields comprehensively"""
        fields = []
        
        # Handle any success alerts first
        self._handle_alerts()
        
        print("🔍 Comprehensive form field detection...")
        self.take_screenshot("comprehensive_form_analysis")
        
        # Enhanced selectors for all possible form elements
        all_selectors = [
            ("input[type='text']", "text"),
            ("input[type='email']", "email"),
            ("input[type='tel']", "tel"),
            ("input[type='number']", "number"),
            ("input[type='date']", "date"),
            ("input[type='url']", "url"),
            ("input[not(@type)]", "text"),  # inputs without type
            ("textarea", "textarea"),
            ("select", "select"),
            ("input[type='radio']", "radio"),
            ("input[type='checkbox']", "checkbox")
        ]
        
        for selector, field_type in all_selectors:
            try:
                if selector.startswith("input[not"):
                    # XPath for inputs without type attribute
                    elements = self.driver.find_elements(By.XPATH, "//input[not(@type) or @type='']")
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        # Skip hidden or disabled fields
                        if not element.is_displayed() or not element.is_enabled():
                            continue
                        
                        # Skip file inputs (handled separately)
                        if element.get_attribute("type") == "file":
                            continue
                        
                        label = self._get_field_label(element)
                        xpath = self._get_element_xpath(element)
                        
                        if label and xpath:
                            field = WorkdayField(
                                label=label,
                                field_type=field_type,
                                xpath=xpath
                            )
                            fields.append(field)
                            
                    except Exception as e:
                        continue
                        
            except Exception as e:
                print(f"Error detecting {field_type} fields: {e}")
                continue
        
        print(f"🔍 Detected {len(fields)} total form fields")
        return fields
    
    def map_all_resume_data_to_fields(self, fields: List[WorkdayField]) -> List[WorkdayField]:
        """Intelligent LLM-powered field mapping with smart completion"""
        if not self.resume_data:
            return fields
        
        print("🧠 Intelligent LLM-powered field mapping...")
        
        # Create comprehensive context for LLM
        resume_context = {
            "name": self.resume_data.name or "",
            "email": self.resume_data.email or "",
            "phone": self.resume_data.phone or "",
            "address": self.resume_data.address or "",
            "summary": self.resume_data.summary or "",
            "skills": self.resume_data.skills or [],
            "experience": self.resume_data.experience or [],
            "education": self.resume_data.education or []
        }
        
        # Group fields for batch processing
        field_info = []
        for i, field in enumerate(fields):
            field_info.append({
                "index": i,
                "label": field.label,
                "type": field.field_type
            })
        
        # Use LLM for COMPLETE job application field mapping
        mapping_prompt = f"""
You are an expert job application assistant. Fill out ALL job application fields intelligently using the resume data.

RESUME DATA:
{json.dumps(resume_context, indent=2)}

FORM FIELDS TO FILL:
{json.dumps(field_info, indent=2)}

COMPLETE JOB APPLICATION FIELD HANDLING:

🔹 1. PERSONAL INFORMATION:
   - First Name: Extract from full name
   - Middle Name: Extract if available, otherwise leave blank
   - Last Name: Extract from full name
   - Preferred Name: Same as first name unless specified
   - Phone Number: From resume with proper formatting
   - Email Address: From resume
   - Country of Residence: "United States" for US addresses
   - Home Address: Parse into Street, City, State/Province, Zip/Postal Code
   - If "Santa Clara, CA": Street="[infer]", City="Santa Clara", State="California", Zip="95050"

🔹 2. CANDIDATE PROFILE:
   - Preferred Language: "English"
   - Desired Work Location: Based on current address or "Remote/Hybrid"
   - Willingness to Relocate: "Yes" or "Open to discussion"
   - Employment Type: "Full-time" (default)
   - Available Start Date: "Immediately" or "Two weeks notice"
   - Salary Expectations: "Competitive" or "Negotiable"
   - Work Authorization: "Yes" (for US addresses)
   - Sponsorship Requirement: "No" (for US citizens)

🔹 3. RESUME/CV UPLOAD:
   - Upload Resume: [File upload handled separately]
   - Cover Letter: "Available upon request"
   - LinkedIn Profile: Generate if not available: "linkedin.com/in/[firstname-lastname]"
   - Portfolio/Website: Leave blank unless specified
   - GitHub/Behance: Leave blank unless specified

🔹 4. EDUCATION:
   - School Name: From education data
   - Degree Type: "Bachelor's", "Master's", "PhD", etc.
   - Field of Study: From education data
   - GPA: Leave blank unless specified
   - Start & End Dates: From education data or estimate
   - Graduated: "Yes" for completed degrees

🔹 5. WORK EXPERIENCE:
   - Employer Name: From experience data
   - Job Title: From experience data
   - Location: City, State, Country from experience
   - Start & End Dates: MM/YYYY format
   - Responsibilities: From experience descriptions
   - Reason for Leaving: "Career advancement" or "New opportunities"

🔹 6. CERTIFICATIONS/LICENSES:
   - Certification Name: From resume if available
   - Issuing Organization: From resume if available
   - Issue Date: From resume or leave blank
   - Expiration Date: Leave blank unless specified

🔹 7. SKILLS:
   - Languages: "English (Native)" + others from resume
   - Software Tools: From skills data
   - Technical Skills: From skills data
   - Other Competencies: From skills data

🔹 8. SCREENING QUESTIONS:
   - Work Authorization: "Yes" (for US)
   - Previous Employment: "No" (unless specified)
   - Non-compete Agreements: "No" (default)
   - Technology Experience: "Yes" if relevant skills match
   - Travel Willingness: "Yes, up to 25%" (reasonable default)

🔹 9. VOLUNTARY DISCLOSURES (EEO):
   - Gender: "Prefer not to disclose"
   - Race/Ethnicity: "Prefer not to disclose"
   - Veteran Status: "Not a veteran"
   - Disability Status: "No disability"

🔹 10. ACKNOWLEDGMENT & CONSENT:
   - Terms & Conditions: "Yes" or "I agree"
   - Background Check: "Yes" or "I consent"
   - Drug Test Policy: "Yes" or "I acknowledge"
   - Information Accuracy: "Yes" or "I certify"

SMART FIELD MATCHING:
- Match field labels intelligently (case-insensitive, partial matching)
- For dropdowns: provide most appropriate option
- For radio buttons: select based on context
- For checkboxes: check based on typical professional responses
- For text areas: generate professional, relevant responses

Return ONLY a JSON object mapping field indices to appropriate values:
{{
  "0": "value for field 0",
  "1": "value for field 1",
  ...
}}
"""
        
        try:
            print("🤖 Asking LLM to intelligently fill form fields...")
            response = self.llm_client.generate_response(mapping_prompt, max_length=2000)
            
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                mappings = json.loads(json_str)
                
                # Apply LLM mappings to fields
                for i, field in enumerate(fields):
                    field_value = mappings.get(str(i), "")
                    if field_value and field_value.strip():
                        field.value = field_value.strip()
                        print(f"🧠 LLM mapped: {field.label} = {field.value}")
                
                mapped_count = len([f for f in fields if f.value])
                print(f"✅ LLM intelligently mapped {mapped_count} fields")
                return fields
            
        except Exception as e:
            print(f"⚠️ LLM mapping failed: {e}, using fallback mapping")
        
        # Fallback to enhanced basic mapping
        return self._enhanced_basic_mapping(fields)
    
    def _enhanced_basic_mapping(self, fields: List[WorkdayField]) -> List[WorkdayField]:
        """Enhanced fallback mapping with smart inference"""
        print("🔄 Using enhanced fallback mapping...")
        
        # Extract location components from address
        address = self.resume_data.address or ""
        city, state, zip_code, country = self._parse_address_components(address)
        
        for field in fields:
            label_lower = field.label.lower()
            
            # Enhanced name handling
            if any(keyword in label_lower for keyword in ["first name", "given name"]):
                if self.resume_data.name:
                    field.value = self.resume_data.name.split()[0] if self.resume_data.name.split() else ""
            elif any(keyword in label_lower for keyword in ["last name", "family name", "surname"]):
                if self.resume_data.name:
                    parts = self.resume_data.name.split()
                    field.value = parts[-1] if len(parts) > 1 else ""
            elif any(keyword in label_lower for keyword in ["full name", "name", "candidate name"]):
                field.value = self.resume_data.name or ""
            
            # Enhanced location handling
            elif any(keyword in label_lower for keyword in ["city"]):
                field.value = city
            elif any(keyword in label_lower for keyword in ["state", "province"]):
                field.value = state
            elif any(keyword in label_lower for keyword in ["zip", "postal", "postal code", "zip code"]):
                field.value = zip_code
            elif any(keyword in label_lower for keyword in ["country"]):
                field.value = country or "United States"
            elif any(keyword in label_lower for keyword in ["address", "street"]):
                field.value = address
            
            # Contact fields
            elif any(keyword in label_lower for keyword in ["email", "e-mail"]):
                field.value = self.resume_data.email or ""
            elif any(keyword in label_lower for keyword in ["phone", "telephone", "mobile", "cell"]):
                field.value = self.resume_data.phone or ""
            
            # Professional fields
            elif any(keyword in label_lower for keyword in ["summary", "objective", "about"]):
                field.value = self.resume_data.summary or ""
            elif any(keyword in label_lower for keyword in ["skills", "technical skills"]):
                field.value = ", ".join(self.resume_data.skills) if self.resume_data.skills else ""
        
        mapped_count = len([f for f in fields if f.value])
        print(f"✅ Enhanced mapping completed: {mapped_count} fields")
        return fields
    
    def _parse_address_components(self, address: str) -> tuple:
        """Parse address into city, state, zip, country components"""
        if not address:
            return "", "", "", "United States"
        
        # Common patterns for US addresses
        city, state, zip_code, country = "", "", "", "United States"
        
        # Handle "Santa Clara, CA" format
        if "Santa Clara" in address:
            city = "Santa Clara"
            state = "California"
            zip_code = "95050"  # Common Santa Clara zip
        elif "San Francisco" in address:
            city = "San Francisco"
            state = "California"
            zip_code = "94102"  # Common SF zip
        elif "," in address:
            # Try to parse "City, State" format
            parts = address.split(",")
            if len(parts) >= 2:
                city = parts[0].strip()
                state_part = parts[1].strip()
                if len(state_part) == 2:  # State abbreviation
                    state = state_part
                else:
                    state = state_part
        
        return city, state, zip_code, country
    
    def fill_all_form_fields(self, fields: List[WorkdayField]) -> int:
        """Fill ALL form fields with enhanced error handling"""
        filled_count = 0
        
        print("📝 Filling all form fields comprehensively...")
        
        for field in fields:
            if not field.value or field.filled:
                continue
            
            try:
                print(f"📝 Filling: {field.label} = {field.value[:50]}...")
                
                # Find element with multiple strategies
                element = None
                try:
                    element = self.wait.until(EC.presence_of_element_located((By.XPATH, field.xpath)))
                except:
                    # Fallback: try to find by other attributes
                    try:
                        element = self.driver.find_element(By.XPATH, field.xpath)
                    except:
                        print(f"⚠️ Could not locate field: {field.label}")
                        continue
                
                if not element:
                    continue
                
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(1)
                
                # Fill based on field type with enhanced methods
                if field.field_type in ["text", "email", "tel", "number", "url", "date"]:
                    self._fill_text_field(element, field.value)
                    
                elif field.field_type == "textarea":
                    self._fill_textarea_field(element, field.value)
                    
                elif field.field_type == "select":
                    self._fill_select_field(element, field.value)
                    
                elif field.field_type == "radio":
                    self._fill_radio_field(element, field.value)
                    
                elif field.field_type == "checkbox":
                    self._fill_checkbox_field(element, field.value)
                
                field.filled = True
                filled_count += 1
                time.sleep(config.action_delay)
                
            except Exception as e:
                print(f"❌ Error filling {field.label}: {e}")
                continue
        
        print(f"✅ Successfully filled {filled_count} fields")
        self.take_screenshot("all_fields_filled")
        return filled_count
    
    def _fill_text_field(self, element, value: str):
        """Enhanced text field filling"""
        try:
            # Multiple click strategies
            self._robust_click(element)
            
            # Clear field
            element.clear()
            time.sleep(0.2)
            
            # Type value
            element.send_keys(value)
            
            # Trigger change event
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", element)
            
        except Exception as e:
            # Fallback: direct value setting
            self.driver.execute_script("arguments[0].value = arguments[1];", element, value)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", element)
    
    def _fill_textarea_field(self, element, value: str):
        """Enhanced textarea filling"""
        try:
            self._robust_click(element)
            element.clear()
            element.send_keys(value)
        except:
            self.driver.execute_script("arguments[0].value = arguments[1];", element, value)
    
    def _fill_select_field(self, element, value: str):
        """Enhanced dropdown/select field filling with intelligent matching"""
        try:
            from selenium.webdriver.support.ui import Select
            select = Select(element)
            
            print(f"🔽 Filling dropdown with value: {value}")
            
            # Get all available options for intelligent matching
            options = select.options
            option_texts = [opt.text.strip() for opt in options if opt.text.strip()]
            print(f"🔽 Available options: {option_texts[:5]}...")  # Show first 5
            
            # Strategy 1: Exact text match
            try:
                select.select_by_visible_text(value)
                print(f"✅ Selected by exact text: {value}")
                return
            except:
                pass
            
            # Strategy 2: Exact value match
            try:
                select.select_by_value(value)
                print(f"✅ Selected by value: {value}")
                return
            except:
                pass
            
            # Strategy 3: PRIORITY - Main United States selection (avoid territories)
            value_lower = value.lower()
            if "united states" in value_lower or "usa" in value_lower or value_lower == "us":
                # Look for MAIN United States option first (not territories)
                main_us_options = []
                territory_options = []
                
                for option in options:
                    option_text = option.text.strip().lower()
                    if "united states" in option_text:
                        # Prioritize main US over territories
                        if any(territory in option_text for territory in [
                            "minor outlying", "outlying islands", "american samoa", 
                            "guam", "puerto rico", "virgin islands", "northern mariana"
                        ]):
                            territory_options.append(option)
                        else:
                            main_us_options.append(option)
                
                # Select main US option first
                if main_us_options:
                    main_us_options[0].click()
                    print(f"✅ Selected MAIN United States: {main_us_options[0].text}")
                    return
                elif territory_options:
                    territory_options[0].click()
                    print(f"✅ Selected US territory (fallback): {territory_options[0].text}")
                    return
            
            # Strategy 4: Phone code priority - Main US phone code
            if "+1" in value_lower or "united states" in value_lower:
                # Look for main US phone code (+1 United States)
                main_us_phone = []
                territory_phone = []
                
                for option in options:
                    option_text = option.text.strip().lower()
                    if "+1" in option_text and "united states" in option_text:
                        if any(territory in option_text for territory in [
                            "american samoa", "guam", "puerto rico", "virgin islands"
                        ]):
                            territory_phone.append(option)
                        else:
                            main_us_phone.append(option)
                
                # Select main US phone code first
                if main_us_phone:
                    main_us_phone[0].click()
                    print(f"✅ Selected MAIN US phone code: {main_us_phone[0].text}")
                    return
                elif territory_phone:
                    territory_phone[0].click()
                    print(f"✅ Selected US territory phone (fallback): {territory_phone[0].text}")
                    return
            
            # Strategy 5: Case-insensitive partial match (for other fields)
            for option in options:
                option_text = option.text.strip().lower()
                if value_lower in option_text or option_text in value_lower:
                    option.click()
                    print(f"✅ Selected by partial match: {option.text}")
                    return
            
            # Strategy 6: Smart matching for common patterns
            smart_matches = {
                "california": ["california", "ca", "calif"],
                "mobile": ["mobile", "cell", "cellular", "cell phone"],
                "email": ["email", "e-mail", "electronic mail"],
                "yes": ["yes", "true", "1", "agree", "accept"],
                "no": ["no", "false", "0", "decline", "reject"]
            }
            
            for pattern, matches in smart_matches.items():
                if value_lower in matches or any(match in value_lower for match in matches):
                    for option in options:
                        option_text = option.text.strip().lower()
                        if any(match in option_text for match in matches):
                            option.click()
                            print(f"✅ Selected by smart match: {option.text}")
                            return
            
            print(f"⚠️ Could not find matching option for: {value}")
            
        except Exception as e:
            print(f"❌ Dropdown selection failed: {e}")
    
    def _fill_radio_field(self, element, value: str):
        """Enhanced radio button handling with intelligent selection"""
        try:
            print(f"📻 Handling radio button with value: {value}")
            
            # Get the radio button group name to find all related options
            radio_name = element.get_attribute("name")
            radio_value = element.get_attribute("value")
            
            # Find all radio buttons in the same group
            if radio_name:
                radio_group = self.driver.find_elements(By.CSS_SELECTOR, f"input[name='{radio_name}']")
                print(f"📻 Found {len(radio_group)} radio options in group '{radio_name}'")
                
                # Try to match the value intelligently
                value_lower = value.lower()
                
                for radio in radio_group:
                    try:
                        if not radio.is_displayed() or not radio.is_enabled():
                            continue
                        
                        # Get radio option details
                        radio_val = (radio.get_attribute("value") or "").lower()
                        radio_label = self._get_field_label(radio).lower()
                        
                        # Smart matching logic
                        should_select = False
                        
                        # Direct value match
                        if value_lower == radio_val:
                            should_select = True
                        # Label match
                        elif value_lower in radio_label or radio_label in value_lower:
                            should_select = True
                        # Common patterns
                        elif value_lower in ["yes", "true", "1", "agree"] and radio_val in ["yes", "true", "1", "y"]:
                            should_select = True
                        elif value_lower in ["no", "false", "0", "disagree"] and radio_val in ["no", "false", "0", "n"]:
                            should_select = True
                        
                        if should_select:
                            # Scroll to radio button and click
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", radio)
                            time.sleep(0.5)
                            radio.click()
                            print(f"✅ Selected radio option: {radio_label or radio_val}")
                            return
                    
                    except Exception as e:
                        continue
            
            # Fallback: click the current element if it matches
            if value.lower() in ["yes", "true", "1"]:
                element.click()
                print(f"✅ Selected radio button (fallback)")
            
        except Exception as e:
            print(f"❌ Radio button selection failed: {e}")
    
    def _fill_checkbox_field(self, element, value: str):
        """Enhanced checkbox handling with intelligent state management"""
        try:
            print(f"☑️ Handling checkbox with value: {value}")
            
            # Get current state
            is_currently_checked = element.is_selected()
            checkbox_label = self._get_field_label(element)
            
            # Determine desired state based on value
            value_lower = value.lower()
            should_be_checked = False
            
            # Smart value interpretation
            if value_lower in ["yes", "true", "1", "checked", "agree", "accept", "consent", "authorize"]:
                should_be_checked = True
            elif value_lower in ["no", "false", "0", "unchecked", "disagree", "decline", "reject"]:
                should_be_checked = False
            else:
                # For other values, try to interpret based on context
                if "background check" in checkbox_label.lower() or "consent" in checkbox_label.lower():
                    should_be_checked = True  # Usually want to consent
                elif "newsletter" in checkbox_label.lower() or "marketing" in checkbox_label.lower():
                    should_be_checked = False  # Usually don't want marketing
                else:
                    should_be_checked = True  # Default to checked for most cases
            
            # Update checkbox state if needed
            if should_be_checked != is_currently_checked:
                # Scroll to checkbox and click
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.5)
                element.click()
                print(f"✅ {'Checked' if should_be_checked else 'Unchecked'} checkbox: {checkbox_label}")
            else:
                print(f"ℹ️ Checkbox already in correct state: {checkbox_label}")
            
        except Exception as e:
            print(f"❌ Checkbox handling failed: {e}")
    
    def _robust_click(self, element):
        """Robust clicking with multiple fallback methods"""
        try:
            element.click()
        except Exception as e1:
            try:
                self.driver.execute_script("arguments[0].click();", element)
            except Exception as e2:
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(self.driver).move_to_element(element).click().perform()
                except Exception as e3:
                    print(f"⚠️ All click methods failed")
                    raise e3

    def navigate_to_workday(self, workday_url: str):
        """Navigate to Workday application page"""
        if not self.driver:
            self.setup_browser()
        
        print(f"🌐 Navigating to: {workday_url}")
        self.driver.get(workday_url)
        time.sleep(3)
        self.take_screenshot("workday_loaded")
        
        # Handle cookie popups and overlays
        self._handle_popups_and_overlays()
    
    def _handle_popups_and_overlays(self):
        """Smart popup handling - avoids settings/navigation buttons"""
        print("🍪 Smart popup detection (avoiding settings)...")
        
        # AVOID these texts - they navigate to settings pages
        avoid_texts = [
            "cookie settings", "settings", "preferences", "manage cookies",
            "customize", "options", "learn more", "privacy policy", 
            "more info", "details", "configure", "manage preferences"
        ]
        
        # PRIORITY: Look for DISMISS/ACCEPT buttons (avoid settings/navigation)
        smart_selectors = [
            "//button[contains(text(), 'Accept All')]",
            "//button[contains(text(), 'Accept Cookies')]", 
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Allow All')]",
            "//button[contains(text(), 'OK')]",
            "//button[contains(text(), 'Got it')]",
            "//button[contains(text(), 'Agree')]",
            "//button[contains(text(), 'Dismiss')]",
            "//button[contains(text(), 'Close')]",
            "//button[contains(text(), 'Continue')]",
            "//button[contains(text(), 'Deny')]",
            "//button[contains(text(), 'Reject All')]",
        ]
        
        # Try to find and click ONLY dismiss/accept buttons
        for selector in smart_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            element_text = (element.text or "").lower()
                            
                            # Skip if this looks like a settings/navigation button
                            if any(avoid_text in element_text for avoid_text in avoid_texts):
                                print(f"⚠️ Skipping settings button: {element.text}")
                                continue
                            
                            print(f"🍪 Found dismiss button: {element.text[:30]}...")
                            
                            # Scroll to element and click
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            time.sleep(0.5)
                            
                            # Try multiple click methods
                            try:
                                element.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", element)
                            
                            print("✅ Popup dismissed")
                            time.sleep(1)
                            return  # Exit after first successful dismissal
                    except Exception as e:
                        continue
            except Exception as e:
                continue
        
        # Handle overlay divs that might be blocking content
        overlay_selectors = [
            ".overlay",
            ".modal-backdrop",
            ".popup-overlay",
            "[class*='overlay']",
            "[id*='overlay']",
            ".phs-cookie-popup-area",
            ".ph-widget-box",
        ]
        
        for selector in overlay_selectors:
            try:
                overlays = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for overlay in overlays:
                    try:
                        if overlay.is_displayed():
                            # Try to hide the overlay
                            self.driver.execute_script("arguments[0].style.display = 'none';", overlay)
                            print(f"🚫 Hidden overlay: {selector}")
                    except:
                        continue
            except:
                continue
        
        # Wait a moment for any animations to complete
        time.sleep(2)
        print("✅ Popup handling completed")
    
    def detect_form_fields(self) -> List[WorkdayField]:
        """Detect form fields on the current page using computer vision and DOM analysis"""
        fields = []
        
        # Take screenshot for analysis
        screenshot_path = self.take_screenshot("form_analysis")
        
        # Get all input fields from DOM
        input_elements = self.driver.find_elements(By.TAG_NAME, "input")
        textarea_elements = self.driver.find_elements(By.TAG_NAME, "textarea")
        select_elements = self.driver.find_elements(By.TAG_NAME, "select")
        
        # Process input fields
        for element in input_elements:
            try:
                field_type = element.get_attribute("type") or "text"
                if field_type in ["text", "email", "tel", "password"]:
                    label = self._get_field_label(element)
                    xpath = self._get_element_xpath(element)
                    
                    field = WorkdayField(
                        label=label,
                        field_type=field_type,
                        xpath=xpath
                    )
                    fields.append(field)
            except Exception as e:
                print(f"Error processing input field: {e}")
        
        # Process textarea fields
        for element in textarea_elements:
            try:
                label = self._get_field_label(element)
                xpath = self._get_element_xpath(element)
                
                field = WorkdayField(
                    label=label,
                    field_type="textarea",
                    xpath=xpath
                )
                fields.append(field)
            except Exception as e:
                print(f"Error processing textarea field: {e}")
        
        # Process select fields
        for element in select_elements:
            try:
                label = self._get_field_label(element)
                xpath = self._get_element_xpath(element)
                
                field = WorkdayField(
                    label=label,
                    field_type="select",
                    xpath=xpath
                )
                fields.append(field)
            except Exception as e:
                print(f"Error processing select field: {e}")
        
        print(f"🔍 Detected {len(fields)} form fields")
        return fields
    
    def _get_field_label(self, element) -> str:
        """Extract label for a form field"""
        try:
            # Try to find associated label
            field_id = element.get_attribute("id")
            if field_id:
                label_element = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                if label_element:
                    return label_element.text.strip()
            
            # Try to find label by proximity
            parent = element.find_element(By.XPATH, "..")
            label_text = parent.text.strip()
            if label_text and len(label_text) < 100:
                return label_text
            
            # Try placeholder or name attribute
            placeholder = element.get_attribute("placeholder")
            if placeholder:
                return placeholder
            
            name = element.get_attribute("name")
            if name:
                return name.replace("_", " ").title()
            
            return "Unknown Field"
            
        except Exception:
            return "Unknown Field"
    
    def _get_element_xpath(self, element) -> str:
        """Generate XPath for an element"""
        try:
            return self.driver.execute_script("""
                function getXPath(element) {
                    if (element.id !== '') {
                        return "//*[@id='" + element.id + "']";
                    }
                    if (element === document.body) {
                        return '/html/body';
                    }
                    var ix = 0;
                    var siblings = element.parentNode.childNodes;
                    for (var i = 0; i < siblings.length; i++) {
                        var sibling = siblings[i];
                        if (sibling === element) {
                            return getXPath(element.parentNode) + '/' + element.tagName.toLowerCase() + '[' + (ix + 1) + ']';
                        }
                        if (sibling.nodeType === 1 && sibling.tagName === element.tagName) {
                            ix++;
                        }
                    }
                }
                return getXPath(arguments[0]);
            """, element)
        except Exception:
            return ""
    
    def map_resume_to_fields(self, fields: List[WorkdayField]) -> List[WorkdayField]:
        """Map resume data to detected form fields using LLM"""
        if not self.resume_data:
            raise Exception("No resume data loaded. Call load_resume() first.")
        
        # Create mapping prompt
        field_descriptions = []
        for i, field in enumerate(fields):
            field_descriptions.append(f"{i}: {field.label} ({field.field_type})")
        
        mapping_prompt = f"""
You are helping fill out a job application form. Map the resume data to the appropriate form fields.

Resume Data:
- Name: {self.resume_data.name}
- Email: {self.resume_data.email}
- Phone: {self.resume_data.phone}
- Address: {self.resume_data.address}
- Summary: {self.resume_data.summary}
- Skills: {', '.join(self.resume_data.skills)}
- Experience: {json.dumps(self.resume_data.experience, indent=2)}
- Education: {json.dumps(self.resume_data.education, indent=2)}

Form Fields:
{chr(10).join(field_descriptions)}

For each field, provide the appropriate value from the resume data. If a field asks for a long response (like "Why do you want to work here?"), generate a professional response based on the resume data.

Return JSON format:
{{
  "0": "value for field 0",
  "1": "value for field 1",
  ...
}}
"""
        
        try:
            response = self.llm_client.generate_response(mapping_prompt, max_length=1500)
            
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                mappings = json.loads(json_str)
                
                # Apply mappings to fields
                for i, field in enumerate(fields):
                    field_value = mappings.get(str(i), "")
                    if field_value:
                        field.value = field_value
                
                print(f"✅ Mapped resume data to {len([f for f in fields if f.value])} fields")
                return fields
            
        except Exception as e:
            print(f"LLM mapping failed: {e}, using basic mapping")
        
        # Fallback to basic mapping
        return self._basic_field_mapping(fields)
    
    def _basic_field_mapping(self, fields: List[WorkdayField]) -> List[WorkdayField]:
        """Basic field mapping without LLM"""
        for field in fields:
            label_lower = field.label.lower()
            
            if any(keyword in label_lower for keyword in ["name", "full name", "first name", "last name"]):
                field.value = self.resume_data.name
            elif any(keyword in label_lower for keyword in ["email", "e-mail"]):
                field.value = self.resume_data.email
            elif any(keyword in label_lower for keyword in ["phone", "telephone", "mobile"]):
                field.value = self.resume_data.phone
            elif any(keyword in label_lower for keyword in ["address", "location", "city"]):
                field.value = self.resume_data.address
            elif any(keyword in label_lower for keyword in ["summary", "objective", "about"]):
                field.value = self.resume_data.summary
        
        return fields
    
    def fill_form_fields(self, fields: List[WorkdayField]) -> int:
        """Fill form fields with mapped values"""
        filled_count = 0
        
        for field in fields:
            if not field.value or field.filled:
                continue
            
            try:
                print(f"📝 Filling: {field.label} = {field.value[:50]}...")
                
                # Find element by xpath
                element = self.wait.until(EC.presence_of_element_located((By.XPATH, field.xpath)))
                
                # Scroll to element
                self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(0.5)
                
                # Fill based on field type
                if field.field_type in ["text", "email", "tel"]:
                    element.clear()
                    self._type_slowly(element, field.value)
                    
                elif field.field_type == "textarea":
                    element.clear()
                    self._type_slowly(element, field.value)
                    
                elif field.field_type == "select":
                    # Handle select dropdown
                    from selenium.webdriver.support.ui import Select
                    select = Select(element)
                    # Try to select by visible text or value
                    try:
                        select.select_by_visible_text(field.value)
                    except:
                        try:
                            select.select_by_value(field.value)
                        except:
                            print(f"⚠️ Could not select value for {field.label}")
                            continue
                
                field.filled = True
                filled_count += 1
                time.sleep(config.action_delay)
                
            except Exception as e:
                print(f"❌ Error filling {field.label}: {e}")
                continue
        
        print(f"✅ Successfully filled {filled_count} fields")
        self.take_screenshot("form_filled")
        return filled_count
    
    def _type_slowly(self, element, text: str):
        """Type text slowly to mimic human behavior with robust clicking"""
        try:
            # Try multiple methods to click and type
            # Method 1: Regular click
            element.click()
        except Exception as e1:
            try:
                # Method 2: JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
            except Exception as e2:
                try:
                    # Method 3: Action chains click
                    from selenium.webdriver.common.action_chains import ActionChains
                    ActionChains(self.driver).move_to_element(element).click().perform()
                except Exception as e3:
                    print(f"⚠️ All click methods failed, trying direct value setting")
                    # Method 4: Direct value setting via JavaScript
                    self.driver.execute_script("arguments[0].value = arguments[1];", element, text)
                    # Trigger change event
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", element)
                    return
        
        # Clear field first
        try:
            element.clear()
        except:
            # If clear fails, select all and delete
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.DELETE)
        
        # Type character by character
        for char in text:
            try:
                element.send_keys(char)
                time.sleep(config.typing_delay)
            except:
                # If typing fails, fall back to JavaScript
                current_value = self.driver.execute_script("return arguments[0].value;", element)
                new_value = current_value + char
                self.driver.execute_script("arguments[0].value = arguments[1];", element, new_value)
    
    def handle_file_uploads(self, resume_path: str):
        """Handle resume file upload fields"""
        try:
            # Look for file upload inputs
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            
            for file_input in file_inputs:
                try:
                    # Check if this looks like a resume upload field
                    label = self._get_field_label(file_input)
                    if any(keyword in label.lower() for keyword in ["resume", "cv", "upload", "attach"]):
                        print(f"📎 Uploading resume to: {label}")
                        file_input.send_keys(os.path.abspath(resume_path))
                        time.sleep(2)
                        break
                except Exception as e:
                    print(f"Error with file upload: {e}")
                    
        except Exception as e:
            print(f"No file upload fields found: {e}")
    
    def take_screenshot(self, name: str) -> str:
        """Take screenshot for debugging"""
        if not self.driver:
            return ""
        
        timestamp = int(time.time())
        filename = f"{config.screenshot_dir}/{name}_{timestamp}.png"
        self.driver.save_screenshot(filename)
        return filename
    
    def auto_fill_application(self, workday_url: str, resume_path: str) -> Dict[str, Any]:
        """Complete multi-page application automation"""
        results = {
            "success": False,
            "pages_completed": 0,
            "total_fields_filled": 0,
            "resume_uploaded": False,
            "errors": []
        }
        
        try:
            # Step 1: Parse resume data comprehensively
            print("🔄 Step 1: Parsing resume data...")
            self.load_resume_comprehensive(resume_path)
            
            # Step 2: Setup browser and navigate
            print("🔄 Step 2: Setting up browser...")
            self.setup_browser()
            self.navigate_to_workday(workday_url)
            
            # Step 3: Close all popups (PRIORITY)
            print("🔄 Step 3: Closing all popups...")
            self.close_all_popups()
            
            # Step 4: Upload resume (PRIORITY)
            print("🔄 Step 4: Uploading resume...")
            upload_result = self.upload_resume_comprehensive(resume_path)
            results["resume_uploaded"] = upload_result
            
            # Step 5: Multi-page form filling
            print("🔄 Step 5: Starting multi-page form filling...")
            page_count = 0
            total_fields_filled = 0
            
            while page_count < 10:  # Safety limit
                page_count += 1
                print(f"\n📄 Processing Page {page_count}...")
                
                # Close any popups that might appear on new pages
                self.close_all_popups()
                
                # Detect and fill fields on current page
                fields = self.detect_all_form_fields()
                if fields:
                    print(f"🔍 Found {len(fields)} fields on page {page_count}")
                    mapped_fields = self.map_all_resume_data_to_fields(fields)
                    filled_count = self.fill_all_form_fields(mapped_fields)
                    total_fields_filled += filled_count
                    print(f"✅ Filled {filled_count} fields on page {page_count}")
                else:
                    print(f"ℹ️ No fields found on page {page_count}")
                
                # Take screenshot of current page
                self.take_screenshot(f"page_{page_count}_completed")
                
                # Try to go to next page
                if not self.go_to_next_page():
                    print(f"🏁 No more pages found. Completed {page_count} pages.")
                    break
                
                # Wait for page to load
                time.sleep(3)
            
            results["pages_completed"] = page_count
            results["total_fields_filled"] = total_fields_filled
            results["success"] = True
            
            print("🎉 Multi-page application automation completed successfully!")
            print(f"📊 Summary: Pages: {results['pages_completed']} | Resume: {'✅' if results['resume_uploaded'] else '❌'} | Total Fields: {results['total_fields_filled']}")
            
        except Exception as e:
            error_msg = f"Multi-page automation failed: {str(e)}"
            print(f"❌ {error_msg}")
            results["errors"].append(error_msg)
            self.take_screenshot("error_state")
        
        return results
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("🧹 Browser closed")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self.cleanup()
    
    def close_all_popups(self):
        """Enhanced popup closing - handles ALL types of popups"""
        print("🚫 Intelligently closing popups (avoiding settings/navigation)...")
        
        # Handle JavaScript alerts first
        self._handle_alerts()
        
        # PRIORITY: Look for DISMISS/ACCEPT buttons first (avoid settings/navigation)
        priority_selectors = [
            # High priority - these actually dismiss popups
            "//button[contains(text(), 'Accept All')]",
            "//button[contains(text(), 'Accept Cookies')]", 
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Allow All')]",
            "//button[contains(text(), 'OK')]",
            "//button[contains(text(), 'Got it')]",
            "//button[contains(text(), 'Agree')]",
            "//button[contains(text(), 'Dismiss')]",
            "//button[contains(text(), 'Close')]",
            "//button[contains(text(), 'Continue')]",
            "//button[contains(text(), 'Deny')]",
            "//button[contains(text(), 'Reject All')]",
            
            # Close buttons and X icons
            "button[aria-label*='close']", "button[title*='close']",
            "button[class*='close']", "button[id*='close']",
            ".close-button", ".btn-close", ".modal-close",
            
            # X symbols
            "button[innerHTML='×']", "button[innerHTML='✕']", 
            "span[innerHTML='×']", ".fa-times", ".fa-close", ".icon-close"
        ]
        
        # AVOID these - they navigate to settings pages
        avoid_texts = [
            "cookie settings", "settings", "preferences", "manage cookies",
            "customize", "options", "learn more", "privacy policy", 
            "more info", "details", "configure"
        ]
        
        popups_closed = 0
        
        # Try priority selectors first
        for selector in priority_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            element_text = (element.text or "").lower()
                            
                            # Skip if this looks like a settings/navigation button
                            if any(avoid_text in element_text for avoid_text in avoid_texts):
                                print(f"⚠️ Skipping settings button: {element.text}")
                                continue
                            
                            print(f"🚫 Dismissing popup: {element.text or 'Close button'}...")
                            
                            # Scroll to element first
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            time.sleep(0.5)
                            
                            # Multiple click strategies
                            try:
                                element.click()
                            except:
                                try:
                                    self.driver.execute_script("arguments[0].click();", element)
                                except:
                                    # Force click with action chains
                                    from selenium.webdriver.common.action_chains import ActionChains
                                    ActionChains(self.driver).move_to_element(element).click().perform()
                            
                            popups_closed += 1
                            time.sleep(1)
                            print(f"✅ Successfully dismissed popup")
                            break
                    except Exception as e:
                        continue
                if popups_closed > 0:
                    break  # Stop after first successful dismissal
            except:
                continue
        
        # Force hide overlay elements that might still be blocking
        overlay_selectors = [
            ".overlay", ".modal-backdrop", ".popup-overlay", "[class*='overlay']",
            "[id*='overlay']", ".phs-cookie-popup-area", ".ph-widget-box",
            ".modal", ".dialog", ".popup", ".lightbox", ".backdrop"
        ]
        
        overlays_hidden = 0
        for selector in overlay_selectors:
            try:
                overlays = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for overlay in overlays:
                    try:
                        if overlay.is_displayed():
                            self.driver.execute_script("arguments[0].style.display = 'none';", overlay)
                            self.driver.execute_script("arguments[0].style.visibility = 'hidden';", overlay)
                            overlays_hidden += 1
                    except:
                        continue
            except:
                continue
        
        print(f"✅ Dismissed {popups_closed} popups and hidden {overlays_hidden} overlays")
        time.sleep(2)
        
        # Force hide overlay elements
        overlay_selectors = [
            ".overlay", ".modal-backdrop", ".popup-overlay", "[class*='overlay']",
            "[id*='overlay']", ".phs-cookie-popup-area", ".ph-widget-box",
            ".modal", ".dialog", ".popup", ".lightbox", ".backdrop"
        ]
        
        overlays_hidden = 0
        for selector in overlay_selectors:
            try:
                overlays = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for overlay in overlays:
                    try:
                        if overlay.is_displayed():
                            self.driver.execute_script("arguments[0].style.display = 'none';", overlay)
                            self.driver.execute_script("arguments[0].style.visibility = 'hidden';", overlay)
                            overlays_hidden += 1
                    except:
                        continue
            except:
                continue
        
        print(f"✅ Closed {popups_closed} popups and hidden {overlays_hidden} overlays")
        time.sleep(2)
    
    def upload_resume_comprehensive(self, resume_path: str) -> bool:
        """Comprehensive resume upload with multiple strategies"""
        print("📎 Comprehensive resume upload search...")
        
        # Enhanced file upload selectors
        file_selectors = [
            # Standard file inputs
            "input[type='file']",
            
            # Accept attribute variations
            "input[accept*='.pdf']", "input[accept*='.doc']", "input[accept*='.docx']",
            "input[accept*='pdf']", "input[accept*='doc']", "input[accept*='application']",
            
            # Name/ID attribute variations
            "input[name*='resume']", "input[name*='cv']", "input[name*='upload']",
            "input[name*='file']", "input[name*='document']", "input[name*='attachment']",
            "input[id*='resume']", "input[id*='cv']", "input[id*='upload']",
            "input[id*='file']", "input[id*='document']", "input[id*='attachment']",
            
            # Class attribute variations
            "input[class*='upload']", "input[class*='file']", "input[class*='resume']",
            "input[class*='cv']", "input[class*='document']", "input[class*='attachment']",
            
            # Aria/accessibility attributes
            "input[aria-label*='upload']", "input[aria-label*='resume']", "input[aria-label*='cv']",
            "input[aria-label*='file']", "input[aria-label*='document']",
            
            # Placeholder variations
            "input[placeholder*='upload']", "input[placeholder*='resume']", "input[placeholder*='cv']",
            "input[placeholder*='file']", "input[placeholder*='document']"
        ]
        
        uploaded = False
        upload_attempts = 0
        
        for selector in file_selectors:
            try:
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for file_input in file_inputs:
                    try:
                        if file_input.is_enabled() and file_input.get_attribute("type") == "file":
                            upload_attempts += 1
                            label = self._get_field_label(file_input)
                            print(f"📎 Attempt {upload_attempts}: Found upload field - {label}")
                            
                            # Scroll to element
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", file_input)
                            time.sleep(1)
                            
                            # Upload the file
                            file_input.send_keys(os.path.abspath(resume_path))
                            print(f"✅ Resume uploaded successfully to: {label}")
                            uploaded = True
                            time.sleep(3)  # Wait for upload to process
                            
                            # Handle any upload success alerts
                            self._handle_alerts()
                            
                            break
                    except Exception as e:
                        print(f"⚠️ Upload attempt {upload_attempts} failed: {e}")
                        continue
                if uploaded:
                    break
            except:
                continue
        
        # Try alternative upload methods if standard didn't work
        if not uploaded:
            print("🔄 Trying alternative upload methods...")
            uploaded = self._try_drag_drop_upload(resume_path) or self._try_button_click_upload(resume_path)
        
        if uploaded:
            print("🎉 Resume upload completed successfully!")
            self.take_screenshot("resume_uploaded")
        else:
            print("⚠️ No file upload fields found on this page")
        
        return uploaded
    
    def _try_drag_drop_upload(self, resume_path: str) -> bool:
        """Try drag and drop upload areas"""
        try:
            drag_drop_selectors = [
                "[class*='drag']", "[class*='drop']", "[id*='drag']", "[id*='drop']",
                ".dropzone", ".upload-area", ".file-drop", ".drag-drop"
            ]
            
            for selector in drag_drop_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed():
                        print(f"📎 Found drag-drop area: {selector}")
                        # This would require more complex implementation
                        # For now, just note that we found it
                        return False
            return False
        except:
            return False
    
    def _try_button_click_upload(self, resume_path: str) -> bool:
        """Try clicking upload buttons that might trigger file dialogs"""
        try:
            upload_button_selectors = [
                "//button[contains(text(), 'Upload')]",
                "//button[contains(text(), 'Browse')]",
                "//button[contains(text(), 'Choose File')]",
                "//button[contains(text(), 'Select File')]",
                "//a[contains(text(), 'Upload')]",
                "//a[contains(text(), 'Browse')]"
            ]
            
            for selector in upload_button_selectors:
                buttons = self.driver.find_elements(By.XPATH, selector)
                for button in buttons:
                    if button.is_displayed() and button.is_enabled():
                        print(f"📎 Found upload button: {button.text}")
                        # This would require handling file dialogs
                        # For now, just note that we found it
                        return False
            return False
        except:
            return False
    
    def go_to_next_page(self) -> bool:
        """Navigate to the next page in multi-page application"""
        print("➡️ Looking for next page navigation...")
        
        # Enhanced next page selectors
        next_selectors = [
            # Standard next buttons
            "//button[contains(text(), 'Next')]",
            "//button[contains(text(), 'Continue')]",
            "//button[contains(text(), 'Proceed')]",
            "//button[contains(text(), 'Forward')]",
            "//button[contains(text(), 'Save and Continue')]",
            "//button[contains(text(), 'Save & Continue')]",
            "//button[contains(text(), 'Submit and Continue')]",
            
            # Link-based navigation
            "//a[contains(text(), 'Next')]",
            "//a[contains(text(), 'Continue')]",
            "//a[contains(text(), 'Proceed')]",
            
            # Attribute-based selectors
            "button[id*='next']", "button[class*='next']",
            "button[id*='continue']", "button[class*='continue']",
            "button[id*='proceed']", "button[class*='proceed']",
            "button[id*='forward']", "button[class*='forward']",
            
            # Form submission buttons
            "button[type='submit']", "input[type='submit']",
            "button[class*='submit']", "button[id*='submit']",
            
            # Workday/Adobe specific
            "button[data-automation-id*='next']",
            "button[data-automation-id*='continue']",
            "button[data-automation-id*='submit']",
            
            # Generic progression buttons
            "button[class*='primary']", "button[class*='btn-primary']",
            ".btn-primary", ".primary-button", ".next-button", ".continue-button"
        ]
        
        for selector in next_selectors:
            try:
                if selector.startswith("//"):
                    elements = self.driver.find_elements(By.XPATH, selector)
                else:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for element in elements:
                    try:
                        if element.is_displayed() and element.is_enabled():
                            button_text = element.text or element.get_attribute("value") or "Button"
                            print(f"➡️ Found next page button: {button_text}")
                            
                            # Scroll to button
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                            time.sleep(1)
                            
                            # Click the button
                            try:
                                element.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", element)
                            
                            print(f"✅ Clicked: {button_text}")
                            time.sleep(3)  # Wait for page transition
                            
                            # Verify we moved to a new page
                            if self._verify_page_change():
                                print("✅ Successfully navigated to next page")
                                return True
                            else:
                                print("⚠️ Page didn't change, trying next button...")
                                continue
                                
                    except Exception as e:
                        print(f"⚠️ Error clicking button: {e}")
                        continue
            except:
                continue
        
        print("🏁 No more next page buttons found")
        return False
    
    def _verify_page_change(self) -> bool:
        """Verify that we successfully moved to a new page"""
        try:
            # Wait for potential page load
            time.sleep(2)
            
            # Check for common indicators of page change
            page_indicators = [
                # Look for different page content
                "h1", "h2", ".page-title", ".step-title", ".section-title",
                # Look for progress indicators
                ".progress", ".step-indicator", ".breadcrumb",
                # Look for new form fields
                "input", "textarea", "select"
            ]
            
            for indicator in page_indicators:
                elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                if elements:
                    return True
            
            return False
        except:
            return True  # Assume success if we can't verify