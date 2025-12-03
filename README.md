# ArXiv Daily Paper Analyzer

An agentic AI workflow system for automated analysis of astronomy papers from arXiv, powered by [CrewAI](https://www.crewai.com/) and local LLM inference via [Ollama](https://ollama.ai/).

## Overview

This system fetches daily astronomy papers from arXiv, filters them based on configurable research interests, and produces detailed analytical summaries using specialized AI agents. The system uses CrewAI's agent orchestration framework to coordinate two PhD-level astronomer agents that sequentially analyze papers and provide research recommendations.

## Features

- Automated paper retrieval from arXiv categories (astro-ph.IM, GA, CO, HE)
- Tag-based filtering using hierarchical keyword matching
- Multi-agent analysis with two specialized agents:
  - **Researcher Agent**: Analyzes papers with section-by-section confidence levels
  - **Recommender Agent**: Evaluates relevance and assigns priority
- Generates both JSON and Markdown output
- Runs entirely locally using Ollama
- Configurable via YAML configuration file

## Architecture

### Agentic Workflow

```
ArXiv API → Tag Filter → Researcher Agent → Recommender Agent → Output (JSON + Markdown)
```

The system uses [CrewAI](https://github.com/joaomdmoura/crewAI) for agent orchestration, where two autonomous agents work sequentially:

1. **Researcher Agent** receives paper metadata and produces structured analysis
2. **Recommender Agent** receives the analysis and evaluates relevance to user's research interests
3. Results are aggregated and output in JSON and Markdown formats

### Components

- **arxiv_fetcher.py**: Fetches papers from arXiv API and applies tag filtering
- **tags.py**: Implements tag matching with keyword extraction and scoring
- **agents.py**: Defines agent roles, goals, and task structures
- **crew.py**: Orchestrates the workflow and generates output
- **config.yaml**: Configuration for tags, categories, and LLM settings
- **test_ollama.py**: Tests Ollama connectivity and model availability

## Installation

### Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- LLM model(s) pulled in Ollama

### Setup

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Install Ollama from [ollama.ai](https://ollama.ai/)

3. Pull an LLM model:
   ```bash
   ollama pull llama3.2
   ```

4. Test Ollama connection:
   ```bash
   python test_ollama.py
   ```

5. Edit `config.yaml` to configure research tags (optional)

## Usage

### Run Complete Pipeline

```bash
python crew.py
```

Outputs:
- `arxiv_papers/summaries_YYYYMMDD_HHMMSS.md` - Markdown summary
- `arxiv_papers/analysis_YYYYMMDD_HHMMSS.json` - JSON data

### Fetch Papers Only

```bash
python arxiv_fetcher.py
```

Output: `arxiv_papers/papers_YYYYMMDD.json`

### Test Components

```bash
python tags.py          # Test tag matching
python test_ollama.py   # Test Ollama connection
```

## Configuration

### Research Tags (config.yaml)

Define research interests using hierarchical tags:

```yaml
active_tags:
  facilities:
    - vla
    - meerkat
    - alma
  
  techniques:
    - radio_interferometry
    - polarimetry
  
  data_processing:
    - calibration
    - rfi_mitigation
  
  computational:
    - machine_learning
    - gpu_acceleration
  
  science_topics:
    - cosmic_magnetism
    - absorption_lines
```

### ArXiv Categories

```yaml
arxiv_categories:
  - "astro-ph.IM"  # Instrumentation and Methods
  - "astro-ph.GA"  # Astrophysics of Galaxies
  - "astro-ph.CO"  # Cosmology
  - "astro-ph.HE"  # High Energy
```

### LLM Configuration

```yaml
ollama:
  base_url: "http://localhost:11434"
  summarizer_model: "llama3.2:latest"
```

### Keyword Patterns

Extend keyword patterns for tag matching:

```yaml
keyword_patterns:
  your_tag:
    - "keyword one"
    - "keyword phrase"
```

## Output Format

### Markdown Summary Structure

```markdown
# ArXiv Paper Summaries

**Generated:** [timestamp]
**Papers Analyzed:** [count]
**Research Focus:** [tags]

## Table of Contents
[Links to each paper]

## [Paper Title]

**arXiv ID:** [link]
**PDF:** [link]
**Authors:** [names]
**Published:** [date]
**Tags:** [matched tags]
**Tag Score:** [score]

### Research Analysis
[Researcher Agent output with confidence levels]

### Recommendation
[Recommender Agent output with relevance score and priority]
```

### JSON Structure

```json
[
  {
    "arxiv_id": "...",
    "title": "...",
    "authors": [...],
    "published": "...",
    "pdf_url": "...",
    "matched_tags": [...],
    "tag_score": 0,
    "research_analysis": "...",
    "recommendation": "...",
    "analyzed_at": "..."
  }
]
```

## How It Works

### Tag Filtering

1. Fetches papers from specified arXiv categories
2. Extracts keywords from title and abstract
3. Matches against configured tag patterns
4. Scores papers based on number of tag matches
5. Keeps papers with score ≥ 1

### Agent Analysis

**Researcher Agent** produces:
- Motivation and context (with confidence %)
- Methodology (with confidence %)
- Key results (with confidence %)
- Implications (with confidence %)
- Relevant references cited in paper

**Recommender Agent** produces:
- Relevance score (1-10)
- Priority level (High/Medium/Low)
- Connections to user's research
- Key takeaways

## System Requirements

- Python 3.10+
- Internet connection for arXiv API

**"Crew execution failed"**
- Run with error output: `python crew.py 2>&1 | tee error.log`
- Check error.log for details

## Technical Details

- Uses [CrewAI](https://docs.crewai.com/) for agent orchestration
- Integrates with Ollama via [LiteLLM](https://github.com/BerriAI/litellm)
- Queries [arXiv API](https://arxiv.org/help/api/) for paper metadata
- Implements keyword-based tag matching with regex patterns
- Sequential agent workflow (Researcher → Recommender)

## Files

- `arxiv_fetcher.py` - Fetches and filters papers
- `tags.py` - Tag matching and scoring
- `agents.py` - Agent and task definitions
- `crew.py` - Workflow orchestration
- `config.yaml` - Configuration
- `test_ollama.py` - Ollama connectivity test
- `requirements.txt` - Python dependencies

## References

- [CrewAI Documentation](https://docs.crewai.com/)
- [Ollama](https://ollama.ai/)
- [arXiv API](https://arxiv.org/help/api/)
- [LiteLLM](https://litellm.ai/)

---

**Note**: This is a research tool. Agent-generated summaries should be verified by consulting original papers.