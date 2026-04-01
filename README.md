# Facebook Public Post Scraper

Small Python script that uses `crawl4ai` to scrape publicly visible Facebook post/page content and save it as markdown.

## Project Files

- `scrape_public.py`: main scraper script
- `requirements.txt`: Python dependencies
- `.gitignore`: files/folders excluded from git

## Prerequisites

- Python 3.10+
- Git
- Internet access

## 1) Clone the Repository

```bash
git clone <YOUR_NEW_REPO_URL>
cd fb_scraper
```

## 2) Create a Virtual Environment

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Windows (cmd)

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### macOS/Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3) Install Dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4) Install Browser Binaries (required by Crawl4AI/Playwright)

```bash
python -m playwright install
```

If your environment has issues with all browsers, try only Chromium:

```bash
python -m playwright install chromium
```

## 5) Set the Target URL

Open `scrape_public.py` and update `fb_url` in the `if __name__ == "__main__":` block.

## 6) Run the Scraper

```bash
python scrape_public.py
```

If successful, markdown output is saved to `fb_post_output.md`.

## Notes

- Facebook may change page structure or add anti-bot protections that affect results.
- Use only on public content and follow platform terms and local laws.
- For best stability, keep `crawl4ai` and browser binaries up to date.

## Suggested First Commit

```bash
git add .
git commit -m "Initial scraper setup"
git branch -M main
git remote add origin <YOUR_NEW_REPO_URL>
git push -u origin main
```
