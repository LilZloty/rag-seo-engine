"""
Seed generic prompt templates and link them to knowledge libraries.
This allows the AI to merge instructions from multiple selected libraries.
"""
import sqlite3
import os
from datetime import datetime

base_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(base_dir, 'rag_seo.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. Create Generic Prompt Templates
# Format: (id, name, type, instructions, priority, version)
# Priority: Lower = applied first (base=0), Brand=50, ProductType=60, Transmission=70, Override=100
templates = [
    # Brand Templates (priority 50)
    ("prompt_brand_tss", "Brand: TSS Guidelines", "brand", 
     "INSTRUCCIONES PARA MARCA TSS:\n"
     "- Enfatiza que TSS Genuine Parts ofrece calidad equivalente a equipo original (OEM).\n"
     "- Menciona que son componentes diseñados para durabilidad extrema en transmisiones automáticas.\n"
     "- Destaca que TSS es la opción preferida por especialistas para reparaciones que requieren precisión.",
     50, 1),
    
    ("prompt_brand_transgo", "Brand: Transgo Guidelines", "brand",
     "INSTRUCCIONES PARA MARCA TRANSGO:\n"
     "- Resalta que Transgo es el líder en ingeniería de corrección de cambios (Shift Kits).\n"
     "- Enfócate en la solución de problemas endémicos de la transmisión (TCC slip, presión, ruidos).\n"
     "- Usa un tono más técnico y orientado a la mejora del rendimiento.",
     50, 1),

    # Product Type Templates (priority 60)
    ("prompt_type_filters", "Type: Filter Guidelines", "product_type",
     "INSTRUCCIONES PARA FILTROS:\n"
     "- Explica la importancia de la filtración para prevenir el desgaste prematuro de los clutches.\n"
     "- Menciona que un filtro limpio asegura un flujo de aceite constante y una presión estable.\n"
     "- Sugiere el cambio del filtro en cada mantenimiento preventivo.",
     60, 1),

    ("prompt_type_oils", "Type: Oil Guidelines", "product_type",
     "INSTRUCCIONES PARA ACEITES:\n"
     "- Enfatiza la estabilidad térmica y la resistencia a la oxidación.\n"
     "- Explica cómo el aceite correcto previene el sobrecalentamiento y protege los componentes internos.\n"
     "- Menciona la compatibilidad específica con estándares (ATF, CVT, Dexron, etc.).",
     60, 1),

    # Transmission Templates (priority 70)
    ("prompt_trans_allison", "Trans: Allison Guidelines", "transmission",
     "INSTRUCCIONES PARA ALLISON:\n"
     "- Resalta la robustez de las transmisiones Allison en aplicaciones de trabajo pesado (Heavy Duty).\n"
     "- Menciona que estos componentes están diseñados para soportar altos torques y condiciones exigentes.\n"
     "- Enfócate en la confiabilidad para flotas y camiones de carga.",
     70, 1)
]

print("📝 Seeding prompt templates...")
for t_id, name, t_type, inst, priority, version in templates:
    cursor.execute("""
        INSERT OR REPLACE INTO prompt_templates (id, name, template_type, system_instructions, priority, version, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
    """, (t_id, name, t_type, inst, priority, version, datetime.now().isoformat()))
    print(f"   ✓ {name} (priority: {priority})")

# 2. Link Templates to Libraries
links = [
    ("brand_tss", "prompt_brand_tss"),
    ("brand_transgo", "prompt_brand_transgo"),
    ("type_filters", "prompt_type_filters"),
    ("type_oils", "prompt_type_oils"),
    ("trans_zf6hp", "prompt_brand_zf") # ZF using a brand prompt as example
]

# Note: Using trans_allison if it exists
cursor.execute("SELECT id FROM libraries WHERE id LIKE 'trans_allison%'")
allison_lib = cursor.fetchone()
if allison_lib:
    links.append((allison_lib[0], "prompt_trans_allison"))
else:
    # If it doesn't exist, create it for testing
    cursor.execute("""
        INSERT OR REPLACE INTO libraries (id, name, name_es, library_type, is_active, created_at)
        VALUES ('trans_allison', 'Allison', 'Allison (Heavy Duty)', 'transmission', 1, ?)
    """, (datetime.now().isoformat(),))
    links.append(('trans_allison', "prompt_trans_allison"))

print("\n🔗 Linking templates to libraries...")
for lib_id, prompt_id in links:
    cursor.execute("""
        UPDATE libraries SET prompt_template_id = ? WHERE id = ?
    """, (prompt_id, lib_id))
    print(f"   ✓ Linked {lib_id} -> {prompt_id}")

conn.commit()
conn.close()
print("\n✅ Seed complete!")
