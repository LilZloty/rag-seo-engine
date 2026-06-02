"""
Migration script to create library-related tables for Phase 2 RAG system.
Run this once to add the tables to your database.
"""
import sqlite3
import os

# Find the database file
db_path = os.path.join(os.path.dirname(__file__), 'rag_seo.db')
if not os.path.exists(db_path):
    db_path = 'rag_seo.db'

print(f"Looking for database at: {db_path}")

if not os.path.exists(db_path):
    print("❌ Database file not found!")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# List of tables to create
tables_created = []
tables_skipped = []

# 1. Libraries table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS libraries (
            id TEXT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            name_es VARCHAR(100),
            library_type VARCHAR(50) NOT NULL,
            filter_value VARCHAR(100),
            description TEXT,
            icon VARCHAR(50),
            color VARCHAR(20),
            prompt_template_id TEXT,
            document_count INTEGER DEFAULT 0,
            last_updated_at TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            scrape_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP,
            FOREIGN KEY (prompt_template_id) REFERENCES prompt_templates(id)
        )
    """)
    # Check if table was just created or already existed
    cursor.execute("SELECT COUNT(*) FROM libraries")
    tables_created.append("libraries")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        tables_skipped.append("libraries")
    else:
        print(f"Error creating libraries: {e}")

# 2. Documents table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            content TEXT NOT NULL,
            content_preview VARCHAR(500),
            source_type VARCHAR(50) NOT NULL,
            source_url TEXT,
            source_filename VARCHAR(255),
            brands JSON DEFAULT '[]',
            product_types JSON DEFAULT '[]',
            transmission_codes JSON DEFAULT '[]',
            part_numbers JSON DEFAULT '[]',
            tags JSON DEFAULT '[]',
            chunk_count INTEGER DEFAULT 0,
            qdrant_ids JSON DEFAULT '[]',
            embedding_model VARCHAR(100),
            verified BOOLEAN DEFAULT 0,
            verified_by VARCHAR(100),
            verified_at TIMESTAMP,
            quality_score INTEGER,
            scraped_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    tables_created.append("documents")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        tables_skipped.append("documents")
    else:
        print(f"Error creating documents: {e}")

# 3. Document-Library association table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_library (
            document_id TEXT NOT NULL,
            library_id TEXT NOT NULL,
            PRIMARY KEY (document_id, library_id),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
        )
    """)
    tables_created.append("document_library")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        tables_skipped.append("document_library")
    else:
        print(f"Error creating document_library: {e}")

# 4. Document chunks table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            token_count INTEGER,
            qdrant_id TEXT UNIQUE,
            chunk_metadata JSON DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    tables_created.append("document_chunks")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        tables_skipped.append("document_chunks")
    else:
        print(f"Error creating document_chunks: {e}")

# 5. Prompt templates table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompt_templates (
            id TEXT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            template_type VARCHAR(50) NOT NULL,
            system_instructions TEXT NOT NULL,
            example_output TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_readonly BOOLEAN DEFAULT 0,
            priority INTEGER DEFAULT 0,
            product_type_filter VARCHAR(50),
            brand_filter VARCHAR(50),
            transmission_filter VARCHAR(50),
            usage_count INTEGER DEFAULT 0,
            last_used_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    tables_created.append("prompt_templates")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        tables_skipped.append("prompt_templates")
    else:
        print(f"Error creating prompt_templates: {e}")

# 6. Generation history table
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generation_history (
            id TEXT PRIMARY KEY,
            product_id TEXT,
            libraries_used JSON DEFAULT '[]',
            prompts_used JSON DEFAULT '[]',
            image_count INTEGER,
            image_types JSON DEFAULT '[]',
            documents_retrieved JSON DEFAULT '[]',
            chunks_retrieved JSON DEFAULT '[]',
            h1_title VARCHAR(60),
            description_html TEXT,
            alt_tags JSON,
            compatible_vehicles TEXT,
            short_description VARCHAR(160),
            meta_title VARCHAR(70),
            meta_description VARCHAR(160),
            url_handle VARCHAR(255),
            hashtags TEXT,
            llm_used VARCHAR(50),
            llm_tokens_input INTEGER,
            llm_tokens_output INTEGER,
            generation_time_ms INTEGER,
            status VARCHAR(20) DEFAULT 'draft',
            approved_at TIMESTAMP,
            published_at TIMESTAMP,
            published_to_shopify BOOLEAN DEFAULT 0,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    tables_created.append("generation_history")
except sqlite3.OperationalError as e:
    if "already exists" in str(e):
        tables_skipped.append("generation_history")
    else:
        print(f"Error creating generation_history: {e}")

# Create indexes
try:
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_generation_history_product_id ON generation_history(product_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_libraries_library_type ON libraries(library_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_templates_template_type ON prompt_templates(template_type)")
except Exception as e:
    print(f"Note: Some indexes may already exist: {e}")

conn.commit()
conn.close()

print("\n✅ Migration complete!")
print(f"   Tables created/verified: {', '.join(tables_created) if tables_created else 'None'}")
if tables_skipped:
    print(f"   Tables already existed: {', '.join(tables_skipped)}")
print("\n📚 Phase 2 RAG Library tables are ready!")
