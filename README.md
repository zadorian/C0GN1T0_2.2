# C0GN1T0_2.2

A Python-based web archival and content retrieval system that supports:
- Common Crawl archive searching
- Wayback Machine integration
- Domain-wide and single-page content retrieval
- Content caching and indexing
- Historical content analysis

## Features

- Search historical web content from multiple sources
- Support for domain-wide and specific page searches
- Flexible date range queries (specific year, year range, all since year)
- Content caching for improved performance
- Full-text search indexing

## Usage

```bash
# Format examples:
2022!example.com?          # All domain content from 2022
2020-2022!example.com?     # Domain content from 2020-2022
2022!?example.com/page.html # Single page from 2022
```

## Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## License

MIT

## Content Search

The system includes a full-text search capability for cached content:

### Using the Search Interface

Run the search interface:
```bash
python indexing/scraping_indexing/scraping_index_searcher.py
```

Search syntax:
- `query???` - Get raw results with extended context
- `query??` - Get AI-analyzed results (saved to operational memory)

Examples:
```bash
python???     # Search for "python" with raw results
bitcoin??    # Search for "bitcoin" with AI analysis
```

The search results include:
- URL and timestamp
- Relevance score
- Extended context (approximately 20 words before/after matches)
- AI analysis (when using ??)

## Web Scraping Features

### Current Web Scraping
Run current web scraping to fetch fresh content from live websites:
```bash
python scrapers/current_scraping.py domain.com
```

Options:
- Single page: `python scrapers/current_scraping.py domain.com/page.html`
- Full domain: `python scrapers/current_scraping.py domain.com`
- With depth: `python scrapers/current_scraping.py domain.com --depth 2`

### Archive Scraping
Search and retrieve historical content from web archives:
```bash
python scrapers/archived_scraping.py 2020!domain.com?
```

Syntax options:
- `2022!domain.com?` - All domain content from 2022
- `2020-2022!domain.com?` - Content from 2020-2022 range
- `2022!?domain.com/page.html` - Single page from 2022

Sources:
- Common Crawl archives
- Wayback Machine
- Local cache (if previously retrieved)

All scraped content is automatically:
1. Cached locally for future use
2. Indexed for full-text search
3. Available through the search interface
