# DAAP MCP Server

A lightweight MCP (Model Context Protocol) server for CSV analysis, deployable to AWS Lambda.

## Features

- **CSV Analysis**: Analyze CSV files with row/column counts
- **S3 CSV Tools**: Read and analyze CSV files directly from AWS S3
- **AWS Lambda Deployment**: Serverless deployment with API Gateway
- **Cursor Integration**: Works with Cursor IDE via MCP proxy
- **External MCP Server**: OAuth 2.0 support for Claude, Cursor, MCP Inspector
- **Secure Authentication**: Both OAuth and Personal Access Token (PAT) support
- **Databricks Compatible**: Works as External MCP Server with Unity Catalog
- **Configurable**: Environment-based configuration

## Configuration

### Environment Variables

- `MCP_SERVER_URL`: Your deployed MCP server URL (default: current Lambda URL)
- `AWS_PROFILE`: AWS profile for local development
- `AWS_REGION`: AWS region (default: eu-central-1)
- `DATABRICKS_WORKSPACE_HOSTNAME`: Your Databricks workspace hostname (for OAuth)
- `OAUTH_ACCESS_TOKEN_TTL_MINUTES`: OAuth access token TTL in minutes (default: 60)
- `OAUTH_REFRESH_TOKEN_TTL_MINUTES`: OAuth refresh token TTL in minutes (default: 10080)
- `DEV_PAT_TOKEN`: Personal Access Token for development/testing

### Setup

1. **Copy environment template**:
   ```bash
   cp env.example .env
   ```

2. **Update your MCP server URL** in `.env`:
   ```
   MCP_SERVER_URL=https://your-api-gateway-id.execute-api.eu-central-1.amazonaws.com/prod/mcp
   ```

### Centralized Configuration

All deployment scripts use centralized configuration from `config.env`:

- `FUNCTION_NAME`: Lambda function name
- `API_GATEWAY_NAME`: API Gateway name
- `AWS_REGION`: AWS region
- `MCP_SERVER_URL`: MCP server endpoint URL

## Usage

### Local Testing

```bash
# Test Lambda handler
uv run lambda_handler.py

# Test MCP proxy
uv run test_proxy.py
```

### S3 CSV Tools

The server includes a simple tool for getting basic information from CSV files stored in AWS S3:

- **`analyze_s3_csv`**: Basic info - count, columns, and sample 50 records

**📊 Ultra Simple (KISS):**
- **Pandas integration** - uses `pd.read_csv()` directly with S3 URLs
- **No analysis** - just count, columns, and sample data
- **Easy to use** - just provide bucket name and file key

**Example Usage:**
```bash
# Get basic info from a CSV file in S3
analyze_s3_csv("my-bucket", "data/sales.csv")
```

### Deployment

```bash
# Create deployment package
./create_deployment_package.sh

# Deploy via GitHub Actions (manual trigger)
# Or upload mcp-server-deployment.zip to AWS Lambda
```

### Cleanup

```bash
# Local cleanup (requires confirmation)
./cleanup.sh

# GitHub Actions cleanup (manual trigger with confirmation)
# Go to Actions → Cleanup AWS Resources → Run workflow
# Type "DELETE" when prompted
```

### External MCP Server (OAuth)

Supports OAuth 2.0 authentication for external clients (Claude, Cursor, MCP Inspector).

**Endpoints:**
- `GET /oauth/authorize` - OAuth authorization
- `POST /oauth/token` - Token exchange/refresh
- `POST /mcp` - MCP endpoint (requires Bearer token)

### Cursor Integration

The MCP proxy automatically connects to your deployed server using the configured URL.

## Project Structure

```
├── lambda_handler.py          # AWS Lambda entry point
├── mcp_proxy.py              # MCP proxy for Cursor
├── server.py                 # MCP server configuration
├── tools/
│   ├── __init__.py           # Auto-registers all tools
│   ├── csv_tools.py          # Local CSV analysis tools
│   └── s3_csv_tools.py       # S3 CSV analysis tools
├── utils/
│   ├── file_reader.py        # Local file utilities
│   └── s3_csv_processor.py   # S3 CSV processing utilities
├── create_deployment_package.sh  # Deployment script
└── .github/workflows/deploy.yml  # GitHub Actions
```
# fast-mcp-demo
