#!/usr/bin/env python3
"""
Direct testing of the MCP server functionality without HTTP transport.
This tests the core server logic directly.
"""

import asyncio
import json
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import mcp

async def test_server_directly():
    """Test the MCP server functionality directly."""
    print("🔧 Testing MCP Server Functionality Directly")
    print("=" * 50)
    
    try:
        # Test 1: Get available tools
        print("1. Testing tools discovery...")
        tools = await mcp.get_tools()
        print(f"   ✅ Found {len(tools)} tools:")
        for tool_name, tool_obj in tools.items():
            print(f"      - {tool_name}: {tool_obj.description}")
        
        # Test 2: Test say_hello tool
        print("\n2. Testing say_hello tool...")
        hello_tool = tools.get('say_hello')
        if hello_tool:
            result = hello_tool.fn(name="Test User")
            print(f"   ✅ say_hello result: {result}")
        else:
            print("   ❌ say_hello tool not found")
        
        # Test 3: Test say_goodbye tool
        print("\n3. Testing say_goodbye tool...")
        goodbye_tool = tools.get('say_goodbye')
        if goodbye_tool:
            result = goodbye_tool.fn(name="Test User")
            print(f"   ✅ say_goodbye result: {result}")
        else:
            print("   ❌ say_goodbye tool not found")
        
        # Test 4: Test get_greeting_info tool
        print("\n4. Testing get_greeting_info tool...")
        info_tool = tools.get('get_greeting_info')
        if info_tool:
            result = info_tool.fn()
            print(f"   ✅ get_greeting_info result: {result}")
        else:
            print("   ❌ get_greeting_info tool not found")
        
        # Test 5: Get available resources
        print("\n5. Testing resources discovery...")
        resources = await mcp.get_resources()
        print(f"   ✅ Found {len(resources)} resources:")
        for resource_uri, resource_obj in resources.items():
            print(f"      - {resource_uri}: {resource_obj.description}")
        
        # Test 6: Test system status resource
        print("\n6. Testing system status resource...")
        status_resource = resources.get('system://status')
        if status_resource:
            result = status_resource.fn()
            print(f"   ✅ system status: {json.dumps(result, indent=2)}")
        else:
            print("   ❌ system status resource not found")
        
        # Test 7: Test system info resource
        print("\n7. Testing system info resource...")
        info_resource = resources.get('system://info')
        if info_resource:
            result = info_resource.fn()
            print(f"   ✅ system info: {json.dumps(result, indent=2)}")
        else:
            print("   ❌ system info resource not found")
        
        print("\n🎉 All direct tests completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_server_directly())
