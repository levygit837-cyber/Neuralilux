#!/usr/bin/env python3
"""
Script de teste para verificar conexão com Evolution API e gerar QR code.
"""
import httpx
import asyncio

# Configurações
EVOLUTION_API_URL = "http://localhost:8081"
EVOLUTION_API_KEY = "3v0lut10n_4P1_K3y_S3cur3_2026!"
INSTANCE_NAME = "levas"

async def test_fetch_instances():
    """Testa o endpoint de listar instâncias."""
    print("=" * 60)
    print("TESTE 1: Fetch Instances (Listar todas as instâncias)")
    print("=" * 60)

    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/fetchInstances",
                headers=headers
            )

            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")

            if response.status_code == 200:
                instances = response.json()
                print(f"\n✅ Instâncias encontradas: {len(instances) if isinstance(instances, list) else 'N/A'}")
                if instances and isinstance(instances, list):
                    for inst in instances:
                        name = inst.get('instance', {}).get('instanceName', 'N/A')
                        status = inst.get('instance', {}).get('status', 'N/A')
                        print(f"   - {name}: {status}")
                return True
            else:
                print(f"\n❌ Erro: {response.status_code}")
                return False

    except Exception as e:
        print(f"\n❌ Erro na requisição: {e}")
        return False


async def test_create_instance():
    """Testa criar uma instância se não existir."""
    print("\n" + "=" * 60)
    print("TESTE 2: Create Instance (Criar instância 'levas')")
    print("=" * 60)

    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }

    data = {
        "instanceName": INSTANCE_NAME,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True,
        "webhook": {
            "enabled": True,
            "url": "http://host.docker.internal:8000/api/v1/webhooks/evolution",
            "byEvents": True,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EVOLUTION_API_URL}/instance/create",
                headers=headers,
                json=data
            )

            print(f"Status Code: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")

            if response.status_code == 200:
                print(f"\n✅ Instância criada com sucesso!")
                print(f"   Instance ID: {result.get('instance', {}).get('instanceId')}")
                print(f"   Hash: {result.get('hash')}")
                if result.get('qrcode', {}).get('base64'):
                    print(f"   QR Code: Disponível na resposta")
                return True
            elif response.status_code == 400 and "already exists" in response.text.lower():
                print(f"\n⚠️  Instância já existe (isso é normal)")
                return True
            else:
                print(f"\n❌ Erro ao criar instância: {response.status_code}")
                return False

    except Exception as e:
        print(f"\n❌ Erro na requisição: {e}")
        return False


async def test_get_qr_code():
    """Testa obter QR code para conexão."""
    print("\n" + "=" * 60)
    print("TESTE 3: Get QR Code (Conectar instância)")
    print("=" * 60)

    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/connect/{INSTANCE_NAME}",
                headers=headers
            )

            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")

            if response.status_code == 200:
                result = response.json()
                print(f"Response: {result}")

                # Verifica se tem QR code
                if result.get('base64'):
                    print(f"\n✅ QR Code obtido com sucesso!")
                    print(f"   Base64 (primeiros 100 chars): {result.get('base64')[:100]}...")
                    return True
                elif result.get('instance', {}).get('state') == 'open':
                    print(f"\n⚠️  Instância já está conectada (state: open)")
                    return True
                else:
                    print(f"\n⚠️  Resposta inesperada: {result}")
                    return False
            elif response.status_code == 401:
                print(f"\n❌ Erro 401: Não autorizado - Verifique a API key")
                return False
            elif response.status_code == 404:
                print(f"\n❌ Erro 404: Instância não encontrada")
                return False
            else:
                print(f"\n❌ Erro: {response.status_code}")
                print(f"Response: {response.text}")
                return False

    except httpx.HTTPStatusError as e:
        print(f"\n❌ Erro HTTP: {e.response.status_code}")
        print(f"Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"\n❌ Erro na requisição: {e}")
        return False


async def test_check_status():
    """Testa verificar status da instância."""
    print("\n" + "=" * 60)
    print("TESTE 4: Check Instance Status")
    print("=" * 60)

    headers = {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/connectionState/{INSTANCE_NAME}",
                headers=headers
            )

            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"Response: {result}")
                state = result.get('instance', {}).get('state', 'unknown')
                print(f"\n✅ Estado da instância: {state}")
                return True
            else:
                print(f"\n❌ Erro: {response.status_code}")
                print(f"Response: {response.text}")
                return False

    except Exception as e:
        print(f"\n❌ Erro na requisição: {e}")
        return False


async def main():
    print("\n🔍 TESTANDO EVOLUTION API - QR CODE\n")

    # Teste 1: Listar instâncias
    await test_fetch_instances()

    # Teste 2: Criar instância (se não existir)
    await test_create_instance()

    # Teste 3: Obter QR code
    success = await test_get_qr_code()

    # Teste 4: Verificar status
    await test_check_status()

    print("\n" + "=" * 60)
    if success:
        print("✅ TESTE CONCLUÍDO - QR Code disponível!")
    else:
        print("❌ TESTE FALHOU - Verifique os logs acima")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
