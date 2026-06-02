"""
Stock Health Scorer — Store-level Inventory Health Score (0-100).
Evaluates overall inventory health using weighted metrics.
"""
from typing import Dict, Any
from sqlalchemy.orm import Session

from app.models.product import Product
from app.services.redis_service import cache


class StockHealthScorer:
    """Computes a store-level Inventory Health Score (0-100)."""

    # Weights must sum to 1.0
    WEIGHTS = {
        "in_stock_rate": 0.30,
        "stockout_frequency": 0.20,
        "supply_coverage": 0.20,
        "dead_stock_ratio": 0.15,
        "velocity_alignment": 0.15,
    }

    def __init__(self, db: Session):
        self.db = db

    def calculate(self) -> Dict[str, Any]:
        """
        Calculate store-level inventory health score.
        Returns score (0-100) with breakdown.
        """
        cached = cache.get("inventory:health")
        if cached:
            return cached

        products = self.db.query(Product).filter(
            Product.inventory_quantity.isnot(None)
        ).all()

        if not products:
            return {
                "score": 0,
                "breakdown": {},
                "message": "No inventory data. Run a sync first.",
            }

        total = len(products)
        breakdown = {}

        # 1. In-Stock Rate (30%) — % of products currently in stock
        in_stock = sum(1 for p in products if (p.inventory_quantity or 0) > 0)
        in_stock_pct = (in_stock / total * 100) if total > 0 else 0
        breakdown["in_stock_rate"] = {
            "value": round(in_stock_pct, 1),
            "score": min(in_stock_pct, 100),
            "label": f"{in_stock}/{total} products in stock",
        }

        # 2. Stockout Frequency (20%) — inverse of avg stockout events
        avg_stockout = (
            sum(p.stockout_frequency_90d or 0 for p in products) / total
            if total > 0 else 0
        )
        # Score: 100 if avg_stockout=0, drops toward 0 as stockouts increase
        stockout_score = max(0, 100 - (avg_stockout * 25))
        breakdown["stockout_frequency"] = {
            "value": round(avg_stockout, 2),
            "score": round(stockout_score, 1),
            "label": f"Avg {avg_stockout:.1f} stockouts per product (90d)",
        }

        # 3. Days of Supply Coverage (20%) — % of products with >14 days of supply
        products_with_supply = [
            p for p in products
            if p.days_of_supply is not None and p.days_of_supply > 14 and p.inventory_status == "in_stock"
        ]
        supply_pct = (len(products_with_supply) / in_stock * 100) if in_stock > 0 else 0
        breakdown["supply_coverage"] = {
            "value": round(supply_pct, 1),
            "score": min(supply_pct, 100),
            "label": f"{len(products_with_supply)}/{in_stock} products with >14 days supply",
        }

        # 4. Dead Stock Ratio (15%) — inverse of dead stock percentage
        dead_stock = sum(1 for p in products if p.stock_health == "dead")
        dead_pct = (dead_stock / total * 100) if total > 0 else 0
        dead_score = max(0, 100 - (dead_pct * 2))  # 50% dead stock = 0 score
        breakdown["dead_stock_ratio"] = {
            "value": round(dead_pct, 1),
            "score": round(dead_score, 1),
            "label": f"{dead_stock} dead stock products ({dead_pct:.1f}%)",
        }

        # 5. Velocity Alignment (15%) — how well stock matches demand
        # Products with healthy=good, warning/critical=bad, dead=bad
        healthy_count = sum(1 for p in products if p.stock_health == "healthy")
        alignment_pct = (healthy_count / total * 100) if total > 0 else 0
        breakdown["velocity_alignment"] = {
            "value": round(alignment_pct, 1),
            "score": min(alignment_pct, 100),
            "label": f"{healthy_count}/{total} products with healthy stock levels",
        }

        # Weighted score
        overall = sum(
            breakdown[key]["score"] * self.WEIGHTS[key]
            for key in self.WEIGHTS
        )
        overall = min(int(round(overall)), 100)

        # Health label
        if overall >= 80:
            label = "Excellent"
        elif overall >= 60:
            label = "Good"
        elif overall >= 40:
            label = "Needs Attention"
        elif overall >= 20:
            label = "Poor"
        else:
            label = "Critical"

        result = {
            "score": overall,
            "label": label,
            "breakdown": breakdown,
            "total_products_tracked": total,
        }

        cache.set("inventory:health", result, ttl=300)
        return result
