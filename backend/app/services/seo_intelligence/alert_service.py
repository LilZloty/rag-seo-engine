"""
SEO Alert Service - Early Warning System

Generates and manages SEO alerts based on threshold checks
against historical data in keyword_daily_metrics and page_daily_metrics.

Alert types:
    - position_drop: Top query drops >3 positions in 7 days
    - traffic_drop: Total organic clicks down >20% vs 7 days ago
    - ctr_drop: Page-1 query CTR drops >50% vs 7 days ago
    - new_opportunity: New query appears with >100 impressions
    - cannibalization: New cannibalization detected

Thresholds are conservative to avoid alert fatigue.
"""

import uuid
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func as sql_func, and_, desc

from app.models.seo_intelligence import (
    KeywordDailyMetric, KeywordPageMapping, SEOAlert
)


class AlertService:
    """
    Generates and manages SEO alerts.
    
    Thresholds are configurable. Defaults are conservative 
    to avoid alert fatigue.
    """
    
    # Default thresholds
    THRESHOLDS = {
        "position_drop_spots": 3,         # Alert if drops >3 positions
        "traffic_drop_pct": 20,           # Alert if total clicks down >20%
        "ctr_drop_pct": 50,               # Alert if CTR drops >50%
        "new_query_min_impressions": 100,  # Alert on new queries with >100 impr
        "min_query_importance": 50,        # Only alert on queries with >50 impr
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    # ========================================================================
    # ALERT GENERATION (called by DailyCollector)
    # ========================================================================
    
    def generate_alerts(self) -> int:
        """
        Run all alert checks and create SEOAlert records.
        Returns number of alerts generated.
        """
        target_date = (datetime.now() - timedelta(days=3)).date()
        total = 0
        
        total += self._check_position_drops(target_date)
        total += self._check_traffic_drops(target_date)
        total += self._check_ctr_drops(target_date)
        total += self._check_new_opportunities(target_date)
        total += self._check_cannibalization(target_date)
        
        self.db.flush()
        return total
    
    def _check_position_drops(self, target_date: date) -> int:
        """
        Alert: Any top-50 query drops >3 positions in 7 days.
        Severity: high if top-10, medium otherwise.
        """
        threshold = self.THRESHOLDS["position_drop_spots"]
        min_impressions = self.THRESHOLDS["min_query_importance"]
        
        records = self.db.query(KeywordDailyMetric).filter(
            KeywordDailyMetric.date == target_date,
            KeywordDailyMetric.position_change_7d != None,
            KeywordDailyMetric.position_change_7d > threshold,  # positive = worsened
            KeywordDailyMetric.impressions >= min_impressions,
            KeywordDailyMetric.position <= 50
        ).order_by(
            desc(KeywordDailyMetric.position_change_7d)
        ).limit(20).all()
        
        count = 0
        for record in records:
            # Avoid duplicate alerts for same query+type in last 7 days
            existing = self.db.query(SEOAlert).filter(
                SEOAlert.alert_type == 'position_drop',
                SEOAlert.affected_query == record.query,
                SEOAlert.created_at >= datetime.utcnow() - timedelta(days=7)
            ).first()
            if existing:
                continue
            
            old_position = record.position - record.position_change_7d
            severity = "high" if old_position <= 10 else "medium"
            
            alert = SEOAlert(
                id=str(uuid.uuid4()),
                alert_type='position_drop',
                severity=severity,
                title=f"Position drop: '{record.query}'",
                description=(
                    f"Query '{record.query}' dropped {record.position_change_7d:+.1f} positions "
                    f"in 7 days (from {old_position:.1f} to {record.position:.1f}). "
                    f"This query has {record.impressions} daily impressions."
                ),
                affected_query=record.query,
                metric_before=old_position,
                metric_after=record.position,
                metric_change=record.position_change_7d,
            )
            self.db.add(alert)
            count += 1
        
        return count
    
    def _check_traffic_drops(self, target_date: date) -> int:
        """
        Alert: Total organic clicks down >20% vs same day last week.
        Severity: critical if >40%, high if >20%.
        """
        threshold_pct = self.THRESHOLDS["traffic_drop_pct"]
        
        # Today's total clicks
        today_total = self.db.query(
            sql_func.sum(KeywordDailyMetric.clicks)
        ).filter(
            KeywordDailyMetric.date == target_date
        ).scalar() or 0
        
        # Same day last week
        week_ago = target_date - timedelta(days=7)
        week_ago_total = self.db.query(
            sql_func.sum(KeywordDailyMetric.clicks)
        ).filter(
            KeywordDailyMetric.date == week_ago
        ).scalar() or 0
        
        if week_ago_total == 0:
            return 0
        
        change_pct = ((today_total - week_ago_total) / week_ago_total) * 100
        
        if change_pct >= -threshold_pct:
            return 0  # Not a significant drop
        
        # Avoid duplicate
        existing = self.db.query(SEOAlert).filter(
            SEOAlert.alert_type == 'traffic_drop',
            SEOAlert.created_at >= datetime.utcnow() - timedelta(days=7)
        ).first()
        if existing:
            return 0
        
        severity = "critical" if change_pct <= -40 else "high"
        
        alert = SEOAlert(
            id=str(uuid.uuid4()),
            alert_type='traffic_drop',
            severity=severity,
            title=f"Organic traffic drop: {change_pct:.0f}%",
            description=(
                f"Total organic clicks dropped from {week_ago_total} to {today_total} "
                f"({change_pct:+.1f}%) compared to the same day last week. "
                f"Investigate potential algorithm update, technical issues, or seasonal patterns."
            ),
            metric_before=float(week_ago_total),
            metric_after=float(today_total),
            metric_change=change_pct,
        )
        self.db.add(alert)
        return 1
    
    def _check_ctr_drops(self, target_date: date) -> int:
        """
        Alert: Page-1 query CTR drops >50% vs 7-day average.
        Severity: high (these are your money queries).
        """
        threshold_pct = self.THRESHOLDS["ctr_drop_pct"]
        min_impressions = self.THRESHOLDS["min_query_importance"]
        
        records = self.db.query(KeywordDailyMetric).filter(
            KeywordDailyMetric.date == target_date,
            KeywordDailyMetric.position <= 10,  # Page 1 only
            KeywordDailyMetric.impressions >= min_impressions,
            KeywordDailyMetric.ctr_change_7d != None,
        ).all()
        
        count = 0
        for record in records:
            if record.ctr_change_7d is None:
                continue
            
            # Calculate percentage drop
            old_ctr = record.ctr - record.ctr_change_7d
            if old_ctr <= 0:
                continue
            
            drop_pct = (record.ctr_change_7d / old_ctr) * 100
            
            if drop_pct >= -threshold_pct:
                continue  # Not a significant drop
            
            # Avoid duplicate
            existing = self.db.query(SEOAlert).filter(
                SEOAlert.alert_type == 'ctr_drop',
                SEOAlert.affected_query == record.query,
                SEOAlert.created_at >= datetime.utcnow() - timedelta(days=7)
            ).first()
            if existing:
                continue
            
            alert = SEOAlert(
                id=str(uuid.uuid4()),
                alert_type='ctr_drop',
                severity='high',
                title=f"CTR drop: '{record.query}'",
                description=(
                    f"Query '{record.query}' at position {record.position:.1f} "
                    f"CTR dropped from {old_ctr*100:.1f}% to {record.ctr*100:.1f}% "
                    f"({drop_pct:+.0f}%). "
                    f"Consider refreshing meta title/description."
                ),
                affected_query=record.query,
                metric_before=old_ctr,
                metric_after=record.ctr,
                metric_change=drop_pct,
            )
            self.db.add(alert)
            count += 1
        
        return count
    
    def _check_new_opportunities(self, target_date: date) -> int:
        """
        Alert: New query appears with >100 impressions that wasn't tracked before.
        Severity: low (informational, but actionable).
        """
        min_impressions = self.THRESHOLDS["new_query_min_impressions"]
        
        # Get today's queries
        today_queries = self.db.query(KeywordDailyMetric.query).filter(
            KeywordDailyMetric.date == target_date,
            KeywordDailyMetric.impressions >= min_impressions
        ).all()
        today_set = {q.query for q in today_queries}
        
        # Get queries from the previous 7 days
        week_ago = target_date - timedelta(days=7)
        historical_queries = self.db.query(
            KeywordDailyMetric.query
        ).filter(
            KeywordDailyMetric.date >= week_ago,
            KeywordDailyMetric.date < target_date
        ).distinct().all()
        historical_set = {q.query for q in historical_queries}
        
        # New queries = in today but not in last 7 days
        new_queries = today_set - historical_set
        
        count = 0
        for query_text in list(new_queries)[:10]:  # Limit to 10 alerts
            record = self.db.query(KeywordDailyMetric).filter(
                KeywordDailyMetric.date == target_date,
                KeywordDailyMetric.query == query_text
            ).first()
            
            if not record:
                continue
            
            alert = SEOAlert(
                id=str(uuid.uuid4()),
                alert_type='new_opportunity',
                severity='low',
                title=f"New query: '{query_text}'",
                description=(
                    f"New query '{query_text}' appeared with {record.impressions} impressions "
                    f"at position {record.position:.1f}. "
                    f"Consider creating or optimizing content for this query."
                ),
                affected_query=query_text,
                metric_after=float(record.impressions),
                metric_change=float(record.impressions),
            )
            self.db.add(alert)
            count += 1
        
        return count
    
    def _check_cannibalization(self, target_date: date) -> int:
        """
        Alert: New cannibalization detected (queries competing across pages).
        Severity: medium.
        """
        # Get cannibalized queries from today
        cannibalized = self.db.query(
            KeywordPageMapping.query,
            sql_func.count(sql_func.distinct(KeywordPageMapping.page_url)).label('page_count'),
            sql_func.sum(KeywordPageMapping.impressions).label('total_impressions')
        ).filter(
            KeywordPageMapping.date == target_date,
            KeywordPageMapping.is_cannibalized == True
        ).group_by(
            KeywordPageMapping.query
        ).having(
            sql_func.sum(KeywordPageMapping.impressions) >= self.THRESHOLDS["min_query_importance"]
        ).all()
        
        count = 0
        for row in cannibalized:
            # Avoid duplicate
            existing = self.db.query(SEOAlert).filter(
                SEOAlert.alert_type == 'cannibalization',
                SEOAlert.affected_query == row.query,
                SEOAlert.created_at >= datetime.utcnow() - timedelta(days=30)
            ).first()
            if existing:
                continue
            
            alert = SEOAlert(
                id=str(uuid.uuid4()),
                alert_type='cannibalization',
                severity='medium',
                title=f"Cannibalization: '{row.query}'",
                description=(
                    f"Query '{row.query}' has {row.page_count} competing pages "
                    f"with {row.total_impressions} total impressions. "
                    f"Consolidate content to avoid splitting ranking signals."
                ),
                affected_query=row.query,
                metric_after=float(row.page_count),
            )
            self.db.add(alert)
            count += 1
        
        return count
    
    # ========================================================================
    # ALERT QUERYING (for API/Frontend)
    # ========================================================================
    
    def get_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        alert_type: Optional[str] = None,
        days: int = 30,
        limit: int = 50
    ) -> List[SEOAlert]:
        """Get alerts with optional filtering."""
        query = self.db.query(SEOAlert).filter(
            SEOAlert.created_at >= datetime.utcnow() - timedelta(days=days)
        )
        
        if status:
            query = query.filter(SEOAlert.status == status)
        if severity:
            query = query.filter(SEOAlert.severity == severity)
        if alert_type:
            query = query.filter(SEOAlert.alert_type == alert_type)
        
        return query.order_by(desc(SEOAlert.created_at)).limit(limit).all()
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """
        Dashboard summary of alerts.
        
        Returns:
        {
          open_alerts: 5,
          by_severity: { critical: 1, high: 2, medium: 2 },
          by_type: { position_drop: 2, ctr_drop: 1, ... },
          recent: [ ... top 5 ... ]
        }
        """
        open_alerts = self.db.query(SEOAlert).filter(
            SEOAlert.status == 'open'
        )
        
        total_open = open_alerts.count()
        
        # By severity
        severity_counts = self.db.query(
            SEOAlert.severity,
            sql_func.count(SEOAlert.id)
        ).filter(
            SEOAlert.status == 'open'
        ).group_by(SEOAlert.severity).all()
        
        by_severity = {s: c for s, c in severity_counts}
        
        # By type
        type_counts = self.db.query(
            SEOAlert.alert_type,
            sql_func.count(SEOAlert.id)
        ).filter(
            SEOAlert.status == 'open'
        ).group_by(SEOAlert.alert_type).all()
        
        by_type = {t: c for t, c in type_counts}
        
        # Recent 5
        recent = open_alerts.order_by(
            desc(SEOAlert.created_at)
        ).limit(5).all()
        
        return {
            "open_alerts": total_open,
            "by_severity": by_severity,
            "by_type": by_type,
            "recent": recent
        }
    
    def update_alert_status(
        self,
        alert_id: str,
        status: str,
        resolution_notes: Optional[str] = None
    ) -> Optional[SEOAlert]:
        """Update alert status (acknowledge, resolve, dismiss)."""
        alert = self.db.query(SEOAlert).filter(SEOAlert.id == alert_id).first()
        if not alert:
            return None
        
        alert.status = status
        if status == 'resolved':
            alert.resolved_at = datetime.utcnow()
        if resolution_notes:
            alert.resolution_notes = resolution_notes
        
        self.db.flush()
        return alert
