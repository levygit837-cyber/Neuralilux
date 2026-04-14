#!/usr/bin/env python3
"""
Script para criar dados de estoque baseados nos itens do cardápio.
Converte os MenuItems em Products com estoque inicial.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.models import Product, ProductType, Company, MenuItem, MenuCatalog
DEFAULT_COMPANY_NAME = "Empresa Padrão"

def ensure_product_types(db: Session) -> dict[str, str]:
    """Create default product types and return mapping name->id."""
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
    """Map category to product type."""
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
    """Generate SKU based on item name."""
    prefix = "".join([c[0] for c in category_name.split()[:2]]).upper()
    name_part = "".join([c for c in item_name[:3] if c.isalnum()]).upper()
    return f"{prefix}-{name_part}{index:03d}"


def seed_inventory_from_menu():
    """Create products from menu items."""
    db = SessionLocal()
    
    try:
        # Get company
        company = db.query(Company).filter(Company.name == DEFAULT_COMPANY_NAME).first()
        if not company:
            print(f"❌ Empresa '{DEFAULT_COMPANY_NAME}' não encontrada!")
            # List available companies
            all_companies = db.query(Company).all()
            print(f"   Empresas disponíveis: {[c.name for c in all_companies]}")
            return
        
        print(f"✓ Empresa encontrada: {company.name} (ID: {company.id})")
        
        # Ensure product types exist
        type_map = ensure_product_types(db)
        print(f"✓ Tipos de produto criados: {len(type_map)}")
        
        # Get menu catalog
        catalog = (
            db.query(MenuCatalog)
            .filter(MenuCatalog.company_id == company.id)
            .first()
        )
        if not catalog:
            print("❌ Catálogo não encontrado! Sincronize o cardápio primeiro.")
            return
        
        # Get all menu items
        menu_items = (
            db.query(MenuItem)
            .filter(MenuItem.catalog_id == catalog.id)
            .all()
        )
        
        print(f"✓ Itens do cardápio encontrados: {len(menu_items)}")
        
        # Create products for each menu item
        created_count = 0
        skipped_count = 0
        
        for index, item in enumerate(menu_items, 1):
            # Check if product already exists with same name
            existing = (
                db.query(Product)
                .filter(
                    Product.company_id == company.id,
                    Product.name == item.name
                )
                .first()
            )
            
            if existing:
                skipped_count += 1
                continue
            
            # Get category name
            category_name = item.category.name if item.category else "Geral"
            product_type_id = get_product_type_by_category(category_name, type_map)
            
            # Generate SKU
            sku = generate_sku(item.name, category_name, index)
            
            # Create product with random stock quantity
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
            
            if index % 20 == 0:
                print(f"  Progresso: {index}/{len(menu_items)} itens processados...")
        
        db.commit()
        
        print(f"\n{'='*50}")
        print(f"✅ Estoque populado com sucesso!")
        print(f"   • Produtos criados: {created_count}")
        print(f"   • Produtos ignorados (já existiam): {skipped_count}")
        print(f"{'='*50}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed_inventory_from_menu()
