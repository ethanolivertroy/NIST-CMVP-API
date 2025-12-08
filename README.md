# NIST CMVP API

Static JSON API for NIST Cryptographic Module Validation Program data. Auto-updates daily via GitHub Actions.

## Endpoints

Base URL: `https://ethanolivertroy.github.io/NIST-CMVP-API/api/`

| Endpoint | Description |
|----------|-------------|
| `modules.json` | Validated cryptographic modules |
| `historical-modules.json` | Expired/revoked modules |
| `modules-in-process.json` | Modules in validation |
| `metadata.json` | Dataset info (last update, counts) |

## Usage

```bash
# Get validated modules
curl https://ethanolivertroy.github.io/NIST-CMVP-API/api/modules.json

# Filter by vendor
curl https://ethanolivertroy.github.io/NIST-CMVP-API/api/modules.json | jq '.modules[] | select(.Vendor == "Microsoft")'
```

## Local Development

```bash
pip install -r requirements.txt
python scraper.py
```

## Source

Data scraped from [NIST CMVP](https://csrc.nist.gov/projects/cryptographic-module-validation-program).
