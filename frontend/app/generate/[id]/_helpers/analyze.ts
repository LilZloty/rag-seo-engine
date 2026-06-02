/**
 * Content quality analyzers for the product editor.
 *
 * Four pure functions that score a product's content across the three SEO
 * dimensions we care about, plus images. No React, no state — just inputs
 * → score + structured findings. Used by ProductMetricsPanel and any other
 * surface that wants a quick read on content health.
 */

export interface AnalyzerCheck {
    label: string;
    passed: boolean;
    importance: 'high' | 'medium' | 'low';
    tip: string;
}

export interface AEOAnalysis {
    score: number;
    checks: AnalyzerCheck[];
    snippetOpportunities: string[];
    recommendedQuestions: string[];
}

export interface GEOAnalysis {
    score: number;
    checks: AnalyzerCheck[];
    entityClarity: 'good' | 'medium' | 'poor';
    contextGaps: string[];
    authoritySignals: string[];
}

export interface SEOFieldAnalysis {
    score: number;
    maxScore: number;
    issues: string[];
    suggestions: string[];
}

export interface ImageAnalysis {
    score: number;
    total: number;
    withAlt: number;
    withGoodAlt: number;
    issues: string[];
}

// ============================================
// AEO (Answer Engine Optimization) — for voice search + featured snippets
// ============================================

export function analyzeAEOContent(
    title: string,
    description: string,
    metaDescription: string,
    fitments: Array<any>
): AEOAnalysis {
    const checks: AnalyzerCheck[] = [];
    const snippetOpportunities: string[] = [];
    const recommendedQuestions: string[] = [];
    let score = 0;

    const lowerDesc = description.toLowerCase();
    const lowerTitle = title.toLowerCase();

    // 1. Direct answer in first paragraph
    const firstParagraph = description.split(/<\/p>/i)[0] || '';
    const hasDirectAnswer = firstParagraph.length > 100 && firstParagraph.length < 400;
    checks.push({
        label: 'Respuesta directa en primer párrafo',
        passed: hasDirectAnswer,
        importance: 'high',
        tip: 'El primer párrafo debe responder qué es el producto en 2-3 oraciones',
    });
    if (hasDirectAnswer) score += 20;
    else snippetOpportunities.push('Agregar definición clara en el primer párrafo');

    // 2. Question-answer format
    const hasQuestions = description.includes('?');
    checks.push({
        label: 'Formato pregunta-respuesta',
        passed: hasQuestions,
        importance: 'high',
        tip: 'Incluir FAQ o preguntas comunes que los clientes hacen',
    });
    if (hasQuestions) {
        score += 20;
        const questions = description.match(/[^.!?]*\?/g) || [];
        questions.slice(0, 3).forEach(q => {
            if (q.length > 20) recommendedQuestions.push(q.trim());
        });
    } else {
        snippetOpportunities.push('Agregar sección de Preguntas Frecuentes');
        recommendedQuestions.push(`¿Qué es ${title}?`);
        recommendedQuestions.push(`¿Para qué vehículos sirve ${title}?`);
    }

    // 3. List structure (for featured snippets)
    const hasLists = description.includes('<ul>') || description.includes('<ol>') || description.includes('<li>');
    checks.push({
        label: 'Estructura de listas (pasos, beneficios)',
        passed: hasLists,
        importance: 'medium',
        tip: 'Usar listas para características, compatibilidades, pasos de instalación',
    });
    if (hasLists) score += 15;
    else snippetOpportunities.push('Convertir características a formato de lista');

    // 4. Concise definitions (30-60 words)
    // Explicit string[] typing prevents TS from inferring `never[]` for the `|| []` branch.
    const sentences: string[] = description.match(/[^.!?]+[.!?]+/g) ?? [];
    const conciseDefinitions = sentences.filter(s => {
        const wordCount = s.trim().split(/\s+/).length;
        return wordCount >= 30 && wordCount <= 60;
    });
    const hasConciseDefinitions = conciseDefinitions.length > 0;
    checks.push({
        label: 'Definiciones concisas (30-60 palabras)',
        passed: hasConciseDefinitions,
        importance: 'high',
        tip: 'Google prefiere respuestas directas de 40-60 palabras para snippets',
    });
    if (hasConciseDefinitions) score += 20;

    // 5. Table data (comparisons, specs)
    const hasTables = description.includes('<table>');
    checks.push({
        label: 'Datos en tabla (especificaciones)',
        passed: hasTables,
        importance: 'medium',
        tip: 'Tablas de especificaciones técnicas aparecen en snippets destacados',
    });
    if (hasTables) score += 10;

    // 6. Structured data intent
    const hasStructuredIntent =
        lowerDesc.includes('compatible con') ||
        lowerDesc.includes('aplicaciones') ||
        fitments.length > 0;
    checks.push({
        label: 'Datos estructurados de compatibilidad',
        passed: hasStructuredIntent,
        importance: 'high',
        tip: 'Marcar claramente años, marcas y modelos compatibles',
    });
    if (hasStructuredIntent) score += 15;

    // 7. Voice search keywords
    const voiceKeywords = ['cómo', 'qué es', 'para qué', 'cuándo', 'dónde', 'por qué'];
    const hasVoiceKeywords = voiceKeywords.some(kw => lowerDesc.includes(kw));
    checks.push({
        label: 'Keywords de búsqueda por voz',
        passed: hasVoiceKeywords,
        importance: 'medium',
        tip: 'Incluir frases como "Cómo instalar...", "Qué es..."',
    });
    if (hasVoiceKeywords) score += 10;

    // Generate recommended questions based on fitment context
    if (fitments.length > 0) {
        recommendedQuestions.push(`¿Con qué transmisiones es compatible ${title}?`);
        const makes = [...new Set(fitments.flatMap(f => f.make))].slice(0, 2);
        if (makes.length > 0) {
            recommendedQuestions.push(`¿Sirve para ${makes.join(', ')}?`);
        }
    }

    return { score: Math.min(100, score), checks, snippetOpportunities, recommendedQuestions };
}

