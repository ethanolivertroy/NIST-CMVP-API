#!/usr/bin/env python3
"""
NIST CMVP Data Scraper

This script scrapes the NIST Cryptographic Module Validation Program (CMVP)
validated modules database and saves the data as JSON files for a static API.

Features:
- Scrapes validated, historical, and in-process modules
- Extracts algorithm information from certificate detail pages using crawl4ai
- Can import algorithm data from existing NIST-CMVP-ReportGen database
- Generates security policy PDF URLs

Environment Variables:
    NIST_SEARCH_PATH: Override the search path (default: /all)
                      Example: export NIST_SEARCH_PATH="/all"
    SKIP_ALGORITHMS: Set to "1" to skip algorithm extraction (faster scraping)
    CMVP_DB_PATH: Path to existing cmvp.db from NIST-CMVP-ReportGen project
                  If set, algorithm data will be imported from this database
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

# Crawl4AI imports (for algorithm extraction)
try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False


BASE_URL = "https://csrc.nist.gov/projects/cryptographic-module-validation-program/validated-modules/search"
CERTIFICATE_DETAIL_URL = "https://csrc.nist.gov/projects/cryptographic-module-validation-program/certificate"
SECURITY_POLICY_BASE_URL = "https://csrc.nist.gov/CSRC/media/projects/cryptographic-module-validation-program/documents/security-policies"
MODULES_IN_PROCESS_URL = "https://csrc.nist.gov/Projects/cryptographic-module-validation-program/modules-in-process/modules-in-process-list"
# Allow override via environment variable for flexibility
SEARCH_PATH = os.getenv("NIST_SEARCH_PATH", "/all")
HISTORICAL_SEARCH_PARAMS = "?SearchMode=Advanced&CertificateStatus=Historical&ValidationYear=0"
USER_AGENT = "NIST-CMVP-Data-Scraper/1.0 (GitHub Project)"
SKIP_ALGORITHMS = os.getenv("SKIP_ALGORITHMS", "0") == "1"

# Path to NIST-CMVP-ReportGen database (if available for importing algorithms)
CMVP_DB_PATH = os.getenv("CMVP_DB_PATH", "")

# Algorithm keywords to look for when parsing
# Order matters: more specific keywords should come before general ones (HMAC before SHA)
ALGORITHM_KEYWORDS = [
    'HMAC', 'AES', 'RSA', 'ECDSA', 'ECDH', 'DRBG',
    'KDF', 'DES', 'DSA', 'CVL', 'KAS', 'KTS', 'PBKDF',
    'SHS', 'SHA', 'TLS', 'SSH', 'EDDSA', 'ML-KEM', 'ML-DSA'
]


def fetch_page(url: str, timeout: int = 30) -> Optional[str]:
    """
    Fetch a web page and return its HTML content.

    Args:
        url: The URL to fetch
        timeout: Request timeout in seconds

    Returns:
        HTML content as string, or None if request fails
    """
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def get_security_policy_url(cert_number: int) -> str:
    """
    Get the URL for a certificate's Security Policy PDF.

    Args:
        cert_number: The certificate number

    Returns:
        URL to the security policy PDF
    """
    return f"{SECURITY_POLICY_BASE_URL}/140sp{cert_number}.pdf"


def get_certificate_detail_url(cert_number: int) -> str:
    """
    Get the URL for a certificate's detail page.

    Args:
        cert_number: The certificate number

    Returns:
        URL to the certificate detail page
    """
    return f"{CERTIFICATE_DETAIL_URL}/{cert_number}"


def parse_algorithms_from_markdown(markdown: str) -> Tuple[List[str], List[str]]:
    """
    Extract algorithm information from markdown text.

    Returns both detailed algorithm entries (full names with parameters)
    and simplified categories for display.

    Args:
        markdown: Markdown text from certificate detail page

    Returns:
        Tuple of (detailed_algorithms, categories)
        - detailed_algorithms: Full algorithm names like "HMAC-SHA2-256", "ECDSA SigGen (FIPS186-4)"
        - categories: Simplified names like "HMAC", "ECDSA", "AES"
    """
    detailed: List[str] = []
    categories: Set[str] = set()

    # Find lines that look like algorithm entries
    # On NIST pages, algorithms appear as plain text lines before [Axxxx] validation links
    for line in markdown.split('\n'):
        line = line.strip()

        # Skip empty lines, markdown links, headers, and table separators
        if not line or line.startswith('[') or line.startswith('#') or line.startswith('|') or line == '---':
            continue

        # Skip lines that are just numbers or very short
        if len(line) < 3:
            continue

        # Check if this line contains an algorithm keyword
        line_upper = line.upper()
        for kw in ALGORITHM_KEYWORDS:
            if kw in line_upper:
                # This looks like an algorithm entry - add the full line as detailed
                if line not in detailed:
                    detailed.append(line)
                # Add the category
                categories.add(kw)
                break

    return detailed, sorted(categories)


def parse_certificate_details_from_markdown(markdown: str) -> Dict:
    """
    Extract certificate details from markdown text.

    Args:
        markdown: Markdown text from certificate detail page

    Returns:
        Dictionary with certificate details
    """
    details = {}
    lines = markdown.split('\n')

    # Field patterns to look for (label: field_name)
    field_patterns = {
        'module name': 'module_name',
        'standard': 'standard',
        'status': 'status',
        'sunset date': 'sunset_date',
        'overall level': 'overall_level',
        'caveat': 'caveat',
        'module type': 'module_type',
        'embodiment': 'embodiment',
        'description': 'description',
        'validation date': 'validation_date',
        'laboratory': 'lab',
        'vendor': 'vendor_name',
    }

    for i, line in enumerate(lines):
        line_lower = line.lower().strip()

        for pattern, field in field_patterns.items():
            # Match pattern at start of line or as table cell (not just anywhere in line)
            # This prevents matching "nist-information-quality-standards" when looking for "standard"
            is_field_label = (
                line_lower.startswith(pattern) or
                line_lower.startswith(f'| {pattern}')
            )

            if is_field_label:
                # Try to extract value from same line (after colon or pipe)
                if '|' in line:
                    parts = [p.strip() for p in line.split('|') if p.strip()]
                    # In table format "| Field | Value |", parts would be ['Field', 'Value']
                    if len(parts) >= 2:
                        value = parts[1]  # Second non-empty part is the value
                        if value and value != '---':
                            details[field] = value
                elif ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        value = parts[1].strip()
                        if value:
                            details[field] = value
                # Also check next line for value
                elif i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not any(p in next_line.lower() for p in field_patterns.keys()):
                        details[field] = next_line

    # Extract overall level as integer
    if 'overall_level' in details:
        match = re.search(r'\d+', str(details['overall_level']))
        if match:
            details['overall_level'] = int(match.group())

    # Extract algorithms (both detailed and categories)
    detailed_algorithms, categories = parse_algorithms_from_markdown(markdown)
    details['algorithms'] = categories  # Simplified categories for display
    details['algorithms_detailed'] = detailed_algorithms  # Full algorithm entries

    return details


async def crawl_certificate_page(crawler, cert_number: int) -> str:
    """
    Crawl a certificate page and return markdown.

    Args:
        crawler: AsyncWebCrawler instance
        cert_number: Certificate number to crawl

    Returns:
        Markdown content of the page, or empty string on failure
    """
    url = get_certificate_detail_url(cert_number)
    try:
        result = await crawler.arun(
            url=url,
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                delay_before_return_html=2.0  # Wait for JS to load dynamic content
            )
        )
        return result.markdown if result.success else ""
    except Exception:
        return ""


def import_algorithms_from_database(db_path: str) -> Dict[int, List[str]]:
    """
    Import algorithm data from an existing CMVP database.

    Args:
        db_path: Path to the cmvp.db SQLite database

    Returns:
        Dictionary mapping certificate numbers to lists of algorithms
    """
    algorithms_map = {}

    if not os.path.exists(db_path):
        print(f"Warning: Database not found at {db_path}", file=sys.stderr)
        return algorithms_map

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if the table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='certificate_algorithms'")
        if not cursor.fetchone():
            print("Warning: certificate_algorithms table not found in database", file=sys.stderr)
            conn.close()
            return algorithms_map

        # Fetch all algorithm data
        cursor.execute("SELECT cert_number, algorithm_name FROM certificate_algorithms ORDER BY cert_number")
        rows = cursor.fetchall()

        for cert_num, algo_name in rows:
            if cert_num not in algorithms_map:
                algorithms_map[cert_num] = []
            algorithms_map[cert_num].append(algo_name)

        conn.close()
        print(f"Imported algorithms for {len(algorithms_map)} certificates from database")

    except Exception as e:
        print(f"Error importing from database: {e}", file=sys.stderr)

    return algorithms_map


async def extract_certificate_details(cert_numbers: List[int]) -> Dict[int, Dict]:
    """
    Extract full details for a list of certificates using crawl4ai.

    Args:
        cert_numbers: List of certificate numbers to process

    Returns:
        Dictionary mapping certificate numbers to detail dictionaries
    """
    if not CRAWL4AI_AVAILABLE:
        print("Warning: crawl4ai not available. Skipping detail extraction.", file=sys.stderr)
        print("Install with: pip install crawl4ai && crawl4ai-setup", file=sys.stderr)
        return {}

    details_map = {}
    total = len(cert_numbers)
    success = 0
    failed = 0

    print(f"\nExtracting details from {total} certificate pages...")

    async with AsyncWebCrawler() as crawler:
        for i, cert_num in enumerate(cert_numbers, 1):
            try:
                markdown = await crawl_certificate_page(crawler, cert_num)
                if markdown:
                    details = parse_certificate_details_from_markdown(markdown)
                    if details:
                        details_map[cert_num] = details
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

            if i % 50 == 0 or i == total:
                print(f"  Progress: {i}/{total} ({success} success, {failed} failed)")

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.3)

    print(f"Detail extraction complete: {len(details_map)} certificates processed")
    return details_map


def parse_modules_table(html: str) -> List[Dict]:
    """
    Parse the validated modules table from NIST CMVP HTML page.
    
    Args:
        html: HTML content of the page
        
    Returns:
        List of dictionaries containing module information
    """
    soup = BeautifulSoup(html, "lxml")
    modules = []
    
    # Find the table containing validated modules
    # The exact structure may vary, so we look for common patterns
    table = soup.find("table")
    
    if not table:
        print("Warning: No table found on page", file=sys.stderr)
        return modules
    
    # Extract headers
    headers = []
    thead = table.find("thead")
    if thead:
        header_row = thead.find("tr")
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
    
    # If no thead, try to get headers from first row
    if not headers:
        tbody = table.find("tbody")
        if tbody:
            first_row = tbody.find("tr")
        else:
            first_row = table.find("tr")
        
        if first_row:
            # Check if first row looks like headers
            cells = first_row.find_all(["th", "td"])
            if cells and cells[0].name == "th":
                headers = [cell.get_text(strip=True) for cell in cells]
    
    # Extract data rows
    tbody = table.find("tbody")
    rows = tbody.find_all("tr") if tbody else table.find_all("tr")
    
    # Skip header row if it's included in rows
    start_idx = 1 if (not thead and headers and rows and 
                      all(cell.name == "th" for cell in rows[0].find_all(["th", "td"]))) else 0
    
    for row in rows[start_idx:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        
        # Create module dictionary
        module = {}
        
        for idx, cell in enumerate(cells):
            # Use header as key if available, otherwise use index
            key = headers[idx] if idx < len(headers) and headers[idx] else f"column_{idx}"
            
            # Extract text content
            text = cell.get_text(strip=True)
            
            # Extract links if present
            link = cell.find("a")
            if link and link.get("href"):
                href = link.get("href")
                # Make absolute URL if relative
                if href.startswith("/"):
                    href = f"https://csrc.nist.gov{href}"
                module[f"{key}_url"] = href
            
            module[key] = text
        
        if module:  # Only add non-empty modules
            modules.append(module)
    
    return modules


def scrape_all_modules() -> List[Dict]:
    """
    Scrape all validated modules from NIST CMVP.
    
    Returns:
        List of all modules found
    """
    all_modules = []
    
    # Construct the search URL using BASE_URL and SEARCH_PATH
    url = f"{BASE_URL}{SEARCH_PATH}"
    print(f"Fetching: {url}")
    print(f"Note: If this URL is incorrect, set NIST_SEARCH_PATH environment variable")
    
    html = fetch_page(url)
    if not html:
        print("Failed to fetch main page", file=sys.stderr)
        print(f"Verify the URL is correct: {url}", file=sys.stderr)
        return all_modules
    
    modules = parse_modules_table(html)
    all_modules.extend(modules)
    
    print(f"Found {len(modules)} modules on page")
    
    # Note: If the site uses pagination, we would need to detect and follow
    # "next page" links here. For now, we're assuming all results are on one page
    # or implementing basic pagination detection.
    
    return all_modules


def scrape_historical_modules() -> List[Dict]:
    """
    Scrape historical modules from NIST CMVP.
    
    Returns:
        List of all historical modules found
    """
    all_modules = []
    
    # Construct the URL for historical modules
    url = f"{BASE_URL}{HISTORICAL_SEARCH_PARAMS}"
    print(f"Fetching historical modules: {url}")
    
    html = fetch_page(url)
    if not html:
        print("Failed to fetch historical modules page", file=sys.stderr)
        print(f"Verify the URL is correct: {url}", file=sys.stderr)
        return all_modules
    
    modules = parse_modules_table(html)
    all_modules.extend(modules)
    
    print(f"Found {len(modules)} historical modules on page")
    
    return all_modules


def scrape_modules_in_process() -> List[Dict]:
    """
    Scrape modules in process from NIST CMVP.
    
    Returns:
        List of all modules in process found
    """
    print(f"Fetching: {MODULES_IN_PROCESS_URL}")
    
    html = fetch_page(MODULES_IN_PROCESS_URL)
    if not html:
        print("Failed to fetch modules in process page", file=sys.stderr)
        print(f"Verify the URL is correct: {MODULES_IN_PROCESS_URL}", file=sys.stderr)
        return []
    
    modules = parse_modules_table(html)
    
    print(f"Found {len(modules)} modules in process on page")
    
    return modules


def save_json(data: Dict, filepath: str) -> None:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save
        filepath: Path to output file
    """
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved: {filepath}")


