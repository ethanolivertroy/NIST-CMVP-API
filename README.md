# NIST CMVP Data

A static API providing access to the NIST Cryptographic Module Validation Program (CMVP) validated modules database. The data is automatically scraped and updated every other day via GitHub Actions.

## 🔍 What is CMVP?

The Cryptographic Module Validation Program (CMVP) is a joint effort between NIST and the Canadian Centre for Cyber Security (CCCS) to validate cryptographic modules to FIPS 140-2 and FIPS 140-3 standards. This repository maintains a queryable database of all validated modules.

## 📊 API Endpoints

Once GitHub Pages is enabled, the API will be available at:

```
https://<username>.github.io/nist-CMVP-data/api/
```

### Available Endpoints

- **`/api/index.json`** - API information and status
- **`/api/modules.json`** - Complete list of all validated modules with metadata
- **`/api/historical-modules.json`** - Complete list of historical (expired/revoked) modules
- **`/api/metadata.json`** - Metadata about the dataset (last update, total count, etc.)

### Example Usage

```bash
# Get all validated modules
curl https://<username>.github.io/nist-CMVP-data/api/modules.json

# Get all historical modules
curl https://<username>.github.io/nist-CMVP-data/api/historical-modules.json

# Get metadata
curl https://<username>.github.io/nist-CMVP-data/api/metadata.json

# Using jq to filter results
curl https://<username>.github.io/nist-CMVP-data/api/modules.json | jq '.modules[] | select(.Vendor == "Microsoft")'

# Filter historical modules by vendor
curl https://<username>.github.io/nist-CMVP-data/api/historical-modules.json | jq '.modules[] | select(."Vendor Name" == "Microsoft")'
```

## 🚀 Setup Instructions

### 1. Enable GitHub Pages

1. Go to your repository **Settings** → **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Select the **main** branch and **/ (root)** folder
4. Click **Save**

Your API will be available at `https://<username>.github.io/nist-CMVP-data/api/` within a few minutes.

### 2. Trigger Initial Data Collection

The scraper runs automatically every other day, but you can trigger it manually:

1. Go to the **Actions** tab
2. Select **Update NIST CMVP Data** workflow
3. Click **Run workflow**
4. Wait for the workflow to complete

## 🔄 Automatic Updates

The GitHub Action workflow (`.github/workflows/update-data.yml`) runs:
- **Every other day** at 2 AM UTC (configurable via cron schedule)
- **On push** to main branch when scraper files are modified
- **Manually** via workflow dispatch

## 🛠️ Local Development

### Prerequisites

- Python 3.12 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/<username>/nist-CMVP-data.git
cd nist-CMVP-data

# Install dependencies
pip install -r requirements.txt
```

### Running the Scraper

```bash
python scraper.py
```

This will:
1. Fetch validated modules data from the NIST CMVP website
2. Fetch historical modules data from the NIST CMVP website
3. Parse the modules information
4. Generate JSON files in the `api/` directory

## 📁 Repository Structure

```
.
├── .github/
│   └── workflows/
│       └── update-data.yml    # GitHub Actions workflow
├── api/                        # Static API data (generated)
│   ├── index.json             # API index
│   ├── metadata.json          # Dataset metadata
│   ├── modules.json           # All validated modules
│   └── historical-modules.json # All historical modules
├── scraper.py                 # Web scraper script
├── test_scraper.py            # Test suite for scraper
├── requirements.txt           # Python dependencies
├── .gitignore                # Git ignore rules
└── README.md                 # This file
```

## 📖 Data Schema

### Module Object

Each module in the `modules.json` file contains:

```json
{
  "Certificate Number": "1234",
  "Vendor": "Example Corp",
  "Module Name": "Crypto Library",
  "Validation Date": "2024-01-01",
  "Standard": "FIPS 140-3",
  "Status": "Active",
  "...": "Additional fields from NIST"
}
```

Note: The exact fields depend on the NIST website structure and may include additional information like links to security policies and validation certificates.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Areas for Contribution

- Enhance scraper to handle pagination
- Add data validation and error handling
- Create additional API endpoints (by vendor, by date, etc.)
- Add data transformation/enrichment
- Improve documentation

## 📝 License

This project is provided as-is for educational and informational purposes. The data itself is sourced from NIST's public CMVP database.

## ⚠️ Disclaimer

This is an unofficial project and is not affiliated with or endorsed by NIST. Always refer to the [official NIST CMVP website](https://csrc.nist.gov/projects/cryptographic-module-validation-program/validated-modules) for the most accurate and up-to-date information.

## 🔗 Resources

- [NIST CMVP Official Site](https://csrc.nist.gov/projects/cryptographic-module-validation-program)
- [NIST Validated Modules Search](https://csrc.nist.gov/projects/cryptographic-module-validation-program/validated-modules/search)
- [FIPS 140-2 Standard](https://csrc.nist.gov/publications/detail/fips/140/2/final)
- [FIPS 140-3 Standard](https://csrc.nist.gov/publications/detail/fips/140/3/final)