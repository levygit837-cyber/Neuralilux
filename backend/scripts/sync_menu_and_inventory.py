#!/usr/bin/env python3
"""
Script para sincronizar cardápio e criar dados de estoque.
"""
import sys
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Product, ProductType, Company, MenuItem, MenuCatalog
from app.services.menu_catalog_service import sync_macedos_menu_from_json

def ensure_product_types(db: Session) -> dict[str, str]:
    types = {
        "ingrediente": "Ingredientes",
        "bebida": "Bebidas", 
        "pizza": "Pizzas",
        "carne": "Carnes",
        "peixe": "Peixes",
        "sobremesa": "Sobremesas",
        "salada": "Saladas",
        "geral": "Geral",
    }
    
    type_map = {}
    for slug, name in types.items():
        pt = db.query(ProductType).filter(ProductType.slug == slug).first()
        if not pt:
            pt = ProductType(slug=slug, name=name, description=f"Produtos tipo: {name}")
            db.add(pt)
            db.flush()
        type_map[slug] = pt.id
    
    db.commit()
    return type_map

def get_product_type_by_category(category_name: str, type_map: dict) -> str:
    category_lower = category_name.lower()
    
    if "pizza" in category_lower:
        return type_map["pizza"]
    elif "bebida" in category_lower or "vinho" in category_lower:
        return type_map["bebida"]
    elif "carne" in category_lower or "brasa" in category_lower or "aves" in category_lower:
        return type_map["carne"]
    elif "peixe" in category_lower:
        return type_map["peixe"]
    elif "sobremesa" in category_lower:
        return type_map["sobremesa"]
    elif "salada" in category_lower:
        return type_map["salada"]
    elif "pasta" in category_lower or "porcao" in category_lower or "acompanhamento" in category_lower:
        return type_map["ingrediente"]
    else:
        return type_map["geral"]

def generate_sku(item_name: str, category_name: str, index: int) -> str:
    prefix = "".join([c[0] for c in category_name.split()[:2]]).upper()
    name_part = "".join([c for c in item_name[:3] if c.isalnum()]).upper()
    return f"{prefix}-{name_part}{index:03d}"

def main():
    db = SessionLocal()
    
    try:
        # 1. Get or create company
        company_name = "Empresa Padrão"
        company = db.query(Company).filter(Company.name == company_name).first()
        
        if not company:
            # Check if we have any company
            any_company = db.query(Company).first()
            if any_company:
                company = any_company
                print(f"✓ Usando empresa existente: {company.name}")
            else:
                print("❌ Nenhuma empresa encontrada!")
                return
        else:
            print(f"✓ Empresa encontrada: {company.name} (ID: {company.id})")
        
        # 2. Sync menu
        print("\n📋 Sincronizando cardápio...")
        try:
            catalog = sync_macedos_menu_from_json(db)
            print(f"✓ Cardápio sincronizado: {catalog.name} (ID: {catalog.id})")
        except FileNotFoundError:
            print("❌ Arquivo macedos_cardapio.json não encontrado!")
            return
        
        # 3. Ensure product types
        type_map = ensure_product_types(db)
        print(f"✓ Tipos de produto: {len(type_map)}")
        
        # 4. Create products from menu items
        print("\n📦 Criando produtos no estoque...")
        menu_items = db.query(MenuItem).filter(MenuItem.catalog_id == catalog.id).all()
        print(f"   Itens do cardápio: {len(menu_items)}")
        
        created_count = 0
        skipped_count = 0
        
        for index, item in enumerate(menu_items, 1):
            # Check if product already exists
            existing = (
                db.query(Product)
                .filter(Product.company_id == company.id, Product.name == item.name)
                .first()
            )
            
            if existing:
                skipped_count += 1
                continue
            
            category_name = item.category.name if item.category else "Geral"
            product_type_id = get_product_type_by_category(category_name, type_map)
            sku = generate_sku(item.name, category_name, index)
            
            # Stock quantity based on availability
            stock_qty = 50 if item.is_available else 0
            
            product = Product(
                company_id=company.id,
                product_type_id=product_type_id,
                name=item.name,
                description=item.description,
                price=item.price or 0,
                sku=sku,
                is_available=item.is_available,
                stock_quantity=stock_qty,
            )
            db.add(product)
            created_count += 1
            
            if index % 30 == 0:
                print(f"   Progresso: {index}/{len(menu_items)}...")
        
        db.commit()
        
        # 5. Verify
        total_products = db.query(Product).filter(Product.company_id == company.id).count()
        
        print(f"\n{'='*55}")
        print(f"✅ SINCRONIZAÇÃO COMPLETA!")
        print(f"{'='*55}")
        print(f"   📋 Cardápio: {len(menu_items)} itens")
        print(f"   📦 Estoque: {total_products} produtos")
        print(f"   ➕ Produtos criados agora: {created_count}")
        print(f"   ⏭️  Produtos já existentes: {skipped_count}")
        print(f"{'='*55}")
        
        # 6. Sample products
        print("\n📄 Amostra de produtos criados:")
        sample = db.query(Product).filter(Product.company_id == company.id).limit(5).all()
        for p in sample:
            print(f"   • {p.name} | SKU: {p.sku} | Estoque: {p.stock_quantity} | Preço: R${p.price}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
