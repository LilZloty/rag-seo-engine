from typing import List, Dict, Any
import re

class AIReferralTracker:
    """
    Detects and categorizes AI-sourced traffic.
    
    Identifies traffic from:
    1. Known AI engine referrers (Perplexity, ChatGPT, etc.)
    2. Specific UTM parameters (utm_source=llms.txt)
    """
    
    AI_REFERRER_PATTERNS = [
        r"perplexity\.ai",
        r"chatgpt\.com", 
        r"claude\.ai",
        r"copilot\.microsoft\.com",
        r"you\.com",
        r"phind\.com",
        r"openai\.com",
        r"google\.com/search.*ai_overviews" # Future proofing for G SGE
    ]
    
    @classmethod
    def is_ai_referral(cls, referrer: str, source: str = None) -> bool:
        """Check if a session comes from an AI source."""
        if source == "llms.txt":
            return True
            
        if not referrer:
            return False
            
        for pattern in cls.AI_REFERRER_PATTERNS:
            if re.search(pattern, referrer, re.IGNORECASE):
                return True
        return False

    @classmethod
    def categorize_sessions(cls, sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Categorize a list of session data into AI vs Traditional."""
        summary = {
            "total_sessions": 0,
            "ai_sessions": 0,
            "llms_txt_sessions": 0,
            "traditional_sessions": 0,
            "referrers": {}
        }
        
        for s in sessions:
            count = s.get('sessions', 0)
            summary["total_sessions"] += count
            
            is_llms = s.get('source') == "llms.txt"
            is_ai = cls.is_ai_referral(s.get('referrer'), s.get('source'))
            
            if is_llms:
                summary["llms_txt_sessions"] += count
                summary["ai_sessions"] += count
            elif is_ai:
                summary["ai_sessions"] += count
            else:
                summary["traditional_sessions"] += count
                
            # Track referrers
            ref = s.get('referrer') or s.get('source') or "Direct"
            summary["referrers"][ref] = summary["referrers"].get(ref, 0) + count
            
        return summary
