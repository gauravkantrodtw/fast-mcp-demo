#!/usr/bin/env python3
"""
Test script for OAuth 2.0 flow in External MCP Server.
Tests both authorization code flow and token refresh.
"""

import json
import sys
from utils.oauth_handler import OAuthHandler

def test_oauth_flow():
    """Test complete OAuth authorization code flow."""
    print("=" * 60)
    print("Testing OAuth 2.0 Authorization Code Flow")
    print("=" * 60)
    
    # Initialize OAuth handler
    oauth = OAuthHandler()
    
    # Test data
    client_id = "test-client"
    redirect_uri = "http://localhost:8080/callback"
    state = "test-state-123"
    
    print("\n1. Generate Authorization URL")
    print("-" * 60)
    
    # Generate PKCE pair
    code_verifier, code_challenge = OAuthHandler.generate_pkce_pair()
    print(f"Code Verifier: {code_verifier[:20]}...")
    print(f"Code Challenge: {code_challenge[:20]}...")
    
    auth_url = oauth.generate_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
        code_challenge_method="S256"
    )
    print(f"\nAuthorization URL generated:")
    print(f"{auth_url[:100]}...")
    
    print("\n2. Simulate Authorization Callback")
    print("-" * 60)
    
    # Simulate authorization code generation
    auth_code = oauth._generate_token()
    print(f"Authorization Code: {auth_code[:20]}...")
    
    success, error = oauth.handle_authorization_callback(
        code=auth_code,
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state
    )
    
    if success:
        print("✓ Authorization callback handled successfully")
    else:
        print(f"✗ Authorization callback failed: {error}")
        return False
    
    print("\n3. Exchange Authorization Code for Token")
    print("-" * 60)
    
    success, token_response, error = oauth.exchange_code_for_token(
        code=auth_code,
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier
    )
    
    if not success:
        print(f"✗ Token exchange failed: {error}")
        return False
    
    print("✓ Token exchange successful")
    print(f"\nToken Response:")
    print(json.dumps(token_response, indent=2))
    
    access_token = token_response['access_token']
    refresh_token = token_response['refresh_token']
    
    print("\n4. Validate Access Token")
    print("-" * 60)
    
    is_valid, token_data = oauth.validate_token(access_token)
    
    if is_valid:
        print("✓ Access token is valid")
        print(f"Token Data: {json.dumps(token_data, indent=2, default=str)}")
    else:
        print("✗ Access token is invalid")
        return False
    
    print("\n5. Test Refresh Token Flow")
    print("-" * 60)
    
    success, new_token_response, error = oauth.refresh_access_token(
        refresh_token=refresh_token,
        client_id=client_id
    )
    
    if not success:
        print(f"✗ Token refresh failed: {error}")
        return False
    
    print("✓ Token refresh successful")
    print(f"\nNew Token Response:")
    print(json.dumps(new_token_response, indent=2))
    
    new_access_token = new_token_response['access_token']
    
    print("\n6. Validate New Access Token")
    print("-" * 60)
    
    is_valid, token_data = oauth.validate_token(new_access_token)
    
    if is_valid:
        print("✓ New access token is valid")
        print(f"Token Data: {json.dumps(token_data, indent=2, default=str)}")
    else:
        print("✗ New access token is invalid")
        return False
    
    print("\n7. Test Authorization Code Reuse Prevention")
    print("-" * 60)
    
    success, _, error = oauth.exchange_code_for_token(
        code=auth_code,  # Try to reuse the same code
        client_id=client_id,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier
    )
    
    if not success and "already used" in error:
        print(f"✓ Authorization code reuse prevented: {error}")
    else:
        print("✗ Authorization code reuse was not prevented")
        return False
    
    print("\n" + "=" * 60)
    print("All OAuth 2.0 Flow Tests Passed! ✓")
    print("=" * 60)
    
    return True


