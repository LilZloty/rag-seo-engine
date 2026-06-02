/**
 * Vehicle Fitment Parser
 * 
 * Extracts vehicle fitment data from HTML product descriptions.
 * Supports:
 * - H4 section detection with multiple keywords
 * - Table parsing with smart column detection
 * - DIV-wrapped tables (responsive layouts)
 * - Plain text fallback with brand detection
 * - 2-digit and 4-digit year formats
 */

// ============ Types ============

export interface VehicleFitment {
    id: number;
    make: string[];
    modelo: string[];
    year_start: number | null;
    year_end: number | null;
    transmission_type: string;
    transmission_model: string;
    engine: string;
}

export interface ParseOptions {
    title?: string;
    vendor?: string;
}

export interface ParseResult {
    fitments: VehicleFitment[];
    transmissionModel: string;
    warnings: string[];
}

// ============ Constants ============

const H4_KEYWORDS = [
    'vehículo', 'vehiculo', 'vehiculos',
    'compatible', 'compatibility',
    'aplicación', 'aplicaciones', 'aplicacion',
    'fitment', 'fits',
    'modelos', 'vehicles'
];

const TABLE_HEADER_KEYWORDS = [
    'marca', 'make', 'modelo', 'model',
    'año', 'años', 'year', 'years',
    'motor', 'engine', 'drivetrain',
    'transmisión', 'transmision', 'transmission', 'caja'
];

// Specific transmission MODEL codes (JF011E, RE0F10A, 09G, 4L60E…). Preferred over generic types.
const SPECIFIC_TRANS_PATTERN = /\b(09G|09M|09D|09K|01M|01N|01P|01J|02E|02M|0AM|0AW|0B5|0BH|0BT|0CK|0DD|0GC|DQ200|DQ250|DQ381|DQ500|DL382|DL501|68RFE|48RE|545RFE|62TE|42RLE|A518|A618|46RE|47RE|A343F|A340|A750|A760|722\.\d|4L60E|4L80E|5R55|6R80|10R80|AS68RC|AS69RC|AS66RC|TR-6060|T56|TR-6070|CD4E|AX4N|4F27E|4F50N|4R70W|AOD|AODE|E4OD|4R100|5R110|6R140|A4CF\d*|A6LF\d*|A6MF\d*|A8LF\d*|F4A\d*|F5A\d*|JF010E|JF011E|JF015E|JF016E|JF017E|JF018E|JF019E|JF020E|JF506E|JF613E|RE0F06A|RE0F08A|RE0F09A|RE0F10[A-E]|RE0F11A|RE4F03[AB]|RE4F04[AB]|RE4R01A|RE5F22A|RE5R01A|RE5R05A|RE7R01A|5HP19|5HP24|6HP19|6HP21|6HP26|6HP28|8HP45|8HP55|8HP70|8HP90|U140E|U240E|U250E|U660E|U760E|U880E)\b/gi;

// Generic transmission TYPES (CVT, DCT, DSG…). Fallback when no specific code is present.
const GENERIC_TRANS_PATTERN = /\b(CVT|DCT|DSG|AMT|TorqShift|Allison|Aisin|ZF)\b/gi;

// Kept for backwards compatibility / single-pass scans. Specific first so extractTransmissionModel prefers JF011E over CVT.
const TRANSMISSION_PATTERNS = [SPECIFIC_TRANS_PATTERN, GENERIC_TRANS_PATTERN];

