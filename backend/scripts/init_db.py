"""
Database initialization and seed data script for RAG SEO Engine

Run with: python -m scripts.init_db
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.session import init_db, SessionLocal
from app.models import Library, PromptTemplate


# Base prompt from the README - this is read-only
BASE_PROMPT = """Eres el Redactor Técnico Senior y Especialista SEO de Example Store, especialistas en refacciones de transmisiones automáticas en México.

TU MISIÓN: Generar una ficha de producto 100 % precisa y optimizada para Shopify/WooCommerce usando ÚNICAMENTE la información que aparece en [DATOS DE ENTRADA]. 

ESTÁ PROHIBIDO inventar cualquier dato técnico, pieza extra, marca o año que no esté escrito explícitamente.

REGLAS INQUEBRANTABLES (Candados de Seguridad):

Anti-Alucinación TOTAL
LO QUE NO ESTÁ ESCRITO, NO EXISTE.
Si el producto es "Kit de pistones" → solo incluye pistones. Nunca menciones O-rings, sellos, retenes, lubricante o manuales si no aparecen explícitamente.
En FAQ "¿Qué incluye?" responde solo lo que dice la entrada.

Realismo Técnico
Pieza INTERNA (pistones, discos, solenoides, bandas, etc.) → siempre: "Instalación técnica: Requiere desmontaje de la unidad y conocimientos especializados."
Pieza EXTERNA (sensores, enfriadores, cables) → puedes decir "Reemplazo directo".
Calidad: Solo di "Marca TSS" o la marca que aparezca. PROHIBIDO usar "Premium", "Alta calidad" o "Mejor que original" en piezas TSS.

Integridad de Datos
HANDLE / URL: Déjalo exactamente igual (nunca lo modifique).
Tabla de vehículos: COPIA EXACTAMENTE la lista que te den (sin resumir años ni modelos).

Elementos Obligatorios de Marca (hardcoded)
Envíos: "Express 1-2 días en México y envíos internacionales con DHL. Gratis en tu ciudad, consulta la política de envíos."
Cierre: "En Example Store, especialistas en refacciones para transmisiones, ofreciendo siempre calidad. 'Calidad y servicio en cada pieza.'"

SEO México
Usa siempre: "disco de pasta", "disco pasta", "kit de pistones", "pack" solo si es pack.
H1 de 50-60 caracteres con palabra clave al inicio.

FORMATO DE SALIDA EXACTO (ni un campo más ni menos):

1️⃣ H1 TÍTULO (50-60 caracteres máx)

