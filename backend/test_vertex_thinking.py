"""
Test script to verify native Vertex AI thinking token parsing.
Run directly with: python3 test_vertex_thinking.py
"""
import asyncio
import os
import sys

# Add backend to path
sys.path.insert(0, '/home/levybonito/Projetos/Neuralilux/backend')

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from app.services.vertex_inference_service import VertexInferenceService


async def test_vertex_native_thinking():
    """Test Vertex AI with native thinking configuration."""
    print("=" * 60)
    print("Testing Vertex AI Native Thinking Token Support")
    print("=" * 60)
    
    # Check for API key
    vertex_key = os.getenv("VERTEX_API_KEY")
    
    print(f"\nEnvironment Check:")
    print(f"  VERTEX_API_KEY: {'✓ Set' if vertex_key else '✗ Not set'}")
    
    if not vertex_key:
        print("\n❌ ERROR: VERTEX_API_KEY is not set")
        return False
    
    # Initialize service with Gemini 3 model that officially supports thinking
    print("\nInitializing Vertex AI service with Gemini 3 model...")
    service = VertexInferenceService(
        api_key=vertex_key,
        model="gemini-3-flash-preview",
        max_tokens=2048,
        temperature=0.7,
    )
    
    print("=" * 60)
    print("Vertex AI Native Thinking Test - Complex Reasoning")
    print("=" * 60)
    
    # Check for API key
    print(f"\nEnvironment Check:")
    print(f"  VERTEX_API_KEY: {'✓ Set' if vertex_key else '✗ Not set'}")
    
    if not vertex_key:
        print("\n❌ ERROR: VERTEX_API_KEY is not set")
        return False
    
    print(f"\n✓ Service initialized with model: {service.model}")
    
    # Complex query that requires multi-step reasoning
    complex_query = """
    Analyze this business scenario step by step and provide your reasoning:

    A restaurant has the following data:
    - Daily revenue: $3,500 on weekdays, $5,200 on weekends
    - Food cost: 35% of revenue
    - Labor cost: 25% of revenue
    - Rent: $1,200 per month
    - Utilities: $400 per month
    
    Questions to answer:
    1. What is the total monthly revenue?
    2. What is the total monthly food cost?
    3. What is the total monthly labor cost?
    4. What is the total monthly profit?
    5. What is the profit margin percentage?
    
    Show all your calculations and reasoning step by step.
    """
    
    messages = [
        {"role": "user", "content": complex_query}
    ]
    
    thinking_tokens = []
    response_tokens = []
    
    async def on_thinking_token(token: str):
        thinking_tokens.append(token)
        print(f"[THINKING] {token}")
    
    async def on_response_token(token: str):
        response_tokens.append(token)
        # Don't print every response token to avoid spam, just accumulate
        # print(f"[RESPONSE] {token}")
    
    try:
        print("Starting inference with complex reasoning query...")
        result = await service.stream_chat_completion_with_tools(
            messages=messages,
            tools=[],
            max_tokens=2048,
            temperature=0.7,
            on_thinking_token=on_thinking_token,
            on_response_token=on_response_token,
        )
        
        print("\n" + "=" * 60)
        print("Test Results:")
        print("=" * 60)
        print(f"Thinking tokens received: {len(thinking_tokens)}")
        print(f"Response tokens received: {len(response_tokens)}")
        print(f"Total thinking length: {sum(len(t) for t in thinking_tokens)}")
        print(f"Total response length: {sum(len(t) for t in response_tokens)}")
        
        if thinking_tokens:
            print(f"\n=== THINKING CONTENT ===")
            print(''.join(thinking_tokens))
            print("=" * 60)
        
        if response_tokens:
            print(f"\n=== RESPONSE CONTENT ===")
            print(''.join(response_tokens))
            print("=" * 60)
        
        # Check if thinking contains actual reasoning content
        thinking_content = ''.join(thinking_tokens)
        has_reasoning = any(keyword in thinking_content.lower() for keyword in 
                           ['calculate', 'multiply', 'add', 'subtract', 'step', 'first', 'then', 
                            'revenue', 'cost', 'profit', 'margin', '%'])
        
        print(f"\nReasoning detected in thinking: {has_reasoning}")
        print(f"Test {'PASSED' if (thinking_tokens and has_reasoning) else 'FAILED'}")
        
        return thinking_tokens and has_reasoning
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_vertex_native_thinking())
    print(f"\n{'=' * 60}")
    print(f"FINAL RESULT: {'PASSED - Real thinking tokens detected' if success else 'FAILED - No real thinking tokens'}")
    print(f"{'=' * 60}")
    sys.exit(0 if success else 1)
