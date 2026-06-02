"""
Migration: Add AI Visibility Tracker Tables

Creates tables for:
- prompt_panel_items: Prompts to query LLMs
- ai_visibility_results: Results of LLM queries
- visibility_snapshots: Aggregated daily metrics

Run with: python -m backend.scripts.migrate_visibility_tables
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import inspect
from app.db.session import engine, SessionLocal
from app.models.aeo_models import (
    PromptPanelItem,
    AIVisibilityResult,
    VisibilitySnapshot,
    FaultCode,
    Base
)


def get_existing_tables():
    """Get list of existing tables in the database."""
    inspector = inspect(engine)
    return set(inspector.get_table_names())


def create_visibility_tables():
    """Create the AI Visibility Tracker tables."""
    existing_tables = get_existing_tables()
    tables_to_create = [
        ("prompt_panel_items", PromptPanelItem),
        ("ai_visibility_results", AIVisibilityResult),
        ("visibility_snapshots", VisibilitySnapshot),
    ]
    
    created = []
    skipped = []
    
    for table_name, model in tables_to_create:
        if table_name in existing_tables:
            print(f"  ⏭️  Table '{table_name}' already exists, skipping.")
            skipped.append(table_name)
        else:
            print(f"  ✅ Creating table '{table_name}'...")
            model.__table__.create(engine)
            created.append(table_name)
    
    return created, skipped


def seed_required_fault_codes(db):
    """Seed fault codes that are referenced by initial prompts."""
    # Fault codes referenced in initial_prompts
    required_codes = [
        {
            "code": "P0700",
            "name": "Transmission Control System Malfunction",
            "description": "Código genérico que indica un problema en el sistema de control de transmisión automática.",
            "severity": "medium",
            "is_priority": True,
            "include_in_llms_txt": True
        },
        {
            "code": "P0706",
            "name": "Transmission Range Sensor Circuit Range/Performance",
            "description": "Indica un problema con el sensor de rango de transmisión (sensor TR/PRNDL).",
            "severity": "medium",
            "is_priority": True,
            "include_in_llms_txt": True
        },
        {
            "code": "P0715",
            "name": "Input/Turbine Speed Sensor Circuit Malfunction",
            "description": "Problema con el sensor de velocidad de entrada/turbina de la transmisión.",
            "severity": "medium",
            "is_priority": True,
            "include_in_llms_txt": True
        },
    ]
    
    created = 0
    for fc_data in required_codes:
        existing = db.query(FaultCode).filter(FaultCode.code == fc_data["code"]).first()
        if not existing:
            fault_code = FaultCode(**fc_data)
            db.add(fault_code)
            created += 1
            print(f"    ✅ Created fault code: {fc_data['code']}")
        else:
            print(f"    ⏭️  Fault code {fc_data['code']} already exists, skipping.")
    
    if created > 0:
        db.commit()
    
    return created


def seed_initial_prompts(db):
    """Seed initial prompts from top GSC queries."""
    # Check if already seeded
    existing = db.query(PromptPanelItem).count()
    if existing > 0:
        print(f"  ⏭️  Prompts already seeded ({existing} items), skipping.")
        return 0
    
    # Initial prompts based on top GSC queries and fault codes
    initial_prompts = [
        # Fault code prompts (high priority)
        {"prompt_text": "¿Qué significa el código de falla P0700 en transmisión automática?", "category": "fault_code", "priority": 100, "linked_fault_code": "P0700"},
        {"prompt_text": "¿Cómo solucionar el código P0706 sensor de rango?", "category": "fault_code", "priority": 95, "linked_fault_code": "P0706"},
        {"prompt_text": "Código P0715 sensor de velocidad de entrada, ¿cómo reparar?", "category": "fault_code", "priority": 90, "linked_fault_code": "P0715"},
        {"prompt_text": "¿Qué causa el código P0730 relación de engranajes incorrecta?", "category": "fault_code", "priority": 85},
        {"prompt_text": "Código P0841 baja presión de fluido CVT, ¿solución?", "category": "fault_code", "priority": 80},
        
        # Product/Solution prompts
        {"prompt_text": "¿Dónde comprar kit de reparación transmisión 4L60E en México?", "category": "product", "priority": 90, "linked_transmission": "4L60E"},
        {"prompt_text": "¿Quién vende solenoides para transmisión JF011E CVT Nissan?", "category": "product", "priority": 85, "linked_transmission": "JF011E"},
        {"prompt_text": "¿Dónde conseguir cuerpo de válvulas DSG DQ200 en México?", "category": "product", "priority": 80, "linked_transmission": "DQ200"},
        {"prompt_text": "Kit de embrague transmisión automática Ford 6R80 precio", "category": "product", "priority": 75, "linked_transmission": "6R80"},
        
        # Competitor prompts
        {"prompt_text": "¿Qué marcas de refacciones de transmisión son confiables en México?", "category": "competitor", "priority": 70},
        {"prompt_text": "TransGo vs TSS kits de reparación transmisión, ¿cuál es mejor?", "category": "competitor", "priority": 65},
        {"prompt_text": "Mejores proveedores de refacciones transmisión automática Latinoamérica", "category": "competitor", "priority": 60},
        
        # General/Symptom prompts
        {"prompt_text": "¿Por qué mi carro no entra la reversa?", "category": "general", "priority": 85},
        {"prompt_text": "Transmisión automática patina al acelerar, ¿qué hacer?", "category": "general", "priority": 80},
        {"prompt_text": "¿Por qué mi transmisión CVT hace ruido de zumbido?", "category": "general", "priority": 75},
        {"prompt_text": "Mi transmisión se calienta mucho, ¿cuál es la causa?", "category": "general", "priority": 70},
        {"prompt_text": "Cambios bruscos en transmisión automática, ¿cómo arreglar?", "category": "general", "priority": 65},
    ]
    
    for prompt_data in initial_prompts:
        prompt = PromptPanelItem(
            prompt_text=prompt_data["prompt_text"],
            category=prompt_data["category"],
            priority=prompt_data["priority"],
            linked_fault_code=prompt_data.get("linked_fault_code"),
            linked_transmission=prompt_data.get("linked_transmission"),
            source="gsc_import",
            is_active=True
        )
        db.add(prompt)
    
    db.commit()
    print(f"  ✅ Seeded {len(initial_prompts)} initial prompts.")
    return len(initial_prompts)


def main():
    print("\n" + "=" * 60)
    print("AI Visibility Tracker - Database Migration")
    print("=" * 60)
    
    print("\n1. Creating tables...")
    created, skipped = create_visibility_tables()
    
    db = SessionLocal()
    try:
        print("\n2. Seeding required fault codes...")
        fault_codes_created = seed_required_fault_codes(db)
        
        print("\n3. Seeding initial prompts...")
        seeded = seed_initial_prompts(db)
    finally:
        db.close()
    
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print(f"  Tables created: {len(created)}")
    print(f"  Tables skipped: {len(skipped)}")
    print(f"  Fault codes created: {fault_codes_created}")
    print(f"  Prompts seeded: {seeded if seeded else 'already seeded'}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