// ============================================
// GEO (Generative Engine Optimization) — for AI search (ChatGPT, Perplexity, Bing AI)
// ============================================

export function analyzeGEOContent(
    title: string,
    description: string,
    metaTitle: string,
    fitments: Array<any>,
    vehicleFitments: Array<any>
): GEOAnalysis {
    const checks: AnalyzerCheck[] = [];
    const contextGaps: string[] = [];
    const authoritySignals: string[] = [];
    let score = 0;

    const lowerDesc = description.toLowerCase();
    const lowerTitle = title.toLowerCase();

    // 1. Clear entity definition
    const entityPatterns = [
        /es (un|una) [a-z\s]+ (transmisión|convertidor|kit|solenoides?)/i,
        /(transmisión|convertidor|solenoides?) (automática|de transmisión)/i,
    ];
    const hasEntityDefinition =
        entityPatterns.some(p => p.test(description)) ||
        description.match(/\b(transmisión|transmission|convertidor|converter|solenoid)\b/i);
    checks.push({
        label: 'Definición clara de entidad (qué ES)',
        passed: !!hasEntityDefinition,
        importance: 'high',
        tip: 'La IA debe entender inmediatamente qué tipo de producto es',
    });
    if (hasEntityDefinition) {
        score += 20;
        authoritySignals.push('Entidad claramente definida');
    } else {
        contextGaps.push('Definición de producto ambigua');
    }

    // 2. Technical specifications
    const techSpecs = ['número de parte', 'part number', 'oem', 'sku', 'especificaciones'];
    const hasTechSpecs = techSpecs.some(spec => lowerDesc.includes(spec));
    checks.push({
        label: 'Especificaciones técnicas detalladas',
        passed: hasTechSpecs,
        importance: 'high',
        tip: 'Números de parte OEM, especificaciones técnicas ayudan a la IA',
    });
    if (hasTechSpecs) {
        score += 15;
        authoritySignals.push('Especificaciones técnicas presentes');
    } else {
        contextGaps.push('Faltan especificaciones técnicas');
    }

    // 3. Vehicle compatibility context
    const hasCompatibilityContext =
        lowerDesc.includes('compatible') ||
        lowerDesc.includes('aplicaciones') ||
        lowerDesc.includes('vehículos') ||
        vehicleFitments.length > 0;
    checks.push({
        label: 'Contexto de compatibilidad vehicular',
        passed: hasCompatibilityContext,
        importance: 'high',
        tip: 'Las IA usan datos de compatibilidad para responder "sirve para mi carro?"',
    });
    if (hasCompatibilityContext) {
        score += 20;
        authoritySignals.push('Datos de compatibilidad claros');
        if (vehicleFitments.length > 0) {
            authoritySignals.push(`${vehicleFitments.length} vehículos documentados`);
        }
    } else {
        contextGaps.push('Falta contexto de compatibilidad');
    }

    // 4. Relationship mapping
    const relationshipTerms = ['funciona con', 'compatible con', 'se usa en', 'para transmisiones'];
    const hasRelationships = relationshipTerms.some(term => lowerDesc.includes(term));
    checks.push({
        label: 'Mapeo de relaciones (con qué conecta)',
        passed: hasRelationships,
        importance: 'high',
        tip: 'Las IA construyen grafos de conocimiento con relaciones explícitas',
    });
    if (hasRelationships) {
        score += 15;
        authoritySignals.push('Relaciones de compatibilidad mapeadas');
    } else {
        contextGaps.push('Relaciones del producto no claras');
    }

    // 5. Unique value proposition
    const valueProps = ['garantía', 'calidad', 'original', 'oem', 'mejor', 'único'];
    const hasValueProp = valueProps.some(vp => lowerDesc.includes(vp));
    checks.push({
        label: 'Propuesta de valor única',
        passed: hasValueProp,
        importance: 'medium',
        tip: 'La IA debe entender por qué elegir este producto sobre otros',
    });
    if (hasValueProp) {
        score += 10;
        authoritySignals.push('Diferenciadores claros');
    }

    // 6. Trust indicators
    const trustSignals = ['garantía', 'años de experiencia', 'certificado', 'iso', 'garantía de por vida'];
    const hasTrust = trustSignals.some(ts => lowerDesc.includes(ts));
    checks.push({
        label: 'Indicadores de confianza',
        passed: hasTrust,
        importance: 'medium',
        tip: 'Menciones de garantía, certificaciones aumentan credibilidad',
    });
    if (hasTrust) {
        score += 10;
        authoritySignals.push('Señales de confianza presentes');
    }

    // 7. Content depth
    const wordCount = description.replace(/<[^>]*>/g, '').split(/\s+/).length;
    const hasDepth = wordCount > 200;
    checks.push({
        label: 'Contenido profundo (>200 palabras)',
        passed: hasDepth,
        importance: 'medium',
        tip: 'Las IA prefieren contenido completo para generar respuestas',
    });
    if (hasDepth) {
        score += 10;
        authoritySignals.push('Contenido profundo');
    } else {
        contextGaps.push('Contenido superficial');
    }

    let entityClarity: 'good' | 'medium' | 'poor' = 'poor';
    if (hasEntityDefinition && hasCompatibilityContext && hasRelationships) {
        entityClarity = 'good';
    } else if (hasEntityDefinition || hasCompatibilityContext) {
        entityClarity = 'medium';
    }

    return { score: Math.min(100, score), checks, entityClarity, contextGaps, authoritySignals };
}

