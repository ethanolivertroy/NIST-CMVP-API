# GitHub Pages Setup Guide

This guide will help you set up GitHub Pages to serve the NIST CMVP data as a static API.

## Step-by-Step Instructions

### 1. Enable GitHub Pages

1. Navigate to your repository on GitHub
2. Click on **Settings** (top menu)
3. Scroll down and click on **Pages** in the left sidebar
4. Under **Source**, select:
   - **Deploy from a branch**
   - Branch: **main**
   - Folder: **/ (root)**
5. Click **Save**

### 2. Wait for Deployment

GitHub will automatically build and deploy your site. This typically takes 1-2 minutes.

You can check the deployment status:
- Go to the **Actions** tab
- Look for "pages build and deployment" workflows

### 3. Access Your API

Once deployed, your API will be available at:

```
https://<your-username>.github.io/nist-CMVP-data/api/
```

Replace `<your-username>` with your GitHub username or organization name.

### 4. Test the Endpoints

Try accessing these URLs in your browser or with curl:

```bash
# API index
curl https://<your-username>.github.io/nist-CMVP-data/api/index.json

# Metadata
curl https://<your-username>.github.io/nist-CMVP-data/api/metadata.json

# All modules (this may be large)
curl https://<your-username>.github.io/nist-CMVP-data/api/modules.json
```

## Triggering the First Data Collection

After enabling GitHub Pages, trigger the scraper to collect data:

1. Go to the **Actions** tab in your repository
2. Click on **Update NIST CMVP Data** workflow
3. Click **Run workflow** button
4. Select the **main** branch
5. Click **Run workflow**

The workflow will:
- Install Python dependencies
- Run the scraper
- Commit the data to the `api/` directory
- GitHub Pages will automatically update with the new data

## Troubleshooting

### Pages not deploying

- Ensure the repository is public (or you have GitHub Pro/Organization for private repos)
- Check the Actions tab for any deployment errors
- Verify the `api/` directory exists in the main branch

### API returning 404

- Make sure GitHub Pages is enabled in Settings
- Wait a few minutes after enabling (initial deployment takes time)
- Check that the URL uses your correct username/organization name
- Ensure the path includes `/api/` and `.json` file extensions

### Data not updating

- Check the workflow runs in the Actions tab
- Review workflow logs for errors
- Ensure the repository has write permissions for GitHub Actions
- Verify the cron schedule in `.github/workflows/update-data.yml`

## Custom Domain (Optional)

If you want to use a custom domain:

1. In Settings → Pages, enter your custom domain
2. Configure DNS records with your domain provider:
   - Add a CNAME record pointing to `<your-username>.github.io`
3. Wait for DNS propagation (can take up to 24 hours)
4. GitHub will automatically handle HTTPS certificates

## API Usage Examples

### JavaScript/TypeScript

```javascript
// Fetch all modules
fetch('https://<your-username>.github.io/nist-CMVP-data/api/modules.json')
  .then(response => response.json())
  .then(data => {
    console.log(`Total modules: ${data.metadata.total_modules}`);
    console.log('First module:', data.modules[0]);
  });
```

### Python

```python
import requests

# Get metadata
response = requests.get('https://<your-username>.github.io/nist-CMVP-data/api/metadata.json')
metadata = response.json()
print(f"Last updated: {metadata['generated_at']}")
print(f"Total modules: {metadata['total_modules']}")

# Get all modules
response = requests.get('https://<your-username>.github.io/nist-CMVP-data/api/modules.json')
data = response.json()
modules = data['modules']

# Filter by vendor
microsoft_modules = [m for m in modules if 'Microsoft' in m.get('Vendor', '')]
print(f"Microsoft modules: {len(microsoft_modules)}")
```

### curl + jq

```bash
# Get total count
curl -s https://<your-username>.github.io/nist-CMVP-data/api/metadata.json | jq '.total_modules'

# List all vendors
curl -s https://<your-username>.github.io/nist-CMVP-data/api/modules.json | jq '.modules[].Vendor' | sort -u

# Filter by specific vendor
curl -s https://<your-username>.github.io/nist-CMVP-data/api/modules.json | jq '.modules[] | select(.Vendor == "Microsoft")'
```

## Rate Limiting

GitHub Pages has the following limits:
- 100 GB bandwidth per month
- 100 GB storage
- 10 builds per hour

For most use cases, these limits are sufficient. The API is static and cached by GitHub's CDN, so it can handle significant traffic.

## CORS Support

GitHub Pages automatically supports CORS (Cross-Origin Resource Sharing), so you can access the API from any web application without CORS issues.
