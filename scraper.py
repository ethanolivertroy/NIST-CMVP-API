#!/usr/bin/env python3
"""
NIST CMVP Data Scraper

This script scrapes the NIST Cryptographic Module Validation Program (CMVP)
validated modules database and saves the data as JSON files for a static API.

Environment Variables:
    NIST_SEARCH_PATH: Override the search path (default: /all)
                      Example: export NIST_SEARCH_PATH="/all"
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://csrc.nist.gov/projects/cryptographic-module-validation-program/validated-modules/search"
MODULES_IN_PROCESS_URL = "https://csrc.nist.gov/Projects/cryptographic-module-validation-program/modules-in-process/modules-in-process-list"
# Allow override via environment variable for flexibility
SEARCH_PATH = os.getenv("NIST_SEARCH_PATH", "/all")
USER_AGENT = "NIST-CMVP-Data-Scraper/1.0 (GitHub Project)"


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


def main():
    """Main entry point for the scraper."""
    print("=" * 60)
    print("NIST CMVP Data Scraper")
    print("=" * 60)
    print()
    
    # Scrape all validated modules
    print("Scraping validated modules...")
    modules = scrape_all_modules()
    
    if not modules:
        print("No validated modules found!", file=sys.stderr)
        sys.exit(1)
    
    print(f"\nTotal validated modules scraped: {len(modules)}")
    
    # Scrape modules in process
    print("\nScraping modules in process...")
    modules_in_process = scrape_modules_in_process()
    
    print(f"Total modules in process scraped: {len(modules_in_process)}")
    
    # Prepare output directory
    output_dir = "api"
    
    # Create metadata
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "total_modules": len(modules),
        "total_modules_in_process": len(modules_in_process),
        "source": BASE_URL,
        "modules_in_process_source": MODULES_IN_PROCESS_URL,
        "version": "1.0"
    }
    
    # Save main modules data
    main_data = {
        "metadata": metadata,
        "modules": modules
    }
    save_json(main_data, f"{output_dir}/modules.json")
    
    # Save modules in process data
    modules_in_process_data = {
        "metadata": metadata,
        "modules_in_process": modules_in_process
    }
    save_json(modules_in_process_data, f"{output_dir}/modules-in-process.json")
    
    # Save metadata separately for quick access
    save_json(metadata, f"{output_dir}/metadata.json")
    
    # Create index page
    index_data = {
        "name": "NIST CMVP Data API",
        "description": "Static API for NIST Cryptographic Module Validation Program validated modules",
        "endpoints": {
            "modules": "/api/modules.json",
            "modules_in_process": "/api/modules-in-process.json",
            "metadata": "/api/metadata.json"
        },
        "last_updated": metadata["generated_at"],
        "total_modules": len(modules),
        "total_modules_in_process": len(modules_in_process)
    }
    save_json(index_data, f"{output_dir}/index.json")
    
    print("\n" + "=" * 60)
    print("Scraping completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
