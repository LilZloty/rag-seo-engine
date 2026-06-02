"""
Shopify B2B Tier Tag Sync Service
=================================
State-based tier tag assignment that replaces unreliable Shopify Flow triggers.

Uses Shopify Admin GraphQL API to:
1. Query customer segment members (customerSegmentMembers)
2. Apply/remove tier tags (tagsAdd/tagsRemove)

Priority hierarchy: Platino > Oro > Plata > Bronce
If a customer qualifies for multiple tiers, only the highest tier tag is applied.
"""

import time
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from app.core.config import settings


# ============ Tier Definitions ============

TIER_HIERARCHY = [
    # Ordered by priority: index 0 = highest
    {"name": "Platino B2B", "tag": "Platino B2B", "segment_id": "gid://shopify/Segment/451113615465"},
    {"name": "Oro B2B",     "tag": "Oro B2B",     "segment_id": "gid://shopify/Segment/451113648233"},
    {"name": "Plata B2B",   "tag": "Plata B2B",   "segment_id": "gid://shopify/Segment/451111747689"},
    {"name": "Bronce B2B",  "tag": "Bronce B2B",  "segment_id": "gid://shopify/Segment/451113418857"},
]

ALL_TIER_TAGS = [t["tag"] for t in TIER_HIERARCHY]


@dataclass
class TierSyncResult:
    """Result of a tier tag sync operation."""
    success: bool = True
    dry_run: bool = False
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0
    
    # Segment member counts
    segment_counts: Dict[str, int] = field(default_factory=dict)
    
    # Changes
    total_customers_checked: int = 0
    tags_added: int = 0
    tags_removed: int = 0
    already_correct: int = 0
    
    # Detailed changes log
    changes: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


