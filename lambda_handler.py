#!/usr/bin/env python3
"""
Direct AWS Lambda handler for FastMCP server without Mangum.
This bypasses ASGI issues by handling MCP protocol directly.
Supports External MCP Server authentication (OAuth and PAT).
"""

import logging
import time
import json
import asyncio
import os
from urllib.parse import parse_qs, urlparse
from server import mcp
from utils.auth import extract_and_validate_auth
from utils.oauth_handler import oauth_handler

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global MCP server instance (created once per Lambda container)
_mcp_server = None

def get_mcp_server():
    """Get or create MCP server instance for Lambda."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = mcp
        logger.info("FastMCP server initialized for direct Lambda handling")
    return _mcp_server

def lambda_handler(event, context):
    """AWS Lambda handler function with direct MCP protocol handling."""
    start_time = time.time()
    
    try:
        # Parse the API Gateway event - handle both v1 and v2 formats
        # Try v2 format first
        http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
        path = event.get('rawPath', '')
        
        # If v2 format doesn't work, try v1 format
        if not http_method:
            http_method = event.get('httpMethod', '')
        if not path:
            path = event.get('path', '')
        
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # Debug logging
        logger.info(f"Event structure: {json.dumps(event, indent=2)}")
        logger.info(f"Processing {http_method} {path}")
        logger.info(f"Headers: {headers}")
        logger.info(f"Body: {body}")
        
        # Fallback for missing method or path
        if not http_method or not path:
            logger.error(f"Missing method or path: method='{http_method}', path='{path}'")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Bad Request", "message": f"Missing method or path: method='{http_method}', path='{path}'"})
            }
        
        # Handle health check endpoint
        if path == '/health' and http_method == 'GET':
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                },
                "body": json.dumps({"status": "healthy", "service": "daap-mcp-server"})
            }
        
        # Handle OAuth authorization endpoint
        elif path == '/oauth/authorize' and http_method == 'GET':
            return handle_oauth_authorize(event)
        
        # Handle OAuth callback endpoint
        elif path == '/oauth/callback' and http_method == 'GET':
            return handle_oauth_callback(event)
        
        # Handle OAuth token endpoint
        elif path == '/oauth/token' and http_method == 'POST':
            return handle_oauth_token(body, headers)
        
        # Handle MCP endpoint (requires authentication for external clients)
        elif path == '/mcp' and http_method == 'POST':
            # Authenticate request for external MCP clients
            is_authenticated, user_info, error_msg = extract_and_validate_auth(headers)
            
            if not is_authenticated:
                logger.warning(f"Authentication failed: {error_msg}")
                return {
                    "statusCode": 401,
                    "headers": {
                        "Content-Type": "application/json",
                        "WWW-Authenticate": "Bearer realm=\"Databricks MCP Server\""
                    },
                    "body": json.dumps({
                        "error": "Unauthorized",
                        "message": error_msg or "Authentication required"
                    })
                }
            
            logger.info(f"Request authenticated for user: {user_info.get('user_id', 'unknown')}")
            return handle_mcp_request(body, headers, user_info)
        
        # Handle CORS preflight
        elif http_method == 'OPTIONS':
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization"
                },
                "body": ""
            }
        
        # Handle unsupported endpoints
        else:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Not Found", "message": f"No handler for {http_method} {path}"})
            }
    
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal Server Error", "message": str(e)})
        }
    
    finally:
        logger.info(f"Processed request in {time.time() - start_time:.3f}s")

def handle_mcp_request(body, headers, user_info=None):
    """Handle MCP protocol requests directly with user context."""
    try:
        # Parse MCP request
        if not body:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Bad Request", "message": "Empty request body"})
            }
        
        try:
            mcp_request = json.loads(body)
        except json.JSONDecodeError as e:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Bad Request", "message": f"Invalid JSON: {str(e)}"})
            }
        
        # Validate MCP request format
        if not isinstance(mcp_request, dict) or 'jsonrpc' not in mcp_request:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Bad Request", "message": "Invalid MCP request format"})
            }
        
        # Handle MCP request asynchronously
        response = asyncio.run(process_mcp_request(mcp_request))
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization"
            },
            "body": json.dumps(response)
        }
    
    except Exception as e:
        logger.error(f"MCP request handling error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal Server Error", "message": str(e)})
        }

async def process_mcp_request(request):
    """Process MCP request using FastMCP directly."""
    try:
        method = request.get('method', '')
        params = request.get('params', {})
        request_id = request.get('id')
        
        logger.info(f"Processing MCP method: {method}")
        
        # Handle different MCP methods
        if method == 'tools/list':
            tools = await mcp.get_tools()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": name,
                            "description": tool.description,
                            "inputSchema": tool.parameters
                        }
                        for name, tool in tools.items()
                    ]
                }
            }
        
        elif method == 'tools/call':
            tool_name = params.get('name', '')
            tool_args = params.get('arguments', {})
            
            if not tool_name:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params",
                        "data": "Tool name is required"
                    }
                }
            
            # Get the tool function
            tools = await mcp.get_tools()
            if tool_name not in tools:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": "Method not found",
                        "data": f"Tool '{tool_name}' not found"
                    }
                }
            
            # Call the tool
            tool_obj = tools[tool_name]
            try:
                # Check if the function is async
                import asyncio
                if asyncio.iscoroutinefunction(tool_obj.fn):
                    result = await tool_obj.fn(**tool_args)
                else:
                    result = tool_obj.fn(**tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
            except Exception as e:
                logger.error(f"Tool execution error: {str(e)}", exc_info=True)
                
                # Extract detailed error message from ToolExecutionError
                if hasattr(e, 'args') and e.args and isinstance(e.args[0], str):
                    error_message = e.args[0]
                else:
                    error_message = str(e)
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": error_message,  # Use detailed error message instead of generic
                        "data": {
                            "tool": tool_name,
                            "error_type": type(e).__name__,
                            "details": str(e)
                        }
                    }
                }
        
        elif method == 'initialize':
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        },
                        "resources": {
                            "subscribe": False,
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": "daap-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif method == 'notifications/initialized':
            # This is a notification, so no response needed
            logger.info("Client initialized successfully")
            return None
        
        elif method == 'resources/list':
            # List available resources
            resources = await mcp.get_resources()
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": [
                        {
                            "uri": uri,
                            "name": resource.name if hasattr(resource, 'name') else uri.split('://')[-1],
                            "description": resource.description if hasattr(resource, 'description') else f"Resource at {uri}",
                            "mimeType": "application/json"
                        }
                        for uri, resource in resources.items()
                    ]
                }
            }
        
        elif method == 'resources/read':
            # Read a specific resource
            uri = params.get('uri', '')
            if not uri:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32602,
                        "message": "Invalid params",
                        "data": "Resource URI is required"
                    }
                }
            
            try:
                resources = await mcp.get_resources()
                if uri in resources:
                    resource = resources[uri]
                    # Call the resource function
                    if hasattr(resource, 'fn'):
                        content = resource.fn()
                    else:
                        content = resource()
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "contents": [
                                {
                                    "uri": uri,
                                    "mimeType": "application/json",
                                    "text": json.dumps(content, indent=2)
                                }
                            ]
                        }
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": "Resource not found",
                            "data": f"Resource {uri} not found"
                        }
                    }
            except Exception as e:
                logger.error(f"Error reading resource {uri}: {e}")
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": f"Failed to read resource: {str(e)}"
                    }
                }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": "Method not found",
                    "data": f"Unknown method: {method}"
                }
            }
    
    except Exception as e:
        logger.error(f"MCP processing error: {str(e)}", exc_info=True)
        
        # Extract detailed error message
        error_message = str(e) if str(e) else "Internal error"
        
        return {
            "jsonrpc": "2.0",
            "id": request.get('id'),
            "error": {
                "code": -32603,
                "message": error_message,  # Use detailed error message
                "data": {
                    "error_type": type(e).__name__,
                    "details": str(e)
                }
            }
        }

def handle_oauth_authorize(event):
    """
    Handle OAuth authorization endpoint.
    Redirects to callback endpoint or external redirect_uri with authorization code.
    """
    try:
        # Parse query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        
        client_id = query_params.get('client_id')
        redirect_uri = query_params.get('redirect_uri')
        state = query_params.get('state')
        scope = query_params.get('scope', 'all-apis')
        code_challenge = query_params.get('code_challenge')
        code_challenge_method = query_params.get('code_challenge_method', 'S256')
        
        if not client_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "invalid_request",
                    "error_description": "Missing client_id"
                })
            }
        
        # If no redirect_uri provided, use API Gateway callback
        api_gateway_url = os.environ.get('API_GATEWAY_URL', event.get('headers', {}).get('host', ''))
        if not redirect_uri:
            # Get the base URL from the request
            protocol = event.get('headers', {}).get('x-forwarded-proto', 'https')
            host = event.get('headers', {}).get('host', api_gateway_url)
            redirect_uri = f"{protocol}://{host}/oauth/callback"
        
        # Generate authorization code
        auth_code = oauth_handler._generate_token()
        
        # Store authorization code
        success, error = oauth_handler.handle_authorization_callback(
            auth_code, client_id, redirect_uri, state
        )
        
        if not success:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "invalid_request",
                    "error_description": error
                })
            }
        
        # Build redirect URL with authorization code
        redirect_params = f"code={auth_code}"
        if state:
            redirect_params += f"&state={state}"
        
        separator = "&" if "?" in redirect_uri else "?"
        redirect_url = f"{redirect_uri}{separator}{redirect_params}"
        
        logger.info(f"OAuth authorization successful for client: {client_id}, redirecting to: {redirect_uri}")
        
        # Return redirect response
        return {
            "statusCode": 302,
            "headers": {
                "Location": redirect_url,
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": ""
        }
    
    except Exception as e:
        logger.error(f"OAuth authorize error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "server_error",
                "error_description": str(e)
            })
        }

def handle_oauth_callback(event):
    """
    Handle OAuth callback endpoint.
    Used by Databricks and external OAuth clients to receive authorization codes.
    This endpoint should be registered in Databricks OAuth App Connection as redirect_uri.
    """
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        
        code = query_params.get('code')
        state = query_params.get('state')
        error = query_params.get('error')
        error_description = query_params.get('error_description')
        
        if error:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": error,
                    "error_description": error_description or "Authorization failed",
                    "state": state
                })
            }
        
        if not code:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": "invalid_request",
                    "error_description": "Missing authorization code"
                })
            }
        
        # Return success with authorization code
        # External clients (Claude, Cursor, MCP Inspector) will use this code
        # to exchange for access token via POST /oauth/token
        logger.info(f"OAuth callback received with code, state: {state}")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "code": code,
                "state": state,
                "message": "Authorization successful. Exchange code for access token via POST /oauth/token"
            })
        }
    
    except Exception as e:
        logger.error(f"OAuth callback error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "server_error",
                "error_description": str(e)
            })
        }

def handle_oauth_token(body, headers):
    """
    Handle OAuth token endpoint.
    Exchanges authorization code for access token or refreshes token.
    """
    try:
        # Parse request body
        if not body:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "invalid_request",
                    "error_description": "Missing request body"
                })
            }
        
        # Parse form data or JSON
        content_type = headers.get('content-type', '').lower()
        
        if 'application/x-www-form-urlencoded' in content_type:
            params = parse_qs(body)
            # parse_qs returns lists, get first value
            token_params = {k: v[0] if isinstance(v, list) else v for k, v in params.items()}
        else:
            token_params = json.loads(body)
        
        grant_type = token_params.get('grant_type')
        client_id = token_params.get('client_id')
        
        if not grant_type or not client_id:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "invalid_request",
                    "error_description": "Missing grant_type or client_id"
                })
            }
        
        # Handle authorization code flow
        if grant_type == 'authorization_code':
            code = token_params.get('code')
            redirect_uri = token_params.get('redirect_uri')
            code_verifier = token_params.get('code_verifier')
            client_secret = token_params.get('client_secret')
            
            if not code:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": "invalid_request",
                        "error_description": "Missing authorization code"
                    })
                }
            
            success, token_response, error = oauth_handler.exchange_code_for_token(
                code, client_id, client_secret, redirect_uri, code_verifier
            )
            
            if not success:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": "invalid_grant",
                        "error_description": error
                    })
                }
            
            logger.info(f"Issued access token for client: {client_id}")
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                    "Pragma": "no-cache"
                },
                "body": json.dumps(token_response)
            }
        
        # Handle refresh token flow
        elif grant_type == 'refresh_token':
            refresh_token = token_params.get('refresh_token')
            client_secret = token_params.get('client_secret')
            
            if not refresh_token:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": "invalid_request",
                        "error_description": "Missing refresh_token"
                    })
                }
            
            success, token_response, error = oauth_handler.refresh_access_token(
                refresh_token, client_id, client_secret
            )
            
            if not success:
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "error": "invalid_grant",
                        "error_description": error
                    })
                }
            
            logger.info(f"Refreshed access token for client: {client_id}")
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                    "Pragma": "no-cache"
                },
                "body": json.dumps(token_response)
            }
        
        else:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "unsupported_grant_type",
                    "error_description": f"Grant type '{grant_type}' is not supported"
                })
            }
    
    except json.JSONDecodeError as e:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "invalid_request",
                "error_description": f"Invalid JSON: {str(e)}"
            })
        }
    except Exception as e:
        logger.error(f"OAuth token error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "error": "server_error",
                "error_description": str(e)
            })
        }

# Local test mode
if __name__ == "__main__":
    # Test health endpoint
    health_event = {
        "version": "2.0",
        "routeKey": "GET /health",
        "rawPath": "/health",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {
                "method": "GET", 
                "path": "/health", 
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1"
            },
            "requestId": "test-health-request-id"
        },
        "body": "",
        "isBase64Encoded": False,
    }

    logger.info("Testing direct Lambda handler...")
    logger.info("Testing health endpoint...")
    result = lambda_handler(health_event, None)
    logger.info("Health response:")
    logger.info(f"Status Code: {result.get('statusCode')}")
    logger.info(f"Body: {result.get('body')}")
    
    # Test MCP tools/list endpoint
    mcp_event = {
        "version": "2.0",
        "routeKey": "POST /mcp",
        "rawPath": "/mcp",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {
                "method": "POST", 
                "path": "/mcp", 
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1"
            },
            "requestId": "test-mcp-request-id"
        },
        "body": '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}',
        "isBase64Encoded": False,
    }
    
    logger.info("Testing MCP tools/list endpoint...")
    result = lambda_handler(mcp_event, None)
    logger.info("MCP response:")
    logger.info(f"Status Code: {result.get('statusCode')}")
    logger.info(f"Body: {result.get('body')}")
    
    # Test MCP tools/call endpoint
    tool_call_event = {
        "version": "2.0",
        "routeKey": "POST /mcp",
        "rawPath": "/mcp",
        "headers": {"content-type": "application/json"},
        "requestContext": {
            "http": {
                "method": "POST", 
                "path": "/mcp", 
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1"
            },
            "requestId": "test-tool-call-request-id"
        },
        "body": '{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "summarize_csv_file", "arguments": {"filename": "sample.csv"}}}',
        "isBase64Encoded": False,
    }
    
    logger.info("Testing MCP tools/call endpoint...")
    result = lambda_handler(tool_call_event, None)
    logger.info("Tool call response:")
    logger.info(f"Status Code: {result.get('statusCode')}")
    logger.info(f"Body: {result.get('body')}")
