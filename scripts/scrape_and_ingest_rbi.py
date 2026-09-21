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
    parser.add_argument("--max", type=int, default=15, help="Maximum number of main circulars to scrape")
    parser.add_argument("--no-db", action="store_true", help="Skip database ingestion (PDF generation only)")
    parser.add_argument("--no-sublinks", action="store_true", help="Do not crawl internal hyperlinked sub-directives and amendment directions")
    parser.add_argument("--no-amendments", action="store_true", help="Skip Master Amendment Directions index crawling")
    parser.add_argument("--hyper-pages", type=int, default=0, help="Number of sequential hyper-page circular ID records to crawl (e.g. 15)")
    parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory for PDFs")
    args = parser.parse_args()

    if args.output_dir:
        rbi_scraper.output_dir = args.output_dir
        os.makedirs(rbi_scraper.output_dir, exist_ok=True)

    print("================================================================")
    print("      RBI OFFICIAL CIRCULAR INDEX SCRAPER & PDF PIPELINE       ")
    print("================================================================")
    print(f"Target Portal: https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx")
    print(f"Max Main Circulars: {args.max}")
    print(f"Sub-Link & Hyperlink Extraction: {'DISABLED' if args.no_sublinks else 'ENABLED'}")
    print(f"Amendment Directions Crawling: {'DISABLED' if args.no_amendments else 'ENABLED'}")
    print(f"Hyper-Pages Sequence Traversal: {args.hyper_pages if args.hyper_pages > 0 else 'DEFAULT INDEX'}")
    print(f"Output PDF Directory: {rbi_scraper.output_dir}")
    print(f"Database Ingestion: {'DISABLED' if args.no_db else 'ENABLED (PostgreSQL)'}")
    print("----------------------------------------------------------------")

    db = None
    if not args.no_db:
        init_and_migrate_db(engine)
        db = SessionLocal()

    try:
        if args.hyper_pages > 0:
            result_list = rbi_scraper.crawl_hyper_pages(
                start_id=13705,
                count=args.hyper_pages,
                db_session=db,
                include_sublinks=not args.no_sublinks
            )
            print("\n================================================================")
            print("             HYPER-PAGE TRAVERSAL COMPLETE                      ")
            print("================================================================")
            print(f"Total Directives Processed: {len(result_list)}")
            for i, item in enumerate(result_list, 1):
                print(f"  [{i}] {item.get('circular_number', '')} — {item.get('subject', '')[:70]}")
        else:
            result = rbi_scraper.crawl_and_ingest(
                max_circulars=args.max,
                db_session=db,
                include_sublinks=not args.no_sublinks,
                include_amendments=not args.no_amendments
            )
            print("\n================================================================")
            print("                  SCRAPING & PDF REPORT COMPLETE                ")
            print("================================================================")
            print(f"Total Directives Scraped: {result['total_scraped']}")
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
