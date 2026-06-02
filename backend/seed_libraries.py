"""
Seed script to populate the Knowledge Library with Example Store's brands, product types, and foundational knowledge.
Run this after the migration to set up initial libraries.
"""
import sqlite3
import os
from datetime import datetime

# Find the database file
db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
if not os.path.exists(db_path):
    db_path = 'rag_seo.db'

print(f"Connecting to database: {db_path}")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# ============== BRAND LIBRARIES ==============
brands = [
    ("brand_transgo", "Transgo", "Transgo", "brand", "Shift kits, valves and repair components for enhanced transmission performance", "🔧", "#3B82F6"),
    ("brand_xtra_rev", "Xtra Rev", "Xtra Rev", "brand", "Oils and lubricants for transmissions - ATF, CVT, Dexron fluids", "🛢️", "#10B981"),
    ("brand_transtec", "Transtec", "Transtec", "brand", "Gasket kits, seals, and overhaul components", "📦", "#8B5CF6"),
    ("brand_tss", "TSS Genuine Parts", "TSS / Refacciones Originales", "brand", "Filters, electrical parts, and genuine-equivalent components", "🔌", "#F59E0B"),
    ("brand_zf", "ZF Aftermarket", "ZF Aftermarket", "brand", "Transmission fluids and hard parts - LifeguardFluid series", "⚙️", "#EF4444"),
    ("brand_sonnax", "Sonnax", "Sonnax", "brand", "Performance upgrades and repair tools - valves, bushings", "🎯", "#EC4899"),
    ("brand_raybestos", "Raybestos Powertrain", "Raybestos Powertrain", "brand", "Friction plates, bands, and powertrain materials", "💿", "#6366F1"),
    ("brand_apc", "Allomatic (APC)", "Allomatic Products Company", "brand", "Filters and friction materials - budget-friendly options", "🔍", "#14B8A6"),
    ("brand_freudenberg", "Freudenberg", "Freudenberg", "brand", "High-quality seals and gaskets - piston kits", "🔐", "#F97316"),
    ("brand_freudenberg_nok", "Freudenberg NOK", "Freudenberg NOK", "brand", "Precision seals and piston kits for various transmissions", "🎖️", "#84CC16"),
    ("brand_hp_tuners", "HP Tuners", "HP Tuners", "brand", "Diagnostic and tuning tools for transmission tuning", "💻", "#0EA5E9"),
    ("brand_lubegard", "Lubegard", "Lubegard", "brand", "Additives and protective fluids - transmission protectants", "🧴", "#A855F7"),
]

print("\n📚 Creating brand libraries...")
for lib_id, name, name_es, lib_type, description, icon, color in brands:
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO libraries (id, name, name_es, library_type, description, icon, color, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (lib_id, name, name_es, lib_type, description, icon, color, datetime.now().isoformat()))
        print(f"   ✓ {icon} {name}")
    except Exception as e:
        print(f"   ✗ {name}: {e}")

# ============== PRODUCT TYPE LIBRARIES ==============
product_types = [
    ("type_oils", "Oils & Lubricants", "Aceites y Lubricantes", "product_type", "ATF fluids, CVT oils, Dexron, Mercon - prevent wear and overheating", "🛢️", "#F59E0B"),
    ("type_filters", "Transmission Filters", "Filtros de Transmisión", "product_type", "OEM replacement filters for all transmission types", "🔍", "#3B82F6"),
    ("type_gasket_kits", "Gasket & Piston Kits", "Kits de Juntas y Pistones", "product_type", "Overhaul kits, seals, and gaskets for rebuilds", "📦", "#8B5CF6"),
    ("type_shift_kits", "Shift Kits", "Kits de Cambio", "product_type", "Performance upgrades for improved shift quality", "🔧", "#EF4444"),
    ("type_electrical", "Electrical Parts", "Partes Eléctricas", "product_type", "Solenoids, sensors, and electrical components", "⚡", "#10B981"),
    ("type_friction", "Friction Components", "Componentes de Fricción", "product_type", "Clutch packs, bands, and friction plates", "💿", "#EC4899"),
    ("type_steering", "Power Steering", "Dirección Hidráulica", "product_type", "Steering racks, pumps, and EPS/EHPS components", "🎯", "#6366F1"),
    ("type_manuals", "Technical Manuals", "Manuales Técnicos", "product_type", "DSG, Ford, GM, Transgo, ZF training guides", "📚", "#14B8A6"),
]

