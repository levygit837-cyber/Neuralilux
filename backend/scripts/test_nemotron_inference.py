"""
Script de diagnóstico para testar inferência do modelo Nemotron via LM Studio.

Este script conecta diretamente ao LM Studio e testa:
1. Conexão com a API
2. Resposta bruta do modelo (sem parsing)
3. Identificação de tokens thinking/response
4. Formato de resposta do modelo nemotron-3-nano-4b
"""

import asyncio
import aiohttp
import json
import os
from typing import Dict, Any, AsyncGenerator

# Configuração do LM Studio
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234")
MODEL_NAME = "nvidia/nemotron-3-nano-4b"

async def test_connection():
    """Testa conexão com LM Studio."""
    print("🔍 Testando conexão com LM Studio...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{LM_STUDIO_BASE_URL}/v1/models") as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Conexão bem-sucedida!")
                    print(f"📊 Modelos disponíveis: {json.dumps(data, indent=2)}")
                    
                    # Verificar se o modelo nemotron está disponível
                    models = data.get("data", [])
                    nemotron_available = any(
                        MODEL_NAME in model.get("id", "") 
                        for model in models
                    )
                    
                    if nemotron_available:
                        print(f"✅ Modelo {MODEL_NAME} encontrado!")
                    else:
                        print(f"⚠️  Modelo {MODEL_NAME} não encontrado na lista")
                        print("📋 Modelos disponíveis:")
                        for model in models:
                            print(f"   - {model.get('id', 'unknown')}")
                    
                    return True
                else:
                    print(f"❌ Erro na conexão: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")
        return False

async def test_simple_completion():
    """Testa uma completion simples."""
    print("\n🧪 Testando completion simples...")
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": "Olá, como você está?"
            }
        ],
        "temperature": 0.7,
        "max_tokens": 100,
        "stream": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Completion bem-sucedida!")
                    print(f"📝 Resposta bruta:")
                    print(json.dumps(data, indent=2))
                    
                    # Analisar estrutura da resposta
                    choices = data.get("choices", [])
                    if choices:
                        message = choices[0].get("message", {})
                        content = message.get("content", "")
                        print(f"\n📄 Conteúdo da resposta: '{content}'")
                        print(f"📊 Tamanho do conteúdo: {len(content)} caracteres")
                        
                        # Verificar se há tokens de thinking
                        if "<thinking>" in content or "thinking" in content.lower():
                            print("🧠 Detectado conteúdo de thinking na resposta!")
                        
                        # Verificar se a resposta está vazia
                        if not content or content.isspace():
                            print("⚠️  ATENÇÃO: Resposta está vazia!")
                    
                    return data
                else:
                    error_text = await response.text()
                    print(f"❌ Erro na completion: {response.status}")
                    print(f"📄 Erro: {error_text}")
                    return None
    except Exception as e:
        print(f"❌ Erro na completion: {e}")
        return None

async def test_streaming_completion():
    """Testa uma completion com streaming."""
    print("\n🧪 Testando completion com streaming...")
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": "Conte-me uma história curta sobre um gato."
            }
        ],
        "temperature": 0.7,
        "max_tokens": 200,
        "stream": True
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    print("✅ Streaming iniciado!")
                    
                    full_content = ""
                    thinking_tokens = []
                    response_tokens = []
                    
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        
                        if line.startswith('data: '):
                            data_str = line[6:]
                            
                            if data_str == '[DONE]':
                                print("✅ Streaming finalizado!")
                                break
                            
                            try:
                                chunk = json.loads(data_str)
                                choices = chunk.get("choices", [])
                                
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    
                                    if content:
                                        full_content += content
                                        
                                        # Verificar se é thinking token
                                        if "<thinking>" in content or "thinking" in content.lower():
                                            thinking_tokens.append(content)
                                            print(f"🧠 Thinking: '{content}'")
                                        else:
                                            response_tokens.append(content)
                                            print(f"💬 Response: '{content}'")
                            except json.JSONDecodeError:
                                pass
                    
                    print(f"\n📊 Análise do streaming:")
                    print(f"   Total de caracteres: {len(full_content)}")
                    print(f"   Thinking tokens: {len(thinking_tokens)}")
                    print(f"   Response tokens: {len(response_tokens)}")
                    
                    if thinking_tokens and not response_tokens:
                        print("⚠️  ATENÇÃO: Apenas thinking tokens encontrados!")
                        print("   O modelo pode estar gerando apenas reasoning tokens.")
                    
                    return {
                        "full_content": full_content,
                        "thinking_tokens": thinking_tokens,
                        "response_tokens": response_tokens
                    }
                else:
                    error_text = await response.text()
                    print(f"❌ Erro no streaming: {response.status}")
                    print(f"📄 Erro: {error_text}")
                    return None
    except Exception as e:
        print(f"❌ Erro no streaming: {e}")
        return None

