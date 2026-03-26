#!/usr/bin/env python3
"""
Test script for the NIST CMVP scraper.
Tests the parsing logic with sample HTML.
"""

import json
import sys
from scraper import parse_certificate_detail_page, parse_modules_table


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


def test_parse_historical_modules_table():
    """Test parsing a table with historical modules format."""
    html = """
    <html>
        <body>
            <table>
                <thead>
                    <tr>
                        <th>Certificate Number</th>
                        <th>Vendor Name</th>
                        <th>Module Name</th>
                        <th>Module Type</th>
                        <th>Validation Date</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><a href="/cert/9999">9999</a></td>
                        <td>Historical Vendor</td>
                        <td>Historical Crypto Module</td>
                        <td>Software</td>
                        <td>01/01/2010</td>
                    </tr>
                    <tr>
                        <td><a href="/cert/8888">8888</a></td>
                        <td>Old Corp</td>
                        <td>Legacy Module</td>
                        <td>Hardware</td>
                        <td>12/31/2009</td>
                    </tr>
                </tbody>
            </table>
        </body>
    </html>
    """
    
    modules = parse_modules_table(html)
    
    assert len(modules) == 2, f"Expected 2 modules, got {len(modules)}"
    assert modules[0]["Certificate Number"] == "9999", "First historical module certificate mismatch"
    assert modules[0]["Vendor Name"] == "Historical Vendor", "First historical module vendor mismatch"
    assert modules[0]["Module Name"] == "Historical Crypto Module", "First historical module name mismatch"
    assert "Certificate Number_url" in modules[0], "Expected URL field for certificate number"
    
    assert modules[1]["Certificate Number"] == "8888", "Second historical module certificate mismatch"
    assert modules[1]["Validation Date"] == "12/31/2009", "Second historical module date mismatch"
    
    print("✓ Historical modules table test passed")


def test_parse_modules_in_process():
    """Test parsing modules in process table structure."""
    html = """
    <html>
        <body>
            <table>
                <thead>
                    <tr>
                        <th>Lab Code</th>
                        <th>Vendor Name</th>
                        <th>Module Name</th>
                        <th>Module Type</th>
                        <th>Module Version</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1234</td>
                        <td>Test Vendor</td>
                        <td><a href="/modules/test">Test Module In Process</a></td>
                        <td>Software</td>
                        <td>1.0</td>
                    </tr>
                </tbody>
            </table>
        </body>
    </html>
    """
    
    modules = parse_modules_table(html)
    
    assert len(modules) == 1, f"Expected 1 module, got {len(modules)}"
    assert modules[0]["Lab Code"] == "1234", "Lab Code mismatch"
    assert modules[0]["Vendor Name"] == "Test Vendor", "Vendor Name mismatch"
    assert modules[0]["Module Name"] == "Test Module In Process", "Module Name mismatch"
    assert modules[0]["Module Type"] == "Software", "Module Type mismatch"
    assert modules[0]["Module Version"] == "1.0", "Module Version mismatch"
    assert "Module Name_url" in modules[0], "Expected URL field for module name"
    
    print("✓ Modules in process table test passed")


