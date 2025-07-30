# Workday Desktop Agent

🤖 **Fully automated job application filling using your resume and AI**

Upload your resume, provide a Workday URL, and watch the agent automatically fill out the entire application using computer vision, web automation, and open source LLMs.

## Features

- 🖥️ **Desktop Automation**: Actually fills out forms in your browser automatically
- 📄 **Resume Parsing**: Extracts data from PDF/DOCX resumes using AI
- 🧠 **Smart Field Mapping**: Uses LLM to intelligently map resume data to form fields
- 📝 **AI-Generated Responses**: Creates professional answers for essay questions
- 📸 **Visual Debugging**: Takes screenshots at each step for transparency
- 🔧 **Multiple LLM Support**: Works with Ollama, Hugging Face, and other backends

## How It Works

1. **Parse Resume**: Extracts your information from PDF/DOCX using AI
2. **Navigate Browser**: Opens Workday application page automatically  
3. **Detect Fields**: Uses computer vision to find all form fields
4. **Map Data**: AI intelligently matches your resume data to form fields
5. **Fill Forms**: Automatically types information and uploads files
6. **Generate Essays**: Creates professional responses for open-ended questions

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Setup LLM Service (Ollama Recommended)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull a model
ollama pull llama2
```

### 3. Test Your Setup
```bash
python main.py test
```

### 4. Fill a Workday Application
```bash
python main.py fill --resume your_resume.pdf --url "https://company.workday.com/apply"
```

## All Commands

```bash
# Parse and preview your resume data
python main.py parse --resume your_resume.pdf

# Automatically fill a Workday application
python main.py fill --resume your_resume.pdf --url "https://company.workday.com/jobs/apply"

# Test system requirements (LLM + Browser)
python main.py test

# Run demo mode
python main.py demo
```

## Configuration

Create a `.env` file for custom settings:
```env
LLM_API_URL=http://localhost:11434/api/generate
LLM_MODEL=llama2
TESSERACT_PATH=/usr/local/bin/tesseract  # If not in PATH
```

## What Gets Filled Automatically

- **Personal Information**: Name, email, phone, address
- **Work Experience**: Job titles, companies, dates, descriptions
- **Education**: Schools, degrees, graduation dates
- **Skills**: Technical and soft skills from resume
- **Cover Letters**: AI-generated based on job and your background
- **Essay Questions**: Professional responses to "Why do you want to work here?" etc.
- **File Uploads**: Automatically uploads your resume file

## Programmatic Usage

```python
from src.agent import WorkdayAgent

# Initialize agent
agent = WorkdayAgent()

# Automatically fill application
results = agent.auto_fill_application(
    workday_url="https://company.workday.com/apply",
    resume_path="your_resume.pdf"
)

print(f"Filled {results['fields_filled']} out of {results['fields_detected']} fields")
```

## LLM Backends

### Ollama (Default)
- Local, private, fast
- Models: llama2, codellama, mistral, etc.
- No API costs

### Hugging Face
- Cloud-based
- Wide model selection
- Requires API token

## Tips for Best Results

1. **Detailed Profile**: More information = better responses
2. **Company Research**: Provide specific company information
3. **Review & Edit**: Always review generated responses before submitting
4. **Model Selection**: Larger models generally produce better results

## Troubleshooting

**LLM Connection Issues:**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

**Response Quality:**
- Try different models (llama2, mistral, codellama)
- Adjust temperature in config.py
- Provide more detailed input information

## Contributing

Feel free to submit issues and enhancement requests!