// ============================================
// SEO field analyzer — per-field score for title/description/meta_*
// ============================================

export function analyzeSEOContent(
    content: string,
    type: 'title' | 'description' | 'meta_title' | 'meta_description'
): SEOFieldAnalysis {
    const issues: string[] = [];
    const suggestions: string[] = [];
    let score = 0;
    const maxScore = 100;

    if (!content || content.trim().length === 0) {
        return { score: 0, maxScore, issues: ['Contenido vacío'], suggestions: ['Agregar contenido'] };
    }

    const lowerContent = content.toLowerCase();

    switch (type) {
        case 'title':
            if (content.length < 30) {
                issues.push('Título muy corto (< 30 caracteres)');
                suggestions.push('Expandir el título con keywords relevantes');
            } else if (content.length > 60) {
                issues.push('Título muy largo (> 60 caracteres) - Google truncará');
                suggestions.push('Acortar el título a 50-60 caracteres para mejor SEO');
                score += 10;
            } else {
                score += 25;
            }

            const genericWords = ['producto', 'item', 'nuevo', 'nueva'];
            const hasGenericOnly = genericWords.every(w => lowerContent.includes(w)) && content.length < 40;
            if (hasGenericOnly) {
                issues.push('Título demasiado genérico');
                suggestions.push('Incluir palabras clave específicas del producto');
            } else {
                score += 25;
            }

            if (!lowerContent.includes('example store') && !lowerContent.includes('example-store')) {
                suggestions.push('Considerar agregar la marca al título');
            } else {
                score += 15;
            }

            if (/\d/.test(content)) {
                score += 15;
            } else {
                suggestions.push('Agregar números o especificaciones técnicas para mejor CTR');
            }

            if (content === content.toUpperCase()) {
                issues.push('Título en MAYÚSCULAS');
                suggestions.push('Usar capitalización apropiada');
                score -= 10;
            } else {
                score += 10;
            }
            break;

        case 'description':
        case 'meta_description':
            if (content.length < 100) {
                issues.push('Descripción muy corta');
                suggestions.push('Expandir a 150-300 palabras con información valiosa');
            } else if (content.length > 500 && type === 'meta_description') {
                issues.push('Meta descripción demasiado larga (> 160 caracteres recomendado)');
                suggestions.push('Acortar meta descripción a 150-160 caracteres');
                score += 10;
            } else {
                score += 20;
            }

            const hasHTML = /<[a-z][\s\S]*>/i.test(content);
            if (!hasHTML && content.length > 200) {
                suggestions.push('Agregar formato HTML (h2, p, ul) para mejor estructura');
            } else if (hasHTML) {
                score += 15;
            }

            const wordCount = content.split(/\s+/).length;
            if (wordCount < 50 && content.length > 200) {
                suggestions.push('Aumentar densidad de palabras clave');
            } else {
                score += 20;
            }

            const sentences = content.split(/[.!?]+/).filter(s => s.trim().length > 10);
            const uniqueSentences = new Set(sentences.map(s => s.trim().toLowerCase()));
            if (uniqueSentences.size < sentences.length * 0.8) {
                issues.push('Posible contenido repetitivo');
                suggestions.push('Revisar y eliminar frases repetidas');
            } else {
                score += 15;
            }

            const ctaWords = ['comprar', 'adquirir', 'ordenar', 'llamar', 'contactar', 'ahora', 'hoy'];
            const hasCTA = ctaWords.some(w => lowerContent.includes(w));
            if (!hasCTA) {
                suggestions.push('Agregar llamado a la acción (CTA)');
            } else {
                score += 15;
            }

            if (type === 'description' && !lowerContent.includes('compatible') && !lowerContent.includes('vehículo')) {
                suggestions.push('Mencionar compatibilidad con vehículos');
            } else if (type === 'description') {
                score += 15;
            }
            break;

        case 'meta_title':
            if (content.length < 50) {
                issues.push('Meta título muy corto');
                suggestions.push('Expandir a 50-60 caracteres');
            } else if (content.length > 70) {
                issues.push('Meta título muy largo');
                suggestions.push('Reducir a máximo 60 caracteres');
                score += 15;
            } else {
                score += 40;
            }

            if (content.includes('|')) {
                score += 20;
            } else {
                suggestions.push('Usar formato: "Título | Example Store"');
            }

            if (/\d/.test(content)) {
                score += 20;
            }
            break;
    }

    return { score: Math.max(0, Math.min(100, score)), maxScore, issues, suggestions };
}

