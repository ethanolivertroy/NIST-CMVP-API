#!/usr/bin/env python3
"""
Test script for the NIST CMVP scraper.
Tests the parsing logic with sample HTML.
"""

import json
import sys
from scraper import parse_modules_table


def test_parse_simple_table():
    """Test parsing a simple HTML table."""
    html = """
    <html>
        <body>
            <table>
                <thead>
                    <tr>
                        <th>Certificate Number</th>
                        <th>Vendor</th>
                        <th>Module Name</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1234</td>
                        <td>Test Vendor</td>
                        <td><a href="/test">Test Module</a></td>
                    </tr>
                    <tr>
                        <td>5678</td>
                        <td>Another Vendor</td>
                        <td>Another Module</td>
                    </tr>
                </tbody>
            </table>
        </body>
    </html>
    """
    
    modules = parse_modules_table(html)
    
    assert len(modules) == 2, f"Expected 2 modules, got {len(modules)}"
    assert modules[0]["Certificate Number"] == "1234", "First module certificate mismatch"
    assert modules[0]["Vendor"] == "Test Vendor", "First module vendor mismatch"
    assert modules[0]["Module Name"] == "Test Module", "First module name mismatch"
    assert "Module Name_url" in modules[0], "Expected URL field for module name"
    assert modules[0]["Module Name_url"] == "https://csrc.nist.gov/test", "URL should be absolute"
    
    assert modules[1]["Certificate Number"] == "5678", "Second module certificate mismatch"
    
    print("✓ Simple table test passed")


def test_parse_table_without_thead():
    """Test parsing a table without explicit thead."""
    html = """
    <html>
        <body>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                </tr>
                <tr>
                    <td>100</td>
                    <td>Module A</td>
                </tr>
            </table>
        </body>
    </html>
    """
    
    modules = parse_modules_table(html)
    
    assert len(modules) == 1, f"Expected 1 module, got {len(modules)}"
    assert modules[0]["ID"] == "100", "Module ID mismatch"
    assert modules[0]["Name"] == "Module A", "Module name mismatch"
    
    print("✓ Table without thead test passed")


def test_parse_empty_table():
    """Test parsing an empty table."""
    html = """
    <html>
        <body>
            <table>
                <thead>
                    <tr>
                        <th>Column 1</th>
                    </tr>
                </thead>
                <tbody>
                </tbody>
            </table>
        </body>
    </html>
    """
    
    modules = parse_modules_table(html)
    
    assert len(modules) == 0, f"Expected 0 modules, got {len(modules)}"
    
    print("✓ Empty table test passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing NIST CMVP Scraper")
    print("=" * 60)
    print()
    
    try:
        test_parse_simple_table()
        test_parse_table_without_thead()
        test_parse_empty_table()
        
        print()
        print("=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
