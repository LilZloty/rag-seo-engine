"""
Knowledge Graph Manager for GEO (Generative Engine Optimization)

Manages the relationship between:
- Fault Codes (P0700, P0841, etc.)
- Symptoms
- Solutions
- Products
"""

import re
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.logging import get_logger
from app.models.aeo_models import (
    FaultCode, Solution, TransmissionPattern, ChunkApprovalStatus
)

logger = get_logger(__name__)

# Default priority fault codes from GA data
PRIORITY_FAULT_CODES = [
    {
        'code': 'P0700',
        'name': 'Falla General de Transmisión',
        'description': 'Código genérico que indica una falla en el sistema de transmisión detectada por el TCM.',
        'monthly_clicks': 1113,
        'monthly_impressions': 40005,
        'transmissions': ['4L60E', '6L80', 'A604', 'RE5R05A'],
        'vehicles': ['Chevrolet Silverado', 'Dodge Ram', 'Jeep Grand Cherokee'],
        'common_causes': ['Falla de solenoide', 'Problema de cableado', 'TCM defectuoso'],
        'symptoms_text': ['Luz Check Engine', 'Transmisión en modo seguro', 'Cambios erráticos'],
    },
    {
        'code': 'P0706',
        'name': 'Sensor de Rango de Transmisión (TR)',
        'description': 'Problema en el circuito del sensor de rango, común en vehículos GM y Nissan.',
        'monthly_clicks': 761,
        'monthly_impressions': 9299,
        'transmissions': ['4L60E', '4T65E', 'JF011E'],
        'vehicles': ['Chevrolet Optra', 'Chevrolet Aveo', 'Nissan Sentra'],
        'common_causes': ['Sensor TR defectuoso', 'Ajuste de chicote incorrecto', 'Humedad en el conector'],
        'symptoms_text': ['No arranca en P o N', 'No entra la reversa', 'Indicador de tablero erróneo'],
    },
    {
        'code': 'P0715',
        'name': 'Sensor de Velocidad de Entrada (ISS)',
        'description': 'Falla en el circuito del sensor de velocidad de entrada o turbina.',
        'monthly_clicks': 696,
        'monthly_impressions': 11545,
        'transmissions': ['RE5R05A', '4L60E', 'A604'],
        'vehicles': ['Nissan Altima', 'Chevrolet Malibu', 'Chrysler Town & Country'],
        'common_causes': ['Sensor ISS dañado', 'Reluctor de turbina sucio', 'Cableado abierto'],
        'symptoms_text': ['Cambios bruscos', 'Velocímetro deja de funcionar', 'Pérdida de potencia'],
    },
]

