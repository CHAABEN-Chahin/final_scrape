# Facebook + LinkedIn Email-Triggered Scraper Pipeline

This project scrapes publicly visible Facebook or LinkedIn content from a URL received by email, retries automatically when scraping is unstable, filters the output, runs image analysis with Ollama VLM, and then sends text + VLM output to Groq LLM for a final answer.

## Architecture

- `scrape_public.py`: existing low-level scraper (unchanged)
- `run_with_retries.py`: existing retry wrapper (unchanged)
- `scrape_linkedin_public.py`: LinkedIn low-level scraper
- `run_linkedin_with_retries.py`: LinkedIn retry wrapper (max 10)
- `email_listener.py`: monitors inbox and triggers workflow
- `parser.py`: validates subject and extracts project name + URL
- `scraper_pipeline.py`: orchestrates retry scraper + filter + AI prep
- `filter.py`: keeps only post text, image URLs, source URL, poster name
- `filter_linkedin.py`: keeps LinkedIn caption + images
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
- `EMAIL_SUBJECT_PREFIXES`
- `EMAIL_MAX_AGE_DAYS`
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
- It returns a structured decision with `validated` and `next_phase_ready`.
- Validation is based on 3 conditions: age eligibility, paid work, and Sfax location.
- The target user age is configured in `ai_pipeline.py` via `TARGET_USER_AGE`.
- When `next_phase_ready=true`, the pipeline emits `next_phase_payload` containing `category/platform`, `project_name`, `source_url`, `conclusion_two_sentences`, `price`, and `deadline` for handoff to the next phase.

## Email Format (Trigger Contract)

- Subject must be one of:
	- `facebook - <project_name>`
	- `linkedin - <project_name>`
- Body must include at least one URL for the same platform.

Example:

```text
Subject: facebook - road_safety_project

Please process this post:
https://www.facebook.com/share/p/xxxxxxxx/
```

```text
Subject: linkedin - road_safety_project

Please process this post:
https://www.linkedin.com/posts/xxxxxxxx/
```

## Usage

### A) Run Pipeline Directly (No Email)

Facebook:

```bash
python scraper_pipeline.py facebook my_project "https://www.facebook.com/share/p/xxxxxxxx/"
```

LinkedIn:

```bash
python scraper_pipeline.py linkedin my_project "https://www.linkedin.com/posts/xxxxxxxx/"
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

Reliability behavior in listener mode:

- New emails are first added to a durable waiting list in `workflow_queue/pending/`.
- Jobs are processed sequentially to avoid collisions when many emails arrive at the same time.
- Successful jobs are moved to `workflow_queue/processed/`.
- Failed jobs (including scraper failure after max retries) are moved to `workflow_queue/failed/` for manual review.
- This prevents losing posts when automatic processing fails.
- Listener only ingests emails within the configured max age window and matching allowed subject prefixes.

## What Gets Kept After Filtering

- Post text content
- Post image URL(s)
- Source post URL (Facebook or LinkedIn)
- Poster name

All other metadata is ignored.

## Notes

- Facebook and LinkedIn output can vary between attempts; retries are expected behavior.
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