print("\n📂 Creating product type libraries...")
for lib_id, name, name_es, lib_type, description, icon, color in product_types:
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO libraries (id, name, name_es, library_type, description, icon, color, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (lib_id, name, name_es, lib_type, description, icon, color, datetime.now().isoformat()))
        print(f"   ✓ {icon} {name}")
    except Exception as e:
        print(f"   ✗ {name}: {e}")

# ============== TRANSMISSION LIBRARIES ==============
transmissions = [
    ("trans_4l60e", "4L60E / 4L65E", "4L60E / 4L65E (GM)", "transmission", "GM 4-speed automatic - Chevrolet, GMC, Cadillac", "🚗", "#3B82F6"),
    ("trans_6l80", "6L80 / 6L90", "6L80 / 6L90 (GM)", "transmission", "GM 6-speed automatic - Silverado, Sierra, Camaro", "🚐", "#10B981"),
    ("trans_68rfe", "68RFE", "68RFE (Chrysler)", "transmission", "Chrysler/Dodge 6-speed - Ram 2500/3500 diesel", "🛻", "#8B5CF6"),
    ("trans_zf6hp", "ZF 6HP", "ZF 6HP", "transmission", "ZF 6-speed - BMW, Jaguar, Bentley, Audi", "🏎️", "#EF4444"),
    ("trans_aode_4r70w", "AODE / 4R70W", "AODE / 4R70W / 4R75W (Ford)", "transmission", "Ford 4-speed - F-150, Mustang, Explorer", "🚙", "#F59E0B"),
    ("trans_09g", "09G / TF-60SN", "09G / TF-60SN (VW/Audi)", "transmission", "Aisin Warner 6-speed - Jetta, Golf, Beetle", "🚕", "#EC4899"),
    ("trans_jf015e", "JF015E / RE0F11A", "JF015E / RE0F11A (Nissan CVT)", "transmission", "Nissan CVT - Versa, Note, Micra", "🚗", "#6366F1"),
    ("trans_jf010e", "JF010E / RE0F09A", "JF010E / RE0F09A (Nissan CVT)", "transmission", "Nissan CVT - Altima, Maxima, Murano", "🚙", "#14B8A6"),
    ("trans_a604", "A604 / 41TE", "A604 / 41TE (Chrysler)", "transmission", "Chrysler 4-speed - Caravan, Town & Country", "🚐", "#A855F7"),
    ("trans_6t40", "6T40 / 6T45", "6T40 / 6T45 (GM)", "transmission", "GM 6-speed - Cruze, Malibu, Equinox", "🚗", "#0EA5E9"),
]

print("\n🔩 Creating transmission libraries...")
for lib_id, name, name_es, lib_type, description, icon, color in transmissions:
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO libraries (id, name, name_es, library_type, description, icon, color, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (lib_id, name, name_es, lib_type, description, icon, color, datetime.now().isoformat()))
        print(f"   ✓ {icon} {name}")
    except Exception as e:
        print(f"   ✗ {name}: {e}")

conn.commit()

# Count total libraries
cursor.execute("SELECT COUNT(*) FROM libraries")
total = cursor.fetchone()[0]

conn.close()

print(f"\n✅ Seed complete! Total libraries: {total}")
print("\n📊 Summary:")
print(f"   • {len(brands)} brand libraries")
print(f"   • {len(product_types)} product type libraries")
print(f"   • {len(transmissions)} transmission libraries")
print("\nRestart your backend server to see the changes!")
