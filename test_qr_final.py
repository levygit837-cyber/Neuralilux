#!/usr/bin/env python3
"""
Script final para testar QR code na Evolution API.
Uso: python3 test_qr_final.py
"""
import httpx
import asyncio
import sys

EVOLUTION_API_URL = "http://localhost:8081"
EVOLUTION_API_KEY = "3v0lut10n_4P1_K3y_S3cur3_2026!"
INSTANCE_NAME = "levas"

headers = {
    "apikey": EVOLUTION_API_KEY,
    "Content-Type": "application/json",
}

async def test_qr_code():
    """Testa geração de QR code."""
    print("=" * 60)
    print("TESTE DE QR CODE - EVOLUTION API")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Deletar instância existente
        print("\n1. Deletando instância existente...")
        try:
            resp = await client.delete(
                f"{EVOLUTION_API_URL}/instance/delete/{INSTANCE_NAME}",
                headers=headers
            )
            print(f"   ✓ Delete: {resp.status_code}")
        except Exception as e:
            print(f"   ⚠ Delete: {e}")
        
        await asyncio.sleep(2)
        
        # 2. Criar nova instância
        print("\n2. Criando nova instância...")
        data = {
            "instanceName": INSTANCE_NAME,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True
        }
        resp = await client.post(
            f"{EVOLUTION_API_URL}/instance/create",
            headers=headers,
            json=data
        )
        result = resp.json()
        print(f"   Status: {resp.status_code}")
        print(f"   Instance Status: {result.get('instance', {}).get('status')}")
        
        if result.get('qrcode', {}).get('base64'):
            print(f"\n   🎉 QR CODE NA CRIAÇÃO!")
            print(f"   Base64: {result['qrcode']['base64'][:80]}...")
            return True
        
        # 3. Aguardar e tentar obter QR
        print("\n3. Aguardando 5 segundos...")
        await asyncio.sleep(5)
        
        print("\n4. Tentando obter QR code...")
        for i in range(10):
            resp = await client.get(
                f"{EVOLUTION_API_URL}/instance/connect/{INSTANCE_NAME}",
                headers=headers
            )
            result = resp.json()
            
            if result.get('base64') or result.get('code'):
                print(f"\n   🎉 TENTATIVA {i+1} - QR CODE OBTIDO!")
                print(f"   base64: {result.get('base64', result.get('code'))[:80]}...")
                print(f"   count: {result.get('count', 'N/A')}")
                return True
            
            print(f"   Tentativa {i+1}: {result}")
            await asyncio.sleep(3)
        
        print("\n   ❌ QR code não obtido após 10 tentativas")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_qr_code())
        print("\n" + "=" * 60)
        if success:
            print("✅ TESTE CONCLUÍDO - QR CODE FUNCIONANDO!")
        else:
            print("❌ TESTE FALHOU - QR CODE NÃO GERADO")
            print("\nVerifique:")
            print("- Se CONFIG_SESSION_PHONE_VERSION está configurado")
            print("- Logs do container: docker logs neuralilux-evolution")
        print("=" * 60)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