// ============================================
// Image analyzer — alt text coverage + quality
// ============================================

export function analyzeImages(
    images: Array<{ alt: string; filename: string }>
): ImageAnalysis {
    const issues: string[] = [];
    let score = 0;

    if (images.length === 0) {
        return { score: 0, total: 0, withAlt: 0, withGoodAlt: 0, issues: ['Sin imágenes'] };
    }

    const withAlt = images.filter(img => img.alt && img.alt.trim().length > 0).length;
    const withGoodAlt = images.filter(img =>
        img.alt &&
        img.alt.trim().length > 10 &&
        !img.alt.toLowerCase().includes('image') &&
        !img.alt.toLowerCase().includes('img') &&
        !img.alt.toLowerCase().includes('foto')
    ).length;

    score += Math.min(30, images.length * 10);

    const altCoverage = withAlt / images.length;
    score += Math.round(altCoverage * 40);

    const qualityCoverage = withGoodAlt / images.length;
    score += Math.round(qualityCoverage * 30);

    if (withAlt === 0) {
        issues.push('Ninguna imagen tiene texto alternativo');
    } else if (withAlt < images.length) {
        issues.push(`${images.length - withAlt} imágenes sin alt text`);
    }

    if (withGoodAlt < withAlt) {
        issues.push(`${withAlt - withGoodAlt} imágenes con alt text genérico`);
    }

    return { score: Math.min(100, score), total: images.length, withAlt, withGoodAlt, issues };
}
