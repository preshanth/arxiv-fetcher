"""
Simple ArXiv daily paper fetcher.
Fetches papers from specified categories and filters by user tags.
Agents will do the deep analysis.
"""

import arxiv
import yaml
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path
import json
from tags import TagMatcher


class ArxivFetcher:
    """Fetch daily astro-ph papers from arXiv."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize fetcher with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.categories = self.config['arxiv_categories']
        self.tag_matcher = TagMatcher(config_path)
        
        # Setup output directory
        self.output_dir = Path(self.config['output']['output_dir'])
        self.output_dir.mkdir(exist_ok=True)
    
    def fetch_papers(self, days_back: int = 1) -> List[Dict]:
        """
        Fetch papers from arXiv from the last N days.
        Filter by tags - keep anything with score >= 1.
        """
        print(f"\nFetching papers from arXiv...")
        print(f"Categories: {', '.join(self.categories)}")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        
        # Build query for multiple categories
        category_query = " OR ".join([f"cat:{cat}" for cat in self.categories])
        
        # Query arXiv
        search = arxiv.Search(
            query=category_query,
            max_results=200,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending
        )
        
        papers = []
        for result in search.results():
            # Check if within date range
            if result.published.replace(tzinfo=None) < start_date:
                break
            
            # Basic paper data
            paper_data = {
                'arxiv_id': result.entry_id.split('/')[-1],
                'title': result.title,
                'abstract': result.summary,  # Changed from result.abstract to result.summary
                'authors': [author.name for author in result.authors],
                'published': result.published.strftime('%Y-%m-%d'),
                'categories': result.categories,
                'pdf_url': result.pdf_url,
                'primary_category': result.primary_category
            }
            
            # Score with tags
            tag_result = self.tag_matcher.score_paper(
                paper_data['title'],
                paper_data['abstract'],
                paper_data['categories']
            )
            
            # Keep if has ANY tag match (score >= 1)
            if tag_result['score'] >= 1:
                paper_data['tag_score'] = tag_result['score']
                paper_data['matched_tags'] = list(tag_result['matched_tags'])
                papers.append(paper_data)
        
        # Sort by tag score (highest first)
        papers.sort(key=lambda x: x['tag_score'], reverse=True)
        
        print(f"\n✓ Fetched {len(papers)} relevant papers")
        
        return papers
    
    def save_papers(self, papers: List[Dict]):
        """Save papers to JSON file."""
        filename = f"papers_{datetime.now().strftime('%Y%m%d')}.json"
        output_file = self.output_dir / filename
        
        with open(output_file, 'w') as f:
            json.dump(papers, f, indent=2)
        
        print(f"✓ Saved to: {output_file}")
        return output_file
    
    def print_summary(self, papers: List[Dict]):
        """Print summary of fetched papers."""
        print(f"\n{'='*70}")
        print(f"FETCHED PAPERS - {len(papers)} total")
        print(f"{'='*70}\n")
        
        for i, paper in enumerate(papers[:10], 1):
            tags = ', '.join(paper['matched_tags'][:3])
            print(f"{i}. [Score: {paper['tag_score']}] {paper['title'][:60]}...")
            print(f"   Tags: {tags}")
            print(f"   {paper['arxiv_id']}\n")
        
        if len(papers) > 10:
            print(f"... and {len(papers) - 10} more papers")


def main():
    """Run the fetcher."""
    fetcher = ArxivFetcher()
    papers = fetcher.fetch_papers(days_back=1)
    
    if papers:
        fetcher.print_summary(papers)
        fetcher.save_papers(papers)
    else:
        print("No papers found matching your tags")
    
    return papers


if __name__ == "__main__":
    main()
