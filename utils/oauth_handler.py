#!/usr/bin/env python3
"""
OAuth 2.0 authorization handler for External MCP Server.
Implements OAuth flows compatible with Databricks MCP server requirements.
"""

import os
import json
import base64
import hashlib
import secrets
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode, parse_qs
import time

logger = logging.getLogger(__name__)


class OAuthHandler:
    """
    Handles OAuth 2.0 authorization flows for External MCP clients.
    Supports both public clients (no client secret) and confidential clients.
    """
    
    def __init__(self):
        self.workspace_hostname = os.environ.get(
            'DATABRICKS_WORKSPACE_HOSTNAME',
            'your-workspace.cloud.databricks.com'
        )
        
        # OAuth endpoints
        self.authorization_endpoint = f"https://{self.workspace_hostname}/oidc/v1/authorize"
        self.token_endpoint = f"https://{self.workspace_hostname}/oidc/v1/token"
        
        # Store authorization codes and tokens in memory
        # For production: use DynamoDB or Redis
        self.auth_codes: Dict[str, Dict] = {}
        self.access_tokens: Dict[str, Dict] = {}
        self.refresh_tokens: Dict[str, Dict] = {}
        
        # Token TTLs (from environment or defaults)
        self.access_token_ttl = int(os.environ.get('OAUTH_ACCESS_TOKEN_TTL_MINUTES', '60')) * 60
        self.refresh_token_ttl = int(os.environ.get('OAUTH_REFRESH_TOKEN_TTL_MINUTES', '10080')) * 60
    
    def generate_authorization_url(
        self,
        client_id: str,
        redirect_uri: str,
        state: Optional[str] = None,
        scope: str = "all-apis",
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None
    ) -> str:
        """
        Generate OAuth authorization URL for the authorization code flow.
        
        Args:
            client_id: OAuth client ID
            redirect_uri: Redirect URI after authorization
            state: Optional state parameter for CSRF protection
            scope: Requested scopes (default: all-apis)
            code_challenge: PKCE code challenge (for public clients)
            code_challenge_method: PKCE method (S256 or plain)
            
        Returns:
            Authorization URL
        """
        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scope,
        }
        
        if state:
            params['state'] = state
        
        # PKCE support for public clients
        if code_challenge:
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = code_challenge_method or 'S256'
        
        return f"{self.authorization_endpoint}?{urlencode(params)}"
    
    def handle_authorization_callback(
        self,
        code: str,
        client_id: str,
        redirect_uri: str,
        state: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Handle OAuth authorization callback.
        
        Args:
            code: Authorization code from callback
            client_id: OAuth client ID
            redirect_uri: Original redirect URI
            state: State parameter for validation
            
        Returns:
            Tuple of (success, error_message)
        """
        # Store authorization code with metadata
        auth_code_data = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': 'all-apis',
            'created_at': time.time(),
            'expires_at': time.time() + 600,  # 10 minutes
            'used': False
        }
        
        self.auth_codes[code] = auth_code_data
        logger.info(f"Stored authorization code for client: {client_id}")
        
        return True, None
    
    def exchange_code_for_token(
        self,
        code: str,
        client_id: str,
        client_secret: Optional[str] = None,
        redirect_uri: str = None,
        code_verifier: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code
            client_id: OAuth client ID
            client_secret: Client secret (for confidential clients)
            redirect_uri: Original redirect URI
            code_verifier: PKCE code verifier (for public clients)
            
        Returns:
            Tuple of (success, token_response, error_message)
        """
        # Validate authorization code
        auth_code_data = self.auth_codes.get(code)
        
        if not auth_code_data:
            return False, None, "Invalid authorization code"
        
        # Check if already used (prevent replay attacks)
        if auth_code_data.get('used'):
            return False, None, "Authorization code already used"
        
        # Check expiration
        if time.time() > auth_code_data.get('expires_at', 0):
            return False, None, "Authorization code expired"
        
        # Validate client
        if auth_code_data.get('client_id') != client_id:
            return False, None, "Client ID mismatch"
        
        # Validate redirect URI
        if redirect_uri and auth_code_data.get('redirect_uri') != redirect_uri:
            return False, None, "Redirect URI mismatch"
        
        # Mark code as used
        auth_code_data['used'] = True
        
        # Generate tokens
        access_token = self._generate_token()
        refresh_token = self._generate_token()
        
        # Store token metadata
        current_time = time.time()
        token_data = {
            'client_id': client_id,
            'scope': auth_code_data.get('scope', 'all-apis'),
            'user_id': auth_code_data.get('user_id', 'authenticated_user'),
            'created_at': current_time,
            'expires_at': current_time + self.access_token_ttl
        }
        
        self.access_tokens[access_token] = token_data.copy()
        self.refresh_tokens[refresh_token] = token_data.copy()
        self.refresh_tokens[refresh_token]['expires_at'] = current_time + self.refresh_token_ttl
        
        # Build token response
        token_response = {
            'access_token': access_token,
            'token_type': 'Bearer',
            'expires_in': self.access_token_ttl,
            'refresh_token': refresh_token,
            'scope': token_data['scope']
        }
        
        logger.info(f"Issued access token for client: {client_id}")
        
        return True, token_response, None
    
    def refresh_access_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Refresh token
            client_id: OAuth client ID
            client_secret: Client secret (for confidential clients)
            
        Returns:
            Tuple of (success, token_response, error_message)
        """
        # Validate refresh token
        refresh_token_data = self.refresh_tokens.get(refresh_token)
        
        if not refresh_token_data:
            return False, None, "Invalid refresh token"
        
        # Check expiration
        if time.time() > refresh_token_data.get('expires_at', 0):
            return False, None, "Refresh token expired"
        
        # Validate client
        if refresh_token_data.get('client_id') != client_id:
            return False, None, "Client ID mismatch"
        
        # Generate new access token
        new_access_token = self._generate_token()
        
        current_time = time.time()
        token_data = {
            'client_id': client_id,
            'scope': refresh_token_data.get('scope', 'all-apis'),
            'user_id': refresh_token_data.get('user_id', 'authenticated_user'),
            'created_at': current_time,
            'expires_at': current_time + self.access_token_ttl
        }
        
        self.access_tokens[new_access_token] = token_data
        
        # Build token response
        token_response = {
            'access_token': new_access_token,
            'token_type': 'Bearer',
            'expires_in': self.access_token_ttl,
            'refresh_token': refresh_token,  # Reuse same refresh token
            'scope': token_data['scope']
        }
        
        logger.info(f"Refreshed access token for client: {client_id}")
        
        return True, token_response, None
    
    def validate_token(self, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate an access token.
        
        Args:
            access_token: Access token to validate
            
        Returns:
            Tuple of (is_valid, token_data)
        """
        token_data = self.access_tokens.get(access_token)
        
        if not token_data:
            return False, None
        
        # Check expiration
        if time.time() > token_data.get('expires_at', 0):
            logger.warning("Token expired")
            return False, None
        
        return True, token_data
    
    def _generate_token(self) -> str:
        """Generate a secure random token."""
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def generate_pkce_pair() -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge pair.
        Used by public clients (Claude, Cursor, MCP Inspector).
        
        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge


# Global OAuth handler instance
oauth_handler = OAuthHandler()

