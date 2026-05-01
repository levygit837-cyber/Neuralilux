"""
Test script to check if Vertex AI supports explicit thinking/reasoning tokens.
Try different models and configurations.
"""
import asyncio
import os
import sys
import warnings

# Add backend to path
sys.path.insert(0, '/home/levybonito/Projetos/Neuralilux/backend')

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

# Suppress Pydantic warnings from google.genai
warnings.filterwarnings("ignore", message="Field name .* shadows an attribute in parent")

from google import genai
from google.genai.types import GenerateContentConfig, Content, Part


async def test_vertex_explicit_thinking():
    """Test Vertex AI with different models to check for thinking token support."""
    print("=" * 60)
    print("Testing Vertex AI for Explicit Thinking Token Support")
    print("=" * 60)
    
    vertex_key = os.getenv("VERTEX_API_KEY")
    print(f"\nVERTEX_API_KEY: {'✓ Set' if vertex_key else '✗ Not set'}")
    
    if not vertex_key:
        print("\n❌ ERROR: VERTEX_API_KEY is not set")
        return False
    
    client = genai.Client(vertexai=True, api_key=vertex_key)
    
    # Test different models
    models_to_test = [
        "gemini-3.1-flash-lite-preview",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
    ]
    
    for model in models_to_test:
        print(f"\n{'=' * 60}")
        print(f"Testing model: {model}")
        print(f"{'=' * 60}")
        
        try:
            messages = [
                Content(role="user", parts=[Part(text="Think step by step: What is 15 x 23?")])
            ]
            
            config = GenerateContentConfig(
                system_instruction="You are a helpful assistant. Think step by step before answering.",
                max_output_tokens=2048,
                temperature=0.7,
            )
            
            print(f"Sending request...")
            response = client.models.generate_content(
                model=model,
                contents=messages,
                config=config,
            )
            
            print(f"\n✓ Response received")
            
            # Check response structure
            if response.candidates:
                candidate = response.candidates[0]
                print(f"  Finish reason: {candidate.finish_reason}")
                
                if candidate.content and candidate.content.parts:
                    for idx, part in enumerate(candidate.content.parts):
                        if part.text:
                            print(f"\n  Part {idx} (text):")
                            print(f"    {part.text[:200]}...")
                        elif part.function_call:
                            print(f"\n  Part {idx} (function_call):")
                            print(f"    Name: {part.function_call.name}")
                
                # Check for any special fields that might contain thinking
                print(f"\n  Checking for special fields...")
                print(f"  Has thought field: {hasattr(candidate, 'thought')}")
                print(f"  Has reasoning field: {hasattr(candidate, 'reasoning')}")
                print(f"  Has thinking field: {hasattr(candidate, 'thinking')}")
                
                # Check raw response attributes
                print(f"\n  Candidate attributes:")
                for attr in dir(candidate):
                    if not attr.startswith('_'):
                        print(f"    - {attr}")
                
            # Check usage metadata
            if response.usage_metadata:
                print(f"\n  Usage metadata:")
                print(f"    Prompt tokens: {response.usage_metadata.prompt_token_count}")
                print(f"    Candidates tokens: {response.usage_metadata.candidates_token_count}")
                print(f"    Total tokens: {response.usage_metadata.total_token_count}")
                
                # Check for thinking token counts
                if hasattr(response.usage_metadata, 'thought_token_count'):
                    print(f"    Thought tokens: {response.usage_metadata.thought_token_count}")
        
        except Exception as e:
            print(f"\n❌ Error with model {model}: {str(e)}")
            continue
    
    print("\n" + "=" * 60)
    print("✓ All model tests completed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_vertex_explicit_thinking())
    sys.exit(0 if success else 1)