class TierTagSyncService:
    """Syncs B2B tier tags based on Shopify customer segment membership."""
    
    def __init__(self):
        self._last_sync_result: Optional[TierSyncResult] = None
    
    def _graphql_request(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL request to Shopify Admin API."""
        url = f"https://{settings.SHOPIFY_STORE}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN
        }
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f"Shopify API error: {response.status_code} - {response.text}")
        
        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return result
    
    def get_segment_members(self, segment_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all members of a customer segment using cursor-based pagination.
        Then batch-fetches tags from the Customer type (not available on CustomerSegmentMember).
        
        Returns list of: {id: "gid://shopify/Customer/123", tags: ["tag1", "tag2"]}
        """
        members = []
        cursor = None
        page = 1
        
        # Step 1: Get member IDs from the segment
        while True:
            query = """
            query GetSegmentMembers($segmentId: ID!, $first: Int!, $after: String) {
                customerSegmentMembers(
                    segmentId: $segmentId
                    first: $first
                    after: $after
                ) {
                    edges {
                        node {
                            id
                            displayName
                            defaultEmailAddress {
                                emailAddress
                            }
                        }
                        cursor
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """
            
            variables = {
                "segmentId": segment_id,
                "first": 250,
            }
            if cursor:
                variables["after"] = cursor
            
            try:
                result = self._graphql_request(query, variables)
                data = result.get("data", {}).get("customerSegmentMembers", {})
                edges = data.get("edges", [])
                
                for edge in edges:
                    node = edge.get("node", {})
                    # Convert CustomerSegmentMember GID to Customer GID
                    # Shopify returns gid://shopify/CustomerSegmentMember/XXX
                    # but tagsAdd/tagsRemove and nodes queries need gid://shopify/Customer/XXX
                    raw_id = node.get("id", "")
                    customer_id = raw_id.replace("CustomerSegmentMember", "Customer")
                    
                    members.append({
                        "id": customer_id,
                        "display_name": node.get("displayName", ""),
                        "email": (node.get("defaultEmailAddress") or {}).get("emailAddress", ""),
                        "tags": [],  # Will be filled in Step 2
                    })
                
                page_info = data.get("pageInfo", {})
                print(f"  📄 Page {page}: fetched {len(edges)} members (total: {len(members)})")
                
                if page_info.get("hasNextPage"):
                    cursor = page_info.get("endCursor")
                    page += 1
                    time.sleep(0.5)  # Rate limit protection
                else:
                    break
                    
            except Exception as e:
                print(f"  ❌ Error fetching segment members: {e}")
                raise
        
        # Step 2: Batch-fetch tags from Customer type using nodes query
        if members:
            self._batch_fetch_tags(members)
        
        return members
    
    def _batch_fetch_tags(self, members: List[Dict[str, Any]]) -> None:
        """
        Fetch tags for a list of customers using the nodes query.
        Updates members in-place with their tags.
        Processes in batches of 50 to stay within query complexity limits.
        """
        batch_size = 50
        
        for i in range(0, len(members), batch_size):
            batch = members[i:i + batch_size]
            customer_ids = [m["id"] for m in batch]
            
            query = """
            query GetCustomerTags($ids: [ID!]!) {
                nodes(ids: $ids) {
                    ... on Customer {
                        id
                        tags
                    }
                }
            }
            """
            
            try:
                result = self._graphql_request(query, {"ids": customer_ids})
                nodes = result.get("data", {}).get("nodes", [])
                
                # Build a lookup map
                tags_map = {}
                for node in nodes:
                    if node and node.get("id"):
                        tags_map[node["id"]] = node.get("tags", [])
                
                # Apply tags to members
                for member in batch:
                    member["tags"] = tags_map.get(member["id"], [])
                
                print(f"  🏷️  Fetched tags for batch {i // batch_size + 1} ({len(batch)} customers)")
                
                if i + batch_size < len(members):
                    time.sleep(0.3)  # Rate limit between batches
                    
            except Exception as e:
                print(f"  ⚠️ Failed to fetch tags for batch {i // batch_size + 1}: {e}")
                # Keep empty tags — sync will still add the correct tag
    
    def _add_tags(self, customer_gid: str, tags: List[str]) -> bool:
        """Add tags to a customer using tagsAdd mutation."""
        mutation = """
        mutation tagsAdd($id: ID!, $tags: [String!]!) {
            tagsAdd(id: $id, tags: $tags) {
                node { id }
                userErrors { field message }
            }
        }
        """
        
        try:
            result = self._graphql_request(mutation, {"id": customer_gid, "tags": tags})
            user_errors = result.get("data", {}).get("tagsAdd", {}).get("userErrors", [])
            if user_errors:
                print(f"  ⚠️ tagsAdd errors for {customer_gid}: {user_errors}")
                return False
            return True
        except Exception as e:
            print(f"  ❌ Failed to add tags to {customer_gid}: {e}")
            return False
    
    def _remove_tags(self, customer_gid: str, tags: List[str]) -> bool:
        """Remove tags from a customer using tagsRemove mutation."""
        mutation = """
        mutation tagsRemove($id: ID!, $tags: [String!]!) {
            tagsRemove(id: $id, tags: $tags) {
                node { id }
                userErrors { field message }
            }
        }
        """
        
        try:
            result = self._graphql_request(mutation, {"id": customer_gid, "tags": tags})
            user_errors = result.get("data", {}).get("tagsRemove", {}).get("userErrors", [])
            if user_errors:
                print(f"  ⚠️ tagsRemove errors for {customer_gid}: {user_errors}")
                return False
            return True
        except Exception as e:
            print(f"  ❌ Failed to remove tags from {customer_gid}: {e}")
            return False
    
    def sync_tier_tags(self, dry_run: bool = False) -> TierSyncResult:
        """
        Main sync method. Fetches all tier segments and applies correct tags.
        
        Priority: Platino > Oro > Plata > Bronce
        - Each customer gets ONLY their highest qualifying tier tag
        - All lower/incorrect tier tags are removed
        
        Args:
            dry_run: If True, calculates changes but doesn't apply them
        
        Returns:
            TierSyncResult with detailed report
        """
        result = TierSyncResult(
            dry_run=dry_run,
            started_at=datetime.now().isoformat()
        )
        
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print(f"🔄 TIER TAG SYNC {'(DRY RUN)' if dry_run else '(LIVE)'}")
        print(f"{'='*60}")
        
        # Step 1: Fetch all segment members
        # customer_gid -> highest_tier_tag
        customer_tier_map: Dict[str, str] = {}
        # customer_gid -> customer info (name, email, current tags)
        customer_info_map: Dict[str, Dict] = {}
        
        for tier in TIER_HIERARCHY:
            tier_name = tier["name"]
            segment_id = tier["segment_id"]
            
            print(f"\n📊 Fetching segment: {tier_name} ({segment_id})")
            
            try:
                members = self.get_segment_members(segment_id)
                result.segment_counts[tier_name] = len(members)
                print(f"  ✅ Found {len(members)} members in {tier_name}")
                
                for member in members:
                    customer_gid = member["id"]
                    
                    # Store customer info (first time we see them)
                    if customer_gid not in customer_info_map:
                        customer_info_map[customer_gid] = member
                    
                    # Only assign if customer doesn't already have a HIGHER tier
                    # Since we iterate from highest to lowest, first assignment wins
                    if customer_gid not in customer_tier_map:
                        customer_tier_map[customer_gid] = tier["tag"]
                        
            except Exception as e:
                error_msg = f"Failed to fetch segment {tier_name}: {str(e)}"
                result.errors.append(error_msg)
                print(f"  ❌ {error_msg}")
        
        result.total_customers_checked = len(customer_tier_map)
        
        print(f"\n📋 Total unique customers across all tiers: {len(customer_tier_map)}")
        
        # Step 2: Apply correct tags
        print(f"\n{'─'*40}")
        print(f"🏷️  Applying tags...")
        
        for customer_gid, desired_tag in customer_tier_map.items():
            info = customer_info_map.get(customer_gid, {})
            current_tags = info.get("tags", [])
            display_name = info.get("display_name", "Unknown")
            
            # Determine current tier tags on this customer
            current_tier_tags = [t for t in current_tags if t in ALL_TIER_TAGS]
            
            # What needs to change?
            tags_to_add = [desired_tag] if desired_tag not in current_tier_tags else []
            tags_to_remove = [t for t in current_tier_tags if t != desired_tag]
            
            if not tags_to_add and not tags_to_remove:
                result.already_correct += 1
                continue
            
            # Log the change
            change = {
                "customer_gid": customer_gid,
                "display_name": display_name,
                "email": info.get("email", ""),
                "desired_tier": desired_tag,
                "current_tier_tags": current_tier_tags,
                "tags_to_add": tags_to_add,
                "tags_to_remove": tags_to_remove,
                "applied": False,
            }
            
            if not dry_run:
                success = True
                
                # Add the correct tag
                if tags_to_add:
                    if self._add_tags(customer_gid, tags_to_add):
                        result.tags_added += len(tags_to_add)
                    else:
                        success = False
                
                # Remove incorrect tier tags
                if tags_to_remove:
                    if self._remove_tags(customer_gid, tags_to_remove):
                        result.tags_removed += len(tags_to_remove)
                    else:
                        success = False
                
                change["applied"] = success
                
                if success:
                    print(f"  ✅ {display_name}: {' → '.join(current_tier_tags) if current_tier_tags else '(none)'} → {desired_tag}")
                else:
                    print(f"  ⚠️ {display_name}: partial failure")
                
                # Rate limit: small delay between mutations
                time.sleep(0.2)
            else:
                # Dry run - just log what would happen
                result.tags_added += len(tags_to_add)
                result.tags_removed += len(tags_to_remove)
                change["applied"] = True  # Would be applied
                print(f"  🔍 {display_name}: would change {current_tier_tags or '(none)'} → {desired_tag}")
            
            result.changes.append(change)
        
        # Finalize
        result.completed_at = datetime.now().isoformat()
        result.duration_seconds = round(time.time() - start_time, 2)
        
        print(f"\n{'='*60}")
        print(f"{'🔍 DRY RUN' if dry_run else '✅ SYNC'} COMPLETE")
        print(f"  Duration: {result.duration_seconds}s")
        print(f"  Customers checked: {result.total_customers_checked}")
        print(f"  Already correct: {result.already_correct}")
        print(f"  Tags {'would be ' if dry_run else ''}added: {result.tags_added}")
        print(f"  Tags {'would be ' if dry_run else ''}removed: {result.tags_removed}")
        print(f"  Errors: {len(result.errors)}")
        print(f"{'='*60}\n")
        
        self._last_sync_result = result
        return result
    
    def get_preview(self) -> Dict[str, Any]:
        """
        Quick preview: fetch member counts per segment without making any changes.
        Also checks tag status for each segment.
        """
        preview = {
            "tiers": [],
            "fetched_at": datetime.now().isoformat(),
        }
        
        total_customers = 0
        total_missing_tags = 0
        
        for tier in TIER_HIERARCHY:
            tier_name = tier["name"]
            tag = tier["tag"]
            segment_id = tier["segment_id"]
            
            print(f"📊 Previewing segment: {tier_name}")
            
            try:
                members = self.get_segment_members(segment_id)
                
                # Count how many have the correct tag
                with_tag = sum(1 for m in members if tag in m.get("tags", []))
                without_tag = len(members) - with_tag
                
                # Count how many have conflicting tier tags
                with_wrong_tag = sum(
                    1 for m in members
                    if any(t in m.get("tags", []) for t in ALL_TIER_TAGS if t != tag)
                )
                
                tier_info = {
                    "tier": tier_name,
                    "tag": tag,
                    "segment_id": segment_id,
                    "total_members": len(members),
                    "with_correct_tag": with_tag,
                    "missing_tag": without_tag,
                    "with_wrong_tier_tag": with_wrong_tag,
                    "members": [
                        {
                            "display_name": m.get("display_name", ""),
                            "email": m.get("email", ""),
                            "tags": m.get("tags", []),
                            "has_correct_tag": tag in m.get("tags", []),
                            "tier_tags": [t for t in m.get("tags", []) if t in ALL_TIER_TAGS],
                        }
                        for m in members
                    ]
                }
                
                preview["tiers"].append(tier_info)
                total_customers += len(members)
                total_missing_tags += without_tag
                
                print(f"  ✅ {tier_name}: {len(members)} members, {with_tag} tagged, {without_tag} missing")
                
            except Exception as e:
                preview["tiers"].append({
                    "tier": tier_name,
                    "tag": tag,
                    "segment_id": segment_id,
                    "error": str(e),
                    "total_members": 0,
                })
                print(f"  ❌ {tier_name}: {e}")
        
        preview["total_customers"] = total_customers
        preview["total_missing_tags"] = total_missing_tags
        
        return preview
    
    def get_last_sync_status(self) -> Optional[Dict]:
        """Get the result of the last sync operation."""
        if self._last_sync_result:
            return self._last_sync_result.to_dict()
        return None


# Global singleton
tier_sync_service = TierTagSyncService()
