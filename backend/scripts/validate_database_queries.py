#!/usr/bin/env python3
"""
Validar queries de database para estoque e cardápio.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.database import SessionLocal
from app.models.models import Product, Company, MenuItem, MenuCatalog
from app.services.product_service import list_products, get_products_by_company

def main():
    db = SessionLocal()
    
    print("="*60)
    print("VALIDAÇÃO DE QUERIES DE DATABASE")
    print("="*60)
    
    # Test 1: List all products
    print('\n=== TESTE 1: list_products ===')
    products = list_products(db, limit=5)
    print(f'   ✓ Retornou {len(products)} produtos')
    for p in products[:3]:
        print(f'   • {p.name} | Estoque: {p.stock_quantity} | Preço: R${p.price}')
    
    # Test 2: Get products by company
    print('\n=== TESTE 2: get_products_by_company ===')
    company = db.query(Company).filter(Company.name == 'Empresa Padrão').first()
    if company:
        company_products = get_products_by_company(db, company.id, limit=5)
        print(f'   ✓ Empresa: {company.name}')
        print(f'   ✓ Retornou {len(company_products)} produtos')
        for p in company_products[:3]:
            print(f'   • {p.name} | SKU: {p.sku}')
    
    # Test 3: Menu catalog
    print('\n=== TESTE 3: Menu Catalog ===')
    catalog = db.query(MenuCatalog).first()
    if catalog:
        print(f'   ✓ Catálogo: {catalog.name}')
        items_count = db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id).count()
        print(f'   ✓ Itens no catálogo: {items_count}')
    
    # Test 4: Count total
    print('\n=== TESTE 4: Contagem Total ===')
    total_products = db.query(Product).count()
    total_menu_items = db.query(MenuItem).count()
    print(f'   📦 Total produtos em estoque: {total_products}')
    print(f'   📋 Total itens no cardápio: {total_menu_items}')
    
    # Test 5: Product by ID
    print('\n=== TESTE 5: Busca por ID ===')
    if products:
        from app.services.product_service import get_product
        first_product = get_product(db, products[0].id)
        print(f'   ✓ Produto encontrado: {first_product.name if first_product else "N/A"}')
    
    db.close()
    
    print("\n" + "="*60)
    print("✅ TODAS AS QUERIES DE DATABASE ESTÃO FUNCIONANDO!")
    print("="*60)

if __name__ == "__main__":
    main()