# Default transmission patterns
# Expanded May 20 2026 from 17 -> ~95 entries after the title cross-reference
# audit flagged the VAG 01M / VW0xx / Mopar A* / Asian RE* / ZF 6HP variant
# families as unrecognized. Honda 4-letter codes are kept in a separate
# whitelist (HONDA_AUTOMATIC_CODES) because they can't be regex-matched safely.
DEFAULT_PATTERNS = [
    # === DSG / Dual-clutch ===
    ('DQ200', 'VAG', 'DSG 7-speed dry clutch', 10),
    ('DQ250', 'VAG', 'DSG 6-speed wet clutch', 11),

    # === VAG 01-series (transverse/longitudinal 4- and 5-speed) ===
    ('01M', 'VAG', 'VW/Audi 4-speed transverse (Jetta/Golf MK4)', 12),
    ('01N', 'VAG', 'VW/Audi 4-speed (replaces 01M)', 13),
    ('01P', 'VAG', 'VW/Audi 4-speed longitudinal (Audi A4)', 14),
    ('01V', 'VAG', 'VW/Audi 5-speed longitudinal (Audi A4/A6)', 15),
    ('AG4', 'VAG', 'Audi marketing alias for 01M family', 16),

    # === VAG 09-series (5- and 6-speed) ===
    ('09A', 'VAG', 'VW 5-speed (alias of JF506E)', 17),
    ('09B', 'VAG', 'VW 5-speed automatic', 18),
    ('09D', 'VAG', 'Aisin TR60SN 6-speed (Touareg/Q7)', 19),
    ('09G', 'VAG', 'VW/Audi 6-speed transverse (TF60SN)', 20),
    ('09K', 'VAG', 'VW Crafter 6-speed', 21),
    ('09M', 'VAG', 'VW/Audi 6-speed automatic', 22),

    # === VAG legacy 0xx (older 3-/4-speed) ===
    ('VW010', 'VAG', 'VW 3-speed automatic (early Jetta/Golf)', 25),
    ('VW087', 'VAG', 'VW 4-speed automatic', 26),
    ('VW089', 'VAG', 'VW 4-speed automatic', 27),
    ('VW090', 'VAG', 'VW 4-speed (Beetle/Cabriolet)', 28),
    ('VW095', 'VAG', 'VW 4-speed (Passat 1990s)', 29),
    ('VW096', 'VAG', 'VW 4-speed (Passat/Audi A4)', 30),
    ('VW097', 'VAG', 'VW 4-speed (Touareg early)', 31),
    ('VW098', 'VAG', 'VW 4-speed (Touareg/Cayenne)', 32),

    # === GM 3-/4-speed RWD/FWD ===
    ('4L60E', 'GM', '4-speed RWD electronic (Silverado/Tahoe)', 40),
    ('4L65E', 'GM', '4-speed RWD heavy-duty', 41),
    ('4L70E', 'GM', '4-speed RWD updated', 42),
    ('4L80E', 'GM', '4-speed RWD truck heavy-duty', 43),
    ('4L85E', 'GM', '4-speed RWD uprated 4L80', 44),
    ('4T65E', 'GM', '4-speed FWD electronic', 45),
    ('TH350', 'GM', '3-speed RWD turbo hydramatic', 46),
    ('TH400', 'GM', '3-speed RWD heavy-duty turbo hydramatic', 47),
    ('TH700', 'GM', '4-speed RWD turbo hydramatic (precursor of 4L60)', 48),
    ('700R4', 'GM', '4-speed RWD (alias of TH700R4)', 49),

    # === GM 6-/8-speed ===
    ('6L45', 'GM', '6-speed RWD light-duty', 50),
    ('6L50', 'GM', '6-speed RWD mid-duty', 51),
    ('6L80', 'GM', '6-speed RWD (alias of 6L80E)', 52),
    ('6L80E', 'GM', '6-speed RWD electronic', 53),
    ('6L90', 'GM', '6-speed RWD heavy-duty', 54),
    ('6L90E', 'GM', '6-speed RWD heavy-duty electronic', 55),
    ('6T30', 'GM', '6-speed FWD light-duty', 56),
    ('6T40', 'GM', '6-speed FWD (Cruze/Sonic)', 57),
    ('6T45', 'GM', '6-speed FWD (Malibu/LaCrosse)', 58),
    ('6T70', 'GM', '6-speed FWD (Equinox/Traverse)', 59),
    ('6T75', 'GM', '6-speed FWD heavy-duty', 60),
    ('8L45', 'GM', '8-speed RWD (Camaro/CTS)', 61),
    ('8L90', 'GM', '8-speed RWD (Corvette/Silverado)', 62),

    # === Ford 4-speed ===
    ('AODE', 'Ford', '4-speed RWD electronic overdrive', 70),
    ('4R70W', 'Ford', '4-speed RWD overdrive (Mustang/F150)', 71),
    ('4R70E', 'Ford', '4-speed RWD overdrive electronic', 72),
    ('4R75W', 'Ford', '4-speed RWD updated 4R70W', 73),
    ('4R75E', 'Ford', '4-speed RWD updated electronic', 74),
    ('AX4N', 'Ford', '4-speed FWD (Taurus/Sable)', 75),
    ('AX4S', 'Ford', '4-speed FWD (alias of AXOD-E)', 76),
    ('4F27E', 'Ford', '4-speed FWD (Focus/Escape)', 77),

    # === Ford 5-/6-/10-speed ===
    ('5R55E', 'Ford', '5-speed RWD electronic (Ranger/Explorer)', 80),
    ('5R55W', 'Ford', '5-speed RWD updated', 81),
    ('5R55S', 'Ford', '5-speed RWD S-variant', 82),
    ('6R80', 'Ford', '6-speed RWD (F150/Mustang)', 83),
    ('6F35', 'Ford', '6-speed FWD light-duty', 84),
    ('6F50', 'Ford', '6-speed FWD mid-duty (Edge/MKX)', 85),
    ('10R80', 'Ford', '10-speed RWD (F150 newer)', 86),

    # === Mopar/Chrysler ===
    ('A604', 'Mopar', '4-speed FWD (41TE/Caravan/Dakota)', 90),
    ('A606', 'Mopar', '4-speed FWD heavy-duty (42LE)', 91),
    ('A500', 'Mopar', '4-speed RWD (Dakota/Durango)', 92),
    ('A518', 'Mopar', '4-speed RWD truck (46RH)', 93),
    ('A618', 'Mopar', '4-speed RWD diesel (47RH)', 94),
    ('41AE', 'Mopar', '4-speed FWD AWD variant', 95),
    ('41TE', 'Mopar', '4-speed FWD (modernized A604)', 96),
    ('41TES', 'Mopar', '4-speed FWD updated', 97),
    ('42LE', 'Mopar', '4-speed FWD longitudinal', 98),
    ('42RLE', 'Mopar', '4-speed RWD electronic (Jeep Wrangler/Liberty)', 99),
    ('46RE', 'Mopar', '4-speed RWD electronic (Ram/Durango)', 100),
    ('47RE', 'Mopar', '4-speed RWD diesel electronic', 101),
    ('48RE', 'Mopar', '4-speed RWD heavy-duty diesel', 102),
    ('62TE', 'Mopar', '6-speed FWD (Caravan/Journey)', 103),
    ('65RFE', 'Mopar', '6-speed RWD (Dakota/Durango newer)', 104),
    ('66RFE', 'Mopar', '6-speed RWD diesel', 105),
    ('68RFE', 'Mopar', '6-speed RWD heavy-duty diesel (Ram 2500)', 106),

    # === Asian (Nissan/JATCO/Mazda) ===
    ('JF011E', 'Asian', 'Nissan/JATCO CVT (Altima/Sentra)', 110),
    ('JF015E', 'Asian', 'Nissan/JATCO CVT compact', 111),
    ('JF016E', 'Asian', 'Nissan/JATCO CVT updated', 112),
    ('JF017E', 'Asian', 'Nissan/JATCO CVT mid-size', 113),
    ('JF506E', 'Asian', 'JATCO 5-speed (Jaguar/Land Rover/VW 09A)', 114),
    ('RE0F10A', 'Asian', 'Nissan CVT (alias of JF011E)', 115),
    ('RE4R01A', 'Asian', 'Nissan 4-speed RWD (Frontier/Pathfinder)', 116),
    ('RE5R01A', 'Asian', 'Nissan 5-speed RWD', 117),
    ('RE5R05A', 'Asian', 'Nissan 5-speed RWD (Frontier/Xterra)', 118),
    ('RL4R01A', 'Asian', 'Nissan 4-speed RWD light-duty', 119),
    ('R4AXEL', 'Asian', 'Mazda 4-speed automatic', 120),

    # === Toyota/Aisin ===
    ('A340', 'Toyota', '4-speed RWD (Tacoma/4Runner/Cressida)', 130),
    ('A341', 'Toyota', '4-speed RWD heavy-duty (Tacoma)', 131),
    ('A343', 'Toyota', '4-speed RWD turbo (Supra)', 132),
    ('A750E', 'Toyota', '5-speed RWD (Tacoma/4Runner)', 133),
    ('A750F', 'Toyota', '5-speed RWD 4WD variant', 134),
    ('A760E', 'Toyota', '6-speed RWD (Camry V6)', 135),
    ('AW4', 'Toyota', 'Aisin 4-speed RWD (Jeep Cherokee XJ)', 136),
    ('U660E', 'Toyota', '6-speed FWD (Camry/Highlander)', 137),

    # === ZF (luxury European) ===
    ('6HP', 'ZF', 'ZF 6-speed family (alias)', 140),
    ('ZF6HP19', 'ZF', 'ZF 6-speed light (BMW 3-series)', 141),
    ('ZF6HP26', 'ZF', 'ZF 6-speed mid (BMW 5-series)', 142),
    ('ZF6HP28', 'ZF', 'ZF 6-speed heavy (BMW X5)', 143),
    ('8HP', 'ZF', 'ZF 8-speed family (alias)', 144),
    ('ZF8HP45', 'ZF', 'ZF 8-speed light-duty', 145),
    ('ZF8HP55', 'ZF', 'ZF 8-speed mid-duty', 146),
]