const KNOWN_BRANDS = [
    'DODGE', 'MITSUBISHI', 'JEEP', 'CHRYSLER', 'FORD', 'CHEVROLET', 'GMC', 'TOYOTA',
    'NISSAN', 'HONDA', 'MAZDA', 'VOLKSWAGEN', 'AUDI', 'BMW', 'SUBARU', 'HYUNDAI',
    'KIA', 'RAM', 'LINCOLN', 'MERCURY', 'BUICK', 'CADILLAC', 'ACURA', 'INFINITI',
    'LEXUS', 'PONTIAC', 'SATURN', 'SAAB', 'VOLVO', 'SEAT', 'SKODA', 'PEUGEOT',
    'CITROEN', 'MG', 'ROEWE', 'DAEWOO', 'SUZUKI', 'MERCEDES', 'MERCEDES-BENZ',
    'MARUTI-SUZUKI', 'MARUTI', 'PROTON', 'RENAULT', 'DACIA', 'OPEL', 'VAUXHALL',
    'DAIHATSU', 'ISUZU', 'FIAT', 'ALFA ROMEO', 'LANCIA', 'MINI', 'SMART', 'GEELY',
    'CHERY', 'BYD', 'JAC', 'GREAT WALL', 'CHANGAN', 'FOTON', 'HAVAL', 'SSANGYONG'
];

// ============ Helper Functions ============

/**
 * Convert 2-digit year to 4-digit (00-29 → 2000-2029, 30-99 → 1930-1999)
 */
function toFullYear(yr: string | undefined): number | null {
    if (!yr) return null;
    const num = parseInt(yr);
    if (yr.length === 2) {
        return num < 30 ? 2000 + num : 1900 + num;
    }
    return num;
}

/**
 * Generate unique ID for fitment
 */
function generateId(): number {
    return Date.now() + Math.random();
}

/**
 * Extract transmission model from text. Specific codes (JF011E, RE0F10A) preferred over generic types (CVT).
 */
function extractTransmissionModel(text: string): string {
    for (const pattern of TRANSMISSION_PATTERNS) {
        const match = text.match(pattern);
        if (match) {
            return match[0].toUpperCase();
        }
    }
    return '';
}

/** Extract a specific transmission code (JF011E, RE0F10A, 4L60E…) from text. */
function extractSpecificTransCode(text: string): string {
    const match = text.match(SPECIFIC_TRANS_PATTERN);
    return match ? match[0].toUpperCase() : '';
}

/** Extract a generic transmission type (CVT, DCT, DSG…) from text. */
function extractGenericTransType(text: string): string {
    const match = text.match(GENERIC_TRANS_PATTERN);
    return match ? match[0].toUpperCase() : '';
}

/**
 * Find H4 element containing vehicle-related keywords
 */
function findVehicleSection(doc: Document): Element | null {
    const h4Elements = doc.querySelectorAll('h4');

    for (const h4 of Array.from(h4Elements)) {
        const text = h4.textContent?.toLowerCase() || '';
        if (H4_KEYWORDS.some(kw => text.includes(kw))) {
            console.log('[FitmentParser] Found vehicle section H4:', text);
            return h4;
        }
    }
    return null;
}

/**
 * Collect all tables including those inside DIVs
 */
function collectAllTables(doc: Document): Element[] {
    const allTables: Element[] = [];
    doc.querySelectorAll('table').forEach(t => allTables.push(t));
    doc.querySelectorAll('div table').forEach(t => {
        if (!allTables.includes(t)) allTables.push(t);
    });
    return allTables;
}

/**
 * Check if table has vehicle-related headers
 */
function isVehicleTable(table: Element): boolean {
    const headerCells = Array.from(table.querySelectorAll('th, thead td, tr:first-child td'));
    const headerText = headerCells.map(h => h.textContent?.toLowerCase().trim() || '').join(' ');
    const matchingKeywords = TABLE_HEADER_KEYWORDS.filter(kw => headerText.includes(kw));
    return matchingKeywords.length >= 2;
}

// ============ Table Parser ============

