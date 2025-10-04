#!/usr/bin/env python3
"""
OAuth 2.0 configuration for External MCP Server support.
Supports both public and confidential clients per MCP Authorization specification.
"""

import os
from typing import Dict, List

# OAuth Configuration
OAUTH_CONFIG = {
    # Databricks OAuth endpoints (adjust based on your workspace)
    "authorization_endpoint": os.environ.get(
        "OAUTH_AUTHORIZATION_ENDPOINT",
        "https://<workspace-hostname>/oidc/v1/authorize"
    ),
    "token_endpoint": os.environ.get(
        "OAUTH_TOKEN_ENDPOINT", 
        "https://<workspace-hostname>/oidc/v1/token"
    ),
    
    # Token settings
    "access_token_ttl_minutes": int(os.environ.get("OAUTH_ACCESS_TOKEN_TTL", "60")),
    "refresh_token_ttl_minutes": int(os.environ.get("OAUTH_REFRESH_TOKEN_TTL", "10080")),  # 7 days
    
    # Supported grant types
    "supported_grant_types": ["authorization_code", "refresh_token"],
    
    # Scopes
    "supported_scopes": ["all-apis"],
    "default_scope": "all-apis"
}

# Client configurations for different MCP clients
MCP_CLIENT_CONFIGS = {
    "claude": {
        "name": "claude-mcp-client",
        "redirect_urls": ["https://claude.ai/api/mcp/auth_callback"],
        "client_type": "public",  # No client secret
        "scopes": ["all-apis"],
        "description": "Claude Desktop and Claude.ai connector"
    },
    "cursor": {
        "name": "cursor-mcp-client", 
        "redirect_urls": ["http://localhost:*"],  # Cursor uses localhost
        "client_type": "public",
        "scopes": ["all-apis"],
        "description": "Cursor IDE MCP integration"
    },
    "mcp_inspector": {
        "name": "mcp-inspector-client",
        "redirect_urls": [
            "http://localhost:6274/oauth/callback",
            "http://localhost:6274/oauth/callback/debug"
        ],
        "client_type": "public",
        "scopes": ["all-apis"],
        "description": "MCP Inspector debugging tool"
    }
}

# IP allowlist for workspace restrictions (if using IP access control)
# Add Claude's outbound IPs if you have IP restrictions
CLAUDE_OUTBOUND_IPS = [
    # Add Claude's outbound IP addresses here if you have workspace IP restrictions
    # Example: "52.1.2.3/32", "54.2.3.4/32"
]

def get_client_config(client_name: str) -> Dict:
    """Get OAuth configuration for a specific MCP client."""
    return MCP_CLIENT_CONFIGS.get(client_name.lower(), {})

def validate_redirect_uri(redirect_uri: str, client_name: str) -> bool:
    """Validate that redirect URI matches registered client."""
    config = get_client_config(client_name)
    if not config:
        return False
    
    allowed_urls = config.get("redirect_urls", [])
    
    # Exact match
    if redirect_uri in allowed_urls:
        return True
    
    # Wildcard matching for localhost (e.g., Cursor)
    for allowed_url in allowed_urls:
        if "*" in allowed_url:
            prefix = allowed_url.split("*")[0]
            if redirect_uri.startswith(prefix):
                return True
    
    return False

