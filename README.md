# monopigi-sdk

Python SDK and CLI for the **Monopigi Greek Government Data API**.

One API. 31M+ government decisions. 18K EU procurement notices. 172 energy permit layers. 84 open datasets. Normalized JSON. One bearer token.

## Installation

```bash
# Base package
pip install monopigi-sdk

# With DataFrame support (Polars + Pandas)
pip install monopigi-sdk[dataframe]

# With interactive TUI browser
pip install monopigi-sdk[fuzzy]

# Everything
pip install monopigi-sdk[all]
```

Requires Python 3.12+.

---

## Quick Start

### Python SDK

```python
from monopigi_sdk import MonopigiClient

with MonopigiClient("mp_live_your_token_here") as client:
    # Search across all 6 data sources
    results = client.search("hospital procurement", limit=10)
    for doc in results.results:
        print(f"{doc.source}: {doc.title}")
```

### CLI

```bash
# Save your token (once)
monopigi auth login mp_live_your_token_here

# Search
monopigi search "hospital procurement"

# Get your API key at https://monopigi.com
```

---

## Data Sources

| Source | What it contains | Volume |
|--------|-----------------|--------|
| **Diavgeia** | Government spending decisions, contracts, financial data | 31M+ decisions |
| **TED (EU)** | EU public procurement notices for Greece (EL/EN) | 18K+ notices |
| **RAE Energy** | Energy permits — wind, solar, hydro with GeoJSON | 172 WFS layers |
| **data.gov.gr** | National open data — health, economy, crime, energy | 84 datasets |
| **ELSTAT** | Statistical time series — GDP, unemployment, trade | 28 series |
| **Mitos** | Government org registry — names, addresses, VAT | 2,886 orgs |

---

## SDK Reference

### Client

```python
from monopigi_sdk import MonopigiClient, AsyncMonopigiClient

# Sync client
client = MonopigiClient(token="mp_live_...", base_url="https://api.monopigi.com")

# With caching (5 min TTL)
client = MonopigiClient(token="mp_live_...", cache_ttl=300)

# With custom retry (default: 3)
client = MonopigiClient(token="mp_live_...", max_retries=5)

# Context manager (auto-closes connection)
with MonopigiClient("mp_live_...") as client:
    ...

# Async client
async with AsyncMonopigiClient("mp_live_...") as client:
    results = await client.search("hospital")
```

### Core Methods

```python
# Search across all sources
results = client.search("hospital procurement", limit=100, offset=0)

# Query a specific source
docs = client.documents("ted", limit=50, since="2026-01-01")

# List available sources
sources = client.sources()

# Platform statistics
stats = client.stats()

# Your API usage today
usage = client.usage()
```

### Source-Specific Clients

Typed convenience wrappers for each data source:

```python
# TED EU procurement
tenders = client.ted.notices(limit=100, since="2026-01-01")

# Diavgeia government decisions
decisions = client.diavgeia.decisions(limit=50)

# ELSTAT statistics
datasets = client.elstat.datasets()

# RAE energy permits
permits = client.rae.permits()

# data.gov.gr national data
data = client.data_gov_gr.datasets()

# Mitos government organizations
orgs = client.mitos.organizations()
```

### Auto-Pagination

Iterate through all results without manual offset management:

```python
# Yields every document, auto-fetches next pages
for doc in client.search_iter("procurement"):
    print(doc.title)

# Same for source-specific queries
for doc in client.documents_iter("ted", since="2026-01-01"):
    process(doc)
```

### DataFrame Conversion

Convert any response to Polars or Pandas (requires `[dataframe]` extra):

```python
# Polars DataFrame
df = client.search("hospital").to_polars()

# Pandas DataFrame
df = client.documents("ted", limit=500).to_pandas()
```

### Bulk Export

Export entire sources to files with progress bars:

```python
# JSON
count = client.export("ted", "tenders.json", format="json")

# CSV
count = client.export("diavgeia", "decisions.csv", format="csv", since="2026-01-01")

# Parquet (requires polars)
count = client.export("ted", "tenders.parquet", format="parquet")
```

### Caching

Disk-based cache with TTL to avoid repeated API calls:

```python
# Cache responses for 1 hour
client = MonopigiClient("mp_live_...", cache_ttl=3600)

# First call hits the API
results1 = client.search("hospital")

# Second identical call served from disk cache
results2 = client.search("hospital")  # instant, no API call
```

Cache is stored in `~/.monopigi/cache/` as SHA-256 keyed JSON files.

### Rate-Limit Handling

The client automatically handles HTTP 429 (rate limit exceeded):

```python
# Auto-waits when rate-limited, retries up to max_retries times
client = MonopigiClient("mp_live_...", max_retries=3)

# If rate limit is hit, the client:
# 1. Reads X-RateLimit-Reset header
# 2. Waits until reset time (capped at 5 min)
# 3. Retries the request
# 4. Raises RateLimitError only after exhausting retries
```

