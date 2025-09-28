#!/usr/bin/env python3
"""
Direct AWS Lambda handler for FastMCP server without Mangum.
This bypasses ASGI issues by handling MCP protocol directly.
"""

import logging
import time
import json
import asyncio
from server import mcp

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
        # Parse the API Gateway event
        http_method = event.get('requestContext', {}).get('http', {}).get('method', '')
        path = event.get('rawPath', '')
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        logger.info(f"Processing {http_method} {path}")
        
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
        
        # Handle MCP endpoint
        elif path == '/mcp' and http_method == 'POST':
            return handle_mcp_request(body, headers)
        
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

def handle_mcp_request(body, headers):
    """Handle MCP protocol requests directly."""
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
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": "Internal error",
                        "data": f"Tool execution failed: {str(e)}"
                    }
                }
        
        elif method == 'initialize':
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "daap-mcp-server",
                        "version": "1.0.0"
                    }
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
        return {
            "jsonrpc": "2.0",
            "id": request.get('id'),
            "error": {
                "code": -32603,
                "message": "Internal error",
                "data": str(e)
            }
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
