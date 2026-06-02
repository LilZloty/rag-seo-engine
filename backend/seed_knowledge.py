"""
Seed the RAG knowledge base with foundational Example Store business information.
This creates the first document in the system with comprehensive knowledge about the business.
"""
import asyncio
import sqlite3
import os
from datetime import datetime
import uuid

# Foundational knowledge about Example Store
STORE_KNOWLEDGE = """
# example-store.com - Knowledge Base

## About the Company
example-store.com is operated by Example Store in Mexico. It's a specialized e-commerce platform for automotive aftermarket parts, focusing on automatic transmissions and hydraulic power steering systems.

### Key Facts:
- Thousands of trusted clients
- High customer-satisfaction rating
- 24/7 customer service
- Express shipping: 1-2 business days
- International delivery via DHL

## Brands We Sell

### Transgo
Specialty: Shift kits, valves, and repair components for enhanced transmission performance
Products: Shift kits for A500/A518/A618, manual valves for TH400, 4L60E billet kits
Notes: Addresses TCC slip and pressure issues. 10% discounts available.

### Xtra Rev
Specialty: Oils and lubricants for transmissions
Products: ATF CVT, Dexron III/Mercon, Dexron VI (GM-licensed full synthetic), Full Synthetic Global ATF
Notes: 5% off promotions. Multipurpose fluids for CVT and automatic systems.

### Transtec
Specialty: Gasket kits, seals, and overhaul components
Products: Overhaul kits for various transmissions
Notes: Often bundled in repair sets with special pricing.

### TSS Genuine Parts
Specialty: Filters, electrical parts, and genuine-equivalent components
Products: Transmission filters (VW 09G/TF-60SN, GM 4L60E/4L65E, Chrysler A604/41TE, Nissan JF015E/RE0F11A, Ford AODE/4R70W/4R75W)
Notes: OEM replacements for brands like Allison.

### ZF Aftermarket
Specialty: Transmission fluids and hard parts
Products: LifeguardFluid series (5 for 4-5 speed, 6 for 6-speed, 7.4 DCT for dual-clutch, 8 for 8-9 speed)
Notes: Parts for ZF6HP, 6R60/80. Equivalents to Dexron III, Mercon.

### Sonnax
Specialty: Performance upgrades and repair tools
Products: Valves, bushings, and components for transmission rebuilding
Notes: Known for durability enhancements.

### Raybestos Powertrain
Specialty: Friction plates, bands, and powertrain materials
Products: Clutch packs and bands for automatic transmissions
Notes: Focus on reconstruction quality.

### Allomatic (APC)
Specialty: Filters and friction materials
Products: Transmission filters and kits
Notes: Budget-friendly maintenance options.

### Freudenberg / Freudenberg NOK
Specialty: Seals, gaskets, and precision piston kits
Products: Piston kits for A4LB1, 09G/09K, Mazda FW6A, Nissan JF010E, GM 6T40, Toyota U660E
Notes: High-quality sealing solutions.

### HP Tuners
Specialty: Diagnostic and tuning tools
Products: Software and hardware for transmission tuning

### Lubegard
Specialty: Additives and protective fluids
Products: Transmission protectants and additives

## Product Categories

### Oils & Lubricants
Essential for preventing wear and overheating. Bulk options (20-quart buckets) for workshops.

### Transmission Filters
Critical for fluid cleanliness. TSS dominates with OEM replacements.

### Kits & Seals
Gasket kits, piston kits, overhaul kits for rebuilds.

### Shift Kits
Performance upgrades from Transgo for improved shift quality.

### Electrical Parts
Solenoids, sensors, and electrical components.

### Friction Components
Clutch packs, bands from Raybestos Powertrain.

### Power Steering
Steering racks (cremalleras), pump kits, EPS/EHPS/EPAS parts.

### Technical Manuals
Free with purchases over $5,000 MXN. Covers DSG 0AM/DQ200, Ford 10R80/6R80/6R60, GM 6T40, Transgo, ZF6HP.

## Common Transmission Types We Support

- 4L60E / 4L65E (GM) - Chevrolet, GMC, Cadillac
- 6L80 / 6L90 (GM) - Silverado, Sierra, Camaro
- 68RFE (Chrysler) - Ram 2500/3500 diesel
- ZF 6HP - BMW, Jaguar, Bentley, Audi
- AODE / 4R70W / 4R75W (Ford) - F-150, Mustang, Explorer
- 09G / TF-60SN (VW/Audi) - Jetta, Golf, Beetle
- JF015E / RE0F11A (Nissan CVT) - Versa, Note, Micra
- JF010E / RE0F09A (Nissan CVT) - Altima, Maxima, Murano
- A604 / 41TE (Chrysler) - Caravan, Town & Country
- 6T40 / 6T45 (GM) - Cruze, Malibu, Equinox

## Common Issues We Address
- Noise in transmissions
- Wear and tear
- Overheating
- Irregular shifts
- TCC slip
- Pressure issues

## Promotions
- 10% off on Transgo parts
- 5% discounts on Xtra Rev oils
- Free technical manuals with purchases over $5,000 MXN

## Target Audience
Mechanics, workshops, and individual buyers handling transmission and steering repairs.
"""

async def seed_knowledge():
    # Find database
    db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
    if not os.path.exists(db_path):
        db_path = 'rag_seo.db'
    
    print(f"Connecting to: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the document
    doc_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    cursor.execute("""
        INSERT OR REPLACE INTO documents (id, title, content, source_type, brands, product_types, transmission_codes, verified, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doc_id,
        "Example Store - Base de Conocimiento Fundamental",
        STORE_KNOWLEDGE,
        "manual",
        "Transgo,Xtra Rev,Transtec,TSS,ZF,Sonnax,Raybestos,Allomatic,Freudenberg,HP Tuners,Lubegard",
        "oils,filters,kits,shift_kits,electrical,friction,steering,manuals",
        "4L60E,6L80,68RFE,ZF6HP,4R70W,09G,JF015E,JF010E,A604,6T40",
        1,  # verified
        now,
        now
    ))
    
    # Create chunks for the document
    chunk_size = 500
    overlap = 100
    content = STORE_KNOWLEDGE
    chunks = []
    
    start = 0
    while start < len(content):
        end = start + chunk_size
        chunk_text = content[start:end]
        chunks.append(chunk_text)
        start = end - overlap
    
    print(f"Created {len(chunks)} chunks")
    
    for i, chunk in enumerate(chunks):
        chunk_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO document_chunks (id, document_id, chunk_index, content, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (chunk_id, doc_id, i, chunk, now))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Created foundational document: {doc_id}")
    print(f"   Chunks: {len(chunks)}")
    print("\n📚 To generate embeddings, run the backend and use the document ingestion service.")

if __name__ == "__main__":
    asyncio.run(seed_knowledge())
