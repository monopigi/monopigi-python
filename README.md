# monopigi

Python SDK and CLI for the **Monopigi Greek Government Data API**.

One API. 31M+ government decisions. 200K+ EU procurement notices. 10K+ energy permits. Millions of open data records. Normalized JSON. One bearer token.

**[Documentation](https://monopigi.com/docs)** | **[API Reference](https://monopigi.com/docs/api-reference)** | **[Interactive API Docs](https://api.monopigi.com/docs)** | **[Get API Key](https://monopigi.com/signup)**

## Installation

```bash
# Base package
pip install monopigi

# With Polars DataFrame support
pip install monopigi[df]

# With interactive TUI browser
pip install monopigi[fuzzy]

# Everything
pip install monopigi[all]
```

Requires Python 3.12+.

---

## Quick Start

### Python SDK

```python
from monopigi import MonopigiClient

with MonopigiClient("mp_live_your_token_here") as client:
    # Search across all 8 data sources
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
| **KIMDIS** | Greek public procurement — contracts, auctions, payments | 1M+ records/year |
| **TED (EU)** | EU public procurement notices for Greece (EL/EN) | 200K+ notices |
| **RAE Energy** | Energy permits — wind, solar, hydro with GeoJSON | 15K+ permits |
| **data.gov.gr** | National open data — health, economy, crime, energy | 84 datasets, millions of records |
| **ELSTAT** | Statistical time series — GDP, unemployment, trade | 28 indicators, decades of data |
| **Mitos** | Government orgs + services registry — names, addresses, VAT | 2,886 orgs + 4,264 services |
| **Geodata** | Greek geospatial data — environmental, urban, cadastral (OGC WFS) | 193 layers, 500K+ features |

---

## SDK Reference

### Client

```python
from monopigi import MonopigiClient, AsyncMonopigiClient

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

# Mitos government organizations + services
orgs = client.mitos.organizations()
services = client.mitos.services()

# KIMDIS Greek public procurement
contracts = client.kimdis.contracts(limit=100, since="2026-01-01")

# Geodata — Greek geospatial layers
layers = client.geodata.layers()
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

Convert any response to a Polars DataFrame (requires `[df]` extra):

```python
df = client.search("hospital").to_df()
df = client.documents("ted", limit=500).to_df()
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
from monopigi import MonopigiClient, AuthError, RateLimitError, NotFoundError, MonopigiError

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
from monopigi.models import (
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

Token is stored in `~/.monopigi/config.toml`:

```toml
token = "mp_live_..."
base_url = "https://api.monopigi.com"
```

### Configuration

CLI settings are stored separately in `~/.monopigi/settings.json`:

```bash
# Set API base URL (for self-hosted or development)
monopigi config set base_url http://localhost:8000

# Set default output format (table, json, jsonl, csv)
monopigi config set default_format json

# Set default source for documents/diff/export commands
monopigi config set default_source ted

# Set cache TTL in seconds (default: 300)
monopigi config set cache_ttl 600

# Get a config value
monopigi config get cache_ttl

# List all config (auth + settings)
monopigi config list
```

| Key | Default | Description |
|-----|---------|-------------|
| `base_url` | `https://api.monopigi.com` | API base URL |
| `default_format` | `table` | Output format: `table`, `json`, `jsonl`, `csv` |
| `default_source` | — | Default source for `documents`, `diff`, `export` |
| `cache_ttl` | `300` | Local cache TTL in seconds |

### Searching

**Basic search:**

```bash
# Simple keyword search
monopigi search "hospital"

# Multi-word queries
monopigi search "public procurement Athens"

# Greek language queries
monopigi search "δημόσιο νοσοκομείο"
```

**Filtering by source:**

```bash
# Search only in EU procurement tenders
monopigi search "IT services" --source ted

# Search Greek government decisions
monopigi search "hospital" --source diavgeia

# Search public contracts registry
monopigi search "construction" --source kimdis

# Search energy permits
monopigi search "solar" --source rae
```

**Output formats:**

```bash
# Rich table (default in terminal)
monopigi search "procurement" --limit 20

# JSON (syntax highlighted)
monopigi search "hospital" --format json

# JSONL (one JSON object per line — pipe to jq)
monopigi search "tender" --format jsonl | jq '.title'

# CSV (for spreadsheets)
monopigi search "Athens" --format csv > results.csv

# Select specific fields
monopigi search "hospital" --fields source,title,published_at --format csv
```

**Counting and caching:**

```bash
# Just count results
monopigi search "procurement" --count

# Cache results for repeated queries (5 min TTL)
monopigi search "hospital" --cache
```

**Piping and composing:**

```bash
# Filter with grep
monopigi search "hospital" --format jsonl | grep diavgeia

# Count results per source
monopigi search "procurement" --format jsonl | jq -r '.source' | sort | uniq -c | sort -rn

# Extract just titles
monopigi search "tender" --format jsonl | jq -r '.title'

# Save to file
monopigi search "Athens hospital" --format jsonl > hospitals.jsonl

# Watch for new results in real-time
monopigi watch "hospital procurement" --interval 60
```

**Python SDK search examples:**

```python
from monopigi import MonopigiClient

with MonopigiClient("mp_live_...") as client:
    # Basic search
    results = client.search("hospital procurement")
    print(f"Found {results.total} results")
    for doc in results.results:
        print(f"  [{doc.source}] {doc.title}")

    # Search specific source
    results = client.search("solar energy", source="rae")

    # Search with limits
    results = client.search("tender", limit=50)

    # Check tier access
    if client.has_feature("full_text"):
        results = client.search("hospital", limit=100)
    else:
        print(f"Search requires Pro tier. Current: {client.tier}")
```

**Async Python:**

```python
from monopigi import AsyncMonopigiClient

async with AsyncMonopigiClient("mp_live_...") as client:
    results = await client.search("hospital", source="ted")
    async for doc in client.search_iter("procurement"):
        print(doc.title)
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

Requires `monopigi[fuzzy]`:

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

## Enterprise Features

Enterprise tier unlocks AI-powered analysis and cross-source intelligence:

### Ask (RAG) — AI-generated answers from government data

```bash
monopigi ask "What are the largest public contracts in Thessaloniki?"
monopigi ask "How much did the government spend on IT consulting?" --limit 10
```

```python
answer = client.ask("What energy permits were issued in Crete?")
print(answer["answer"])
print(answer["sources"])
```

### Entity Resolution — find all records for a company or person

```bash
monopigi entity 099369820 --type afm
monopigi entity "ΔΗΜΟΣ ΑΘΗΝΑΙΩΝ" --type name
```

```python
entity = client.entity("099369820", identifier_type="afm")
for match in entity["matches"]:
    print(f"  {match['source']}: {match['title']}")
```

### Similar Documents

```bash
monopigi similar "contract:26SYMV018689966"
```

### Content Download — original PDFs, XML, JSON

```bash
monopigi content "diavgeia:ABC123" --output decision.pdf
```

```python
pdf = client.content("diavgeia:ABC123")
Path("decision.pdf").write_bytes(pdf)
```

### Due Diligence Reports — automated entity reports with PDF export

```python
# Request a report
report = client.create_report("123456789", identifier_type="afm")
print(report["id"], report["status"])  # pending

# Check status
report = client.get_report(report["id"])
if report["status"] == "completed":
    print(report["report_json"]["sections"]["executive_summary"])

# Download PDF
pdf_bytes = client.get_report_pdf(report["id"])
with open("report.pdf", "wb") as f:
    f.write(pdf_bytes)

# List past reports
reports = client.list_reports()
```

```bash
monopigi report create 123456789 --type afm
monopigi report list
monopigi report get <id> --pdf --output report.pdf
```

### Procurement Alerts — automated notifications for new tenders

```python
# Create alert profile
profile = client.create_alert_profile(
    name="IT Contracts",
    filters={"keywords": ["πληροφορική", "software"], "min_value": 50000},
    channels=["email"],
)

# List profiles and deliveries
profiles = client.list_alert_profiles()
deliveries = client.list_alert_deliveries()
```

```bash
monopigi alerts create "IT Contracts" --keywords "software,πληροφορική" --min-value 50000
monopigi alerts list
monopigi alerts deliveries
```

### Compliance Monitoring — continuous entity surveillance

```python
# Monitor an entity
entity = client.add_monitored_entity("123456789", identifier_type="afm", label="Acme Corp")

# Check events
events = client.list_entity_events()

# Get health report
report = client.entity_health_report(entity["id"])
```

```bash
monopigi monitor add 123456789 --type afm --label "Acme Corp"
monopigi monitor list
monopigi monitor events
monopigi monitor report <entity-id>
```

### Models — list available LLM models for the Ask endpoint

```python
models = client.models()
print(models["default"])  # mistralai/mistral-large-2512
```

```bash
monopigi models
```

---

## Pricing

| Tier | Price | Daily Queries | Reports | Alert Profiles | Monitored Entities | MCP Server | Other Features |
|------|-------|---------------|---------|----------------|-------------------|------------|----------------|
| Free | EUR 0 | 5 | — | — | — | — | Sources, stats, metadata |
| Pro | EUR 299/mo | 100 | 20/mo | 3 | — | — | + Search, full text, export |
| Enterprise | EUR 999+/mo | 1,000 | Unlimited | Unlimited | EUR 2/entity/mo | Yes | + RAG, entity resolution, MCP, content download |

Get your API key at [monopigi.com](https://monopigi.com).

---

## Links

- **Documentation**: [monopigi.com/docs](https://monopigi.com/docs)
- **Quick Start**: [monopigi.com/docs/quickstart](https://monopigi.com/docs/quickstart)
- **API Reference**: [monopigi.com/docs/api-reference](https://monopigi.com/docs/api-reference)
- **SDK Guide**: [monopigi.com/docs/sdk](https://monopigi.com/docs/sdk)
- **CLI Reference**: [monopigi.com/docs/cli](https://monopigi.com/docs/cli)
- **Interactive API Docs (Swagger)**: [api.monopigi.com/docs](https://api.monopigi.com/docs)
- **Website**: [monopigi.com](https://monopigi.com)
- **Contact**: [info@monopigi.com](mailto:info@monopigi.com)

---

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.

The SDK is open source. The Monopigi API and data platform are proprietary.