# Component vocabulary (Phase 3.1f). Maps a normalized component type to the
# Spanish/English keywords that signal it. Used by get_fault_codes_for_product
# to filter out fault codes whose `common_causes` don't reference any component
# the product actually IS — a Filtro shouldn't claim to fix a Sensor ISS code.
#
# Add new components when audits surface false positives or misses. Keep
# keywords case-insensitive substrings; matched against title + product_type.
COMPONENT_PATTERNS: Dict[str, List[str]] = {
    "filtro":      ["filtro", "filter"],
    "solenoide":   ["solenoide", "solenoid", "epc"],
    "sensor":      ["sensor", " iss", " oss", " trs"],
    "bomba":       ["bomba", "pump"],
    "convertidor": ["convertidor", "tcc", "torque converter"],
    "embrague":    ["embrague", "clutch", "disco", "fricción", "friccion", "pack", "metales", "hierro"],
    "banda":       ["banda"],
    "válvula":     ["válvula", "valvula", "valve body", "spool", "cuerpo de válvulas"],
    "empaque":     ["empaque", "junta", "sello", "retén", "reten", "gasket", "oring"],
    "tcm":         ["tcm", "ecm", "mecatrónico", "mecatronico", "módulo electrónico", "modulo electronico"],
    "servo":       ["servo", "pistón", "piston"],
}

