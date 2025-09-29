#!/usr/bin/env python3
"""
Test the HTTP endpoints of the MCP server.
"""

import requests
import json
import time

def test_http_endpoints():
    """Test the HTTP endpoints of the MCP server."""
    base_url = "http://127.0.0.1:8000"
    
    print("🔧 Testing MCP Server HTTP Endpoints")
    print("=" * 50)
    
    # Test 1: Health endpoint
    print("1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Health check passed: {response.json()}")
        else:
            print(f"   ❌ Health check failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
    
    # Test 2: MCP initialize (this should work)
    print("\n2. Testing MCP initialize...")
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    try:
        response = requests.post(f"{base_url}/mcp", headers=headers, data=json.dumps(initialize_request), stream=True)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Initialize successful")
            response_data = ""
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    response_data += chunk.decode('utf-8')
            
            # Parse the response
            if "event: message" in response_data:
                lines = response_data.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        data = json.loads(line[6:])
                        print(f"   📋 Server info: {data.get('result', {}).get('serverInfo', {})}")
                        print(f"   📋 Capabilities: {data.get('result', {}).get('capabilities', {})}")
                        break
        else:
            print(f"   ❌ Initialize failed: {response.text}")
    except Exception as e:
        print(f"   ❌ Initialize error: {e}")
    
    print("\n📝 Note: Subsequent MCP requests (tools/list, tools/call) will fail")
    print("   because streamable HTTP transport requires session management.")
    print("   This is expected behavior - use the MCP proxy for full functionality.")

if __name__ == "__main__":
    test_http_endpoints()
