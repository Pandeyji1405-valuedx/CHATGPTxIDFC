import os
import sys
import argparse
import logging

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, init_and_migrate_db, engine
from backend.ingestion.rbi_scraper import rbi_scraper

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Scrape official RBI circulars, download authentic PDFs, and ingest into knowledge base.")
    parser.add_argument("--max", type=int, default=15, help="Maximum number of circulars to scrape and process")
    parser.add_argument("--no-db", action="store_true", help="Skip database ingestion (PDF generation only)")
    parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory for PDFs")
    args = parser.parse_args()

    if args.output_dir:
        rbi_scraper.output_dir = args.output_dir
        os.makedirs(rbi_scraper.output_dir, exist_ok=True)

    print("================================================================")
    print("      RBI OFFICIAL CIRCULAR INDEX SCRAPER & PDF PIPELINE       ")
    print("================================================================")
    print(f"Target Portal: https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx")
    print(f"Max Directives: {args.max}")
    print(f"Output PDF Directory: {rbi_scraper.output_dir}")
    print(f"Database Ingestion: {'DISABLED' if args.no_db else 'ENABLED (PostgreSQL)'}")
    print("----------------------------------------------------------------")

    db = None
    if not args.no_db:
        init_and_migrate_db(engine)
        db = SessionLocal()

    try:
        result = rbi_scraper.crawl_and_ingest(max_circulars=args.max, db_session=db)
        print("\n================================================================")
        print("                  SCRAPING & PDF REPORT COMPLETE                ")
        print("================================================================")
        print(f"Total Directives Scraped: {result['total_scraped']}")
        print(f"Total Ingested into Database: {result['ingested_to_db']}")
        print(f"Master Compendium PDF: {result['master_compendium_pdf']}")
        print(f"Individual PDFs Directory: {result['individual_pdfs_dir']}")
        print(f"Generated/Downloaded PDFs: {len(result['pdf_files'])} files")
        print("----------------------------------------------------------------")
        for i, pdf_file in enumerate(result['pdf_files'], 1):
            print(f"  [{i}] {pdf_file}")
        print("================================================================")
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    main()
