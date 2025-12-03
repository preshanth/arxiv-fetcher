"""
CrewAI Orchestration for Paper Analysis
Coordinates Researcher and Recommender agents to analyze arxiv papers
"""

from crewai import Crew, Process
from agents import (
    create_researcher_agent, 
    create_recommender_agent,
    create_analysis_task,
    create_recommendation_task,
    load_user_interests
)
from arxiv_fetcher import ArxivFetcher
from typing import List, Dict
import yaml
import json
from datetime import datetime
from pathlib import Path


class PaperAnalysisCrew:
    """Orchestrate multi-agent paper analysis."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize crew with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Setup LLM configuration for agents
        self.llm_config = self._setup_llm_config()
        
        # Load user research interests
        self.user_interests = load_user_interests(config_path)
        
        # Create agents
        self.researcher = create_researcher_agent(self.llm_config)
        self.recommender = create_recommender_agent(self.llm_config)
        
        # Output directory
        self.output_dir = Path(self.config['output']['output_dir'])
        self.output_dir.mkdir(exist_ok=True)
    
    def _setup_llm_config(self):
        """Setup Ollama LLM configuration for CrewAI."""
        ollama_config = self.config['ollama']
        
        # CrewAI expects a string in format: "ollama/model_name"
        # or we pass None and it will use environment variables
        model_name = ollama_config['summarizer_model'].replace(':latest', '')
        return f"ollama/{model_name}"
    
    def analyze_paper(self, paper: Dict) -> Dict:
        """
        Analyze a single paper using both agents.
        
        Returns:
            dict with research_analysis and recommendation
        """
        print(f"\n{'='*70}")
        print(f"Analyzing: {paper['title'][:60]}...")
        print(f"{'='*70}\n")
        
        try:
            # Task 1: Researcher analyzes the paper
            analysis_task = create_analysis_task(
                self.researcher, 
                paper, 
                self.user_interests
            )
            
            # Create crew for analysis
            analysis_crew = Crew(
                agents=[self.researcher],
                tasks=[analysis_task],
                process=Process.sequential,
                verbose=True
            )
            
            # Run analysis
            print("Researcher Agent analyzing paper...")
            analysis_result = analysis_crew.kickoff()
            print(f"\n✓ Analysis complete")
            
        except Exception as e:
            print(f"\n✗ Error in Researcher Agent: {e}")
            import traceback
            traceback.print_exc()
            # Use simplified analysis on error
            analysis_result = f"Analysis failed: {str(e)}"
        
        try:
            # Task 2: Recommender evaluates relevance
            recommendation_task = create_recommendation_task(
                self.recommender,
                paper,
                str(analysis_result),
                self.user_interests
            )
            
            # Create crew for recommendation
            recommendation_crew = Crew(
                agents=[self.recommender],
                tasks=[recommendation_task],
                process=Process.sequential,
                verbose=True
            )
            
            # Run recommendation
            print("\nRecommender Agent evaluating relevance...")
            recommendation_result = recommendation_crew.kickoff()
            print(f"\n✓ Recommendation complete")
            
        except Exception as e:
            print(f"\n✗ Error in Recommender Agent: {e}")
            import traceback
            traceback.print_exc()
            # Use simplified recommendation on error
            recommendation_result = f"Recommendation failed: {str(e)}"
        
        return {
            'arxiv_id': paper['arxiv_id'],
            'title': paper['title'],
            'authors': paper['authors'],
            'published': paper['published'],
            'pdf_url': paper['pdf_url'],
            'matched_tags': paper['matched_tags'],
            'tag_score': paper['tag_score'],
            'research_analysis': str(analysis_result),
            'recommendation': str(recommendation_result),
            'analyzed_at': datetime.now().isoformat()
        }
    
    def analyze_papers(self, papers: List[Dict], max_papers: int = None) -> List[Dict]:
        """
        Analyze multiple papers.
        
        Args:
            papers: List of paper dicts from arxiv_fetcher
            max_papers: Maximum number of papers to analyze (None = all)
        
        Returns:
            List of analysis results
        """
        if max_papers:
            papers = papers[:max_papers]
        
        print(f"\n{'#'*70}")
        print(f"# Starting Analysis of {len(papers)} Papers")
        print(f"# Research Focus: {self.user_interests}")
        print(f"{'#'*70}\n")
        
        results = []
        
        for i, paper in enumerate(papers, 1):
            print(f"\n{'*'*70}")
            print(f"* Paper {i}/{len(papers)}")
            print(f"{'*'*70}")
            
            try:
                result = self.analyze_paper(paper)
                results.append(result)
            except Exception as e:
                print(f"✗ Error analyzing paper: {e}")
                continue
        
        return results
    
    def save_results(self, results: List[Dict]):
        """Save analysis results to JSON and Markdown."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON
        json_filename = f"analysis_{timestamp}.json"
        json_file = self.output_dir / json_filename
        
        with open(json_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save Markdown
        md_filename = f"summaries_{timestamp}.md"
        md_file = self.output_dir / md_filename
        
        self._write_markdown_summary(results, md_file)
        
        print(f"\n✓ Results saved:")
        print(f"  JSON: {json_file}")
        print(f"  Markdown: {md_file}")
        
        return json_file, md_file
    
    def _write_markdown_summary(self, results: List[Dict], output_file: Path):
        """Write analysis results as formatted markdown."""
        with open(output_file, 'w') as f:
            # Header
            f.write(f"# ArXiv Paper Summaries\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Papers Analyzed:** {len(results)}\n\n")
            f.write(f"**Research Focus:** {self.user_interests}\n\n")
            f.write("---\n\n")
            
            # Table of contents
            f.write("## Table of Contents\n\n")
            for i, result in enumerate(results, 1):
                # Create anchor-friendly title
                anchor = result['arxiv_id'].replace('.', '')
                f.write(f"{i}. [{result['title']}](#{anchor})\n")
            f.write("\n---\n\n")
            
            # Individual paper summaries
            for i, result in enumerate(results, 1):
                anchor = result['arxiv_id'].replace('.', '')
                
                f.write(f"## {i}. {result['title']}\n\n")
                f.write(f"<a name='{anchor}'></a>\n\n")
                
                # Metadata
                f.write(f"**arXiv ID:** [{result['arxiv_id']}](https://arxiv.org/abs/{result['arxiv_id']})\n\n")
                f.write(f"**PDF:** [Download](https://arxiv.org/pdf/{result['arxiv_id']}.pdf)\n\n")
                f.write(f"**Authors:** {', '.join(result['authors'][:5])}")
                if len(result['authors']) > 5:
                    f.write(f" et al. ({len(result['authors'])} total)")
                f.write("\n\n")
                f.write(f"**Published:** {result['published']}\n\n")
                f.write(f"**Tags:** {', '.join(result['matched_tags'])}\n\n")
                f.write(f"**Tag Score:** {result['tag_score']}\n\n")
                
                # Research Analysis
                f.write("### Research Analysis\n\n")
                f.write(result['research_analysis'])
                f.write("\n\n")
                
                # Recommendation
                f.write("### Recommendation\n\n")
                f.write(result['recommendation'])
                f.write("\n\n")
                
                f.write("---\n\n")
    
    def print_summary(self, results: List[Dict]):
        """Print summary of analysis results."""
        print(f"\n{'='*70}")
        print(f"ANALYSIS COMPLETE")
        print(f"{'='*70}\n")
        
        # Sort by relevance (extract score from recommendation)
        # For now, just show in order
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['title']}")
            print(f"   arXiv: {result['arxiv_id']}")
            print(f"   Tags: {', '.join(result['matched_tags'][:3])}")
            print(f"   Tag Score: {result['tag_score']}")
            
            # Try to extract recommendation priority
            rec_text = result['recommendation'].lower()
            if 'high' in rec_text and 'priority' in rec_text:
                priority = "HIGH"
            elif 'medium' in rec_text and 'priority' in rec_text:
                priority = "MEDIUM"
            elif 'low' in rec_text and 'priority' in rec_text:
                priority = "LOW"
            else:
                priority = "UNKNOWN"
            
            print(f"   Priority: {priority}")
            print()


def main():
    """
    Complete workflow:
    1. Fetch papers from arXiv
    2. Analyze with Researcher agent
    3. Evaluate with Recommender agent
    4. Save results
    """
    # Fetch papers
    print("Step 1: Fetching papers from arXiv...")
    fetcher = ArxivFetcher()
    papers = fetcher.fetch_papers(days_back=1)
    
    if not papers:
        print("No papers found. Exiting.")
        return
    
    fetcher.print_summary(papers)
    
    # Analyze papers
    print("\nStep 2: Analyzing papers with AI agents...")
    crew = PaperAnalysisCrew()
    
    # Limit to first 5 papers for testing (remove limit for production)
    results = crew.analyze_papers(papers, max_papers=5)
    
    # Save and display
    crew.save_results(results)
    crew.print_summary(results)
    
    print("\n✓ Complete!")


if __name__ == "__main__":
    main()