function parseTableForVehicles(table: Element, fitments: VehicleFitment[]): void {
    const rows = Array.from(table.querySelectorAll('tr'));
    if (rows.length < 2) return;

    const headers = Array.from(rows[0].querySelectorAll('th, td'))
        .map(h => h.textContent?.toLowerCase().trim() || '');

    // Map columns by header content
    const colMap = {
        make: headers.findIndex(h => h.includes('marca') || h.includes('make')),
        model: headers.findIndex(h => h.includes('modelo') || h.includes('model')),
        years: headers.findIndex(h => h.includes('año') || h.includes('year') || h.includes('años')),
        transmission: headers.findIndex(h => h.includes('transmisión') || h.includes('transmision') || h.includes('transmission') || h.includes('caja')),
        engine: headers.findIndex(h => h.includes('motor') || h.includes('engine') || h.includes('drivetrain'))
    };

    // Fallback defaults if headers aren't clear (headerless table assumes Marca/Modelo/Año/Motor).
    // No positional fallback for transmission — if there's no transmission header, leave it -1
    // and let the title-extracted value fill it via post-processing. Otherwise we'd shadow the engine column.
    if (colMap.make === -1) colMap.make = 0;
    if (colMap.model === -1) colMap.model = 1;
    if (colMap.years === -1) colMap.years = 2;
    if (colMap.engine === -1) colMap.engine = 3;

    rows.slice(1).forEach((row) => {
        const cells = Array.from(row.querySelectorAll('td'));
        if (cells.length < 2) return;

        const makeText = cells[colMap.make]?.textContent?.trim() || '';
        const modelText = cells[colMap.model]?.textContent?.trim() || '';
        const yearsText = cells[colMap.years]?.textContent?.trim() || '';
        const transText = colMap.transmission >= 0 ? (cells[colMap.transmission]?.textContent?.trim() || '') : '';
        const engineText = cells[colMap.engine]?.textContent?.trim() || '';

        // Try 4-digit year range, then 2-digit, then single year
        const yearMatch = yearsText.match(/(\d{4})\s*[-–—]\s*(\d{4})/) ||
            yearsText.match(/\b(\d{2})\s*[-–—]\s*(\d{2})\b/) ||
            yearsText.match(/(\d{4})/);

        // Classify the transmission cell: specific code (JF011E) wins; otherwise generic type (CVT);
        // otherwise preserve raw cell text (e.g. "Aisin AW80-40LS") rather than drop it.
        const rowSpecificCode = extractSpecificTransCode(transText);
        const rowGenericType = extractGenericTransType(transText);
        const rowTransModel = rowSpecificCode || (!rowGenericType && transText ? transText : '');

        fitments.push({
            id: generateId(),
            make: makeText ? [makeText] : [],
            modelo: modelText.split(/[\/,]/).map(s => s.trim()).filter(s => s.length > 1),
            year_start: yearMatch ? toFullYear(yearMatch[1]) : null,
            year_end: yearMatch ? toFullYear(yearMatch[2] || yearMatch[1]) : null,
            transmission_type: rowGenericType,
            transmission_model: rowTransModel,
            engine: engineText
        });
    });
}

// ============ Plain Text Parser ============

