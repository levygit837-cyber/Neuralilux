#!/usr/bin/env python3
"""
Test script for streaming thinking tokens from LM Studio.

Verifies that:
1. SSE streaming works with the model
2. <think> tags or reasoning fields are detected
3. Content tokens are separated from thinking tokens
4. Tool call deltas are accumulated correctly

Usage:
    python backend/scripts/test_thinking_stream.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")

# Minimal tools for testing
TEST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "whatsapp_list_contacts",
            "description": "Lista os contatos da empresa no WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Filtro de busca por nome."},
                    "limit": {"type": "integer", "description": "Máximo de contatos."},
                },
                "required": [],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Você é um Assistente de Negócios Inteligente. "
    "Quando precisar de dados, USE as ferramentas disponíveis. "
    "Pense passo a passo antes de responder."
)


async def test_raw_stream():
    """Test raw SSE stream from LM Studio to see what delta fields come back."""
    print("\n" + "=" * 60)
    print("  TEST 1: Raw SSE Stream (general question)")
    print("=" * 60)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Olá, como vai você?"},
    ]

    payload = {
        "model": "auto",
        "messages": messages,
        "tools": TEST_TOOLS,
        "tool_choice": "auto",
        "max_tokens": 512,
        "temperature": 0.4,
        "stream": True,
    }

    print(f"\nStreaming from {LM_STUDIO_URL}/v1/chat/completions ...")
    print("-" * 60)

    all_content = []
    all_reasoning = []
    chunk_count = 0
    has_think_tags = False
    delta_fields_seen = set()

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", f"{LM_STUDIO_URL}/v1/chat/completions", json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                print(f"ERROR: HTTP {resp.status_code}: {body.decode()[:300]}")
                return

            buffer = ""
            async for text_chunk in resp.aiter_text():
                buffer += text_chunk

                while "\n" in buffer:
                    line_end = buffer.find("\n")
                    line = buffer[:line_end].strip()
                    buffer = buffer[line_end + 1:]

                    if not line or line == "data: [DONE]":
                        if line == "data: [DONE]":
                            print("\n[DONE]")
                        continue

                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    chunk_count += 1

                    # Track all fields we see in delta
                    for key in delta:
                        if delta[key]:
                            delta_fields_seen.add(key)

                    # Check reasoning fields
                    reasoning = delta.get("reasoning") or delta.get("reasoning_content") or ""
                    if reasoning:
                        all_reasoning.append(reasoning)
                        print(f"[REASONING] {reasoning}", end="", flush=True)

                    # Check content
                    content = delta.get("content") or ""
                    if content:
                        all_content.append(content)
                        if "<think>" in content or "</think>" in content:
                            has_think_tags = True
                        print(f"{content}", end="", flush=True)

                    # Check tool_calls
                    tc = delta.get("tool_calls")
                    if tc:
                        print(f"\n[TOOL_CALL_DELTA] {json.dumps(tc, ensure_ascii=False)}")

    full_content = "".join(all_content)
    full_reasoning = "".join(all_reasoning)

    print("\n" + "-" * 60)
    print(f"Total SSE chunks: {chunk_count}")
    print(f"Delta fields seen: {delta_fields_seen}")
    print(f"Has <think> tags in content: {has_think_tags}")
    print(f"Has reasoning field: {bool(full_reasoning)}")
    print(f"Content length: {len(full_content)} chars")
    if full_reasoning:
        print(f"Reasoning length: {len(full_reasoning)} chars")
        print(f"Reasoning preview: {full_reasoning[:200]}...")
    if has_think_tags:
        print(f"Content preview (with tags): {full_content[:300]}...")


async def test_stream_with_tool():
    """Test SSE stream with a message that should trigger tool calls."""
    print("\n\n" + "=" * 60)
    print("  TEST 2: Raw SSE Stream (tool-triggering question)")
    print("=" * 60)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Liste meus contatos do WhatsApp"},
    ]

    payload = {
        "model": "auto",
        "messages": messages,
        "tools": TEST_TOOLS,
        "tool_choice": "auto",
        "max_tokens": 512,
        "temperature": 0.3,
        "stream": True,
    }

    print(f"\nStreaming from {LM_STUDIO_URL}/v1/chat/completions ...")
    print("-" * 60)

    all_content = []
    all_reasoning = []
    tool_calls_acc = {}
    chunk_count = 0
    has_think_tags = False
    delta_fields_seen = set()

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", f"{LM_STUDIO_URL}/v1/chat/completions", json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                print(f"ERROR: HTTP {resp.status_code}: {body.decode()[:300]}")
                return

            buffer = ""
            async for text_chunk in resp.aiter_text():
                buffer += text_chunk

                while "\n" in buffer:
                    line_end = buffer.find("\n")
                    line = buffer[:line_end].strip()
                    buffer = buffer[line_end + 1:]

                    if not line or line == "data: [DONE]":
                        if line == "data: [DONE]":
                            print("\n[DONE]")
                        continue

                    if not line.startswith("data: "):
                        continue

                    data_str = line[6:]
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue

                    delta = choices[0].get("delta", {})
                    chunk_count += 1

                    for key in delta:
                        if delta[key]:
                            delta_fields_seen.add(key)

                    reasoning = delta.get("reasoning") or delta.get("reasoning_content") or ""
                    if reasoning:
                        all_reasoning.append(reasoning)
                        print(f"[R]{reasoning}", end="", flush=True)

                    content = delta.get("content") or ""
                    if content:
                        all_content.append(content)
                        if "<think>" in content or "</think>" in content:
                            has_think_tags = True
                        print(f"{content}", end="", flush=True)

                    tc_deltas = delta.get("tool_calls") or []
                    for tc_delta in tc_deltas:
                        idx = tc_delta.get("index", 0)
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {
                                "id": tc_delta.get("id", ""),
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }
                        entry = tool_calls_acc[idx]
                        if tc_delta.get("id"):
                            entry["id"] = tc_delta["id"]
                        fn_delta = tc_delta.get("function") or {}
                        if fn_delta.get("name"):
                            entry["function"]["name"] += fn_delta["name"]
                        if fn_delta.get("arguments"):
                            entry["function"]["arguments"] += fn_delta["arguments"]
                        print(f"\n[TC idx={idx}] {json.dumps(tc_delta, ensure_ascii=False)}", end="", flush=True)

    full_content = "".join(all_content)
    full_reasoning = "".join(all_reasoning)

    print("\n" + "-" * 60)
    print(f"Total SSE chunks: {chunk_count}")
    print(f"Delta fields seen: {delta_fields_seen}")
    print(f"Has <think> tags: {has_think_tags}")
    print(f"Has reasoning field: {bool(full_reasoning)}")
    print(f"Content length: {len(full_content)} chars")
    print(f"Accumulated tool calls: {len(tool_calls_acc)}")
    for idx in sorted(tool_calls_acc.keys()):
        tc = tool_calls_acc[idx]
        print(f"  Tool #{idx}: {tc['function']['name']}({tc['function']['arguments'][:100]})")

    if full_reasoning:
        print(f"Reasoning preview: {full_reasoning[:300]}...")


async def test_inference_service_stream():
    """Test using the actual InferenceService.stream_chat_completion_with_tools()."""
    print("\n\n" + "=" * 60)
    print("  TEST 3: InferenceService.stream_chat_completion_with_tools()")
    print("=" * 60)

    try:
        from app.services.inference_service import get_inference_service

        svc = get_inference_service("super_agent")

        thinking_tokens = []

        async def on_thinking(token: str) -> None:
            thinking_tokens.append(token)
            print(f"[THINK]{token}", end="", flush=True)

        print("\n--- Test 3a: General question (should get thinking tokens) ---")
        print("Sending: 'Olá, como você está?'\n")

        result = await svc.stream_chat_completion_with_tools(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Olá, como você está?"},
            ],
            tools=TEST_TOOLS,
            max_tokens=512,
            temperature=0.4,
            on_thinking_token=on_thinking,
        )

        print(f"\n\nResult content: {result['content'][:200]}")
        print(f"Tool calls: {len(result.get('tool_calls', []))}")
        print(f"Thinking tokens received: {len(thinking_tokens)}")
        if thinking_tokens:
            full_thinking = "".join(thinking_tokens)
            print(f"Full thinking ({len(full_thinking)} chars): {full_thinking[:300]}...")
        print(f"✅ Test 3a complete")

        # Test 3b: Tool-triggering question
        thinking_tokens.clear()
        print("\n--- Test 3b: Tool question (should get thinking + tool_calls) ---")
        print("Sending: 'Liste meus contatos do WhatsApp'\n")

        result2 = await svc.stream_chat_completion_with_tools(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Liste meus contatos do WhatsApp"},
            ],
            tools=TEST_TOOLS,
            max_tokens=512,
            temperature=0.3,
            on_thinking_token=on_thinking,
        )

        print(f"\n\nResult content: {result2['content'][:200]}")
        print(f"Tool calls: {len(result2.get('tool_calls', []))}")
        for tc in result2.get("tool_calls", []):
            print(f"  → {tc['function']['name']}({json.dumps(tc['function']['arguments'], ensure_ascii=False)[:100]})")
        print(f"Thinking tokens received: {len(thinking_tokens)}")
        if thinking_tokens:
            full_thinking = "".join(thinking_tokens)
            print(f"Full thinking ({len(full_thinking)} chars): {full_thinking[:300]}...")
        print(f"✅ Test 3b complete")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("=" * 60)
    print("  THINKING STREAM TEST - LM Studio")
    print("=" * 60)

    # Check LM Studio
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{LM_STUDIO_URL}/v1/models")
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                if models:
                    print(f"Model: {models[0].get('id', 'unknown')}")
            else:
                print(f"LM Studio returned {resp.status_code}")
                sys.exit(1)
    except Exception as e:
        print(f"Cannot connect to LM Studio: {e}")
        sys.exit(1)

    # Run tests
    await test_raw_stream()
    await test_stream_with_tool()
    await test_inference_service_stream()

    print("\n\n" + "=" * 60)
    print("  ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
