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
