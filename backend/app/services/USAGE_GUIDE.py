"""
Simple Usage Guide for SEO Enhancements
========================================

Step-by-step examples for using the new text-based SEO features.
"""

# ============================================================================
# EXAMPLE 1: Generate a Complete Enhanced Article
# ============================================================================

async def example_1_generate_full_article():
    """
    Generate a complete blog article with ALL SEO enhancements.
    This is the main function you'll use.
    """
    from app.services.blog_content_generator import get_blog_generator
    from app.db.session import get_db
    
    # Get database session
    db = next(get_db())
    
    # Get the blog generator
    generator = get_blog_generator(db)
    
    # Generate article for P0700
    article = await generator.generate_fault_code_article(
        fault_code="P0700",
        include_products=True,
        word_count=1000,
        tone="professional",
        include_faq_expansion=True,      # Add 10-15 FAQs
        include_eeat=True,               # Add authority box
        include_internal_links=True,     # Add internal links
        include_comparison_tables=True   # Add comparison tables
    )
    
    # The article now contains everything:
    print(f"Title: {article['title']}")
    print(f"Quality Score: {article['content_quality_score']['total_score']}/100")
    print(f"Rating: {article['content_quality_score']['rating']}")
    
    # Access the enhanced content
    enhanced = article['enhanced_content']
    
    # 1. FAQs (10-15 questions)
    faqs = enhanced['faq_expansion']['faqs']
    print(f"\nGenerated {len(faqs)} FAQs:")
    for faq in faqs[:3]:  # Show first 3
        print(f"  Q: {faq['question']}")
        print(f"  A: {faq['answer'][:80]}...")
    
    # 2. E-E-A-T Authority Box (HTML)
    eeat_html = enhanced['eeat_box']['html']
    print(f"\nE-E-A-T Box HTML ready: {len(eeat_html)} characters")
    
    # 3. Internal Links
    links = enhanced['internal_links']['links']
    print(f"\nGenerated {len(links)} internal links:")
    for link in links:
        print(f"  - {link['text']} → {link['url']}")
    
    # 4. Comparison Tables
    if enhanced['comparison_tables']:
        print(f"\nComparison with: {enhanced['comparison_tables']['vs_code']}")
    
    return article


# ============================================================================
# EXAMPLE 2: Use Individual Components (If You Need Just One Feature)
# ============================================================================

async def example_2_generate_only_faqs():
    """
    Generate ONLY FAQs for an existing article.
    Use this if you want to add FAQs to content you already have.
    """
    from app.services.faq_expansion_engine import get_faq_engine
    
    # Get the FAQ engine
    faq_engine = get_faq_engine()
    
    # Generate FAQs for P0700
    faqs = faq_engine.generate_faqs(
        fault_code="P0700",
        fault_name="Transmission Control System Malfunction",
        symptoms=[
            "Luz check engine encendida",
            "Transmisión en modo emergencia",
            "Cambios bruscos"
        ],
        causes=[
            "Solenoides desgastados",
            "Sensor de presión defectuoso"
        ],
        transmission="4L60E",
        kit_price=2400.00
    )
    
    # Get the top 10 FAQs
    print(f"Generated {len(faqs)} FAQs:")
    for i, faq in enumerate(faqs[:5], 1):
        print(f"\n{i}. {faq.question}")
        print(f"   Answer: {faq.answer[:100]}...")
        print(f"   Category: {faq.category}")
    
    # Generate Schema.org markup
    schema = faq_engine.generate_faq_schema(faqs)
    print(f"\nSchema.org FAQPage markup ready!")
    
    return faqs, schema


async def example_3_generate_only_eeat_box():
    """
    Generate ONLY an E-E-A-T authority box.
    Use this to add trust signals to any page.
    """
    from app.services.eeat_generator import get_eeat_generator
    
    # Get the E-E-A-T generator
    eeat_gen = get_eeat_generator()
    
    # Generate authority box for a guide
    box = eeat_gen.generate_authority_box(
        context="guide",  # Options: 'general', 'product', 'guide', 'comparison'
        fault_code="P0700",
        transmission="4L60E"
    )
    
    # Access the data
    print(f"Title: {box.title}")
    print(f"Badge: {box.badge_text}")
    
    print(f"\nStatistics:")
    for stat in box.statistics:
        print(f"  - {stat['label']}: {stat['value']}")
    
    print(f"\nTrust Signals:")
    for signal in box.trust_signals[:3]:
        print(f"  ✓ {signal}")
    
    # The HTML is ready to insert into your article
    html = box.html_output
    print(f"\nHTML ready ({len(html)} characters)")
    
    return box


async def example_4_generate_only_internal_links():
    """
    Generate ONLY internal links for an article.
    Use this to add strategic links to existing content.
    """
    from app.services.internal_linking import get_linking_engine
    
    # Get the linking engine
    linker = get_linking_engine()
    
    # Generate links for an article about P0700
    links = linker.generate_article_links(
        current_fault_code="P0700",
        mentioned_products=["kit-solenoide-4l60e", "sensor-presion-transmision"],
        transmission="4L60E",
        max_links=5
    )
    
    print(f"Generated {len(links)} internal links:")
    for link in links:
        print(f"\n  Text: {link.text}")
        print(f"  URL: {link.url}")
        print(f"  Type: {link.link_type}")
        print(f"  Priority: {link.priority}/10")
    
    # Generate HTML for the links section
    links_html = linker.generate_contextual_links_html(links)
    print(f"\nLinks HTML ready ({len(links_html)} characters)")
    
    # Generate breadcrumb
    breadcrumb = linker.generate_breadcrumb(
        fault_code="P0700",
        product_name="Kit Solenoide 4L60E"
    )
    print(f"\nBreadcrumb: {' > '.join([b['name'] for b in breadcrumb])}")
    
    return links


