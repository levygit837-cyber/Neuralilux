"""
Simple test script for Vertex AI inference with fallback.
Run directly with: python3 test_vertex_simple.py
"""
import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, '/home/levybonito/Neuralilux/backend')

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from app.services.inference_service import get_inference_service_with_fallback


async def test_vertex_basic():
    """Test basic Vertex AI inference."""
    print("=" * 60)
    print("Testing Vertex AI Inference with Fallback")
    print("=" * 60)
    
    # Check for API keys
    vertex_key = os.getenv("VERTEX_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    print(f"\nEnvironment Check:")
    print(f"  VERTEX_API_KEY: {'✓ Set' if vertex_key else '✗ Not set'}")
    print(f"  GEMINI_API_KEY: {'✓ Set' if gemini_key else '✗ Not set'}")
    
    if not vertex_key and not gemini_key:
        print("\n❌ ERROR: Neither VERTEX_API_KEY nor GEMINI_API_KEY is set")
        print("   Please set at least one API key to run tests")
        return False
    
    # Test 1: Basic chat completion
    print("\n" + "-" * 60)
    print("Test 1: Basic Chat Completion")
    print("-" * 60)
    
    try:
        service = get_inference_service_with_fallback("whatsapp_agent")
        print(f"✓ Service initialized: {service.__class__.__name__}")
        print(f"  Agent type: {service.agent_type}")
        print(f"  Primary service: {service.primary_service.__class__.__name__}")
        print(f"  Secondary service: {service.secondary_service.__class__.__name__}")
        
        messages = [{"role": "user", "content": "What is 2 + 2? Answer in one word."}]
        
        print(f"\nSending request: {messages[0]['content']}")
        result = await service.chat_completion(messages)
        
        print(f"\n✓ Response received:")
        print(f"  Content: {result.get('content', '')[:100]}...")
        print(f"  Model: {result.get('model', 'unknown')}")
        print(f"  Finish reason: {result.get('finish_reason', 'unknown')}")
        
    except Exception as e:
        print(f"\n❌ Test 1 failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 2: Chat completion with system prompt
    print("\n" + "-" * 60)
    print("Test 2: Chat Completion with System Prompt")
    print("-" * 60)
    
    try:
        messages = [{"role": "user", "content": "Hello!"}]
        system_prompt = "You are a helpful assistant. Keep responses brief."
        
        print(f"System prompt: {system_prompt}")
        print(f"Message: {messages[0]['content']}")
        
        result = await service.chat_completion(messages, system_prompt=system_prompt)
        
        print(f"\n✓ Response received:")
        print(f"  Content: {result.get('content', '')[:100]}...")
        
    except Exception as e:
        print(f"\n❌ Test 2 failed: {str(e)}")
        return False
    
    # Test 3: Tool calling
    print("\n" + "-" * 60)
    print("Test 3: Tool Calling")
    print("-" * 60)
    
    try:
        tools = [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                    },
                    "required": ["location"],
                },
            }
        ]
        
        messages = [{"role": "user", "content": "What's the weather in Tokyo?"}]
        
        print(f"Tools: {[t['name'] for t in tools]}")
        print(f"Message: {messages[0]['content']}")
        
        result = await service.chat_completion_with_tools(messages, tools)
        
        print(f"\n✓ Response received:")
        print(f"  Content: {result.get('content', '')[:100]}...")
        print(f"  Tool calls: {result.get('tool_calls', [])}")
        
    except Exception as e:
        print(f"\n❌ Test 3 failed: {str(e)}")
        # This is not critical, so we continue
        print("  (This test may fail if the provider doesn't support tools)")
    
    print("\n" + "=" * 60)
    print("✓ All critical tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_vertex_basic())
    sys.exit(0 if success else 1)
