"""Prompt templates for the plan workflow."""

SECTIONS_PROMPT = """You are a design document planner. Based on the following feature request, generate a list of section names for a design document.

# Feature Request
{user_query}

# Instructions
- Generate 5-10 section names that would comprehensively cover this feature
- Each section should be on its own line
- Include sections like: Overview, Requirements, Technical Design, API, Testing, etc.
- Be specific to the feature being designed
- Order sections logically (overview first, implementation details in middle, testing/deployment last)

# Output Format
Return ONLY the section names, one per line, with no additional text, numbering, or formatting."""

QA_PROMPT = """You are a design document planner. Generate clarifying questions and answers for the following feature.

# Feature Request
{user_query}

# Planned Sections
{sections}

# Instructions
- Generate 5-10 important questions about this feature
- For each question, provide a thoughtful answer based on best practices
- Focus on clarifying ambiguities and making decisions
- Consider edge cases, error handling, performance, and security
- Format as Q: ... A: ... pairs

# Output Format
Q: [Question 1]
A: [Answer 1]

Q: [Question 2]
A: [Answer 2]

(continue for all questions)"""

DESIGN_PROMPT = """You are a technical writer. Create a comprehensive design document for the following feature.

# Feature Request
{user_query}

# Sections to Include
{sections}

# Q&A Context
{qa_content}

# Instructions
- Create a complete design document using the sections provided
- Use the Q&A to inform your decisions
- Be specific and detailed
- Include code examples where appropriate
- Use markdown formatting with proper headers (## for each section)
- Keep the document concise but thorough

# Output Format
Return a complete markdown design document starting with a # title."""

REFINE_PROMPT = """You are a technical writer refining a design document.

# Current Design Document
{design_doc}

# User's Refinement Request
{refinement_query}

# Instructions
- Carefully consider the user's feedback
- Update the design document accordingly
- Preserve sections that don't need changes
- Make focused changes that address the specific feedback
- Maintain consistent formatting and style

# Output Format
Return the updated complete markdown design document."""