async def example_5_generate_only_comparison():
    """
    Generate ONLY a comparison table.
    Use this for "P0700 vs P0706" type content.
    """
    from app.services.comparison_generator import get_comparison_generator
    
    # Get the comparison generator
    comp_gen = get_comparison_generator()
    
    # Compare P0700 vs P0706
    comparison = comp_gen.generate_fault_code_comparison("P0700", "P0706")
    
    print(f"Comparison: {comparison['code_a']} vs {comparison['code_b']}")
    print(f"\nFeatures compared:")
    for row in comparison['rows']:
        winner = "←" if row['winner'] == 'a' else "→" if row['winner'] == 'b' else "="
        print(f"  {row['feature']}: {row['value_a']} {winner} {row['value_b']}")
    
    # The HTML table is ready
    html = comparison['html']
    print(f"\nComparison table HTML ready ({len(html)} characters)")
    
    # Generate related codes table
    related_html = comp_gen.generate_related_codes_table(
        primary_code="P0700",
        related_codes=["P0706", "P0715", "P0730"]
    )
    print(f"Related codes table HTML ready ({len(related_html)} characters)")
    
    return comparison


# ============================================================================
# EXAMPLE 6: Build Complete Article HTML
# ============================================================================

def example_6_build_complete_html():
    """
    Assemble all components into a complete article.
    This shows how to put everything together.
    """
    
    # Assume we have the article data from Example 1
    article = {
        'title': 'Código P0700: Guía Completa',
        'sections': [
            {'heading': '¿Qué es el Código P0700?', 'content': '<p>El código P0700...</p>', 'type': 'intro'},
            {'heading': 'Síntomas', 'content': '<p>Los síntomas incluyen...</p>', 'type': 'symptoms'},
        ],
        'enhanced_content': {
            'faq_expansion': {
                'faqs': [
                    {'question': '¿Qué significa P0700?', 'answer': 'Indica problema en la transmisión...'},
                    {'question': '¿Es grave?', 'answer': 'Sí, debe repararse pronto...'},
                ]
            },
            'eeat_box': {
                'html': '<div class="eeat-box">...</div>'
            },
            'internal_links': {
                'links': [
                    {'text': 'código P0706', 'url': '/blogs/news/p0706'}
                ]
            }
        }
    }
    
    # Build the HTML
    html_parts = []
    
    # 1. Title
    html_parts.append(f"<h1>{article['title']}</h1>")
    
    # 2. E-E-A-T Box (at the top for trust)
    html_parts.append(article['enhanced_content']['eeat_box']['html'])
    
    # 3. Main content sections
    for section in article['sections']:
        html_parts.append(f"<h2>{section['heading']}</h2>")
        html_parts.append(section['content'])
    
    # 4. FAQ Section
    html_parts.append("<h2>Preguntas Frecuentes</h2>")
    for faq in article['enhanced_content']['faq_expansion']['faqs']:
        html_parts.append(f"<h3>{faq['question']}</h3>")
        html_parts.append(f"<p>{faq['answer']}</p>")
    
    # 5. Internal Links Section
    html_parts.append("<h2>Contenido Relacionado</h2>")
    html_parts.append("<ul>")
    for link in article['enhanced_content']['internal_links']['links']:
        html_parts.append(f'<li><a href="{link["url"]}">{link["text"]}</a></li>')
    html_parts.append("</ul>")
    
    # Combine everything
    full_html = "\n".join(html_parts)
    
    print("Complete article HTML assembled!")
    print(f"Total length: {len(full_html)} characters")
    
    return full_html


# ============================================================================
# QUICK REFERENCE: Most Common Use Cases
# ============================================================================

"""
QUICK START - Copy and paste these:

1. GENERATE COMPLETE ARTICLE:
   article = await generator.generate_fault_code_article("P0700")

2. GET FAQS ONLY:
   faqs = faq_engine.generate_faqs(fault_code="P0700", ...)

3. GET AUTHORITY BOX ONLY:
   box = eeat_gen.generate_authority_box(context="guide")

4. GET INTERNAL LINKS ONLY:
   links = linker.generate_article_links(current_fault_code="P0700")

5. GET COMPARISON TABLE ONLY:
   comparison = comp_gen.generate_fault_code_comparison("P0700", "P0706")

KEY DATA STRUCTURES:

Article Object:
{
    "title": str,
    "meta_description": str,
    "sections": [...],
    "enhanced_content": {
        "faq_expansion": {"faqs": [...], "schema": {...}},
        "eeat_box": {"html": "...", "statistics": [...]},
        "internal_links": {"links": [...], "breadcrumb": [...]},
        "comparison_tables": {"html": "...", "rows": [...]}
    },
    "content_quality_score": {"total_score": 85, "rating": "excellent"}
}

FAQ Object:
{
    "question": str,
    "answer": str,
    "category": str,  # symptom, cause, solution, cost, urgency
    "priority": int   # 1-10
}

Internal Link Object:
{
    "text": str,       # Anchor text
    "url": str,        # Target URL
    "type": str,       # related, product, collection, guide
    "priority": int    # 1-10
}
"""


# ============================================================================
# RUN EXAMPLES
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    # Run the examples
    print("=" * 60)
    print("Example 1: Generate Full Article")
    print("=" * 60)
    # asyncio.run(example_1_generate_full_article())
    
    print("\n" + "=" * 60)
    print("Example 2: Generate Only FAQs")
    print("=" * 60)
    # asyncio.run(example_2_generate_only_faqs())
    
    print("\nGuides created! Uncomment the asyncio.run() lines to execute.")
