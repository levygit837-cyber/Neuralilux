#!/usr/bin/env python3
"""
Script simples para criar instância e obter QR code.
"""
import httpx
import asyncio

EVOLUTION_API_URL = "http://localhost:8081"
EVOLUTION_API_KEY = "3v0lut10n_4P1_K3y_S3cur3_2026!"
INSTANCE_NAME = "levas"

headers = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json",
}

async def create_instance_simple():
    """Cria instância sem webhook."""
    print("=" * 60)
    print("CRIANDO INSTÂNCIA (sem webhook)")
    print("=" * 60)

    data = {
        "instanceName": INSTANCE_NAME,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True
        # Sem webhook por enquanto
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EVOLUTION_API_URL}/instance/create",
                headers=headers,
                json=data
            )
            print(f"Status: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")

            if response.status_code in [200, 201]:
                print("✅ Instância criada!")
                qr = result.get('qrcode', {})
                if qr.get('base64'):
                    print("\n🎉 QR CODE DISPONÍVEL NA CRIAÇÃO!")
                    print(f"Base64: {qr.get('base64')[:150]}...")
                    return True
                return True
            elif "already exists" in str(result).lower():
                print("⚠️  Instância já existe")
                return True
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def get_qr_code():
    """Obtém QR code via endpoint connect."""
    print("\n" + "=" * 60)
    print("OBTENDO QR CODE VIA /instance/connect")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/connect/{INSTANCE_NAME}",
                headers=headers
            )
            print(f"Status: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type')}")
            print(f"Response: {response.text[:500]}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"JSON: {result}")

                    # Verificar se tem QR
                    if result.get('base64'):
                        print("\n🎉 QR CODE ENCONTRADO!")
                        print(f"Base64: {result.get('base64')[:150]}...")
                        return True
                    elif result.get('qrcode', {}).get('base64'):
                        print("\n🎉 QR CODE ENCONTRADO (nested)!")
                        print(f"Base64: {result.get('qrcode', {}).get('base64')[:150]}...")
                        return True
                    elif result.get('instance', {}).get('state') == 'open':
                        print("\n⚠️  Instância já conectada (state: open)")
                        return True
                    else:
                        print(f"\n⚠️  Sem QR code na resposta: {result}")
                        return False
                except:
                    print(f"\nResposta não é JSON: {response.text[:200]}")
                    return False
            elif response.status_code == 304:
                print("\n⚠️  304 Not Modified - QR code pode estar em cache")
                return False
            else:
                print(f"\n❌ Erro HTTP: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def check_instance():
    """Verifica estado da instância."""
    print("\n" + "=" * 60)
    print("VERIFICANDO ESTADO DA INSTÂNCIA")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/fetchInstances?instanceName={INSTANCE_NAME}",
                headers=headers
            )
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {result}")
                if isinstance(result, list) and len(result) > 0:
                    inst = result[0].get('instance', {})
                    print(f"\n📱 Instância: {inst.get('instanceName')}")
                    print(f"📊 Estado: {inst.get('status')}")
                    print(f"🔗 Integração: {inst.get('integration')}")
                    return inst.get('status')
            return None
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None


async def main():
    print("\n🔧 TESTE SIMPLIFICADO - EVOLUTION API\n")

    # Criar instância
    created = await create_instance_simple()

    if created:
        # Aguardar inicialização
        print("\n⏳ Aguardando 3 segundos para inicialização...")
        await asyncio.sleep(3)

        # Verificar estado
        state = await check_instance()

        # Tentar obter QR
        if state != 'open':
            await get_qr_code()

    print("\n" + "=" * 60)
    print("INSTRUÇÕES MANUAIS:")
    print("=" * 60)
    print(f"1. Teste no navegador:")
    print(f"   http://localhost:8081/instance/connect/{INSTANCE_NAME}")
    print(f"")
    print(f"2. Ou com curl:")
    print(f'   curl -X GET "http://localhost:8081/instance/connect/{INSTANCE_NAME}" -H "apikey: {EVOLUTION_API_KEY}"')
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
