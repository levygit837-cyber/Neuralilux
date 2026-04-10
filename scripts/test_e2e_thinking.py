#!/usr/bin/env python3
"""
End-to-end test for streaming thinking tokens from super agent to frontend.

Tests the complete flow:
1. Send message to super agent API
2. Connect to Socket.IO
3. Verify thinking_token events are received
"""

import asyncio
import sys
import time
from typing import Any

import socketio
import structlog

logger = structlog.get_logger()

# Configuration
API_BASE_URL = "http://localhost:9000"
SOCKET_URL = "http://localhost:9000"
SOCKET_PATH = "realtime/socket.io"
TEST_MESSAGE = "Liste os produtos disponíveis"
TEST_SESSION_ID = f"test-session-{int(time.time())}"

# Track received events
received_events: list[dict[str, Any]] = []
thinking_tokens: list[str] = []


async def test_e2e_thinking_stream():
    """Test end-to-end thinking stream from API to Socket.IO."""

    print("=" * 60)
    print("  END-TO-END THINKING STREAM TEST")
    print("=" * 60)
    print(f"API URL: {API_BASE_URL}")
    print(f"Socket URL: {SOCKET_URL}")
    print(f"Test message: {TEST_MESSAGE}")
    print(f"Session ID: {TEST_SESSION_ID}")
    print()

    # Create Socket.IO client
    sio = socketio.AsyncClient(logger=False, engineio_logger=False)

    @sio.event
    async def connect():
        logger.info("Socket.IO connected")
        print("✅ Socket.IO connected")
        # Join agent chat room
        await sio.emit("join_agent_chat", {"sessionId": TEST_SESSION_ID})
        print(f"✅ Joined agent chat room: {TEST_SESSION_ID}")

    @sio.event
    async def disconnect():
        logger.info("Socket.IO disconnected")
        print("❌ Socket.IO disconnected")

    @sio.on("thinking_event")
    async def on_thinking_event(payload: dict[str, Any]):
        received_events.append(payload)
        event = payload.get("event")
        data = payload.get("data", {})

        if event == "thinking_token":
            token = data.get("token", "")
            thinking_tokens.append(token)
            print(f"[THINK] {token}", end="", flush=True)
        elif event == "thinking_start":
            print("\n🧠 Thinking started...")
        elif event == "thinking_end":
            summary = data.get("summary", "")
            print(f"\n✅ Thinking ended. Summary: {summary}")

    # Connect to Socket.IO
    try:
        await sio.connect(
            SOCKET_URL,
            socketio_path="realtime/socket.io",
            auth={"guestAgentChat": True},
        )
    except Exception as exc:
        print(f"❌ Failed to connect to Socket.IO: {exc}")
        return False

    # Wait for connection to establish
    await asyncio.sleep(1)

    # Send message to super agent API
    print(f"\n📤 Sending message to super agent API...")
    import httpx

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/agents/chat",
                json={
                    "message": TEST_MESSAGE,
                    "session_id": TEST_SESSION_ID,
                },
            )

            if response.status_code != 200:
                print(f"❌ API request failed: {response.status_code}")
                print(response.text)
                return False

            result = response.json()
            print(f"✅ API response received")
            print(f"   Response: {result.get('response', '')[:100]}...")

    except Exception as exc:
        print(f"❌ API request failed: {exc}")
        return False

    # Wait for thinking events to arrive
    print("\n⏳ Waiting for thinking events...")
    await asyncio.sleep(5)

    # Disconnect
    await sio.disconnect()

    # Analyze results
    print("\n" + "=" * 60)
    print("  TEST RESULTS")
    print("=" * 60)
    print(f"Total events received: {len(received_events)}")
    print(f"Thinking tokens received: {len(thinking_tokens)}")

    if thinking_tokens:
        full_thinking = "".join(thinking_tokens)
        print(f"\nFull thinking content ({len(full_thinking)} chars):")
        print("-" * 60)
        print(full_thinking[:500])
        if len(full_thinking) > 500:
            print(f"... (truncated, total {len(full_thinking)} chars)")
        print("-" * 60)

    # Verify success
    success = len(thinking_tokens) > 0

    if success:
        print("\n✅ TEST PASSED - Thinking tokens received via Socket.IO")
    else:
        print("\n❌ TEST FAILED - No thinking tokens received")
        print("\nReceived events:")
        for event in received_events:
            print(f"  - {event.get('event')}: {event.get('data', {})}")

    return success


if __name__ == "__main__":
    success = asyncio.run(test_e2e_thinking_stream())
    sys.exit(0 if success else 1)