def test_lambda_handler_integration():
    """Test OAuth endpoints in Lambda handler."""
    print("\n" + "=" * 60)
    print("Testing Lambda Handler OAuth Integration")
    print("=" * 60)
    
    from lambda_handler import handle_oauth_authorize, handle_oauth_token
    
    # Test OAuth authorize endpoint
    print("\n1. Test OAuth Authorize Endpoint")
    print("-" * 60)
    
    authorize_event = {
        "queryStringParameters": {
            "client_id": "test-client",
            "redirect_uri": "http://localhost:8080/callback",
            "response_type": "code",
            "scope": "all-apis",
            "state": "test-123"
        }
    }
    
    response = handle_oauth_authorize(authorize_event)
    print(f"Status Code: {response['statusCode']}")
    
    if response['statusCode'] == 302:
        print("✓ Authorization endpoint returned redirect")
        location = response['headers'].get('Location', '')
        if 'code=' in location:
            print(f"✓ Redirect contains authorization code")
            # Extract code from location
            code = location.split('code=')[1].split('&')[0]
            print(f"Authorization Code: {code[:20]}...")
        else:
            print("✗ Redirect does not contain code")
            return False
    else:
        print(f"✗ Unexpected status code: {response['statusCode']}")
        print(f"Body: {response.get('body')}")
        return False
    
    # Test OAuth token endpoint
    print("\n2. Test OAuth Token Endpoint")
    print("-" * 60)
    
    token_body = f"grant_type=authorization_code&code={code}&client_id=test-client&redirect_uri=http://localhost:8080/callback"
    token_headers = {"content-type": "application/x-www-form-urlencoded"}
    
    response = handle_oauth_token(token_body, token_headers)
    print(f"Status Code: {response['statusCode']}")
    
    if response['statusCode'] == 200:
        print("✓ Token endpoint returned success")
        token_data = json.loads(response['body'])
        print(f"Access Token: {token_data.get('access_token', '')[:20]}...")
        print(f"Refresh Token: {token_data.get('refresh_token', '')[:20]}...")
        print(f"Expires In: {token_data.get('expires_in')} seconds")
    else:
        print(f"✗ Token endpoint failed")
        print(f"Body: {response.get('body')}")
        return False
    
    print("\n" + "=" * 60)
    print("Lambda Handler OAuth Integration Tests Passed! ✓")
    print("=" * 60)
    
    return True


def test_authentication_middleware():
    """Test authentication middleware with OAuth tokens."""
    print("\n" + "=" * 60)
    print("Testing Authentication Middleware")
    print("=" * 60)
    
    from utils.auth import extract_and_validate_auth
    from utils.oauth_handler import oauth_handler
    
    # Generate a valid token
    print("\n1. Generate Valid OAuth Token")
    print("-" * 60)
    
    client_id = "test-client"
    auth_code = oauth_handler._generate_token()
    
    oauth_handler.handle_authorization_callback(
        code=auth_code,
        client_id=client_id,
        redirect_uri="http://localhost:8080/callback"
    )
    
    success, token_response, _ = oauth_handler.exchange_code_for_token(
        code=auth_code,
        client_id=client_id,
        redirect_uri="http://localhost:8080/callback"
    )
    
    if not success:
        print("✗ Failed to generate test token")
        return False
    
    access_token = token_response['access_token']
    print(f"Access Token: {access_token[:20]}...")
    
    # Test valid token
    print("\n2. Test Valid Token Authentication")
    print("-" * 60)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    is_auth, user_info, error = extract_and_validate_auth(headers)
    
    if is_auth:
        print("✓ Valid token authenticated successfully")
        print(f"User Info: {json.dumps(user_info, indent=2, default=str)}")
    else:
        print(f"✗ Valid token authentication failed: {error}")
        return False
    
    # Test invalid token
    print("\n3. Test Invalid Token Authentication")
    print("-" * 60)
    
    headers = {"Authorization": "Bearer invalid-token-12345"}
    is_auth, user_info, error = extract_and_validate_auth(headers)
    
    if not is_auth:
        print(f"✓ Invalid token rejected: {error}")
    else:
        print("✗ Invalid token was accepted")
        return False
    
    # Test missing token
    print("\n4. Test Missing Authorization Header")
    print("-" * 60)
    
    headers = {}
    is_auth, user_info, error = extract_and_validate_auth(headers)
    
    if not is_auth:
        print(f"✓ Missing header rejected: {error}")
    else:
        print("✗ Missing header was accepted")
        return False
    
    print("\n" + "=" * 60)
    print("Authentication Middleware Tests Passed! ✓")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print(" " * 20 + "OAuth 2.0 Implementation Test Suite")
    print("=" * 80)
    
    all_passed = True
    
    # Run tests
    try:
        if not test_oauth_flow():
            all_passed = False
            
        if not test_lambda_handler_integration():
            all_passed = False
            
        if not test_authentication_middleware():
            all_passed = False
    except Exception as e:
        print(f"\n✗ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        all_passed = False
    
    # Final summary
    print("\n" + "=" * 80)
    if all_passed:
        print(" " * 30 + "ALL TESTS PASSED! ✓")
        print("=" * 80)
        print("\nYour OAuth 2.0 implementation is ready for External MCP Server usage!")
        print("\nNext steps:")
        print("1. Deploy to AWS Lambda")
        print("2. Configure API Gateway endpoints")
        print("3. Set up OAuth clients in Databricks")
        print("4. Connect external clients (Claude, Cursor, MCP Inspector)")
        print("\nSee EXTERNAL_MCP_SETUP.md for detailed instructions.")
        sys.exit(0)
    else:
        print(" " * 30 + "SOME TESTS FAILED ✗")
        print("=" * 80)
        print("\nPlease review the test output above and fix any issues.")
        sys.exit(1)

