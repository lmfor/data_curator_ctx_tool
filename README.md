# WeShare Content Scraper & Context Relevance System

A tool for scraping and validating technical documentation from Advantest's WeShare platform. Automatically identifies V93K/SmarTest8-related content and builds a curated database of current technical resources.

## Workflow Overview

```mermaid
flowchart TD
    A[Start: WeShare Wiki Scraping] --> B[Scrape WeShare Pages]
    B --> C[Extract Content & Metadata]
    C --> D[Clean & Preprocess Content]
    D --> E[Send to CTX Agent: Relevance Check]
    E --> F{Is content related to V93K or SmarTest8?}
    
    F -->|NO| G[Log as Not Relevant]
    G --> H[Move to Next Page]
    
    F -->|YES| I[Send to CTX Agent: Currency Check]
    I --> J{Is information current and up-to-date?}
    
    J -->|NO| K[Log as Outdated]
    K --> H
    
    J -->|YES| L[Store WeShare URL in Database]
    L --> M[Log Validation Success]
    M --> H
    
    H --> N{More pages to process?}
    N -->|YES| B
    N -->|NO| O[End: Workflow Complete]
    
    style A fill:#4CAF50,color:#fff
    style O fill:#2196F3,color:#fff
    style F fill:#FF9800,color:#fff
    style J fill:#FF9800,color:#fff
    style L fill:#4CAF50,color:#fff
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) - Astral package manager
- Chrome/Chromium browser with ChromeDriver
- Advantest WeShare credentials

Install uv:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Project Structure

```
weshare-ctx-sort/
├── src/
│   ├── workflow/
│   │   ├── sso_weshare_scraper.py    # Microsoft SSO scraper
│   │   └── html_to_markdown.py       # HTML to Markdown converter
│   └── db/
│       ├── database.py               # Database operations
│       └── models.py                 # SQLAlchemy models
├── tests/
│   ├── test_scraper.py              # Scraper testing
│   └── test_database.py             # Database testing
├── .env                             # Environment variables
└── pyproject.toml                   # uv project configuration
```

## Setup

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Test the system
uv run python tests/test_scraper.py
```