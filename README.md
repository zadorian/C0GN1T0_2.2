# C.0.G.N.1.T.0.2.2

A comprehensive web analysis and search tool.

## Command Syntax

### Website Search Commands

1. Entity Extraction:
   - `p! :domain.com?`              (Find people)
   - `c! :domain.com?`              (Find companies)
   - `l! :domain.com?`              (Find locations)
   - `@! :domain.com?`              (Find emails)
   - `t! :domain.com?`              (Find phone numbers)
   - `ent! :domain.com?`            (Find all entity types)

2. Historic Content:
   - `p! :2022! domain.com?`        (Find people from 2022)
   - `c! :2020<-! domain.com?`      (Find companies from 2020)

3. Multi-Searcher Format:
   - `p!,c!,l! -> domain.com`      (Run multiple searchers)
   - `ai,ner,keyword -> domain.com` (Run different search types)

4. Comparison Format:
   - `p! :domain1.com? =? domain2.com?`     (Compare entities between domains)
   - `p! :2022! domain.com? =? domain.com?` (Compare entities over time)

### Website Analysis Commands

- `bl!<N domain.com?`     (Analyze N referring domains)
- `!bl<N domain.com?`     (Show N individual backlinks)
- `ga! domain.com?`       (Check Google Analytics)
- `whois! domain.com?`    (Get WHOIS information)
- `age! domain.com?`      (Get domain age)
- `alldom! domain.com?`   (Get all domain info)

### System Commands

- `reindex! all`          (Reindex all cached files)
- `help`                  (Show this help message)
- `quit`                  (Exit the program)

### Social Media Search Commands

Search across social media platforms using simple keyword queries:

```bash
# Platform-specific searches
keyword :reddit?      # Search Reddit
keyword :youtube?     # Search YouTube
keyword :vk?         # Search VKontakte
keyword :tumblr?     # Search Tumblr
keyword              # Search all platforms
```

Available platform aliases:
- Reddit: `:reddit`, `:reddit.com`
- YouTube: `:youtube`, `:youtube.com`, `:yt`
- VKontakte: `:vk`, `:vk.com`, `:vk.ru`, `:vkontakte`
- Tumblr: `:tumblr`, `:tumblr.com`
- Web: `:web`

Each result includes:
- Platform name
- Post timestamp
- Author/username
- Content type
- Sentiment analysis
- Full text content
- Original URL

Examples:
```bash
# Search for a topic on Reddit
python tutorials :reddit?

# Search for videos on YouTube
machine learning :youtube?

# Search VKontakte using any alias
data science :vk?
programming :vkontakte?
coding :vk.ru?

# Search across all supported platforms
artificial intelligence
```

Note: Social media searches are separate from domain-based searches (e.g., `p! :domain.com?`) and will only trigger when using the platform-specific suffixes listed above.

## Examples

### Backlinks Analysis
```bash
# Get 50 individual backlinks
!bl<50 example.com?

# Get 100 referring domains
bl!<100 example.com?
```

### Entity Extraction with Historic Content
```bash
# Find people on current version
p! :example.com?

# Find companies from 2022
c! :2022! example.com?

# Find all entities from 2020 backwards
ent! :2020<-! example.com?
```

### Multi-Searcher and Comparison
```bash
# Run multiple entity searches
p!,c!,l! -> example.com

# Compare entities between domains
p! :domain1.com? =? domain2.com?

# Compare entities over time
p! :2022! domain.com? =? domain.com?
```

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

## Website Analysis Modules

The system includes powerful website analysis capabilities through specialized modules:

### Backlinks Analysis
Located in `website_modules/backlinks.py`

```bash
# Reference pages to target domain
!bl domain.com     # List pages linking to domain
!bl domain.com<20  # Show first 20 results

# Reference domains analysis
bl! domain.com     # List domains linking to domain
bl! domain.com<30  # Show first 30 referring domains

# Additional results
more               # Show next page of results
```

Each result includes:
- Domain Rating (DR) or Ahrefs Rank (AR)
- Backlink counts and types (DoFollow/NoFollow)
- First seen dates
- Outgoing link counts

### WHOIS History
Located in `website_modules/whois.py`

```bash
whois! domain.com  # Get complete WHOIS history
```

Provides:
- Domain registration history
- Registrar changes
- Name server updates
- Registration/expiration dates
- Registrant information (when available)

### Age Analysis
Located in `website_modules/age/age.py`

```bash
# Domain age analysis
age! domain.com?   # Get domain registration date and age

# Page age estimation
age! ?domain.com/page  # Estimate specific page age
```

Page age analysis uses multiple sources:
- Wayback Machine archives
- Backlink first-seen dates
- Content analysis
- WHOIS data

### Google Analytics Tracker
Located in `website_modules/google_analytics.py`

```bash
ga! domain.com     # Find Google Analytics IDs
```

Detects:
- Universal Analytics (UA) codes
- Google Analytics 4 (GA4) IDs
- Google Tag Manager (GTM) containers
- Historical tracking code changes

### Domain Explorer
Located in `website_modules/allDom/alldom.py`

```bash
alldom! domain.com     # Full domain exploration
alldom domain.com?     # Alternative syntax
```

Provides comprehensive domain information:
- Subdomains
- URL structure
- File types
- Core pages
- Resource files

### Unified Interface
All modules can be accessed through the central interface:
```bash
python -m website_modules.website_modules
```

Or import programmatically:
```python
from website_modules.website_modules import WebsiteModules

modules = WebsiteModules()
result = await modules.process_command("bl! example.com")
print(result)
```

### Website Comparison Module
Located in `website_searchers/comparison.py`

Enables direct comparison of search results across multiple domains or time periods.

```bash
# Basic domain comparison
products sold by the company? :company1.com? =? company2.com?

# Entity comparison across domains
p! :company1.com! =? company2.com?    # Compare people
c! :domain1.com! =? domain2.com!      # Compare companies
l! :site1.com! =? site2.com!          # Compare locations
t! :url1.com! =? url2.com!            # Compare technologies
ent! :web1.com! =? web2.com!          # Compare all entities
```

Features:
- Parallel search execution across targets
- AI-powered comparison analysis
- Support for temporal comparisons (same domain, different years)
- Specialized NER (Named Entity Recognition) comparison
- Detailed difference and overlap analysis

Output includes:
- Individual search results for each target
- AI-generated comparison summary highlighting:
  - Key differences
  - Common elements
  - Unique findings
  - Temporal changes (when applicable)

Usage examples:
```python
from website_searchers.comparison import ComparisonSearcher

# Initialize the searcher
comp = ComparisonSearcher()

# Run a comparison
result = await comp.handle_comparison_command(
    "p! :company1.com! =? company2.com?"
)
print(result)
```

Or via command line:
```bash
python comparison.py "p! :company1.com! =? company2.com?"
```
