# Facebook Email-Triggered Scraper Pipeline

This project scrapes publicly visible Facebook content from a URL received by email, retries automatically when scraping is unstable, filters the output, runs image analysis with Ollama VLM, and then sends text + VLM output to Groq LLM for a final answer.

## Architecture

- `scrape_public.py`: existing low-level scraper (unchanged)
- `run_with_retries.py`: existing retry wrapper (unchanged)
- `email_listener.py`: monitors inbox and triggers workflow
- `parser.py`: validates subject and extracts project name + URL
- `scraper_pipeline.py`: orchestrates retry scraper + filter + AI prep
- `filter.py`: keeps only post text, image URLs, source URL, poster name
- `ai_pipeline.py`: Ollama VLM + Groq LLM integration (chained)

## Prerequisites

- Python 3.10+
- Git
- Internet access
- An IMAP-enabled mailbox (for listener mode)

## Setup

### 1) Clone

```bash
git clone <YOUR_REPO_URL>
cd fb_scraper
```

### 2) Create Virtual Environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows cmd:

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3) Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
```

If needed:

```bash
python -m playwright install chromium
```

### 4) Configure Environment Variables

Copy the example file and fill your real values:

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Windows cmd:

```bat
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

Then edit `.env` and set:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USER`
- `EMAIL_PASS`
- `EMAIL_FOLDER`
- `GROQ_API_URL`
- `GROQ_API_KEY`
- `GROQ_LLM_MODEL`
- `GROQ_LLM_SYSTEM_PROMPT`
- `OLLAMA_VLM_MODEL`
- `OLLAMA_VLM_PROMPT`

Notes for Ollama VLM:

- Authenticate once in terminal with `ollama login`.
- Pull your model (example): `ollama pull qwen3.5:397b-cloud`.
- No VLM API key is required in this project for Ollama usage.

Notes for Groq LLM:

- Set `GROQ_API_KEY` in `.env`.
- The LLM stage runs after VLM and combines post text + VLM output.

## Email Format (Trigger Contract)

- Subject must be exactly: `facebook - <project_name>`
- Body must include at least one Facebook URL

Example:

```text
Subject: facebook - road_safety_project

Please process this post:
https://www.facebook.com/share/p/xxxxxxxx/
```

## Usage

### A) Run Pipeline Directly (No Email)

```bash
python scraper_pipeline.py my_project "https://www.facebook.com/share/p/xxxxxxxx/"
```

Output JSON is saved in `workflow_output/`.

### C) Test VLM + LLM Together (manual local test)

```bash
python test_llm_vlm_together.py --image "C:/path/to/image.jpg" --text "Paste sample post text here"
```

### B) Run Email Listener

Then start listener:

```bash
python email_listener.py --poll-interval 30 --output-dir workflow_output
```

## What Gets Kept After Filtering

- Post text content
- Post image URL(s)
- Source Facebook URL
- Poster name

All other metadata is ignored.

## Notes

- Facebook output can vary between attempts; retries are expected behavior.
- Retry logic treats empty output and login-wall-only output as failure.
- Mixed output (login snippets + useful content) is treated as success.
- Use only public content and follow platform terms and local law.

## GitHub Push Checklist

```bash
git add .
git commit -m "Add email-driven scraper pipeline"
git branch -M main
git remote add origin <YOUR_REPO_URL>
git push -u origin main
```

If remote already exists:

```bash
git push
```