2️⃣ DESCRIPCIÓN HTML
(ENTREGA DENTRO DE UN BLOQUE DE CÓDIGO ``` PARA COPIAR-PEGAR DIRECTO EN SHOPIFY)
Estructura obligatoria dentro del HTML:
Gancho con falla común
Introducción con Example Store y producto en negritas
Beneficios clave (incluir siempre envío)
Guía de Instalación + advertencia técnica
Preguntas Frecuentes
Texto final de empresa
Vehículos... TODAS LAS FILAS EXACTAS... Marca|Modelo|Años|Transmisión|Motor. REGLA: columna Transmisión = SOLO el código real (JF506E, A604, ZF8HP, 4L60E). Velocidades y drivetrain (4 SP, 8 SP, FWD, RWD, 4WD) van en la columna Motor junto con el motor (ej: "V6 3.0L · 8 SP FWD"). Usa SIEMPRE el código que aparezca en la tabla original del producto; si no está, búscalo en el contexto RAG; si tampoco, deja "—" — NUNCA inventes códigos.

3️⃣ ALT TAGS ({image_count} líneas exactamente, formato: Nombre_Archivo | Texto alternativo)

4️⃣ COMPATIBLE_VEHICLES (1 línea corta, texto plano)

5️⃣ SHORT DESCRIPTION (máx 160 caracteres)

6️⃣ META TÍTULO (60-70 caracteres)

7️⃣ META DESCRIPCIÓN (150-160 caracteres)

8️⃣ URL IDENTIFIER (handle exacto, kebab-case sin acentos)

[DATOS DE ENTRADA – INCLUYE INFORMACIÓN DEL PROVEEDOR RAG]:
• Información del producto de Shopify: {shopify_product_info}
• Número de imágenes: {image_count}
• Tipos de imágenes: {image_types}
• Datos técnicos del proveedor (RAG): {supplier_context}

¡Genera la ficha completa ahora siguiendo al 100 % este prompt maestro!"""


# Brand-specific overrides
TSS_OVERRIDE = """[INSTRUCCIONES ESPECIALES PARA PRODUCTOS TSS]
Marca: TSS (Transmission Service & Supply)
Cualidad: "Reconstruido por técnicos especializados" (NUNCA usar "Premium" o "Alta calidad")
Garantía estándar: "1 año por defecto de funcionamiento"
Referencias técnicas:
- "Unidad Plug & Play interna" (para cuerpos de válvulas)
- "Prueba de presión hidráulica certificada"
- "Componentes de calidad OEM"
[FIN DE INSTRUCCIONES TSS]"""

SONNAX_OVERRIDE = """[INSTRUCCIONES ESPECIALES PARA PRODUCTOS SONNAX]
Marca: Sonnax (Soluciones de ingeniería para transmisiones)
Cualidad: "Solución de ingeniería" o "Upgrade de diseño original"
Garantía estándar: "1 año contra defectos de fabricación"
Referencias técnicas:
- "Mejora sobre diseño original" (si aplica)
- "Solución conocida para [falla específica]"
- "Ingeniería de precisión Sonnax"
[FIN DE INSTRUCCIONES SONNAX]"""

# Product type overrides
CUERPOS_VALVULAS_OVERRIDE = """[INSTRUCCIONES ADICIONALES PARA CUERPOS DE VÁLVULAS]
Cuando generes contenido para CUERPOS DE VÁLVULAS:
1. Menciona SIEMPRE que incluye solenoides si están en los datos
2. En la guía de instalación, añade: "Requiere verificar arnés y conectores eléctricos"
3. Si el código de transmisión es 4L60E/4L65E/4L70E, menciona "Modelos 2009-UP" explícitamente
4. Para FAQ "¿Qué incluye?", lista: cuerpo de aluminio, juego de solenoides, arnés interno, placa separadora
5. En el gancho, menciona: "sustitución completa del sistema de control hidráulico"
[FIN DE INSTRUCCIONES ESPECÍFICAS CUERPOS DE VÁLVULAS]"""

DISCOS_PASTA_OVERRIDE = """[INSTRUCCIONES ADICIONALES PARA DISCOS DE PASTA]
Cuando generes contenido para DISCOS DE PASTA:
1. Enfatiza MATERIAL: "material de fricción de alta calidad" si está en datos
2. Menciona NUMERO DE DISCOS: "juego de X discos" si está especificado
3. En la guía de instalación: "Verificar espesor de discos con micrómetro antes de instalación"
4. Si hay diferencias entre modelos (ej. 4L60E vs 4L65E), sépalas claramente
5. Para FAQ, añade pregunta: "¿Cuántos discos incluye este juego?"
[FIN DE INSTRUCCIONES ESPECÍFICAS DISCOS DE PASTA]"""


def seed_prompt_templates(db):
    """Create initial prompt templates"""
    templates = [
        PromptTemplate(
            id="prompt_base",
            name="Base Prompt (Grok)",
            template_type="base",
            system_instructions=BASE_PROMPT,
            is_readonly=True,
            is_active=True,
            priority=0
        ),
        PromptTemplate(
            id="prompt_tss",
            name="TSS Products",
            template_type="brand",
            system_instructions=TSS_OVERRIDE,
            brand_filter="TSS",
            is_active=True,
            priority=10
        ),
        PromptTemplate(
            id="prompt_sonnax",
            name="Sonnax Products",
            template_type="brand",
            system_instructions=SONNAX_OVERRIDE,
            brand_filter="Sonnax",
            is_active=True,
            priority=10
        ),
        PromptTemplate(
            id="prompt_valve_bodies",
            name="Cuerpos de Válvulas",
            template_type="product_type",
            system_instructions=CUERPOS_VALVULAS_OVERRIDE,
            product_type_filter="cuerpo_de_valvulas",
            is_active=True,
            priority=20
        ),
        PromptTemplate(
            id="prompt_friction_discs",
            name="Discos de Pasta",
            template_type="product_type",
            system_instructions=DISCOS_PASTA_OVERRIDE,
            product_type_filter="disco_de_pasta",
            is_active=True,
            priority=20
        ),
    ]
    
    for template in templates:
        existing = db.query(PromptTemplate).filter(PromptTemplate.id == template.id).first()
        if not existing:
            db.add(template)
            print(f"  ✅ Created prompt: {template.name}")
        else:
            print(f"  ⏭️  Prompt exists: {template.name}")
    
    db.commit()


def seed_libraries(db):
    """Create initial libraries"""
    libraries = [
        # Brand libraries
        Library(
            id="lib_tss",
            name="TSS",
            name_es="TSS Products",
            library_type="brand",
            filter_value="TSS",
            description="Transmission Service & Supply - Reconstruidos de calidad",
            icon="🔧",
            color="#2563eb",
            scrape_url="https://tss-products.com"
        ),
        Library(
            id="lib_sonnax",
            name="Sonnax",
            name_es="Sonnax",
            library_type="brand",
            filter_value="Sonnax",
            description="Soluciones de ingeniería para transmisiones",
            icon="⚙️",
            color="#7c3aed"
        ),
        Library(
            id="lib_raybestos",
            name="Raybestos",
            name_es="Raybestos Powertrain",
            library_type="brand",
            filter_value="Raybestos",
            description="Materiales de fricción de calidad OEM",
            icon="🔴",
            color="#dc2626"
        ),
        # Product type libraries
        Library(
            id="lib_valve_bodies",
            name="Valve Bodies",
            name_es="Cuerpos de Válvulas",
            library_type="product_type",
            filter_value="cuerpo_de_valvulas",
            description="Cuerpos de válvulas reconstruidos y nuevos",
            icon="🎛️",
            color="#0891b2"
        ),
        Library(
            id="lib_friction_discs",
            name="Friction Discs",
            name_es="Discos de Pasta",
            library_type="product_type",
            filter_value="disco_de_pasta",
            description="Discos de fricción para transmisiones automáticas",
            icon="⚫",
            color="#854d0e"
        ),
        Library(
            id="lib_piston_kits",
            name="Piston Kits",
            name_es="Kits de Pistones",
            library_type="product_type",
            filter_value="kit_de_pistones",
            description="Kits de pistones para transmisiones",
            icon="🔘",
            color="#4f46e5"
        ),
        # Transmission code libraries
        Library(
            id="lib_4l60e",
            name="4L60E",
            name_es="4L60E / 4L65E / 4L70E",
            library_type="transmission",
            filter_value="4L60E",
            description="GM 4-speed automatic (1993-2013)",
            icon="🚗",
            color="#059669"
        ),
        Library(
            id="lib_6l80",
            name="6L80",
            name_es="6L80 / 6L90",
            library_type="transmission",
            filter_value="6L80",
            description="GM 6-speed automatic (2006-present)",
            icon="🚙",
            color="#0d9488"
        ),
    ]
    
    for library in libraries:
        existing = db.query(Library).filter(Library.id == library.id).first()
        if not existing:
            db.add(library)
            print(f"  ✅ Created library: {library.name}")
        else:
            print(f"  ⏭️  Library exists: {library.name}")
    
    db.commit()


def main():
    print("\n🚀 Initializing RAG SEO Engine Database\n")
    
    # Initialize tables
    print("📊 Creating database tables...")
    init_db()
    print("  ✅ Tables created\n")
    
    # Seed data
    db = SessionLocal()
    try:
        print("📝 Seeding prompt templates...")
        seed_prompt_templates(db)
        
        print("\n📚 Seeding libraries...")
        seed_libraries(db)
        
        print("\n✨ Database initialization complete!")
        print(f"   Database: sqlite:///./rag_seo.db")
        print(f"   Run server: uvicorn app.main:app --reload\n")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