async def test_thinking_extraction():
    """Testa extração de thinking tokens."""
    print("\n🧪 Testando extração de thinking tokens...")
    
    # Simular resposta com thinking tokens
    test_cases = [
        {
            "name": "Com thinking explícito",
            "content": "<thinking>O usuário está cumprimentando. Devo responder de forma amigável.</thinking>Olá! Estou bem, obrigado por perguntar!"
        },
        {
            "name": "Com thinking implícito",
            "content": "Analisando a pergunta... O usuário quer saber como estou. Vou responder que estou bem."
        },
        {
            "name": "Apenas thinking",
            "content": "<thinking>O usuário está fazendo uma pergunta simples. Devo responder de forma educada e amigável.</thinking>"
        },
        {
            "name": "Resposta normal",
            "content": "Olá! Estou funcionando perfeitamente, obrigado por perguntar!"
        }
    ]
    
    for test_case in test_cases:
        print(f"\n📋 Teste: {test_case['name']}")
        print(f"   Conteúdo: '{test_case['content']}'")
        
        content = test_case['content']
        
        # Verificar se há thinking
        if "<thinking>" in content:
            print("   ✅ Detectado tag <thinking>")
            
            # Extrair thinking
            thinking_start = content.find("<thinking>")
            thinking_end = content.find("</thinking>")
            
            if thinking_end != -1:
                thinking_content = content[thinking_start + 10:thinking_end]
                response_content = content[thinking_end + 11:].strip()
                
                print(f"   🧠 Thinking: '{thinking_content}'")
                print(f"   💬 Response: '{response_content}'")
                
                if not response_content:
                    print("   ⚠️  ATENÇÃO: Não há resposta após o thinking!")
            else:
                print("   ⚠️  Tag <thinking> não fechada")
        else:
            print("   ✅ Conteúdo normal (sem thinking)")

async def main():
    """Função principal."""
    print("=" * 60)
    print("🔍 DIAGNÓSTICO DE INFERÊNCIA - MODELO NEMOTRON")
    print("=" * 60)
    
    # Testar conexão
    connection_ok = await test_connection()
    
    if not connection_ok:
        print("\n❌ Não foi possível conectar ao LM Studio.")
        print("   Verifique se o LM Studio está rodando em:", LM_STUDIO_BASE_URL)
        return
    
    # Testar completion simples
    await test_simple_completion()
    
    # Testar streaming
    streaming_result = await test_streaming_completion()
    
    # Testar extração de thinking
    await test_thinking_extraction()
    
    print("\n" + "=" * 60)
    print("📊 RESUMO DO DIAGNÓSTICO")
    print("=" * 60)
    
    if streaming_result:
        thinking_count = len(streaming_result["thinking_tokens"])
        response_count = len(streaming_result["response_tokens"])
        
        if thinking_count > 0 and response_count == 0:
            print("🔴 PROBLEMA IDENTIFICADO:")
            print("   O modelo está gerando apenas thinking tokens!")
            print("   Não há tokens de resposta separados.")
            print("\n💡 SOLUÇÃO RECOMENDADA:")
            print("   1. Extrair resposta do conteúdo thinking")
            print("   2. Implementar fallback para usar thinking como resposta")
            print("   3. Modificar parser para detectar este cenário")
        elif thinking_count > 0 and response_count > 0:
            print("🟡 ATENÇÃO:")
            print("   O modelo está gerando thinking E response tokens.")
            print("   Verifique se a resposta está sendo exibida corretamente.")
        else:
            print("✅ MODELO FUNCIONANDO CORRETAMENTE:")
            print("   O modelo está gerando apenas response tokens.")
    
    print("\n🔧 PRÓXIMOS PASSOS:")
    print("   1. Se o problema for confirmado, modificar inference_service.py")
    print("   2. Implementar lógica de fallback no generate_response_node")
    print("   3. Testar com o modelo real após as modificações")

if __name__ == "__main__":
    asyncio.run(main())