# Title fragments that signal a full rebuild kit — bypass component filtering
# (a rebuild kit legitimately addresses every fault code on its transmission).
REBUILD_KIT_MARKERS = [
    "kit caja",
    "kit de reparación",
    "kit de reparacion",
    "kits de reparacion",
    "kit overhaul",
    "overhaul kit",
    "rebuild kit",
    "kit completo",
]


def _extract_components_from_text(text: str) -> set:
    """Return the component types referenced in a piece of Spanish/English text."""
    if not text:
        return set()
    lower = text.lower()
    found = set()
    for component, keywords in COMPONENT_PATTERNS.items():
        if any(kw in lower for kw in keywords):
            found.add(component)
    return found


# Honda 4-letter automatic transmission codes — exact-token whitelist.
# Honda uses arbitrary 4-letter codes (BCLA, MAYA, etc.) rather than systematic
# naming, so they can't be regex'd reliably. Matched as standalone uppercase
# tokens with word boundaries during extraction.
#
# Expand this list as new Honda codes appear in the catalog — the audit script
# (`audit_title_cross_reference.py`) surfaces titles in UNCLASSIFIED that
# mention Honda/Acura; spot-check those for new 4-letter codes.
HONDA_AUTOMATIC_CODES = [
    'B7VA', 'B7XA', 'B7YA',   # Accord/TL V6 family
    'BCLA', 'BCYA',           # Accord/Civic family
    'BZHA', 'BZJA',           # Civic Hybrid family
    'GPLA', 'GPPA',           # Ridgeline/Pilot family
    'M4VA', 'M4TA',           # Acura RDX family
    'MAYA', 'MAXA',           # Civic family
    'MCLA', 'MCYA',           # Accord
    'MGFA', 'MGHA',           # Pilot family
    'MJBA', 'MJFA',           # Acura family
    'MKYA', 'MKHA',           # Civic family
    'MLYA', 'MMYA',           # Odyssey family
]


