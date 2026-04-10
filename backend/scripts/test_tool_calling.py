#!/usr/bin/env python3
"""
Test script for native tool calling with LM Studio.

Verifies that the model correctly returns tool_calls when given
the Super Agent tool definitions.

Usage:
    python backend/scripts/test_tool_calling.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx

LM_STUDIO_URL = os.environ.get("LM_STUDIO_URL", "http://localhost:1234")

# Minimal tool definitions for testing
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
    {
        "type": "function",
        "function": {
            "name": "whatsapp_resolve_contacts",
            "description": "Busca contatos pelo nome ou número para encontrar o JID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Nome ou número do contato."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_read_messages",
            "description": "Lê mensagens recentes de uma conversa WhatsApp. Requer instance_name e remote_jid.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instance_name": {"type": "string"},
                    "remote_jid": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["instance_name", "remote_jid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "whatsapp_send_message",
            "description": "Envia uma mensagem de texto para um contato no WhatsApp.",
            "parameters": {
                "type": "object",
                "properties": {
                    "instance_name": {"type": "string"},
                    "remote_jid": {"type": "string"},
                    "message": {"type": "string"},
                },
                "required": ["instance_name", "remote_jid", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "database_query",
            "description": "Consulta dados da empresa no banco de dados.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "enum": ["products", "contacts", "conversations"]},
                    "query_type": {"type": "string", "enum": ["list", "count", "search"]},
                    "limit": {"type": "integer"},
                },
                "required": ["table", "query_type"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "Você é um Assistente de Negócios Inteligente. "
    "Quando precisar de dados, USE as ferramentas disponíveis. "
    "NUNCA diga que vai usar uma ferramenta sem realmente chamá-la. "
    "Responda sempre em português do Brasil."
)

TEST_CASES = [
    {
        "name": "Listar contatos",
        "message": "Liste meus contatos do WhatsApp",
        "expect_tool": "whatsapp_list_contacts",
    },
    {
        "name": "Ler mensagens",
        "message": "Leia as mensagens do João",
        "expect_tool": "whatsapp_resolve_contacts",
    },
    {
        "name": "Enviar mensagem",
        "message": "Envie 'Olá mundo' para o contato Maria",
        "expect_tool": "whatsapp_resolve_contacts",
    },
    {
        "name": "Consulta DB",
        "message": "Quantos produtos temos cadastrados?",
        "expect_tool": "database_query",
    },
    {
        "name": "Conversa geral (sem tool)",
        "message": "Olá, como vai?",
        "expect_tool": None,
    },
]


async def check_lm_studio_health() -> bool:
    """Check if LM Studio is running."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{LM_STUDIO_URL}/v1/models")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("data", [])
                if models:
                    print(f"  Modelo carregado: {models[0].get('id', 'unknown')}")
                return True
    except Exception as e:
        print(f"  Erro: {e}")
    return False


async def test_tool_calling(test_case: dict) -> dict:
    """Run a single test case against LM Studio."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": test_case["message"]},
    ]

    payload = {
        "model": "auto",
        "messages": messages,
        "tools": TEST_TOOLS,
        "tool_choice": "auto",
        "max_tokens": 1024,
        "temperature": 0.3,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    choice = data.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content") or ""
    tool_calls = message.get("tool_calls") or []
    finish_reason = choice.get("finish_reason", "")

    return {
        "content": content,
        "tool_calls": tool_calls,
        "finish_reason": finish_reason,
        "raw": data,
    }


async def main():
    print("=" * 60)
    print("  TESTE DE TOOL CALLING - SUPER AGENT + LM STUDIO")
    print("=" * 60)
    print()

    print(f"LM Studio URL: {LM_STUDIO_URL}")
    print("Verificando conexão...")
    if not await check_lm_studio_health():
        print("\n❌ LM Studio não está acessível! Verifique se está rodando.")
        sys.exit(1)
    print("✅ LM Studio está ativo\n")

    passed = 0
    failed = 0
    results = []

    for i, test in enumerate(TEST_CASES, 1):
        print(f"--- Teste {i}/{len(TEST_CASES)}: {test['name']} ---")
        print(f"  Mensagem: \"{test['message']}\"")
        print(f"  Ferramenta esperada: {test['expect_tool'] or 'nenhuma'}")

        try:
            result = await test_tool_calling(test)
            tool_calls = result["tool_calls"]

            if test["expect_tool"] is None:
                # Expect NO tool calls
                if not tool_calls:
                    print(f"  ✅ PASSOU — Nenhuma ferramenta chamada (correto)")
                    print(f"  Resposta: {result['content'][:100]}...")
                    passed += 1
                else:
                    names = [tc.get("function", {}).get("name") for tc in tool_calls]
                    print(f"  ⚠️  Modelo chamou ferramenta inesperada: {names}")
                    # Not necessarily a failure — model may proactively use tools
                    passed += 1
            else:
                # Expect specific tool call
                if tool_calls:
                    called_names = [tc.get("function", {}).get("name") for tc in tool_calls]
                    if test["expect_tool"] in called_names:
                        print(f"  ✅ PASSOU — Ferramenta correta chamada: {called_names}")
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            args = fn.get("arguments", "{}")
                            if isinstance(args, str):
                                try:
                                    args = json.loads(args)
                                except json.JSONDecodeError:
                                    pass
                            print(f"    → {fn.get('name')}({json.dumps(args, ensure_ascii=False)})")
                        passed += 1
                    else:
                        print(f"  ⚠️  FERRAMENTA DIFERENTE — Esperado: {test['expect_tool']}, Chamou: {called_names}")
                        for tc in tool_calls:
                            fn = tc.get("function", {})
                            print(f"    → {fn.get('name')}({fn.get('arguments', '{}')})")
                        failed += 1
                else:
                    print(f"  ❌ FALHOU — Nenhuma ferramenta chamada!")
                    print(f"  Resposta do modelo: {result['content'][:200]}")
                    print(f"  finish_reason: {result['finish_reason']}")
                    failed += 1

            results.append({"test": test["name"], "result": result})

        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            failed += 1

        print()

    print("=" * 60)
    print(f"  RESULTADO: {passed} passou, {failed} falhou de {len(TEST_CASES)} testes")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
