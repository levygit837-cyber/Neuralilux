#!/usr/bin/env python3
"""
Script para diagnosticar e corrigir problema de QR code na Evolution API.
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

async def restart_instance():
    """Reinicia a instância para forçar novo QR code."""
    print("=" * 60)
    print("REINICIANDO INSTÂNCIA 'levas'")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.put(
                f"{EVOLUTION_API_URL}/instance/restart/{INSTANCE_NAME}",
                headers=headers
            )

            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")

            if response.status_code == 200:
                print("✅ Instância reiniciada!")
                return True
            else:
                print(f"❌ Erro: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def logout_instance():
    """Desconecta a instância (logout)."""
    print("\n" + "=" * 60)
    print("FAZENDO LOGOUT DA INSTÂNCIA 'levas'")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{EVOLUTION_API_URL}/instance/logout/{INSTANCE_NAME}",
                headers=headers
            )

            print(f"Status: {response.status_code}")
            print(f"Response: {response.json()}")

            if response.status_code == 200:
                print("✅ Logout realizado!")
                return True
            else:
                print(f"❌ Erro: {response.text}")
                return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def delete_and_recreate():
    """Deleta e recria a instância."""
    print("\n" + "=" * 60)
    print("DELETANDO E RECRIANDO INSTÂNCIA")
    print("=" * 60)

    # Deletar
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(
                f"{EVOLUTION_API_URL}/instance/delete/{INSTANCE_NAME}",
                headers=headers
            )
            print(f"Delete Status: {response.status_code}")
            if response.status_code == 200:
                print("✅ Instância deletada!")
    except Exception as e:
        print(f"⚠️ Erro ao deletar (pode não existir): {e}")

    # Aguardar 2 segundos
    await asyncio.sleep(2)

    # Criar nova
    data = {
        "instanceName": INSTANCE_NAME,
        "integration": "WHATSAPP-BAILEYS",
        "qrcode": True,
        "webhook": {
            "enabled": False  # Desabilita webhook por enquanto
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EVOLUTION_API_URL}/instance/create",
                headers=headers,
                json=data
            )
            print(f"Create Status: {response.status_code}")
            result = response.json()
            print(f"Response: {result}")

            if response.status_code == 201 or response.status_code == 200:
                print("✅ Instância criada!")
                if result.get('qrcode', {}).get('base64'):
                    print(f"\n🎉 QR CODE DISPONÍVEL!")
                    print(f"Base64: {result.get('qrcode', {}).get('base64')[:100]}...")
                    return True
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def get_qr_with_query_param():
    """Tenta obter QR code usando apikey como query param."""
    print("\n" + "=" * 60)
    print("TESTANDO QR CODE COM QUERY PARAM")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Algumas versões usam query param
            response = await client.get(
                f"{EVOLUTION_API_URL}/instance/connect/{INSTANCE_NAME}?apikey={EVOLUTION_API_KEY}",
                headers={"Content-Type": "application/json"}  # sem apikey no header
            )

            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")

            if response.status_code == 200:
                result = response.json()
                if result.get('base64') or result.get('code'):
                    print("✅ QR Code obtido!")
                    return True
            return False
    except Exception as e:
        print(f"❌ Erro: {e}")
        return False


async def check_all_endpoints():
    """Verifica todos os endpoints disponíveis."""
    print("\n" + "=" * 60)
    print("VERIFICANDO ENDPOINTS ALTERNATIVOS")
    print("=" * 60)

    endpoints = [
        f"/instance/fetchInstances?instanceName={INSTANCE_NAME}",
        f"/instance/connectionState/{INSTANCE_NAME}",
        f"/instance/connect/{INSTANCE_NAME}",
    ]

    for endpoint in endpoints:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{EVOLUTION_API_URL}{endpoint}",
                    headers=headers
                )
                print(f"\n{endpoint}")
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    print(f"  Response: {response.json()}")
        except Exception as e:
            print(f"\n{endpoint}")
            print(f"  Erro: {e}")


async def main():
    print("\n🔧 DIAGNÓSTICO E CORREÇÃO - EVOLUTION API\n")

    # Primeiro, verificar estado atual
    await check_all_endpoints()

    # Tentar obter QR de diferentes formas
    qr_obtained = await get_qr_with_query_param()

    if not qr_obtained:
        print("\n⚠️  QR Code não obtido. Tentando reiniciar...")
        await restart_instance()
        await asyncio.sleep(3)
        qr_obtained = await get_qr_with_query_param()

    if not qr_obtained:
        print("\n⚠️  Ainda sem QR Code. Tentando logout...")
        await logout_instance()
        await asyncio.sleep(3)
        qr_obtained = await get_qr_with_query_param()

    if not qr_obtained:
        print("\n⚠️  Última tentativa: deletar e recriar instância...")
        qr_obtained = await delete_and_recreate()

    print("\n" + "=" * 60)
    if qr_obtained:
        print("✅ QR CODE OBTIDO COM SUCESSO!")
        print(f"Acesse: http://localhost:8081/instance/connect/{INSTANCE_NAME}")
    else:
        print("❌ Não foi possível obter QR Code automaticamente.")
        print("Tente acessar manualmente no navegador ou Postman:")
        print(f"  GET http://localhost:8081/instance/connect/{INSTANCE_NAME}")
        print(f"  Header: apikey: {EVOLUTION_API_KEY}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
