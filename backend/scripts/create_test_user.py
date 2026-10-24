#!/usr/bin/env python3
"""Script para criar usuário de teste"""

import sys
import os

# Adiciona o backend ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import SessionLocal
from app.services.user_service import EmailAlreadyRegistered, create_user
from app.schemas.user import UserCreate

def main():
    db = SessionLocal()
    try:
        user_data = UserCreate(
            email="usuario@teste.com",
            password="teste123",
            full_name="Usuário Teste"
        )
        
        user = create_user(db, user_data)
        print(f"✅ Usuário criado com sucesso!")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Nome: {user.full_name}")
        print(f"   Ativo: {user.is_active}")
    except EmailAlreadyRegistered:
        print("⚠️  Usuário já existe no banco de dados.")
    except Exception as e:
        print(f"❌ Erro: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