function parsePlainTextForVehicles(text: string, fitments: VehicleFitment[]): void {
    let currentBrand = '';
    const lines = text.split(/[\r\n]+/);

    console.log('[FitmentParser] Processing', lines.length, 'lines');

    for (const rawLine of lines) {
        const line = rawLine.trim();
        if (!line || line.length < 4) continue;

        // Check for brand markers from preprocessing
        if (line.includes('BRAND_MARKER:')) {
            currentBrand = line.split('BRAND_MARKER:')[1].trim().toUpperCase();
            continue;
        }

        // Check if line is just a brand name
        const upperLine = line.toUpperCase().replace(/[^A-Z\-]/g, '');
        if (KNOWN_BRANDS.includes(upperLine)) {
            currentBrand = upperLine;
            continue;
        }

        // Try to extract year range
        const yearRangeMatch = line.match(/(\d{4})\s*[-–—]\s*(\d{4})/);
        const singleYearMatch = !yearRangeMatch ? line.match(/\b(19\d{2}|20[0-2]\d)\b/) : null;

        if (yearRangeMatch || singleYearMatch) {
            const yearStart = yearRangeMatch ? parseInt(yearRangeMatch[1]) : parseInt(singleYearMatch![1]);
            const yearEnd = yearRangeMatch ? parseInt(yearRangeMatch[2]) : yearStart;

            // Extract brand from line if present
            let detectedBrand = '';
            for (const brand of KNOWN_BRANDS) {
                if (line.toUpperCase().includes(brand)) {
                    detectedBrand = brand;
                    currentBrand = brand;
                    break;
                }
            }

            const finalBrand = detectedBrand || currentBrand;

            // Extract model - text between brand and year
            let model = '';
            if (detectedBrand) {
                const brandIdx = line.toUpperCase().indexOf(detectedBrand);
                const yearIdx = yearRangeMatch ? line.indexOf(yearRangeMatch[0]) : line.indexOf(singleYearMatch![0]);
                model = line.substring(brandIdx + detectedBrand.length, yearIdx).trim();
            } else if (yearRangeMatch) {
                model = line.substring(0, line.indexOf(yearRangeMatch[0])).trim();
            } else if (singleYearMatch) {
                model = line.substring(0, line.indexOf(singleYearMatch[0])).trim();
            }

            // Clean up model
            model = model.replace(/^[\s,\-:]+|[\s,\-:]+$/g, '');

            // Extract engine info
            let engine = '';
            const afterYears = yearRangeMatch
                ? line.substring(line.indexOf(yearRangeMatch[0]) + yearRangeMatch[0].length)
                : (singleYearMatch ? line.substring(line.indexOf(singleYearMatch[0]) + 4) : '');

            const engineMatch = afterYears.match(/([LVI]\d|\d+\.\d+\s*L?|\d+\s*SP|FWD|RWD|AWD|4WD)/gi);
            if (engineMatch) {
                engine = engineMatch.join(' ');
            }

            if (model) {
                fitments.push({
                    id: generateId(),
                    make: finalBrand ? [finalBrand] : [],
                    modelo: model.split(/[\/,]/).map(s => s.trim()).filter(s => s.length > 0),
                    year_start: yearStart,
                    year_end: yearEnd,
                    transmission_type: '',
                    transmission_model: '',
                    engine: engine
                });
            }
        }
    }
}

// ============ Main Parser Function ============

/**
 * Parse vehicle fitments from HTML product description
 */
