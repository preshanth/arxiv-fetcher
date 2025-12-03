"""
CrewAI Agent Definitions for ArXiv Paper Analysis
Two PhD-level astronomer agents: Researcher and Recommender
"""

from crewai import Agent, Task, Crew
from typing import List, Dict
import yaml


def create_researcher_agent(llm_config: str) -> Agent:
    """
    Researcher Agent: PhD astronomer who deeply analyzes papers.
    
    Responsibilities:
    - Read full paper (title, abstract, intro if available)
    - Extract key findings beyond the abstract
    - Identify methodology, results, and implications
    - Note relevant references cited
    - Provide section-by-section confidence levels
    """
    return Agent(
        role="Research Astronomer",
        goal="Deeply analyze astronomy papers to extract key findings, methodologies, and implications beyond the abstract",
        backstory="""You are a PhD astronomer with expertise in radio astronomy, 
        interferometry, and data processing. You specialize in reading technical papers 
        and extracting the key scientific and technical contributions. You understand 
        observational techniques, calibration methods, RFI mitigation, and computational 
        approaches in radio astronomy. You always cite specific sections and provide 
        confidence levels for your interpretations.""",
        verbose=True,
        allow_delegation=False,
        llm=llm_config
    )


def create_recommender_agent(llm_config: str) -> Agent:
    """
    Recommender Agent: PhD astronomer who evaluates relevance and importance.
    
    Responsibilities:
    - Evaluate paper relevance to user's research interests
    - Assess novelty and potential impact
    - Identify connections to user's ongoing work
    - Rank papers by importance
    - Highlight papers that warrant immediate attention
    """
    return Agent(
        role="Research Recommender",
        goal="Evaluate paper relevance and importance for radio astronomy research, focusing on interferometry, polarimetry, and data processing",
        backstory="""You are a senior PhD astronomer who helps researchers stay current 
        with literature. You excel at identifying papers that are directly relevant to 
        specific research interests, particularly in radio interferometry, polarimetric 
        imaging, RFI mitigation, calibration algorithms, and large-scale survey data 
        processing. You understand which papers represent significant advances versus 
        incremental work. You prioritize papers that could impact ongoing projects.""",
        verbose=True,
        allow_delegation=False,
        llm=llm_config
    )


def create_analysis_task(agent: Agent, paper: Dict, user_interests: str) -> Task:
    """
    Create task for Researcher Agent to analyze a paper.
    
    Returns detailed summary with:
    - Motivation and context
    - Methodology (with confidence level)
    - Key results (with confidence level)
    - Implications for field (with confidence level)
    - Relevant references cited
    """
    return Task(
        description=f"""Analyze this astronomy paper in depth:

Title: {paper['title']}
Authors: {', '.join(paper['authors'][:3])}{'...' if len(paper['authors']) > 3 else ''}
arXiv ID: {paper['arxiv_id']}
Categories: {', '.join(paper['categories'])}

Abstract:
{paper['abstract']}

Your analysis should include:

1. MOTIVATION & CONTEXT (Confidence: X%)
   - What problem does this paper address?
   - Why is this important?
   
2. METHODOLOGY (Confidence: X%)
   - What techniques/instruments/algorithms are used?
   - What is novel about the approach?
   
3. KEY RESULTS (Confidence: X%)
   - What are the main findings?
   - What are the quantitative results?
   
4. IMPLICATIONS (Confidence: X%)
   - How does this advance the field?
   - What future work does it enable?

5. RELEVANT REFERENCES
   - List any key references mentioned that are relevant to: {user_interests}
   - Note why each reference is important

For each section, provide a confidence level (%) indicating how well you understand 
that aspect from the abstract. If certain details are unclear from the abstract alone, 
state what additional information from the full paper would be helpful.

Be specific and technical. Use proper astronomy terminology.""",
        agent=agent,
        expected_output="Detailed structured analysis with confidence levels per section"
    )


def create_recommendation_task(agent: Agent, paper: Dict, analysis: str, user_interests: str) -> Task:
    """
    Create task for Recommender Agent to evaluate paper relevance.
    
    Returns:
    - Relevance score (1-10)
    - Relevance justification
    - Priority level (High/Medium/Low)
    - Connections to user's work
    """
    return Task(
        description=f"""Evaluate the relevance of this paper for a researcher focused on:
{user_interests}

Paper: {paper['title']}
arXiv ID: {paper['arxiv_id']}

Research Analysis:
{analysis}

Provide:

1. RELEVANCE SCORE: X/10 (with justification)
   - How directly relevant is this to the researcher's interests?
   - What specific aspects make it relevant?

2. PRIORITY LEVEL: [High/Medium/Low]
   - High: Must read immediately, directly impacts ongoing work
   - Medium: Important but can wait, provides useful context
   - Low: Tangentially relevant, good to know

3. CONNECTIONS TO RESEARCH
   - How does this relate to: radio interferometry, polarimetry, RFI mitigation, 
     calibration, large-scale surveys, computational methods?
   - Which ongoing projects could this impact?

4. KEY TAKEAWAYS
   - What are the 2-3 most important points for this researcher?
   - Are there specific techniques/methods worth adopting?

Be honest about relevance. Not every paper needs to be highly relevant.""",
        agent=agent,
        expected_output="Relevance evaluation with score, priority, and connections"
    )


def load_user_interests(config_path: str = "config.yaml") -> str:
    """Load user's research interests from config."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Extract key research areas
    interests = []
    for category, tags in config['active_tags'].items():
        if isinstance(tags, list) and tags:
            interests.extend(tags[:3])  # Top 3 from each category
    
    return ", ".join(interests[:10])  # Limit to top 10 overall


if __name__ == "__main__":
    # Example usage
    print("Agent definitions loaded successfully")
    print("\nResearcher Agent: Analyzes papers in depth")
    print("Recommender Agent: Evaluates relevance and importance")