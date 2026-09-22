import sys
import os
import argparse
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.ingestion.rbi_notification_scraper import rbi_notification_scraper
from backend.database import SessionLocal
from backend.models import KnowledgeDocument, KnowledgeChunk

def main():
    parser = argparse.ArgumentParser(description="RBI Notification Web Scraper & Knowledge Base Ingestion")
    parser.add_argument("--url", default="https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=13412&Mode=0", help="Target RBI Notification URL")
    parser.add_argument("--selenium", action="store_true", default=True, help="Use Selenium headless browser for dynamic JavaScript rendering")
    parser.add_argument("--no-selenium", dest="selenium", action="store_false", help="Disable Selenium and use standard HTTP GET")
    parser.add_argument("--no-sublinks", action="store_true", help="Do not crawl internal referenced sub-links")
    parser.add_argument("--no-nav", action="store_true", help="Do not crawl year/month tree navigations")
    parser.add_argument("--max-nav", type=int, default=10, help="Max items per navigation period")
    args = parser.parse_args()

    print(f"Starting RBI web scraping (Selenium JS Engine = {args.selenium}) for: {args.url}")
    result = rbi_notification_scraper.execute_complete_scrape(
        target_url=args.url,
        use_selenium=args.selenium,
        explore_sublinks=not args.no_sublinks,
        explore_navigations=not args.no_nav,
        nav_years_months=[("2026", "4"), ("2026", "0")],
        max_nav_items=args.max_nav
    )

    print("\n" + "="*80)
    print("RBI WEB SCRAPING & KNOWLEDGE BASE INGESTION SUMMARY")
    print("="*80)
    print(f"Target URL:         {result['target_url']}")
    print(f"Selenium JS Engine: {result['used_selenium']}")
    print(f"Total Scraped Docs: {result['total_documents_scraped']}")
    print(f"Total URLs Visited: {result['total_urls_visited']}")
    print("\nIngested Documents:")
    for idx, doc in enumerate(result['documents'], 1):
        via = doc.get('scraped_via', 'selenium' if result['used_selenium'] else 'http')
        print(f"  {idx}. [{doc['publication_date']}] ({via}) {doc['notification_number']} - {doc['title'][:70]}")
        print(f"     Source URL: {doc['source_url']}")
        print(f"     PDF Path:   {doc['pdf_path']}")

    db = SessionLocal()
    try:
        total_kb_docs = db.query(KnowledgeDocument).count()
        total_kb_chunks = db.query(KnowledgeChunk).count()
        print("\nDatabase Knowledge Base Status:")
        print(f"  Total Knowledge Documents: {total_kb_docs}")
        print(f"  Total Knowledge Chunks:    {total_kb_chunks}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
