#!/usr/bin/env python3
"""
Authentication and authorization utilities for External MCP Server support.
Supports both OAuth 2.0 and Personal Access Token (PAT) authentication.
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

# Import OAuth handler (avoid circular import)
try:
    from utils.oauth_handler import oauth_handler as _oauth_handler
except ImportError:
    _oauth_handler = None

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""
    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""
    pass


class OAuthTokenManager:
    """
    Manages OAuth 2.0 tokens for external MCP clients.
    Supports both public and confidential clients per MCP Authorization specification.
    """
    
    def __init__(self):
        self.tokens: Dict[str, Dict] = {}  # Store tokens in memory (for Lambda: consider DynamoDB for production)
        
    def validate_token(self, access_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate an OAuth access token.
        
        Args:
            access_token: The OAuth access token to validate
            
        Returns:
            Tuple of (is_valid, token_info)
        """
        if not access_token:
            return False, None
            
        # In production, validate against OAuth provider (Databricks OAuth)
        # For now, check if token exists and is not expired
        token_info = self.tokens.get(access_token)
        
        if not token_info:
            logger.warning("Token not found in cache")
            return False, None
            
        # Check expiration
        expires_at = token_info.get('expires_at', 0)
        if time.time() > expires_at:
            logger.warning("Token has expired")
            return False, None
            
        return True, token_info
    
    def store_token(self, access_token: str, token_info: Dict):
        """
        Store OAuth token information.
        
        Args:
            access_token: The OAuth access token
            token_info: Token metadata including expiry, scopes, etc.
        """
        self.tokens[access_token] = token_info
        logger.info(f"Stored token with expiry: {datetime.fromtimestamp(token_info.get('expires_at', 0))}")
    
    def refresh_token(self, refresh_token: str) -> Optional[Dict]:
        """
        Refresh an OAuth token using refresh token.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New token information or None if refresh failed
        """
        # In production, call Databricks OAuth token endpoint
        # POST /oidc/v1/token with grant_type=refresh_token
        logger.info("Token refresh requested")
        # TODO: Implement actual refresh token flow
        return None


class PATAuthenticator:
    """
    Authenticates requests using Personal Access Tokens (PAT).
    Simpler authentication method for individual development and testing.
    """
    
    def __init__(self):
        # In production, load PATs from secure storage (AWS Secrets Manager, DynamoDB, etc.)
        self.valid_pats = self._load_pats()
    
    def _load_pats(self) -> Dict[str, Dict]:
        """
        Load valid PATs from secure storage.
        In production, this would query AWS Secrets Manager or DynamoDB.
        
        Returns:
            Dictionary mapping PAT tokens to user information
        """
        # For development, check environment variable
        dev_pat = os.environ.get('DEV_PAT_TOKEN')
        if dev_pat:
            return {
                dev_pat: {
                    'user_id': 'dev_user',
                    'scopes': ['all-apis'],
                    'created_at': time.time(),
                    'expires_at': time.time() + (365 * 24 * 60 * 60)  # 1 year
                }
            }
        return {}
    
    def validate_pat(self, pat_token: str) -> Tuple[bool, Optional[Dict]]:
        """
        Validate a Personal Access Token.
        
        Args:
            pat_token: The PAT token to validate
            
        Returns:
            Tuple of (is_valid, token_info)
        """
        if not pat_token:
            return False, None
            
        token_info = self.valid_pats.get(pat_token)
        
        if not token_info:
            logger.warning("PAT not found")
            return False, None
        
        # Check expiration
        expires_at = token_info.get('expires_at', 0)
        if time.time() > expires_at:
            logger.warning("PAT has expired")
            return False, None
            
        return True, token_info


class AuthMiddleware:
    """
    Middleware for authenticating incoming requests.
    Supports both OAuth and PAT authentication methods.
    """
    
    def __init__(self):
        self.oauth_manager = OAuthTokenManager()
        self.pat_authenticator = PATAuthenticator()
    
    def authenticate_request(self, headers: Dict[str, str]) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Authenticate an incoming request using either OAuth or PAT.
        
        Args:
            headers: Request headers
            
        Returns:
            Tuple of (is_authenticated, user_info, error_message)
        """
        # Extract Authorization header
        auth_header = headers.get('authorization') or headers.get('Authorization')
        
        if not auth_header:
            return False, None, "Missing Authorization header"
        
        # Check if it's Bearer token (OAuth or PAT)
        if not auth_header.startswith('Bearer '):
            return False, None, "Invalid Authorization header format. Expected 'Bearer <token>'"
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Try OAuth first (using global oauth_handler if available)
        if _oauth_handler:
            is_valid, token_info = _oauth_handler.validate_token(token)
            if is_valid:
                logger.info("Request authenticated via OAuth")
                return True, token_info, None
        else:
            # Fallback to local OAuth manager
            is_valid, token_info = self.oauth_manager.validate_token(token)
            if is_valid:
                logger.info("Request authenticated via OAuth (local)")
                return True, token_info, None
        
        # Try PAT
        is_valid, token_info = self.pat_authenticator.validate_pat(token)
        if is_valid:
            logger.info("Request authenticated via PAT")
            return True, token_info, None
        
        return False, None, "Invalid or expired token"
    
    def check_permissions(self, user_info: Dict, required_scope: str = 'all-apis') -> bool:
        """
        Check if user has required permissions.
        
        Args:
            user_info: User information from token validation
            required_scope: Required scope for the operation
            
        Returns:
            True if user has required permissions
        """
        scopes = user_info.get('scopes', [])
        return required_scope in scopes or 'all-apis' in scopes


# Global middleware instance
auth_middleware = AuthMiddleware()


def extract_and_validate_auth(headers: Dict[str, str]) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    Helper function to extract and validate authentication from headers.
    
    Args:
        headers: Request headers
        
    Returns:
        Tuple of (is_authenticated, user_info, error_message)
    """
    return auth_middleware.authenticate_request(headers)

