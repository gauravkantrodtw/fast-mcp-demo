#!/usr/bin/env python3
"""
MCP Proxy for AWS Lambda with IAM Authentication
This proxy handles AWS IAM authentication and forwards MCP requests to Lambda.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional
import urllib3
from urllib3.util.retry import Retry

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPProxy:
    def __init__(self, api_gateway_url: str, region: str):
        self.api_gateway_url = api_gateway_url
        self.region = region
        
        # Get AWS profile from environment
        profile_name = os.getenv('AWS_PROFILE')
        
        # Create boto3 session with profile
        self.session = boto3.Session(profile_name=profile_name)
        
        # Get credentials from session
        try:
            self.credentials = self.session.get_credentials()
            if not self.credentials:
                raise ValueError(f"No credentials found for profile: {profile_name}")
        except Exception as e:
            logger.error(f"Failed to get AWS credentials: {e}")
            raise
        
    def make_authenticated_request(self, method: str, path: str, body: str = None) -> Dict[str, Any]:
        """Make an authenticated request to API Gateway using AWS IAM."""
        url = f"{self.api_gateway_url}{path}"
        
        # Create AWS request
        request = AWSRequest(method=method, url=url, data=body)
        request.headers['Content-Type'] = 'application/json'
        request.headers['Accept'] = 'application/json'
        
        # Sign the request with SigV4
        try:
            SigV4Auth(self.credentials, 'execute-api', self.region).add_auth(request)
            logger.info(f"Request signed successfully for {method} {url}")
        except Exception as e:
            logger.error(f"Failed to sign request: {e}")
            raise
        
        # Make the request using urllib3
        http = urllib3.PoolManager(
            retries=Retry(
                total=3,
                backoff_factor=0.3,
                status_forcelist=[500, 502, 504]
            )
        )
        
        try:
            response = http.request(
                method=request.method,
                url=request.url,
                headers=dict(request.headers),
                body=request.body
            )
            
            return {
                'status_code': response.status,
                'headers': dict(response.headers),
                'body': response.data.decode('utf-8')
            }
        except Exception as e:
            logger.error(f"Request failed: {e}")
            raise
    
    def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request by forwarding to Lambda."""
        try:
            # Forward the request to Lambda
            response = self.make_authenticated_request(
                method='POST',
                path='/mcp',
                body=json.dumps(request)
            )
            
            if response['status_code'] == 200:
                response_body = response['body']
                
                # Handle notifications (no response needed)
                if request.get('method', '').startswith('notifications/'):
                    # For notifications, don't send any response
                    return None
                
                # Parse JSON response for regular requests
                if response_body and response_body.strip():
                    return json.loads(response_body)
                else:
                    # Empty response for notifications
                    return None
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get('id'),
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": f"Lambda returned status {response['status_code']}: {response['body']}"
                    }
                }
        except Exception as e:
            logger.error(f"Error handling MCP request: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request.get('id'),
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }

def main():
    """Main MCP proxy server."""
    # Get configuration from environment variables only
    api_gateway_url = os.getenv('API_GATEWAY_URL')
    region = os.getenv('AWS_REGION')
    
    if not api_gateway_url:
        logger.error("API_GATEWAY_URL environment variable is required")
        sys.exit(1)
    
    if not region:
        logger.error("AWS_REGION environment variable is required")
        sys.exit(1)
    
    proxy = MCPProxy(api_gateway_url, region)
    
    logger.info(f"Starting MCP Proxy for {api_gateway_url} in region {region}")
    
    # Simple MCP server implementation
    while True:
        try:
            # Read MCP request from stdin
            line = sys.stdin.readline()
            if not line:
                break
                
            request = json.loads(line.strip())
            logger.info(f"Received MCP request: {request.get('method', 'unknown')}")
            
            # Handle the request
            response = proxy.handle_mcp_request(request)
            
            # Send response to stdout (only if there's a response)
            if response is not None:
                print(json.dumps(response))
                sys.stdout.flush()
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                    "data": str(e)
                }
            }
            print(json.dumps(error_response))
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    main()
