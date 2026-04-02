# Setup and Next Steps

## What You Already Have

Current workflow pieces:

- Scraper core: scrape_public.py
- Retry wrapper: run_with_retries.py
- Email listener: email_listener.py
- Email parser: parser.py
- Pipeline orchestrator: scraper_pipeline.py
- Output filter: filter.py
- AI API placeholders: ai_pipeline.py
- Local env loader: env_loader.py

## Setup Needed

1. Clone and enter project

```bash
git clone <YOUR_REPO_URL>
cd fb_scraper
```

2. Create and activate virtual environment

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

3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install
```

Fallback if needed:

```bash
python -m playwright install chromium
```

4. Configure secrets and endpoints

Copy example env file:

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

Edit .env and fill:

- EMAIL_HOST
- EMAIL_PORT
- EMAIL_USER
- EMAIL_PASS
- EMAIL_FOLDER
- LLM_API_URL
- LLM_API_KEY
- VLM_API_URL
- VLM_API_KEY

## How To Use What Exists

### Option A: Run one URL directly

```bash
python scraper_pipeline.py my_project "https://www.facebook.com/share/p/xxxxxxxx/"
```

Result file is written to workflow_output/ as JSON.

### Option B: Run from email trigger

Required email format:

- Subject: facebook - <project_name>
- Body: must contain at least one Facebook URL

Start listener:

```bash
python email_listener.py --poll-interval 30 --output-dir workflow_output
```

What happens per email:

1. Parse subject and extract project name
2. Parse body and extract Facebook URL
3. Run scraping with retries (up to 10 attempts)
4. Filter output to keep only:
- post text
- image URLs
- source URL
- poster name
5. Send text and image payloads to LLM/VLM API placeholders
6. Save workflow output JSON in workflow_output/

## Missing / Next Things To Implement

1. Decision logic layer (currently deferred)
- Combine LLM + VLM responses
- Define pass/fail or store/discard policy
- Add confidence thresholds and rule overrides

2. Persistent storage
- Save final approved records to DB (PostgreSQL or SQLite)
- Add schema for project_name, source_url, poster_name, text, images, ai_outputs, timestamp

3. Reliability hardening
- IMAP reconnect logic on network failures
- Dead-letter handling for repeatedly failing emails
- Idempotency keys to avoid reprocessing same URL/message

4. Better filtering quality
- Improve text extraction for multilingual posts
- Better poster name extraction across page/group layouts
- Better image de-duplication and noisy icon filtering

5. API integration hardening
- Request timeout and retry policies per API
- Structured response validation (JSON schema)
- Error categorization and fallback handling

6. Observability
- Structured logs (json logs)
- Metrics: success rate, retry count, processing latency
- Optional alerts for repeated failures

7. Security and ops
- Rotate API keys and email app password regularly
- Add CI checks for lint/syntax/tests
- Add pre-commit to block accidental secret commits

8. Testing
- Unit tests for parser.py and filter.py
- Integration tests for scraper_pipeline.py
- End-to-end test with sample .eml messages

## Suggested Implementation Order

1. Decision logic + storage
2. Reliability hardening
3. Filtering improvements
4. API hardening
5. Tests + CI