class KnowledgeGraphManager:
    """Manages the technical knowledge graph for GEO optimization"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # ============ Fault Code Management ============
    
    def seed_fault_codes(self) -> int:
        """Seed the database with priority fault codes from GA data."""
        count = self.db.query(FaultCode).count()
        if count > 0:
            logger.info(f"Fault codes already seeded ({count} existing)")
            return 0
        
        seeded = 0
        for fc_data in PRIORITY_FAULT_CODES:
            fc = FaultCode(
                code=fc_data['code'],
                name=fc_data['name'],
                description=fc_data.get('description'),
                monthly_clicks=fc_data.get('monthly_clicks', 0),
                monthly_impressions=fc_data.get('monthly_impressions', 0),
                transmissions=fc_data.get('transmissions', []),
                vehicles=fc_data.get('vehicles', []),
                common_causes=fc_data.get('common_causes', []),
                symptoms_text=fc_data.get('symptoms_text', []),
                blog_url=f"/blogs/news/{fc_data['code'].lower()}",
                is_priority=fc_data.get('monthly_clicks', 0) > 500
            )
            self.db.add(fc)
            seeded += 1
        
        self.db.commit()
        logger.info(f"Seeded {seeded} priority fault codes")
        return seeded
    
    def get_fault_codes(self, priority_only: bool = False) -> List[FaultCode]:
        """Get all fault codes from the knowledge graph."""
        query = self.db.query(FaultCode)
        if priority_only:
            query = query.filter(FaultCode.is_priority == True)
        return query.order_by(FaultCode.monthly_clicks.desc()).all()
    
    def get_fault_code(self, code: str) -> Optional[FaultCode]:
        """Get a specific fault code by code."""
        return self.db.query(FaultCode).filter(FaultCode.code == code).first()
    
    def search_fault_codes(self, query: str) -> List[FaultCode]:
        """Search fault codes by code or name."""
        search = f"%{query}%"
        return self.db.query(FaultCode).filter(
            (FaultCode.code.ilike(search)) |
            (FaultCode.name.ilike(search))
        ).all()
    
    def get_fault_codes_for_transmission(self, transmission_code: str) -> List[FaultCode]:
        """Get all fault codes applicable to a specific transmission.

        FaultCode.transmissions is a JSON column; SQLAlchemy's `.contains()`
        compiles to `LIKE` which Postgres rejects for JSON. Filter in Python
        — the table holds tens of rows at most, so the cost is trivial.
        """
        return [
            fc for fc in self.db.query(FaultCode).all()
            if transmission_code in (fc.transmissions or [])
        ]

    def get_fault_codes_for_product(self, product) -> List[FaultCode]:
        """Return FaultCodes this product can actually remedy.

        Two-stage filter:
          1. transmission_codes ∩ FaultCode.transmissions (Phase 3.1 — bridge
             between Phase 1.2 codes and the KG fault code catalog)
          2. component-type filter (Phase 3.1f) — drop codes whose
             `common_causes` reference components this product is NOT.
             Example: a Filtro product no longer claims to fix Sensor ISS
             codes; only filter-related causes like "Filtro tapado" survive.

        Full rebuild kits (title contains "kit caja", "rebuild kit", etc.)
        bypass the component filter — they legitimately address everything.
        Products with no detectable component AND no rebuild-kit marker
        return empty (we'd rather emit nothing than wrong fault codes).

        De-duped on FaultCode.code, ordered by monthly_clicks desc.
        """
        codes = getattr(product, "transmission_codes", None) or []
        if not codes:
            return []

        title = (getattr(product, "title", "") or "")
        product_type = (getattr(product, "product_type", "") or "")
        signal_text = f"{title} {product_type}".lower()

        is_rebuild_kit = any(marker in signal_text for marker in REBUILD_KIT_MARKERS)
        product_components = _extract_components_from_text(signal_text)

        # No component detected AND not a rebuild kit → no safe attribution.
        if not is_rebuild_kit and not product_components:
            return []

        seen: set = set()
        results: List[FaultCode] = []
        for code in codes:
            for fc in self.get_fault_codes_for_transmission(code):
                if fc.code in seen:
                    continue
                if not is_rebuild_kit:
                    fc_components: set = set()
                    for cause in (fc.common_causes or []):
                        fc_components |= _extract_components_from_text(cause)
                    if not (product_components & fc_components):
                        continue
                seen.add(fc.code)
                results.append(fc)
        results.sort(key=lambda fc: -(fc.monthly_clicks or 0))
        return results
    
    # ============ Transmission Patterns ============
    
    def seed_transmission_patterns(self) -> int:
        """Seed default transmission patterns if table is empty."""
        count = self.db.query(TransmissionPattern).count()
        if count == 0:
            logger.info("Seeding default transmission patterns...")
            for code, category, description, priority in DEFAULT_PATTERNS:
                pattern = TransmissionPattern(
                    code=code,
                    category=category,
                    description=description,
                    priority=priority,
                    is_active=True
                )
                self.db.add(pattern)
            self.db.commit()
            logger.info(f"Seeded {len(DEFAULT_PATTERNS)} transmission patterns")
            return len(DEFAULT_PATTERNS)
        return 0

    def ensure_default_patterns_seeded(self) -> int:
        """Idempotently insert any DEFAULT_PATTERNS rows missing from the table.

        Unlike seed_transmission_patterns (which skips entirely if any rows
        exist), this fills gaps after a seed expansion without disturbing
        existing rows. Returns the count of new rows inserted.
        """
        existing = {row[0] for row in self.db.query(TransmissionPattern.code).all()}
        added = 0
        for code, category, description, priority in DEFAULT_PATTERNS:
            if code in existing:
                continue
            self.db.add(TransmissionPattern(
                code=code,
                category=category,
                description=description,
                priority=priority,
                is_active=True,
            ))
            added += 1
        if added:
            self.db.commit()
            logger.info(f"Seeded {added} new transmission patterns (idempotent fill)")
        return added

    def get_transmission_patterns(self, active_only: bool = True) -> Dict[str, Tuple[str, str]]:
        """Get pattern mapping: code -> (category, description)."""
        query = self.db.query(TransmissionPattern)
        if active_only:
            query = query.filter(TransmissionPattern.is_active == True)
        
        patterns = query.order_by(TransmissionPattern.priority).all()
        
        return {
            p.code: (p.category, p.description or '')
            for p in patterns
        }
    
    def extract_all_transmission_codes(
        self,
        title: str,
        patterns: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> List[str]:
        """Return every transmission code in title, deduped, in title order.

        Word-boundary regex matching — '01M' no longer false-matches inside
        '201M-Pump'. Codes from DEFAULT_PATTERNS are matched alongside the
        Honda 4-letter whitelist (HONDA_AUTOMATIC_CODES).
        """
        if not title:
            return []
        if patterns is None:
            patterns = self.get_transmission_patterns()

        # Longest codes first so ZF6HP26 wins over the looser '6HP' alias.
        all_codes = list(patterns.keys()) + list(HONDA_AUTOMATIC_CODES)
        all_codes.sort(key=lambda c: (-len(c), c))

        regex = re.compile(
            r"\b(?:" + "|".join(re.escape(c) for c in all_codes) + r")\b",
            re.IGNORECASE,
        )

        found: List[str] = []
        seen: set = set()
        for match in regex.finditer(title):
            code = match.group(0).upper()
            if code not in seen:
                seen.add(code)
                found.append(code)
        return found

    def compute_transmission_code(
        self,
        title: str,
        patterns: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> Optional[str]:
        """Return the FIRST transmission code in the title, or None.

        Single-code interface kept for callers that only need a primary
        category. New paths should use extract_all_transmission_codes.
        """
        codes = self.extract_all_transmission_codes(title, patterns)
        return codes[0] if codes else None

    def extract_codes_from_product(
        self,
        product,
        patterns: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> List[str]:
        """Extract transmission codes from title AND current_description_html.

        Phase 1.4 — descriptions are higher-fidelity than titles: many carry
        a structured "Transmisiones:" block listing curator-declared codes
        the title may omit (e.g. K119AF title has spaced "VW 095 096 097
        098" that title-regex misses, but description has them explicitly).
        Concatenates title + description-text and runs the same word-boundary
        extraction, preserving first-occurrence order so title-derived codes
        rank ahead of description-only ones in the resulting list.
        """
        title = getattr(product, "title", "") or ""
        desc_html = getattr(product, "current_description_html", "") or ""
        desc_text = ""
        if desc_html:
            desc_text = re.sub(r"<[^>]+>", " ", desc_html)
            desc_text = re.sub(r"\s+", " ", desc_text).strip()
        combined = f"{title} {desc_text}".strip()
        return self.extract_all_transmission_codes(combined, patterns)

    def refresh_codes_for_product(
        self,
        product,
        patterns: Optional[Dict[str, Tuple[str, str]]] = None,
    ) -> bool:
        """Re-extract codes from title+description, update Product columns if changed.

        Phase 1.5 — used by sync paths (sync_tasks, /sync endpoints) and
        content_generator to keep the columns fresh without a manual backfill.
        Mutates the Product instance but does NOT commit; caller owns the
        session and commits at the appropriate boundary. Returns True if
        either column was modified, False otherwise.
        """
        codes = self.extract_codes_from_product(product, patterns)
        if not codes:
            return False
        changed = False
        if codes[0] != product.transmission_code:
            product.transmission_code = codes[0]
            changed = True
        if list(codes) != (product.transmission_codes or []):
            product.transmission_codes = codes
            changed = True
        return changed
    
    # ============ Chunk Management ============
    
    def get_product_chunks(self, include_samples: bool = False) -> List[Dict]:
        """Get all product type chunks with counts and approval status."""
        from app.models.product import Product
        from sqlalchemy import func
        
        # SQL-level aggregation
        chunks_query = self.db.query(
            Product.transmission_code,
            func.count(Product.id).label('product_count')
        ).filter(
            Product.transmission_code.isnot(None)
        ).group_by(Product.transmission_code).all()
        
        # Count products without transmission code
        other_count = self.db.query(func.count(Product.id)).filter(
            Product.transmission_code.is_(None)
        ).scalar() or 0
        
        patterns = self.get_transmission_patterns()
        
        # Get approval status
        approval_map = {
            status.product_type: status
            for status in self.db.query(ChunkApprovalStatus).all()
        }
        
        result = []
        for transmission_code, count in chunks_query:
            if not transmission_code:
                continue
            status = approval_map.get(transmission_code)
            pattern_info = patterns.get(transmission_code, ('Other', ''))
            
            chunk_data = {
                "product_type": transmission_code,
                "product_count": count,
                "category": pattern_info[0],
                "description": pattern_info[1] or f'{count} products',
                "approved": status.approved if status else False,
                "approved_at": status.approved_at if status else None,
                "approved_by": status.approved_by if status else None,
                "notes": status.notes if status else None,
                "sample_products": []
            }
            
            if include_samples:
                samples = self.db.query(Product.id, Product.title, Product.sku).filter(
                    Product.transmission_code == transmission_code
                ).limit(5).all()
                chunk_data["sample_products"] = [
                    {"id": s.id, "title": s.title, "sku": s.sku}
                    for s in samples
                ]
            
            result.append(chunk_data)
        
        # Add "Other" chunk
        if other_count > 0:
            status = approval_map.get("Other")
            result.append({
                "product_type": "Other",
                "product_count": other_count,
                "category": "Other",
                "description": "Uncategorized products",
                "approved": status.approved if status else False,
                "approved_at": status.approved_at if status else None,
                "approved_by": status.approved_by if status else None,
                "notes": status.notes if status else None,
                "sample_products": []
            })
        
        # Sort by count descending
        result.sort(key=lambda x: -x['product_count'])
        
        return result
    
    def approve_chunk(
        self,
        product_type: str,
        approved: bool,
        approved_by: str = "admin",
        notes: str = None
    ) -> ChunkApprovalStatus:
        """Approve or reject a product type chunk."""
        status = self.db.query(ChunkApprovalStatus).filter(
            ChunkApprovalStatus.product_type == product_type
        ).first()
        
        if not status:
            status = ChunkApprovalStatus(product_type=product_type)
            self.db.add(status)
        
        status.approved = approved
        status.approved_at = datetime.utcnow() if approved else None
        status.approved_by = approved_by if approved else None
        status.notes = notes
        
        self.db.commit()
        self.db.refresh(status)
        
        logger.info(
            f"Chunk {'approved' if approved else 'rejected'}: {product_type}",
            extra={"product_type": product_type, "approved": approved, "approved_by": approved_by}
        )
        
        return status
    
    def auto_approve_top_chunks(self, limit: int = 15, min_products: int = 5) -> Dict:
        """Auto-approve top chunks by product count."""
        chunks = self.get_product_chunks()
        approved_count = 0
        approved_types = []
        
        for chunk in chunks[:limit]:
            if chunk['product_count'] >= min_products and not chunk['approved']:
                self.approve_chunk(
                    product_type=chunk['product_type'],
                    approved=True,
                    approved_by='system:auto_approve',
                    notes=f"Auto-approved: {chunk['product_count']} products"
                )
                approved_count += 1
                approved_types.append(chunk['product_type'])
        
        logger.info(
            f"Auto-approved {approved_count} chunks",
            extra={"approved_types": approved_types}
        )
        
        return {
            'approved_count': approved_count,
            'approved_types': approved_types,
            'skipped': limit - approved_count
        }
    
    # ============ Product Linking ============
    
    def get_products_for_fault_code(self, fault_code: str, limit: int = 10):
        """Get real products that can fix a specific fault code."""
        from app.models.product import Product
        
        fc = self.get_fault_code(fault_code)
        if not fc or not fc.transmissions:
            return []
        
        products = self.db.query(Product).filter(
            Product.transmission_code.in_(fc.transmissions),
            Product.sku.isnot(None)
        ).order_by(Product.total_sold.desc()).limit(limit).all()
        
        logger.info(
            f"Found {len(products)} products for fault code {fault_code}",
            extra={"fault_code": fault_code, "product_count": len(products)}
        )
        
        return products
    
    def update_product_transmission_codes(self, force_recompute: bool = False) -> int:
        """Batch update Product.transmission_code (single) AND Product.transmission_codes (array).

        Args:
            force_recompute: If True, re-evaluate every product (used after a
                KG seed expansion so previously-unrecognized titles get codes).
                If False (default), only products missing either column are
                touched.

        Returns the number of products whose stored code(s) changed.
        """
        from sqlalchemy import or_
        patterns = self.get_transmission_patterns()

        from app.models.product import Product
        query = self.db.query(Product)
        if not force_recompute:
            # Catch products missing the array column even if the legacy single
            # column is populated (relevant during Phase 1.2 cutover).
            query = query.filter(
                or_(
                    Product.transmission_code.is_(None),
                    Product.transmission_codes.is_(None),
                )
            )
        products = query.all()

        count = 0
        for product in products:
            # Phase 1.4: extract from title + description for higher recall.
            codes = self.extract_codes_from_product(product, patterns)
            if not codes:
                continue
            changed = False
            primary = codes[0]
            if primary != product.transmission_code:
                product.transmission_code = primary
                changed = True
            if list(codes) != (product.transmission_codes or []):
                product.transmission_codes = codes
                changed = True
            if changed:
                count += 1

        self.db.commit()
        logger.info(
            f"Updated transmission code(s) for {count} products "
            f"(force_recompute={force_recompute}, scanned={len(products)})"
        )
        return count


# Factory function
def create_knowledge_graph_manager(db: Session) -> KnowledgeGraphManager:
    """Create a new KnowledgeGraphManager instance."""
    return KnowledgeGraphManager(db=db)