### Error Handling

```python
from monopigi_sdk import MonopigiClient, AuthError, RateLimitError, NotFoundError, MonopigiError

try:
    client = MonopigiClient("invalid_token")
    client.sources()
except AuthError:
    print("Invalid API token")
except RateLimitError as e:
    print(f"Rate limited. Resets at: {e.reset_at}")
except NotFoundError:
    print("Source not found")
except MonopigiError:
    print("Something went wrong")
```

### Response Models

All responses are typed Pydantic models with full autocomplete:

```python
from monopigi_sdk.models import (
    Source,          # name, label, status, description
    Document,        # source_id, source, title, doc_type, published_at, quality_score, ...
    SearchResponse,  # query, results, total, limit, offset
    DocumentsResponse,
    StatsResponse,
    UsageResponse,
    SourceStatus,    # Enum: ACTIVE, UNAVAILABLE, PLANNED
    Tier,            # Enum: FREE, PRO, ENTERPRISE
)
```

---

## CLI Reference

### Authentication

```bash
# Save your API token
monopigi auth login mp_live_your_token_here

# Check auth status
monopigi auth status

# Remove saved token
monopigi auth logout
```

Token is stored in `~/.monopigi/config.toml`.

### Searching

```bash
# Search all sources (Rich table output)
monopigi search "hospital procurement"

# Limit results
monopigi search "tender" --limit 20

# Output as JSON (syntax-highlighted on terminal)
monopigi search "hospital" --format json

# Output as CSV
monopigi search "hospital" --format csv

# Select specific fields
monopigi search "hospital" --fields source,title,published_at

# Just count results
monopigi search "Athens" --count

# Cache results for repeated queries
monopigi search "hospital" --cache
```

### Querying Sources

```bash
# Query a specific source
monopigi documents ted --limit 20

# Filter by date
monopigi documents diavgeia --since 2026-01-01

# Output as JSONL (one object per line)
monopigi documents ted --format jsonl
```

### Watching for Changes

```bash
# Poll every 60 seconds for new results
monopigi watch "hospital procurement"

# Custom interval
monopigi watch "tender" --interval 30

# Stream to file
monopigi watch "procurement" --format jsonl | tee new_results.jsonl
```

### Diffing

```bash
# What's new since last check?
monopigi diff ted

# Since a specific date
monopigi diff diavgeia --since 2026-03-15
```

### Exporting

```bash
# Export to JSON
monopigi export ted tenders.json

# Export to CSV
monopigi export diavgeia decisions.csv --format csv --since 2026-01-01

# Export to Parquet
monopigi export ted tenders.parquet --format parquet

# Limit export size
monopigi export ted sample.json --limit 100
```

### Interactive Browser

Requires `monopigi-sdk[fuzzy]`:

```bash
# Browse documents from a source
monopigi browse ted

# Browse with a pre-filter
monopigi browse --query "hospital" --limit 200
```

### Piping (stdin enrichment)

```bash
# Search for each line from stdin
echo "hospital" | monopigi pipe

# Enrich a list of queries
cat search_terms.txt | monopigi pipe --limit 5

# Chain with other monopigi commands
monopigi documents ted --format jsonl | jq -r '.title' | monopigi pipe
```

### Configuration

```bash
# Set a config value
monopigi config set cache_ttl 600
monopigi config set default_format json

# Get a config value
monopigi config get cache_ttl

# List all config
monopigi config list
```

Valid keys: `base_url`, `default_format`, `default_source`, `cache_ttl`.

### Shell Completions

```bash
# Show installation instructions
monopigi completions

# Or use Typer's built-in
monopigi --install-completion
```

### Platform Info

```bash
# Platform statistics
monopigi stats

# Your API usage
monopigi usage

# Available data sources
monopigi sources
```

---

## Unix Pipe Recipes

The CLI is pipe-friendly — it auto-switches to JSONL output when piped.

```bash
# Filter with jq
monopigi search "hospital" | jq 'select(.quality_score > 0.9)'

# Count results
monopigi search "Athens" --count

# Extract titles
monopigi documents ted --format jsonl | jq -r '.title'

# Find procurement over EUR 1M
monopigi documents ted --format jsonl | jq 'select(.title | test("1.000.000|1,000,000"))'

# Deduplicate across sources
monopigi search "procurement" --format jsonl | jq -s 'unique_by(.source_id)'

# Top sources by document count
monopigi stats | jq '.sources | to_entries | sort_by(-.value.documents) | .[].key'
```

---

## Pricing

| Tier | Price | Daily Queries |
|------|-------|---------------|
| Free | EUR 0 | 5 |
| Pro | EUR 299/mo | 10,000 |
| Enterprise | Custom | Unlimited |

Get your API key at [monopigi.com](https://monopigi.com).

---

## Links

- Website: [monopigi.com](https://monopigi.com)
- API Docs: [api.monopigi.com/docs](https://api.monopigi.com/docs)
- Contact: info@monopigi.com