def enrich_modules_with_urls(modules: List[Dict]) -> List[Dict]:
    """
    Add security policy URLs and certificate detail URLs to modules.

    Args:
        modules: List of module dictionaries

    Returns:
        List of modules with added URL fields
    """
    for module in modules:
        cert_num_str = module.get("Certificate Number", "")
        if cert_num_str:
            try:
                cert_num = int(cert_num_str)
                module["security_policy_url"] = get_security_policy_url(cert_num)
                module["certificate_detail_url"] = get_certificate_detail_url(cert_num)
            except ValueError:
                pass
    return modules


def enrich_modules_with_algorithms(modules: List[Dict], algorithms_map: Dict[int, List[str]]) -> List[Dict]:
    """
    Add algorithms to modules from the algorithms map.

    Args:
        modules: List of module dictionaries
        algorithms_map: Dictionary mapping certificate numbers to algorithm lists

    Returns:
        List of modules with added algorithms field
    """
    for module in modules:
        cert_num_str = module.get("Certificate Number", "")
        if cert_num_str:
            try:
                cert_num = int(cert_num_str)
                if cert_num in algorithms_map:
                    module["algorithms"] = algorithms_map[cert_num]
            except ValueError:
                pass
    return modules


def enrich_modules_with_details(modules: List[Dict], details_map: Dict[int, Dict]) -> List[Dict]:
    """
    Add full certificate details to modules from the details map.

    Args:
        modules: List of module dictionaries
        details_map: Dictionary mapping certificate numbers to detail dictionaries

    Returns:
        List of modules with added detail fields
    """
    for module in modules:
        cert_num_str = module.get("Certificate Number", "")
        if cert_num_str:
            try:
                cert_num = int(cert_num_str)
                if cert_num in details_map:
                    details = details_map[cert_num]
                    # Add all detail fields to module
                    for key, value in details.items():
                        if value:  # Only add non-empty values
                            module[key] = value
            except ValueError:
                pass
    return modules