export function parseVehicleFitments(html: string, options: ParseOptions = {}): ParseResult {
    const { title = '', vendor = '' } = options;
    const fitments: VehicleFitment[] = [];
    const warnings: string[] = [];

    console.log('[FitmentParser] Starting parse. HTML length:', html?.length, 'Title:', title);

    if (!html && !title) {
        return { fitments: [], transmissionModel: '', warnings: ['No description to analyze'] };
    }

    // Extract transmission signals from title/html. Specific codes (JF011E, RE0F10A) and
    // generic types (CVT) live in different fields and are filled separately during post-processing
    // so a row with "JF011E" in its cell still gets "CVT" as its type from the title.
    const specificFromText = extractSpecificTransCode(title) || extractSpecificTransCode(html || '');
    const genericFromText = extractGenericTransType(title) || extractGenericTransType(html || '');
    const transmissionModel = specificFromText || genericFromText;
    if (transmissionModel) {
        console.log('[FitmentParser] Found transmission:', transmissionModel, '(specific:', specificFromText, '| generic:', genericFromText, ')');
    }

    // Parse HTML
    const parser = new DOMParser();
    const doc = parser.parseFromString(html || '', 'text/html');

    // Strategy 1: Look for H4 vehicle section
    const vehicleSection = findVehicleSection(doc);

    if (vehicleSection) {
        // Collect content after H4 until next header
        let allContent: string[] = [];
        let node: Node | null = vehicleSection.nextSibling;

        while (node) {
            if (node.nodeType === Node.ELEMENT_NODE) {
                const el = node as Element;
                if (['H4', 'H3', 'H2', 'H1'].includes(el.tagName)) {
                    break;
                }

                if (el.tagName === 'TABLE') {
                    parseTableForVehicles(el, fitments);
                } else if (el.tagName === 'DIV') {
                    // Look for tables inside DIV wrappers
                    el.querySelectorAll('table').forEach(t => parseTableForVehicles(t, fitments));
                    el.querySelectorAll('li').forEach(li => {
                        const liText = li.textContent?.trim() || '';
                        if (liText) allContent.push(liText);
                    });
                } else if (el.tagName === 'UL' || el.tagName === 'OL') {
                    el.querySelectorAll('li').forEach(li => {
                        const liText = li.textContent?.trim() || '';
                        if (liText) allContent.push(liText);
                    });
                } else if (el.tagName === 'P') {
                    let pContent = el.innerHTML || '';
                    pContent = pContent.replace(/<strong[^>]*>(.*?)<\/strong>/gi, '\nBRAND_MARKER:$1\n');
                    pContent = pContent.replace(/<br\s*\/?>/gi, '\n');
                    pContent = pContent.replace(/<[^>]*>/g, '');
                    allContent.push(pContent);
                } else if (el.tagName === 'STRONG') {
                    allContent.push('\nBRAND_MARKER:' + (el.textContent?.trim() || '') + '\n');
                }
            } else if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent?.trim();
                if (text) allContent.push(text);
            }
            node = node.nextSibling;
        }

        // Parse collected text
        const fullText = allContent.join('\n');
        if (fullText.length > 10) {
            parsePlainTextForVehicles(fullText, fitments);
        }
    } else {
        // Strategy 2: Smart table detection
        console.log('[FitmentParser] No vehicle section found, trying smart table detection...');
        const allTables = collectAllTables(doc);
        console.log('[FitmentParser] Found', allTables.length, 'tables total');

        // First try tables with vehicle headers
        for (const table of allTables) {
            if (isVehicleTable(table)) {
                console.log('[FitmentParser] Found vehicle table by headers');
                parseTableForVehicles(table, fitments);
            }
        }

        // If no fitments, try all tables
        if (fitments.length === 0 && allTables.length > 0) {
            console.log('[FitmentParser] No vehicle headers found, parsing all tables...');
            allTables.forEach(t => parseTableForVehicles(t, fitments));
        }

        // Strategy 3: Plain text fallback
        if (fitments.length === 0) {
            console.log('[FitmentParser] No fitments from tables, trying plain text fallback...');
            const globalText = html
                .replace(/<br\s*\/?>/gi, '\n')
                .replace(/<\/p>/gi, '\n')
                .replace(/<strong[^>]*>(.*?)<\/strong>/gi, '\nBRAND_MARKER:$1\n')
                .replace(/<[^>]*>/g, ' ');
            parsePlainTextForVehicles(globalText, fitments);
        }
    }

    // Post-processing: fill in missing data. Per-row cell values always win over title-extracted fallbacks.
    fitments.forEach(f => {
        if (vendor && f.make.length === 0) f.make = [vendor];
        if (specificFromText && !f.transmission_model) f.transmission_model = specificFromText;
        if (genericFromText && !f.transmission_type) f.transmission_type = genericFromText;
    });

    // Deduplicate
    const seen = new Set<string>();
    const uniqueFitments = fitments.filter(f => {
        const key = `${f.make.join('|')}-${f.modelo.join('|')}-${f.year_start}-${f.year_end}`.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });

    console.log('[FitmentParser] Final fitments count:', uniqueFitments.length);

    return {
        fitments: uniqueFitments,
        transmissionModel,
        warnings
    };
}

// Export for testing
export { KNOWN_BRANDS, H4_KEYWORDS, TABLE_HEADER_KEYWORDS };
