WORKDAY_PROMPTS = {
    "cover_letter": """
Write a professional cover letter for a job application with the following details:
- Position: {position}
- Company: {company}
- Your background: {background}
- Key skills: {skills}
- Why you're interested: {interest}

Keep it concise, professional, and engaging. Maximum 300 words.
""",
    
    "why_interested": """
Explain why you're interested in working at {company} for the {position} role.
Consider these factors:
- Company background: {company_info}
- Your career goals: {career_goals}
- Relevant experience: {experience}

Write a compelling 2-3 paragraph response that shows genuine interest.
""",
    
    "experience_description": """
Describe your relevant experience for the {position} role at {company}.
Your background includes:
- Previous roles: {previous_roles}
- Key achievements: {achievements}
- Relevant skills: {skills}

Write a detailed but concise description highlighting the most relevant aspects.
""",
    
    "strengths_weaknesses": """
Provide a professional response about your strengths and areas for improvement:
- Your key strengths: {strengths}
- Areas you're working to improve: {improvement_areas}
- How you address challenges: {challenge_approach}

Be honest but positive, showing self-awareness and growth mindset.
""",
    
    "career_goals": """
Describe your career goals and how this {position} role at {company} fits into your plans:
- Short-term goals (1-2 years): {short_term_goals}
- Long-term vision (3-5 years): {long_term_goals}
- How this role helps: {role_alignment}

Show ambition while demonstrating commitment to the company.
"""
}