def create_algorithms_summary(algorithms_map: Dict[int, List[str]]) -> Dict:
    """
    Create a summary of all algorithms across all certificates.

    Args:
        algorithms_map: Dictionary mapping certificate numbers to algorithm lists

    Returns:
        Dictionary with algorithm statistics
    """
    algo_counts = {}
    for cert_num, algos in algorithms_map.items():
        for algo in algos:
            if algo not in algo_counts:
                algo_counts[algo] = {"count": 0, "certificates": []}
            algo_counts[algo]["count"] += 1
            algo_counts[algo]["certificates"].append(cert_num)

    # Sort by count descending
    sorted_algos = dict(sorted(algo_counts.items(), key=lambda x: x[1]["count"], reverse=True))

    return {
        "total_unique_algorithms": len(sorted_algos),
        "total_certificate_algorithm_pairs": sum(len(algos) for algos in algorithms_map.values()),
        "algorithms": sorted_algos
    }


def main():
    """Main entry point for the scraper."""
    print("=" * 60)
    print("NIST CMVP Data Scraper")
    print("=" * 60)
    print()

    # Check algorithm extraction options
    algorithm_source = "none"
    if CMVP_DB_PATH:
        print(f"Note: Will import algorithms from database: {CMVP_DB_PATH}")
        algorithm_source = "database"
    elif not SKIP_ALGORITHMS:
        if CRAWL4AI_AVAILABLE:
            print("Note: Will extract algorithms using crawl4ai (this may take a while)")
            algorithm_source = "crawl4ai"
        else:
            print("Note: crawl4ai not installed. Algorithm extraction will be skipped.")
            print("Install with: pip install crawl4ai && crawl4ai-setup")
    else:
        print("Note: SKIP_ALGORITHMS=1 set. Algorithm extraction will be skipped.")
    print()

    # Scrape all validated modules
    print("Scraping validated modules...")
    modules = scrape_all_modules()

    if not modules:
        print("No validated modules found!", file=sys.stderr)
        sys.exit(1)

    print(f"\nTotal validated modules scraped: {len(modules)}")

    # Scrape historical modules
    print("\nScraping historical modules...")
    historical_modules = scrape_historical_modules()

    print(f"Total historical modules scraped: {len(historical_modules)}")

    # Scrape modules in process
    print("\nScraping modules in process...")
    modules_in_process = scrape_modules_in_process()

    print(f"Total modules in process scraped: {len(modules_in_process)}")

    # Add security policy and detail URLs to all modules
    print("\nEnriching modules with URLs...")
    modules = enrich_modules_with_urls(modules)
    historical_modules = enrich_modules_with_urls(historical_modules)

    # Get algorithms (from database or by crawling)
    algorithms_map = {}

    if algorithm_source == "database":
        # Import from existing database (fast)
        print("\nImporting algorithms from database...")
        algorithms_map = import_algorithms_from_database(CMVP_DB_PATH)
        modules = enrich_modules_with_algorithms(modules, algorithms_map)
        # Also enrich historical modules with algorithms
        historical_modules = enrich_modules_with_algorithms(historical_modules, algorithms_map)

    elif algorithm_source == "crawl4ai":
        # Extract full certificate details via crawl4ai (slow but comprehensive)
        cert_numbers = []
        for module in modules:
            cert_num_str = module.get("Certificate Number", "")
            if cert_num_str:
                try:
                    cert_numbers.append(int(cert_num_str))
                except ValueError:
                    pass

        if cert_numbers:
            # Extract full details including algorithms, caveats, etc.
            details_map = asyncio.run(extract_certificate_details(cert_numbers))
            modules = enrich_modules_with_details(modules, details_map)

            # Build algorithms_map from details for the summary
            for cert_num, details in details_map.items():
                if 'algorithms' in details and details['algorithms']:
                    algorithms_map[cert_num] = details['algorithms']

    # Prepare output directory
    output_dir = "api"

    # Create metadata
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_modules": len(modules),
        "total_historical_modules": len(historical_modules),
        "total_modules_in_process": len(modules_in_process),
        "total_certificates_with_algorithms": len(algorithms_map),
        "source": BASE_URL,
        "modules_in_process_source": MODULES_IN_PROCESS_URL,
        "algorithm_source": algorithm_source,
        "version": "2.0"
    }

    # Save main modules data (validated)
    main_data = {
        "metadata": metadata,
        "modules": modules
    }
    save_json(main_data, f"{output_dir}/modules.json")

    # Save historical modules data
    historical_data = {
        "metadata": metadata,
        "modules": historical_modules
    }
    save_json(historical_data, f"{output_dir}/historical-modules.json")

    # Save modules in process data
    modules_in_process_data = {
        "metadata": metadata,
        "modules_in_process": modules_in_process
    }
    save_json(modules_in_process_data, f"{output_dir}/modules-in-process.json")

    # Save algorithms summary (if available)
    if algorithms_map:
        algorithms_summary = create_algorithms_summary(algorithms_map)
        algorithms_summary["metadata"] = {
            "generated_at": metadata["generated_at"],
            "total_certificates_processed": len(algorithms_map),
            "source": algorithm_source
        }
        save_json(algorithms_summary, f"{output_dir}/algorithms.json")

    # Save metadata separately for quick access
    save_json(metadata, f"{output_dir}/metadata.json")

    # Create index page
    endpoints = {
        "modules": "/api/modules.json",
        "historical_modules": "/api/historical-modules.json",
        "modules_in_process": "/api/modules-in-process.json",
        "metadata": "/api/metadata.json"
    }
    if algorithms_map:
        endpoints["algorithms"] = "/api/algorithms.json"

    index_data = {
        "name": "NIST CMVP Data API",
        "description": "Static API for NIST Cryptographic Module Validation Program validated modules with algorithm information and security policy links",
        "endpoints": endpoints,
        "last_updated": metadata["generated_at"],
        "total_modules": len(modules),
        "total_historical_modules": len(historical_modules),
        "total_modules_in_process": len(modules_in_process),
        "total_certificates_with_algorithms": len(algorithms_map),
        "features": {
            "security_policy_urls": True,
            "certificate_detail_urls": True,
            "algorithm_extraction": algorithm_source != "none"
        }
    }
    save_json(index_data, f"{output_dir}/index.json")

    print("\n" + "=" * 60)
    print("Scraping completed successfully!")
    print("=" * 60)
    print(f"\nSummary:")
    print(f"  - Validated modules: {len(modules)}")
    print(f"  - Historical modules: {len(historical_modules)}")
    print(f"  - Modules in process: {len(modules_in_process)}")
    if algorithms_map:
        print(f"  - Certificates with algorithms: {len(algorithms_map)}")
    print(f"  - Algorithm source: {algorithm_source}")
    print(f"\nOutput files saved to: {output_dir}/")


if __name__ == "__main__":
    main()
