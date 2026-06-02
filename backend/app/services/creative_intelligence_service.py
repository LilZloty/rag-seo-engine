"""
Creative Intelligence Service
Cross-references Shopify sales, Google Search Console, and GA4 data
to identify top vehicle brands/transmissions for Facebook & Instagram ad creatives.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from collections import defaultdict
import re


# Transmission code -> Vehicle brand mapping
# Based on OEM transmission assignments
TRANSMISSION_BRAND_MAP = {
    # GM / Chevrolet
    '4L60E': 'GM / Chevrolet', '4L60': 'GM / Chevrolet', '4L65E': 'GM / Chevrolet',
    '4L70E': 'GM / Chevrolet', '4L80E': 'GM / Chevrolet', '4L30E': 'GM / Chevrolet',
    'TH700': 'GM / Chevrolet', 'TH700-R4': 'GM / Chevrolet',
    'TH350': 'GM / Chevrolet', 'TH350C': 'GM / Chevrolet',
    'TH400': 'GM / Chevrolet', 'TH250': 'GM / Chevrolet', 'TH250C': 'GM / Chevrolet',
    'TH200': 'GM / Chevrolet', 'TH200C': 'GM / Chevrolet', 'TH200-4R': 'GM / Chevrolet',
    'TH125C': 'GM / Chevrolet', 'TH180C': 'GM / Chevrolet',
    '6L50': 'GM / Chevrolet', '6L80': 'GM / Chevrolet', '6L90': 'GM / Chevrolet',
    '6T30': 'GM / Chevrolet', '6T40': 'GM / Chevrolet', '6T45': 'GM / Chevrolet',
    '6T70': 'GM / Chevrolet', '6T75': 'GM / Chevrolet',
    '8L90': 'GM / Chevrolet', '8L45': 'GM / Chevrolet',
    '4T40E': 'GM / Chevrolet', '4T45E': 'GM / Chevrolet',
    '4T60E': 'GM / Chevrolet', '4T65E': 'GM / Chevrolet', '4T80E': 'GM / Chevrolet',
    'M30': 'GM / Chevrolet', 'M33': 'GM / Chevrolet',
    '10L80': 'GM / Chevrolet', '10L90': 'GM / Chevrolet',

    # Ford
    'AODE': 'Ford', 'AOD': 'Ford',
    '4R70W': 'Ford', '4R70E': 'Ford', '4R75W': 'Ford', '4R75E': 'Ford',
    '5R55S': 'Ford', '5R55W': 'Ford', '5R55N': 'Ford', '5R55E': 'Ford',
    'A4LD': 'Ford', '4R44E': 'Ford', '4R55E': 'Ford',
    'C3': 'Ford', 'C4': 'Ford', 'C5': 'Ford', 'C6': 'Ford',
    'FMX': 'Ford', 'FIODE': 'Ford',
    '6R60': 'Ford', '6R80': 'Ford', '6R140': 'Ford',
    '10R80': 'Ford', '10R60': 'Ford',
    '6F35': 'Ford', '6F50': 'Ford', '6F55': 'Ford',
    'E4OD': 'Ford', '4R100': 'Ford',
    '5R110W': 'Ford', '5R110': 'Ford',

    # Chrysler / Dodge / Jeep
    'A604': 'Chrysler / Dodge / Jeep', '41TE': 'Chrysler / Dodge / Jeep', '41AE': 'Chrysler / Dodge / Jeep',
    '62TE': 'Chrysler / Dodge / Jeep',
    'A404': 'Chrysler / Dodge / Jeep', 'A413': 'Chrysler / Dodge / Jeep',
    'A904': 'Chrysler / Dodge / Jeep', 'A727': 'Chrysler / Dodge / Jeep',
    '42RLE': 'Chrysler / Dodge / Jeep', '42RE': 'Chrysler / Dodge / Jeep', '44RE': 'Chrysler / Dodge / Jeep',
    '46RE': 'Chrysler / Dodge / Jeep', '46RH': 'Chrysler / Dodge / Jeep',
    '47RE': 'Chrysler / Dodge / Jeep', '47RH': 'Chrysler / Dodge / Jeep',
    '48RE': 'Chrysler / Dodge / Jeep',
    '68RFE': 'Chrysler / Dodge / Jeep',
    '45RFE': 'Chrysler / Dodge / Jeep', '545RFE': 'Chrysler / Dodge / Jeep',
    'A500': 'Chrysler / Dodge / Jeep', 'A518': 'Chrysler / Dodge / Jeep',
    'A618': 'Chrysler / Dodge / Jeep',
    'T6': 'Chrysler / Dodge / Jeep', 'T8': 'Chrysler / Dodge / Jeep',

    # VW / Audi
    '09G': 'VW / Audi', 'TF-60SN': 'VW / Audi', 'TF60SN': 'VW / Audi',
    '01M': 'VW / Audi', '01N': 'VW / Audi', '01P': 'VW / Audi',
    'VW097': 'VW / Audi', 'VW098': 'VW / Audi', 'VW095': 'VW / Audi', 'AG4': 'VW / Audi',
    '0AM': 'VW / Audi', 'DQ200': 'VW / Audi', 'DQ250': 'VW / Audi', 'DQ500': 'VW / Audi',
    '09D': 'VW / Audi', '09K': 'VW / Audi', '09M': 'VW / Audi',
    '0B5': 'VW / Audi', 'DL501': 'VW / Audi',

    # Nissan
    'JF015E': 'Nissan', 'RE0F11A': 'Nissan',
    'JF011E': 'Nissan', 'RE0F10A': 'Nissan',
    'JF010E': 'Nissan', 'RE0F09A': 'Nissan',
    'JF017E': 'Nissan', 'RE0F10D': 'Nissan',
    'RE4F04A': 'Nissan', 'RE5R05A': 'Nissan',
    'RE4R01A': 'Nissan', 'RE4R03A': 'Nissan',

    # Toyota
    'U660E': 'Toyota', 'U760E': 'Toyota',
    'U140E': 'Toyota', 'U140F': 'Toyota',
    'U150E': 'Toyota', 'U150F': 'Toyota',
    'U250E': 'Toyota', 'U340E': 'Toyota', 'U341E': 'Toyota',
    'A750E': 'Toyota', 'A750F': 'Toyota',
    'A340E': 'Toyota', 'A340F': 'Toyota',
    'A540E': 'Toyota', 'A541E': 'Toyota',
    'A960E': 'Toyota', 'A960F': 'Toyota',
    'AA80E': 'Toyota',

    # Honda
    'BZGA': 'Honda', 'BVGA': 'Honda',
    'BAXA': 'Honda', 'MAXA': 'Honda', 'BGRA': 'Honda',
    'MCVA': 'Honda', 'MRVA': 'Honda',
    'B7XA': 'Honda', 'M7WA': 'Honda',
    'BYBA': 'Honda', 'B97A': 'Honda',

    # BMW / Mercedes / ZF
    'ZF6HP': 'BMW / Mercedes', 'ZF8HP': 'BMW / Mercedes',
    '6HP19': 'BMW / Mercedes', '6HP21': 'BMW / Mercedes', '6HP26': 'BMW / Mercedes',
    '6HP28': 'BMW / Mercedes', '6HP32': 'BMW / Mercedes',
    '8HP45': 'BMW / Mercedes', '8HP50': 'BMW / Mercedes', '8HP70': 'BMW / Mercedes',
    'GA6L45R': 'BMW / Mercedes',
    '722.6': 'BMW / Mercedes', '722.9': 'BMW / Mercedes',
    '5HP19': 'BMW / Mercedes', '5HP24': 'BMW / Mercedes', '5HP30': 'BMW / Mercedes',

    # Hyundai / Kia
    'A6MF1': 'Hyundai / Kia', 'A6MF2': 'Hyundai / Kia',
    'A6GF1': 'Hyundai / Kia', 'A6LF1': 'Hyundai / Kia',
    'A4CF1': 'Hyundai / Kia', 'A4CF2': 'Hyundai / Kia',
    'A5HF1': 'Hyundai / Kia', 'A5GF1': 'Hyundai / Kia',
    'F4A42': 'Hyundai / Kia', 'F4A51': 'Hyundai / Kia',
    'F5A51': 'Hyundai / Kia',

    # Mitsubishi
    'F4A41': 'Mitsubishi', 'F4A33': 'Mitsubishi',
    'F5A5A': 'Mitsubishi',

    # Subaru
    'TR580': 'Subaru', 'TR690': 'Subaru',
    '4EAT': 'Subaru', '5EAT': 'Subaru',

    # Mazda
    'FN4AEL': 'Mazda', 'FNR5': 'Mazda',
    'FS5AEL': 'Mazda', 'SkyActiv': 'Mazda',
}

# Title-based brand detection patterns (fallback when no transmission code)
TITLE_BRAND_PATTERNS = [
    (r'\bGM\b|\bChev(?:rolet|y)\b|\bTahoe\b|\bSilverado\b|\bSuburban\b|\bTraverse\b|\bEquinox\b|\bCamaro\b|\bCruze\b|\bMalibu\b|\bTrax\b|\bBlazer\b|\bColorado\b|\bExpress\b|\bGMC\b|\bSierra\b|\bYukon\b|\bAcadia\b|\bTerrain\b|\bCanyon\b|\bCadillac\b|\bBuick\b|\bPontiac\b|\bOldsmobile\b', 'GM / Chevrolet'),
    (r'\bFord\b|\bF-?150\b|\bF-?250\b|\bF-?350\b|\bExplorer\b|\bEscape\b|\bEdge\b|\bRanger\b|\bFusion\b|\bMustang\b|\bExpedition\b|\bBronco\b|\bMaverick\b|\bLincoln\b|\bMercury\b', 'Ford'),
    (r'\bChrysler\b|\bDodge\b|\bJeep\b|\bRam\b|\bDurango\b|\bCharger\b|\bChallenger\b|\bGrand Cherokee\b|\bWrangler\b|\bCaravan\b|\bPacifica\b|\bCherokee\b|\bCompass\b|\bRenegade\b|\bDart\b|\b300C?\b|\bMopar\b', 'Chrysler / Dodge / Jeep'),
    (r'\bVW\b|\bVolkswagen\b|\bAudi\b|\bJetta\b|\bGolf\b|\bPassat\b|\bTiguan\b|\bAtlas\b|\bBeetle\b|\bBora\b|\bDSG\b|\bSeat\b|\bSkoda\b', 'VW / Audi'),
    (r'\bNissan\b|\bVersa\b|\bSentra\b|\bAltima\b|\bMaxima\b|\bRogue\b|\bPathfinder\b|\bMurano\b|\bFrontier\b|\bTitan\b|\bKicks\b|\bInfiniti\b|\bNP300\b|\bMarch\b|\bTsuru\b|\bXtrail\b|\bX-Trail\b', 'Nissan'),
    (r'\bToyota\b|\bCamry\b|\bCorolla\b|\bRAV4\b|\bHighlander\b|\bTacoma\b|\bTundra\b|\b4Runner\b|\bSienna\b|\bAvalon\b|\bPrius\b|\bLexus\b|\bScion\b|\bYaris\b|\bHilux\b', 'Toyota'),
    (r'\bHonda\b|\bCivic\b|\bAccord\b|\bCR-V\b|\bPilot\b|\bOdyssey\b|\bHR-V\b|\bFit\b|\bRidgeline\b|\bAcura\b|\bCity\b', 'Honda'),
    (r'\bBMW\b|\bMercedes\b|\bBenz\b|\bSerie\s*[1-9]\b|\bZF\b', 'BMW / Mercedes'),
    (r'\bHyundai\b|\bKia\b|\bTucson\b|\bSanta Fe\b|\bElantra\b|\bSonata\b|\bSportage\b|\bSorento\b|\bForte\b|\bSoul\b|\bRio\b|\bAccent\b|\bPalisade\b|\bTelluride\b|\bSeltos\b', 'Hyundai / Kia'),
]


class CreativeIntelligenceService:
    def __init__(self, db: Session):
        self.db = db

    def _detect_brand_from_title(self, title: str) -> Optional[str]:
        """Detect vehicle brand from product title using regex patterns."""
        if not title:
            return None
        for pattern, brand in TITLE_BRAND_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return brand
        return None

    def _detect_brand_from_transmission(self, transmission_code: str) -> Optional[str]:
        """Map transmission code to vehicle brand."""
        if not transmission_code:
            return None
        code = transmission_code.strip().upper()
        # Try exact match first
        if code in TRANSMISSION_BRAND_MAP:
            return TRANSMISSION_BRAND_MAP[code]
        # Try case-insensitive lookup
        for key, brand in TRANSMISSION_BRAND_MAP.items():
            if key.upper() == code:
                return brand
        return None

    def _detect_brand_from_fitments(self, fitments) -> Optional[str]:
        """Detect brand from cached vehicle fitments."""
        if not fitments or not isinstance(fitments, list):
            return None
        for fitment in fitments:
            make = fitment.get('make', '')
            if isinstance(make, list):
                make = make[0] if make else ''
            if not make:
                continue
            make_lower = make.lower()
            if any(k in make_lower for k in ['chevrolet', 'gm', 'gmc', 'buick', 'cadillac', 'pontiac']):
                return 'GM / Chevrolet'
            if 'ford' in make_lower or 'lincoln' in make_lower or 'mercury' in make_lower:
                return 'Ford'
            if any(k in make_lower for k in ['chrysler', 'dodge', 'jeep', 'ram']):
                return 'Chrysler / Dodge / Jeep'
            if any(k in make_lower for k in ['volkswagen', 'vw', 'audi', 'seat', 'skoda']):
                return 'VW / Audi'
            if 'nissan' in make_lower or 'infiniti' in make_lower:
                return 'Nissan'
            if 'toyota' in make_lower or 'lexus' in make_lower or 'scion' in make_lower:
                return 'Toyota'
            if 'honda' in make_lower or 'acura' in make_lower:
                return 'Honda'
            if any(k in make_lower for k in ['bmw', 'mercedes', 'benz']):
                return 'BMW / Mercedes'
            if 'hyundai' in make_lower or 'kia' in make_lower:
                return 'Hyundai / Kia'
            if 'mitsubishi' in make_lower:
                return 'Mitsubishi'
            if 'subaru' in make_lower:
                return 'Subaru'
            if 'mazda' in make_lower:
                return 'Mazda'
        return None

    def _detect_brand(self, product) -> Optional[str]:
        """Detect vehicle brand using all available data (fitments > transmission > title)."""
        # Priority 1: Cached vehicle fitments (most accurate)
        brand = self._detect_brand_from_fitments(product.cached_vehicle_fitments)
        if brand:
            return brand
        # Priority 2: Transmission code
        brand = self._detect_brand_from_transmission(product.transmission_code)
        if brand:
            return brand
        # Priority 3: Title parsing
        return self._detect_brand_from_title(product.title)

    def _extract_transmission_codes_from_title(self, title: str) -> List[str]:
        """Extract all transmission codes mentioned in a product title."""
        if not title:
            return []
        codes = []
        for code in TRANSMISSION_BRAND_MAP.keys():
            if re.search(r'\b' + re.escape(code) + r'\b', title, re.IGNORECASE):
                codes.append(code)
        return codes

    def get_creative_report(self, days: int = 90) -> Dict[str, Any]:
        """
        Generate a comprehensive creative intelligence report.
        Groups products by vehicle brand with sales, search, and traffic data.
        """
        from app.models.product import Product

        # Fetch all products with any sales or search presence
        products = self.db.query(Product).filter(
            (Product.sold_all_time > 0) |
            (Product.gsc_impressions > 0) |
            (Product.ga4_sessions > 0)
        ).all()

        # --- Group by Vehicle Brand ---
        brand_data = defaultdict(lambda: {
            'total_units_all_time': 0,
            'total_revenue_all_time': 0.0,
            'units_30d': 0,
            'revenue_30d': 0.0,
            'units_90d': 0,
            'revenue_90d': 0.0,
            'units_365d': 0,
            'revenue_365d': 0.0,
            'total_impressions': 0,
            'total_clicks': 0,
            'total_sessions': 0,
            'total_ga4_revenue': 0.0,
            'product_count': 0,
            'top_products': [],
            'transmission_codes': defaultdict(int),  # code -> units sold
            'product_types': defaultdict(int),  # type -> units sold
        })

        unassigned = []

        for product in products:
            brand = self._detect_brand(product)

            if not brand:
                if product.sold_all_time and product.sold_all_time > 0:
                    unassigned.append({
                        'title': product.title,
                        'sold_all_time': product.sold_all_time or 0,
                        'transmission_code': product.transmission_code,
                    })
                continue

            bd = brand_data[brand]
            bd['product_count'] += 1
            bd['total_units_all_time'] += product.sold_all_time or 0
            bd['total_revenue_all_time'] += product.revenue_all_time or 0.0
            bd['units_30d'] += product.sold_30d or 0
            bd['revenue_30d'] += product.revenue_30d or 0.0
            bd['units_90d'] += product.sold_90d or 0
            bd['revenue_90d'] += product.revenue_90d or 0.0
            bd['units_365d'] += product.sold_365d or 0
            bd['revenue_365d'] += product.revenue_365d or 0.0
            bd['total_impressions'] += product.gsc_impressions or 0
            bd['total_clicks'] += product.gsc_clicks or 0
            bd['total_sessions'] += product.ga4_sessions or 0
            bd['total_ga4_revenue'] += product.ga4_revenue or 0.0

            # Track transmission codes
            if product.transmission_code:
                bd['transmission_codes'][product.transmission_code] += product.sold_all_time or 0
            # Also extract from title for multi-transmission products
            title_codes = self._extract_transmission_codes_from_title(product.title)
            for code in title_codes:
                if code != product.transmission_code:
                    bd['transmission_codes'][code] += 0  # just register presence

            # Track product types
            if product.product_type:
                bd['product_types'][product.product_type] += product.sold_all_time or 0

            # Track top products per brand
            bd['top_products'].append({
                'title': product.title,
                'handle': product.handle,
                'sold_all_time': product.sold_all_time or 0,
                'sold_30d': product.sold_30d or 0,
                'revenue_all_time': product.revenue_all_time or 0.0,
                'gsc_impressions': product.gsc_impressions or 0,
                'gsc_clicks': product.gsc_clicks or 0,
                'gsc_ctr': round(product.gsc_ctr or 0, 4),
                'gsc_position': round(product.gsc_position or 0, 1),
                'ga4_sessions': product.ga4_sessions or 0,
                'transmission_code': product.transmission_code,
                'product_type': product.product_type,
                'price': product.price,
                'inventory_quantity': product.inventory_quantity,
                'inventory_status': product.inventory_status,
            })

        # --- Build final report ---
        brand_summary = []
        for brand, data in brand_data.items():
            # Sort top products by units sold
            data['top_products'].sort(key=lambda x: x['sold_all_time'], reverse=True)

            # Top transmissions sorted by units sold
            top_transmissions = sorted(
                data['transmission_codes'].items(),
                key=lambda x: x[1], reverse=True
            )[:15]

            # Top product types
            top_types = sorted(
                data['product_types'].items(),
                key=lambda x: x[1], reverse=True
            )[:10]

            # Calculate search demand score (impressions-weighted)
            avg_ctr = (data['total_clicks'] / data['total_impressions'] * 100) if data['total_impressions'] > 0 else 0

            # Creative potential score (0-100)
            # Weights: sales volume (40%), search demand (30%), traffic (20%), revenue (10%)
            max_units = max((d['total_units_all_time'] for d in brand_data.values()), default=1) or 1
            max_impressions = max((d['total_impressions'] for d in brand_data.values()), default=1) or 1
            max_sessions = max((d['total_sessions'] for d in brand_data.values()), default=1) or 1
            max_revenue = max((d['total_revenue_all_time'] for d in brand_data.values()), default=1) or 1

            creative_score = int(
                (data['total_units_all_time'] / max_units) * 40 +
                (data['total_impressions'] / max_impressions) * 30 +
                (data['total_sessions'] / max_sessions) * 20 +
                (data['total_revenue_all_time'] / max_revenue) * 10
            )

            brand_summary.append({
                'vehicle_brand': brand,
                'creative_score': min(creative_score, 100),
                'total_units_all_time': data['total_units_all_time'],
                'total_revenue_all_time': round(data['total_revenue_all_time'], 2),
                'units_30d': data['units_30d'],
                'revenue_30d': round(data['revenue_30d'], 2),
                'units_90d': data['units_90d'],
                'revenue_90d': round(data['revenue_90d'], 2),
                'units_365d': data['units_365d'],
                'revenue_365d': round(data['revenue_365d'], 2),
                'search_impressions': data['total_impressions'],
                'search_clicks': data['total_clicks'],
                'search_ctr': round(avg_ctr, 2),
                'ga4_sessions': data['total_sessions'],
                'ga4_revenue': round(data['total_ga4_revenue'], 2),
                'product_count': data['product_count'],
                'top_transmissions': [
                    {'code': code, 'units_sold': units}
                    for code, units in top_transmissions
                ],
                'top_product_types': [
                    {'type': ptype, 'units_sold': units}
                    for ptype, units in top_types
                ],
                'top_products': data['top_products'][:20],
            })

        # Sort by creative score (highest first)
        brand_summary.sort(key=lambda x: x['creative_score'], reverse=True)

        # --- Search Queries by Vehicle Brand ---
        vehicle_queries = self._get_vehicle_search_queries()

        # --- Creative Suggestions ---
        suggestions = self._generate_creative_suggestions(brand_summary)

        return {
            'generated_at': __import__('datetime').datetime.now().isoformat(),
            'total_products_analyzed': len(products),
            'brands_found': len(brand_summary),
            'brand_ranking': brand_summary,
            'vehicle_search_queries': vehicle_queries,
            'creative_suggestions': suggestions,
            'unassigned_products': sorted(unassigned, key=lambda x: x['sold_all_time'], reverse=True)[:20],
        }

    def _get_vehicle_search_queries(self) -> Dict[str, List[Dict]]:
        """Get search queries from GSC grouped by vehicle brand keywords."""
        try:
            from app.services.google_api_service import GoogleApiService
            gsc = GoogleApiService()
            queries = gsc.get_search_console_data(days=90)
        except Exception as e:
            print(f"[Creative Intelligence] Could not fetch GSC queries: {e}")
            return {}

        if not queries:
            return {}

        brand_queries = defaultdict(list)

        # Vehicle brand keywords to match in search queries
        brand_keywords = {
            'GM / Chevrolet': ['chevrolet', 'chevy', 'silverado', 'tahoe', 'suburban', 'gm ', 'gmc', '4l60', 'th700', '6l80', 'camaro', 'malibu', 'cruze', 'equinox', 'traverse', 'colorado', 'express', 'trax', 'blazer'],
            'Ford': ['ford', 'f-150', 'f150', 'explorer', 'escape', 'ranger', 'mustang', 'edge', 'fusion', 'expedition', 'bronco', '4r70', 'aode', '5r55', 'a4ld', '10r80', '6r80'],
            'Chrysler / Dodge / Jeep': ['chrysler', 'dodge', 'jeep', 'ram', 'durango', 'charger', 'challenger', 'cherokee', 'wrangler', 'caravan', 'a604', '41te', '62te', '42rle', '68rfe', 'mopar'],
            'VW / Audi': ['volkswagen', 'vw', 'audi', 'jetta', 'golf', 'passat', 'tiguan', 'bora', '09g', '01m', 'dsg', 'dq200', 'seat'],
            'Nissan': ['nissan', 'versa', 'sentra', 'altima', 'rogue', 'pathfinder', 'frontier', 'titan', 'march', 'tsuru', 'np300', 'xtrail', 'jf015', 'jf011', 'cvt nissan', 're0f'],
            'Toyota': ['toyota', 'camry', 'corolla', 'rav4', 'highlander', 'tacoma', 'tundra', 'sienna', '4runner', 'prius', 'lexus', 'yaris', 'hilux', 'u660', 'u760'],
            'Honda': ['honda', 'civic', 'accord', 'cr-v', 'pilot', 'odyssey', 'fit', 'acura', 'city', 'hr-v'],
            'BMW / Mercedes': ['bmw', 'mercedes', 'benz', 'zf6hp', 'zf8hp', 'serie 3', 'serie 5', 'x3', 'x5'],
            'Hyundai / Kia': ['hyundai', 'kia', 'tucson', 'santa fe', 'elantra', 'sonata', 'sportage', 'sorento', 'forte', 'soul', 'accent', 'rio'],
        }

        for query_data in queries:
            query_text = query_data['query'].lower()
            for brand, keywords in brand_keywords.items():
                if any(kw in query_text for kw in keywords):
                    brand_queries[brand].append({
                        'query': query_data['query'],
                        'clicks': query_data['clicks'],
                        'impressions': query_data['impressions'],
                        'ctr': round(query_data['ctr'] * 100, 2),
                        'position': round(query_data['position'], 1),
                    })
                    break  # Assign to first matching brand

        # Sort each brand's queries by impressions
        for brand in brand_queries:
            brand_queries[brand].sort(key=lambda x: x['impressions'], reverse=True)
            brand_queries[brand] = brand_queries[brand][:15]  # Top 15 per brand

        return dict(brand_queries)

    def _generate_creative_suggestions(self, brand_summary: List[Dict]) -> List[Dict]:
        """Generate actionable creative suggestions based on data patterns."""
        suggestions = []

        for brand in brand_summary[:8]:  # Top 8 brands
            brand_name = brand['vehicle_brand']
            top_trans = brand['top_transmissions'][:3]
            top_products = brand['top_products'][:5]
            trans_names = ', '.join(t['code'] for t in top_trans) if top_trans else 'Varias'

            # High sales volume = proven demand
            if brand['total_units_all_time'] > 500:
                suggestions.append({
                    'brand': brand_name,
                    'type': 'high_volume',
                    'priority': 'alta',
                    'headline_idea': f"Partes de Transmision {brand_name} ({trans_names})",
                    'reason': f"{brand['total_units_all_time']:,} unidades vendidas historicas - demanda comprobada",
                    'ad_angle': 'Bestseller / Mas Vendido',
                    'target_audience': f"Duenos de vehiculos {brand_name} buscando partes de transmision",
                    'top_products_for_creative': [p['title'] for p in top_products[:3]],
                })

            # High impressions but low CTR = visibility opportunity
            if brand['search_impressions'] > 1000 and brand['search_ctr'] < 3:
                suggestions.append({
                    'brand': brand_name,
                    'type': 'awareness_gap',
                    'priority': 'alta',
                    'headline_idea': f"Transmision {trans_names} para tu {brand_name}?",
                    'reason': f"{brand['search_impressions']:,} impresiones en Google pero solo {brand['search_ctr']}% CTR - la gente busca pero no nos encuentra",
                    'ad_angle': 'Solucion directa al problema',
                    'target_audience': f"Personas buscando partes de transmision {brand_name} en Google",
                    'top_products_for_creative': [p['title'] for p in top_products[:3]],
                })

            # Strong 30d trend (momentum)
            if brand['units_30d'] > 50:
                suggestions.append({
                    'brand': brand_name,
                    'type': 'trending',
                    'priority': 'media',
                    'headline_idea': f"Lo que mas se vende: Transmision {brand_name}",
                    'reason': f"{brand['units_30d']} unidades vendidas en los ultimos 30 dias - tendencia activa",
                    'ad_angle': 'Trending / Tendencia actual',
                    'target_audience': f"Mecanicos y talleres que trabajan con {brand_name}",
                    'top_products_for_creative': [p['title'] for p in top_products[:3]],
                })

        return suggestions

    def get_brand_detail(self, brand_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed data for a specific vehicle brand."""
        report = self.get_creative_report()
        for brand in report['brand_ranking']:
            if brand['vehicle_brand'].lower() == brand_name.lower():
                # Enrich with full search queries
                queries = report['vehicle_search_queries'].get(brand['vehicle_brand'], [])
                brand['search_queries'] = queries
                return brand
        return None

    def get_transmission_report(self) -> List[Dict[str, Any]]:
        """Get a transmission-level breakdown (more granular than brand)."""
        from app.models.product import Product

        products = self.db.query(Product).filter(
            Product.transmission_code.isnot(None),
            (Product.sold_all_time > 0) | (Product.gsc_impressions > 0)
        ).all()

        trans_data = defaultdict(lambda: {
            'brand': None,
            'units_all_time': 0,
            'revenue_all_time': 0.0,
            'units_30d': 0,
            'impressions': 0,
            'clicks': 0,
            'sessions': 0,
            'product_count': 0,
            'top_products': [],
        })

        for product in products:
            code = product.transmission_code
            if not code:
                continue

            td = trans_data[code]
            if not td['brand']:
                td['brand'] = self._detect_brand_from_transmission(code) or 'Otro'
            td['units_all_time'] += product.sold_all_time or 0
            td['revenue_all_time'] += product.revenue_all_time or 0.0
            td['units_30d'] += product.sold_30d or 0
            td['impressions'] += product.gsc_impressions or 0
            td['clicks'] += product.gsc_clicks or 0
            td['sessions'] += product.ga4_sessions or 0
            td['product_count'] += 1
            td['top_products'].append({
                'title': product.title,
                'sold_all_time': product.sold_all_time or 0,
                'price': product.price,
            })

        result = []
        for code, data in trans_data.items():
            data['top_products'].sort(key=lambda x: x['sold_all_time'], reverse=True)
            result.append({
                'transmission_code': code,
                'vehicle_brand': data['brand'],
                'units_all_time': data['units_all_time'],
                'revenue_all_time': round(data['revenue_all_time'], 2),
                'units_30d': data['units_30d'],
                'impressions': data['impressions'],
                'clicks': data['clicks'],
                'sessions': data['sessions'],
                'product_count': data['product_count'],
                'top_products': data['top_products'][:10],
            })

        result.sort(key=lambda x: x['units_all_time'], reverse=True)
        return result

    def export_csv(self) -> str:
        """Export the brand report as CSV string."""
        report = self.get_creative_report()
        lines = ['Vehicle_Brand,Creative_Score,Units_All_Time,Revenue_All_Time,Units_30d,Units_90d,Search_Impressions,Search_Clicks,CTR_%,GA4_Sessions,Product_Count,Top_Transmissions']

        for brand in report['brand_ranking']:
            top_trans = ' | '.join(t['code'] for t in brand['top_transmissions'][:5])
            lines.append(
                f"{brand['vehicle_brand']},"
                f"{brand['creative_score']},"
                f"{brand['total_units_all_time']},"
                f"{brand['total_revenue_all_time']},"
                f"{brand['units_30d']},"
                f"{brand['units_90d']},"
                f"{brand['search_impressions']},"
                f"{brand['search_clicks']},"
                f"{brand['search_ctr']},"
                f"{brand['ga4_sessions']},"
                f"{brand['product_count']},"
                f"\"{top_trans}\""
            )

        # Product-level detail
        lines.append('')
        lines.append('Vehicle_Brand,Product_Title,Units_All_Time,Revenue_All_Time,Units_30d,Search_Impressions,Clicks,CTR_%,Position,Sessions,Transmission,Product_Type')

        for brand in report['brand_ranking']:
            for p in brand['top_products']:
                title = p['title'].replace('"', '""')
                lines.append(
                    f"{brand['vehicle_brand']},"
                    f"\"{title}\","
                    f"{p['sold_all_time']},"
                    f"{p['revenue_all_time']},"
                    f"{p['sold_30d']},"
                    f"{p['gsc_impressions']},"
                    f"{p['gsc_clicks']},"
                    f"{p['gsc_ctr']},"
                    f"{p['gsc_position']},"
                    f"{p['ga4_sessions']},"
                    f"{p.get('transmission_code', '')},"
                    f"\"{p.get('product_type', '')}\""
                )

        return '\n'.join(lines)
