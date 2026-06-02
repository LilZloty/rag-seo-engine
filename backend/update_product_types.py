"""
Update the libraries with actual Shopify product type collections.
This replaces the generic product types with the real ones from Example Store's store.
"""
import sqlite3
import os
from datetime import datetime

# New product type libraries based on Shopify collections
PRODUCT_TYPES = [
    {
        "id": "pt_filtros",
        "name": "Filtros",
        "name_es": "Filtros de Transmisión",
        "description": "Transmission filters from brands like TSS (e.g., for VW 09G or GM 4L60E)",
        "icon": "🔵",
        "scrape_url": "/collections/filtros"
    },
    {
        "id": "pt_partes_electricas",
        "name": "Partes Eléctricas",
        "name_es": "Partes Eléctricas",
        "description": "Electrical parts like solenoids and sensors for transmissions",
        "icon": "⚡",
        "scrape_url": "/collections/partes-electricas"
    },
    {
        "id": "pt_arnes",
        "name": "Arnés",
        "name_es": "Arneses de Transmisión",
        "description": "Harnesses for various transmissions (e.g., Audi, Ford, GM)",
        "icon": "🔌",
        "scrape_url": "/collections/arnes"
    },
    {
        "id": "pt_cadenas",
        "name": "Cadenas",
        "name_es": "Cadenas de Transmisión",
        "description": "Chains for automatic transmissions",
        "icon": "⛓️",
        "scrape_url": "/collections/cadenas"
    },
    {
        "id": "pt_transmision",
        "name": "Transmisión General",
        "name_es": "Partes Generales de Transmisión",
        "description": "General transmission parts, often with Transtec promotions",
        "icon": "⚙️",
        "scrape_url": "/collections/transmision"
    },
    {
        "id": "pt_discos",
        "name": "Discos de Transmisión",
        "name_es": "Discos y Bandas",
        "description": "Friction plates and bands for reconstruction (e.g., from Raybestos)",
        "icon": "💿",
        "scrape_url": "/collections/discos-de-transmision"
    },
    {
        "id": "pt_direccion_hidraulica",
        "name": "Dirección Hidráulica",
        "name_es": "Componentes de Dirección Hidráulica",
        "description": "Hydraulic steering components",
        "icon": "🚗",
        "scrape_url": "/collections/direccion-hidraulica"
    },
    {
        "id": "pt_ligas_bomba",
        "name": "Ligas de Bomba",
        "name_es": "Sellos de Bomba",
        "description": "Pump seals for transmissions like 5R55",
        "icon": "🔘",
        "scrape_url": "/collections/ligas-de-bomba"
    },
    {
        "id": "pt_empaques",
        "name": "Empaques Generales",
        "name_es": "Empaques OEM",
        "description": "General gaskets OEM-compatible for Chrysler, Ford, etc.",
        "icon": "📦",
        "scrape_url": "/collections/empaques-generales"
    },
    {
        "id": "pt_bujes_bomba",
        "name": "Bujes de Bomba",
        "name_es": "Bujes para Bomba",
        "description": "Pump bushings for automatic transmissions",
        "icon": "🔩",
        "scrape_url": "/collections/bujes-de-bomba"
    },
    {
        "id": "pt_engrane_cajas",
        "name": "Engrane de Cajas",
        "name_es": "Engranes y Piñones",
        "description": "Gears and pinions for transmission cases",
        "icon": "⚙️",
        "scrape_url": "/collections/engrane-de-cajas"
    },
    {
        "id": "pt_bomba_direccion",
        "name": "Refacciones Bomba Dirección",
        "name_es": "Partes para Bomba de Dirección Hidráulica",
        "description": "Parts for hydraulic power steering pumps",
        "icon": "🔧",
        "scrape_url": "/collections/refacciones-para-bomba-de-direccion-hidraulica"
    },
    {
        "id": "pt_direccion_electrica",
        "name": "Partes Eléctricas Dirección",
        "name_es": "Partes Eléctricas para Direcciones Electroasistidas",
        "description": "Electrical parts for electro-assisted steering",
        "icon": "🔋",
        "scrape_url": "/collections/partes-electricas-para-direcciones-electroasistidas"
    },
    {
        "id": "pt_cremalleras",
        "name": "Cremalleras EPS/EHPS/EPAS",
        "name_es": "Cremalleras de Dirección Nuevas",
        "description": "New steering racks (EPS/EHPS/EPAS)",
        "icon": "🛞",
        "scrape_url": "/collections/cremalleras-direccion-hidraulica-nuevas-eps-ehps-epas"
    },
]

def update_product_types():
    db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
    if not os.path.exists(db_path):
        db_path = 'rag_seo.db'
    
    print(f"Connecting to: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # First, delete old product_type libraries
    cursor.execute("DELETE FROM libraries WHERE library_type = 'product_type'")
    print(f"Deleted {cursor.rowcount} old product type libraries")
    
    # Insert new product types
    for pt in PRODUCT_TYPES:
        cursor.execute("""
            INSERT INTO libraries (id, name, name_es, library_type, description, icon, scrape_url, document_count, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            pt["id"],
            pt["name"],
            pt.get("name_es", pt["name"]),
            "product_type",
            pt["description"],
            pt["icon"],
            pt.get("scrape_url", ""),
            0,
            True,
            now,
            now
        ))
    
    conn.commit()
    print(f"✅ Added {len(PRODUCT_TYPES)} new product type libraries")
    
    # Show all libraries
    cursor.execute("SELECT library_type, COUNT(*) FROM libraries GROUP BY library_type")
    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]} libraries")
    
    conn.close()

if __name__ == "__main__":
    update_product_types()