def test_parse_certificate_detail_page():
    """Test parsing a NIST-style certificate detail page."""
    html = """
    <html>
      <body>
        <div class="panel panel-default">
          <div class="panel-heading"><h4 class="panel-title">Details</h4></div>
          <div class="panel-body">
            <div class="row padrow">
              <div class="col-md-3"><span>Module Name</span></div>
              <div class="col-md-9" id="module-name">OVHCloud OKMS Provider based on the OpenSSL FIPS Provider</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3">Standard</div>
              <div class="col-md-9" id="module-standard">FIPS 140-3</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3">Status</div>
              <div class="col-md-9">Active</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Sunset Date</span></div>
              <div class="col-md-9">3/10/2030</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Overall Level</span></div>
              <div class="col-md-9">1</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Caveat</span></div>
              <div class="col-md-9"><span class="alert-danger">When operated in approved mode.</span></div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Security Level Exceptions</span></div>
              <div class="col-md-9">
                <ul class="list-left15pxPadding">
                  <li>Physical security: N/A</li>
                  <li>Life-cycle assurance: Level 3</li>
                </ul>
              </div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Module Type</span></div>
              <div class="col-md-9">Software</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Embodiment</span></div>
              <div class="col-md-9" id="embodiment-name">MultiChipStand</div>
            </div>
            <div class="row padrow">
              <div class="col-md-3"><span>Description</span></div>
              <div class="col-md-9">A software library providing cryptographic functionality.</div>
            </div>
          </div>
        </div>

        <div class="panel panel-default">
          <div class="panel-heading"><h4 class="panel-title">Vendor</h4></div>
          <div class="panel-body">
            <a href="https://corporate.ovhcloud.com/en/">OVH SAS</a><br />
            <span class="indent">2 RUE KELLERMANN</span><br />
            <span class="indent">ROUBAIX 59100</span><br />
            <span class="indent">FRANCE</span><br /><br />
            <div style="font-size: 0.9em;">
              <span>
                Data security team<br />
                <span class="indent"><a class="__cf_email__" data-cfemail="b5daded8c6ead3dcc5c6f5dac3dd9bdbd0c1" href="/cdn-cgi/l/email-protection">[email&#160;protected]</a></span><br />
                <span class="indent">Phone: +33 3 20 82 73 32</span><br />
              </span>
            </div>
          </div>
        </div>

        <div class="panel panel-default">
          <div class="panel-heading"><h4 class="panel-title">Related Files</h4></div>
          <div class="panel-body">
            <a href="/CSRC/media/projects/cryptographic-module-validation-program/documents/security-policies/140sp5203.pdf">Security Policy</a><br />
            <a href="https://example.test/other.pdf">Implementation Guidance</a>
          </div>
        </div>

        <div class="panel panel-default">
          <div class="panel-heading"><h4 class="panel-title">Validation History</h4></div>
          <div class="panel-body">
            <table class="table table-condensed table-striped nolinetable" id="validation-history-table">
              <thead>
                <tr><th>Date</th><th>Type</th><th>Lab</th></tr>
              </thead>
              <tbody>
                <tr><td class="text-nowrap">3/21/2026</td><td>Initial</td><td>Lightship Security, Inc.</td></tr>
                <tr><td class="text-nowrap">4/01/2026</td><td>Updated</td><td>Lightship Security, Inc.</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </body>
    </html>
    """

    payload = parse_certificate_detail_page(
        html,
        5203,
        summary_module={
            "Vendor Name": "OVH SAS",
            "Module Name": "OVHCloud OKMS Provider based on the OpenSSL FIPS Provider",
            "algorithms": ["AES", "HMAC"],
            "security_policy_url": "https://csrc.nist.gov/CSRC/media/projects/cryptographic-module-validation-program/documents/security-policies/140sp5203.pdf",
        },
        dataset="active",
        generated_at="2026-03-26T00:00:00.000000Z",
    )

    assert payload["certificate_number"] == "5203", "Certificate number mismatch"
    assert payload["dataset"] == "active", "Dataset mismatch"
    assert payload["module_name"] == "OVHCloud OKMS Provider based on the OpenSSL FIPS Provider", "Module name mismatch"
    assert payload["standard"] == "FIPS 140-3", "Standard mismatch"
    assert payload["status"] == "Active", "Status mismatch"
    assert payload["sunset_date"] == "3/10/2030", "Sunset date mismatch"
    assert payload["overall_level"] == 1, "Overall level mismatch"
    assert payload["security_level_exceptions"] == ["Physical security: N/A", "Life-cycle assurance: Level 3"], "Security level exceptions mismatch"
    assert payload["vendor"]["name"] == "OVH SAS", "Vendor name mismatch"
    assert payload["vendor"]["contact_name"] == "Data security team", "Vendor contact mismatch"
    assert payload["vendor"]["contact_email"] == "okms_fips@ovh.net", "Vendor email mismatch"
    assert payload["vendor"]["contact_phone"] == "+33 3 20 82 73 32", "Vendor phone mismatch"
    assert payload["related_files"][0]["label"] == "Security Policy", "Related file label mismatch"
    assert payload["related_files"][0]["url"].endswith("140sp5203.pdf"), "Related file URL mismatch"
    assert len(payload["validation_history"]) == 2, "Validation history row count mismatch"
    assert payload["validation_history"][1]["type"] == "Updated", "Validation history type mismatch"
    assert payload["validation_dates"] == ["3/21/2026", "4/01/2026"], "Validation dates mismatch"
    assert payload["algorithms"] == ["AES", "HMAC"], "Algorithm list mismatch"

    print("✓ Certificate detail page test passed")


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
        test_parse_historical_modules_table()
        test_parse_modules_in_process()
        test_parse_certificate_detail_page()
        
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
