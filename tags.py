"""
Tag system for filtering astronomy papers by research interests.
Provides hierarchical tags and keyword-based matching.
"""

from typing import Dict, List, Set
import re
import yaml


class TagMatcher:
    """Match papers against user-defined research tags."""
    
    def __init__(self, config_path: str = "config.yaml"):
        """Initialize with configuration file."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.active_tags = self.config['active_tags']
        self.keyword_patterns = self.config['keyword_patterns']
        self.thresholds = self.config['filtering']
        
        # Flatten all active tags for easy checking
        self.all_tags = self._flatten_tags()
        
    def _flatten_tags(self) -> Set[str]:
        """Flatten hierarchical tag structure into a set."""
        tags = set()
        for category, tag_list in self.active_tags.items():
            if isinstance(tag_list, list):
                tags.update(tag_list)
        return tags
    
    def extract_keywords(self, text: str) -> Set[str]:
        """
        Extract matching keywords from text (title + abstract).
        Returns set of matched tag categories.
        """
        text_lower = text.lower()
        matched_tags = set()
        
        # Check each keyword pattern
        for tag_category, patterns in self.keyword_patterns.items():
            for pattern in patterns:
                # Use word boundaries to avoid partial matches
                if re.search(r'\b' + re.escape(pattern.lower()) + r'\b', text_lower):
                    matched_tags.add(tag_category)
                    break  # Found one pattern for this tag, move to next tag
        
        return matched_tags
    
    def score_paper(self, title: str, abstract: str, arxiv_categories: List[str]) -> Dict:
        """
        Score a paper based on tag matches.

        A facility mention (VLA, MeerKAT, etc.) is a strong signal on its
        own and accepts the paper outright. Keyword-pattern matches alone
        are weaker - single generic words (e.g. "polarization" appearing in
        an unrelated chemistry/optics context) are common false positives,
        so keyword-only matches require >= keyword_score_medium hits before
        accepting.

        Returns:
            dict with:
                - score: int (number of matching tags)
                - matched_tags: set of matched tag categories
                - decision: 'accept' or 'reject'
        """
        # Combine text for matching
        text = f"{title} {abstract}"

        # Extract keyword matches
        keyword_matches = self.extract_keywords(text)

        # Check for facility name matches (strong signal, accepts alone)
        facility_matches = self._check_facilities(text)

        matched_tags = keyword_matches | facility_matches
        score = len(matched_tags)

        if facility_matches or len(keyword_matches) >= self.thresholds['keyword_score_medium']:
            decision = 'accept'
        else:
            decision = 'reject'

        return {
            'score': score,
            'matched_tags': matched_tags,
            'decision': decision,
            'arxiv_categories': arxiv_categories
        }

    def _check_facilities(self, text: str) -> Set[str]:
        """Check for specific facility mentions, as whole words only (avoids
        e.g. 'ska' matching inside 'Alaska')."""
        facilities = self.active_tags.get('facilities', [])

        matched = set()
        for facility in facilities:
            # Word-boundary match, case-insensitive - a naive substring check
            # would match "ska" inside "Alaska" or "Nebraska".
            if re.search(r'\b' + re.escape(facility) + r'\b', text, re.IGNORECASE):
                matched.add(f"facility_{facility}")

        return matched
    
    def get_tag_summary(self) -> str:
        """Return a formatted summary of active tags."""
        summary = ["Active Research Tags:\n"]
        
        for category, tags in self.active_tags.items():
            if isinstance(tags, list):
                summary.append(f"  {category.replace('_', ' ').title()}:")
                summary.append(f"    {', '.join(tags[:5])}")
                if len(tags) > 5:
                    summary.append(f"    ... and {len(tags) - 5} more")
                summary.append("")
        
        return "\n".join(summary)


def load_tags(config_path: str = "config.yaml") -> TagMatcher:
    """Load tag configuration and return TagMatcher instance."""
    return TagMatcher(config_path)


if __name__ == "__main__":
    # Test the tag matcher
    matcher = TagMatcher()
    
    print(matcher.get_tag_summary())
    print("\n" + "="*60 + "\n")
    
    # Test case 1: High relevance paper
    test_title_1 = "GPU-Accelerated RFI Mitigation for MeerKAT Polarimetry"
    test_abstract_1 = """
    We present a novel GPU-accelerated algorithm for radio frequency interference
    mitigation in polarimetric observations with the MeerKAT radio telescope.
    Our method achieves 100x speedup compared to traditional CPU-based approaches
    while preserving polarization calibration accuracy.
    """
    
    result_1 = matcher.score_paper(test_title_1, test_abstract_1, ['astro-ph.IM'])
    print(f"Test Paper 1: {test_title_1}")
    print(f"Score: {result_1['score']}")
    print(f"Matched tags: {result_1['matched_tags']}")
    print(f"Decision: {result_1['decision']}")
    print()
    
    # Test case 2: Medium relevance paper
    test_title_2 = "Deep Learning for Galaxy Morphology Classification"
    test_abstract_2 = """
    We apply convolutional neural networks to classify galaxy morphologies
    in optical survey data. Our model achieves 95% accuracy on the test set.
    """
    
    result_2 = matcher.score_paper(test_title_2, test_abstract_2, ['astro-ph.GA'])
    print(f"Test Paper 2: {test_title_2}")
    print(f"Score: {result_2['score']}")
    print(f"Matched tags: {result_2['matched_tags']}")
    print(f"Decision: {result_2['decision']}")
    print()
    
    # Test case 3: Low relevance paper
    test_title_3 = "Stellar Evolution Models for Low-Mass Stars"
    test_abstract_3 = """
    We present new stellar evolution models for low-mass stars based on
    updated nuclear reaction rates and opacity tables.
    """
    
    result_3 = matcher.score_paper(test_title_3, test_abstract_3, ['astro-ph.SR'])
    print(f"Test Paper 3: {test_title_3}")
    print(f"Score: {result_3['score']}")
    print(f"Matched tags: {result_3['matched_tags']}")
    print(f"Decision: {result_3['decision']}")
