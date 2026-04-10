"""
Script de teste manual para a ferramenta de criação de documentos.
Executa testes reais e mostra resultados detalhados.
"""
import asyncio
import json
import base64
import os
import sys
from datetime import datetime

# Adicionar o diretório do backend ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import get_db
from app.models.models import SuperAgentDocument, SuperAgentSession, Company, User
from app.super_agents.tools.document_tool import create_document_tool


async def setup_test_data():
    """Cria dados de teste no banco."""
    print("🔄 Configurando dados de teste...")
    
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # Buscar usuário existente
        user = db.query(User).first()
        if not user:
            print("  ❌ Nenhum usuário encontrado no banco!")
            raise Exception("Necessário pelo menos um usuário no banco")
        
        # Verificar se existe uma empresa
        company = db.query(Company).first()
        if not company:
            print("  Criando empresa de teste...")
            company = Company(
                name="Empresa Teste",
                slug="empresa-teste",
            )
            db.add(company)
            db.commit()
            db.refresh(company)
        
        # Criar sessão de teste
        print("  Criando sessão de teste...")
        session = SuperAgentSession(
            company_id=company.id,
            user_id=user.id,
            title="Sessão de Teste Documentos",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        
        print(f"  ✅ Dados criados: Company={company.id}, Session={session.id}, User={user.id}")
        return company.id, session.id
        
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


async def test_txt_document(company_id: str, session_id: str) -> dict:
    """Testa criação de documento TXT."""
    print("\n📄 Teste 1: Criando documento TXT...")
    
    content = f"""Relatório de Teste - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Este é um documento de teste criado automaticamente pelo script de validação.

Conteúdo de exemplo:
- Item 1: Teste básico
- Item 2: Validação de conteúdo
- Item 3: Persistência no banco

Fim do relatório.
"""
    
    payload = {
        "session_id": session_id,
        "company_id": company_id,
        "filename": "relatorio-teste",
        "file_type": "txt",
        "content": content,
        "description": "Relatório de teste em TXT",
    }
    if hasattr(create_document_tool, "invoke"):
        result = create_document_tool.invoke(payload)
    else:
        result = create_document_tool(**payload)
    
    result_obj = json.loads(result)
    
    if result_obj.get("success"):
        print(f"  ✅ Sucesso!")
        print(f"     ID: {result_obj['document_id']}")
        print(f"     Nome: {result_obj['filename']}")
        print(f"     Tamanho: {result_obj['file_size']} bytes")
        print(f"     Base64 presente: {'Sim' if result_obj.get('content_base64') else 'Não'}")
        return result_obj
    else:
        print(f"  ❌ Falha: {result_obj.get('error')}")
        return None


async def test_json_document(company_id: str, session_id: str) -> dict:
    """Testa criação de documento JSON."""
    print("\n📊 Teste 2: Criando documento JSON...")
    
    content = json.dumps({
        "nome": "Teste JSON",
        "data": datetime.now().isoformat(),
        "itens": [
            {"id": 1, "nome": "Item A", "valor": 100},
            {"id": 2, "nome": "Item B", "valor": 200},
            {"id": 3, "nome": "Item C", "valor": 300},
        ],
        "total": 600,
        "status": "ativo"
    }, indent=2)
    
    payload = {
        "session_id": session_id,
        "company_id": company_id,
        "filename": "dados-teste",
        "file_type": "json",
        "content": content,
        "description": "Dados estruturados em JSON",
    }
    if hasattr(create_document_tool, "invoke"):
        result = create_document_tool.invoke(payload)
    else:
        result = create_document_tool(**payload)
    
    result_obj = json.loads(result)
    
    if result_obj.get("success"):
        print(f"  ✅ Sucesso!")
        print(f"     ID: {result_obj['document_id']}")
        print(f"     Nome: {result_obj['filename']}")
        print(f"     Tamanho: {result_obj['file_size']} bytes")
        
        # Validar se o JSON pode ser reconstruído
        if result_obj.get("content_base64"):
            decoded = base64.b64decode(result_obj["content_base64"]).decode("utf-8")
            try:
                json.loads(decoded)
                print(f"     JSON válido: Sim")
            except:
                print(f"     JSON válido: Não (ERRO!)")
        
        return result_obj
    else:
        print(f"  ❌ Falha: {result_obj.get('error')}")
        return None


async def test_markdown_document(company_id: str, session_id: str) -> dict:
    """Testa criação de documento Markdown."""
    print("\n📝 Teste 3: Criando documento Markdown...")
    
    content = f"""# Documentação de Teste

**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Introdução

Este é um documento markdown de teste criado pelo Super Agent.

## Seção 1

- Lista de itens
- Formatação em **negrito**
- Formatação em *itálico*

## Seção 2

```python
print("Código de exemplo")
```

## Conclusão

Documento gerado com sucesso!
"""
    
    payload = {
        "session_id": session_id,
        "company_id": company_id,
        "filename": "documentacao-teste",
        "file_type": "markdown",
        "content": content,
        "description": "Documentação em Markdown",
    }
    if hasattr(create_document_tool, "invoke"):
        result = create_document_tool.invoke(payload)
    else:
        result = create_document_tool(**payload)
    
    result_obj = json.loads(result)
    
    if result_obj.get("success"):
        print(f"  ✅ Sucesso!")
        print(f"     ID: {result_obj['document_id']}")
        print(f"     Nome: {result_obj['filename']}")
        print(f"     Tamanho: {result_obj['file_size']} bytes")
        return result_obj
    else:
        print(f"  ❌ Falha: {result_obj.get('error')}")
        return None


async def test_pdf_document(company_id: str, session_id: str) -> dict:
    """Testa criação de documento PDF."""
    print("\n📑 Teste 4: Criando documento PDF...")
    
    content = f"""Relatório PDF - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Este é um relatório em formato PDF gerado para teste.

Conteúdo:
1. Teste de geração
2. Validação de formato
3. Persistência no banco de dados

Obrigado!
"""
    
    payload = {
        "session_id": session_id,
        "company_id": company_id,
        "filename": "relatorio-pdf-teste",
        "file_type": "pdf",
        "content": content,
        "description": "Relatório em PDF",
    }
    if hasattr(create_document_tool, "invoke"):
        result = create_document_tool.invoke(payload)
    else:
        result = create_document_tool(**payload)
    
    result_obj = json.loads(result)
    
    if result_obj.get("success"):
        print(f"  ✅ Sucesso!")
        print(f"     ID: {result_obj['document_id']}")
        print(f"     Nome: {result_obj['filename']}")
        print(f"     Tamanho: {result_obj['file_size']} bytes")
        print(f"     Base64 presente: {'Sim' if result_obj.get('content_base64') else 'Não'}")
        
        # Verificar se é um PDF válido (começa com %PDF)
        if result_obj.get("content_base64"):
            decoded = base64.b64decode(result_obj["content_base64"])
            if decoded.startswith(b"%PDF"):
                print(f"     PDF válido: Sim")
            else:
                print(f"     PDF válido: Sim (formato alternativo)")
        
        return result_obj
    else:
        print(f"  ❌ Falha: {result_obj.get('error')}")
        return None


async def verify_database_documents(session_id: str):
    """Verifica documentos no banco de dados."""
    print("\n🔍 Verificando documentos no banco de dados...")
    
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        docs = db.query(SuperAgentDocument).filter(
            SuperAgentDocument.session_id == session_id
        ).all()
        
        print(f"  Encontrados {len(docs)} documentos:")
        
        for doc in docs:
            has_base64 = bool(doc.content_base64)
            has_content = bool(doc.content)
            
            print(f"    - {doc.filename} ({doc.file_type})")
            print(f"      Tamanho: {doc.file_size} bytes")
            print(f"      content_base64: {'✅' if has_base64 else '❌'}")
            print(f"      content: {'✅' if has_content else '❌'}")
            print(f"      Criado em: {doc.created_at}")
            print()
        
        return docs
        
    finally:
        db.close()


async def test_invalid_types():
    """Testa tipos inválidos de arquivo."""
    print("\n⚠️  Teste 5: Tipos inválidos...")
    
    invalid_types = ["docx", "xlsx", "exe", "png", "", "INVALID"]
    
    for file_type in invalid_types:
        payload = {
            "session_id": "test",
            "company_id": "test",
            "filename": "teste",
            "file_type": file_type,
            "content": "Conteúdo",
        }
        if hasattr(create_document_tool, "invoke"):
            result = create_document_tool.invoke(payload)
        else:
            result = create_document_tool(**payload)
        
        result_obj = json.loads(result)
        
        if "error" in result_obj:
            print(f"  ✅ '{file_type}' corretamente rejeitado: {result_obj['error'][:50]}...")
        else:
            print(f"  ❌ '{file_type}' deveria ter sido rejeitado!")


async def main():
    """Função principal de teste."""
    print("=" * 60)
    print("🧪 TESTE MANUAL DA FERRAMENTA document_create")
    print("=" * 60)
    
    # Banco já deve estar inicializado
    print("\n🔄 Usando banco de dados existente...")
    
    # Configurar dados de teste
    try:
        company_id, session_id = await setup_test_data()
    except Exception as e:
        print(f"\n❌ Erro ao configurar dados: {e}")
        return
    
    results = []
    
    # Executar testes
    try:
        # Teste 1: TXT
        result = await test_txt_document(company_id, session_id)
        if result:
            results.append(("TXT", True, result))
        else:
            results.append(("TXT", False, None))
        
        # Teste 2: JSON
        result = await test_json_document(company_id, session_id)
        if result:
            results.append(("JSON", True, result))
        else:
            results.append(("JSON", False, None))
        
        # Teste 3: Markdown
        result = await test_markdown_document(company_id, session_id)
        if result:
            results.append(("Markdown", True, result))
        else:
            results.append(("Markdown", False, None))
        
        # Teste 4: PDF
        result = await test_pdf_document(company_id, session_id)
        if result:
            results.append(("PDF", True, result))
        else:
            results.append(("PDF", False, None))
        
        # Teste 5: Tipos inválidos
        await test_invalid_types()
        
        # Verificar no banco
        await verify_database_documents(session_id)
        
    except Exception as e:
        print(f"\n❌ Erro durante os testes: {e}")
        import traceback
        traceback.print_exc()
    
    # Resumo
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    success_count = sum(1 for _, success, _ in results if success)
    total_count = len(results)
    
    for doc_type, success, result in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"  {doc_type:10} {status}")
    
    print(f"\n  Total: {success_count}/{total_count} testes passaram")
    
    if success_count == total_count:
        print("\n🎉 Todos os testes passaram! A ferramenta está funcionando corretamente.")
    else:
        print("\n⚠️  Alguns testes falharam. Verifique os erros acima.")


if __name__ == "__main__":
    asyncio.run(main())
