import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def scrape_facebook_post(url):
    print(f"🚀 Initializing crawler for: {url}")
    
    # We use a BrowserConfig to look more like a human
    async with AsyncWebCrawler(verbose=True) as crawler:
        # Increase wait_for time because Facebook is heavy
        result = await crawler.arun(
            url=url,
            wait_for="div[role='main']", # Wait for the main content area
            magic=True,                  # Automatically handle some anti-bot measures
            remove_overlay_elements=True, # Try to kill login popups
            bypass_cache=True
        )

        if result.success:
            print("\n✅ Extraction Successful!")
            print("-" * 30)
            # Display the markdown - best for LLM processing
            print("EXTRACTED CONTENT (MARKDOWN):")
            print(result.markdown[:1000] + "...") # Printing first 1000 chars
            
            # If you want to save it to a file
            with open("fb_post_output.md", "w", encoding="utf-8") as f:
                f.write(result.markdown)
            print("-" * 30)
            print("📁 Full content saved to fb_post_output.md")
        else:
            print(f"❌ Failed to scrape: {result.error_message}")

if __name__ == "__main__":
    # Replace with your target URL
    fb_url = "https://www.facebook.com/photo?fbid=122314900382010987&set=gm.24539556319075473&idorvanity=354789207978855"
    asyncio.run(scrape_facebook_post(fb_url))