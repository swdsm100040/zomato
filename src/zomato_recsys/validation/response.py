import json
import logging
from typing import List, Dict, Any, Tuple, Optional
from zomato_recsys.data.models import Restaurant, UserPreferences
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class RecommendationItem(BaseModel):
    restaurant_id: str
    name: str
    city: str
    location: str
    address: Optional[str] = None
    cuisines: List[str] = Field(default_factory=list)
    aggregate_rating: Optional[float] = None
    cost_for_two: Optional[float] = None
    online_order: Optional[str] = None
    book_table: Optional[str] = None
    url: Optional[str] = None
    rank: int
    explanation: str
    backfilled: bool = False

class RecommendationResponse(BaseModel):
    summary: Optional[str] = None
    items: List[RecommendationItem] = Field(default_factory=list)
    debug: Optional[Dict[str, Any]] = None

def parse_llm_json(raw_json_str: str) -> Tuple[Optional[str], List[Dict[str, Any]], Optional[str]]:
    """
    Parse the LLM response JSON string.
    Returns: (summary, rankings_list, error_message)
    """
    try:
        data = json.loads(raw_json_str)
        if not isinstance(data, dict):
            return None, [], "LLM output is not a JSON object."
            
        summary = data.get("summary")
        rankings = data.get("rankings", [])
        
        if not isinstance(rankings, list):
            return summary, [], "The 'rankings' key in LLM JSON is not a list."
            
        return summary, rankings, None
    except json.JSONDecodeError as e:
        return None, [], f"JSON parsing failed: {e}"

def validate_and_merge(
    raw_json_str: str,
    candidates: List[Restaurant],
    prefs: UserPreferences,
    backfill_allowed: bool = True
) -> Tuple[List[RecommendationItem], Optional[str], int]:
    """
    Validate LLM rankings against the candidate set, drop invalid entries,
    and merge restaurant catalog data with the LLM explanation.
    Returns: (recommendation_items, summary, validation_drops_count)
    """
    summary, rankings, parse_error = parse_llm_json(raw_json_str)
    
    candidate_map = {r.restaurant_id: r for r in candidates}
    rec_items: List[RecommendationItem] = []
    seen_ids = set()
    validation_drops = 0
    
    if not parse_error:
        for item in rankings:
            if not isinstance(item, dict):
                validation_drops += 1
                continue
                
            rest_id = item.get("restaurant_id")
            explanation = item.get("explanation", "")
            rank_val = item.get("rank")
            
            if not rest_id or rest_id not in candidate_map:
                logger.warning(f"Validation failure: LLM proposed unknown or hallucinated restaurant ID: {rest_id}")
                validation_drops += 1
                continue
                
            if rest_id in seen_ids:
                logger.warning(f"Validation failure: duplicate restaurant ID: {rest_id}")
                validation_drops += 1
                continue
                
            try:
                rank = int(rank_val) if rank_val is not None else len(rec_items) + 1
            except (ValueError, TypeError):
                rank = len(rec_items) + 1
                
            restaurant = candidate_map[rest_id]
            seen_ids.add(rest_id)
            
            rec_item = RecommendationItem(
                restaurant_id=restaurant.restaurant_id,
                name=restaurant.name,
                city=restaurant.city,
                location=restaurant.location,
                address=restaurant.address,
                cuisines=restaurant.cuisines,
                aggregate_rating=restaurant.aggregate_rating,
                cost_for_two=restaurant.cost_for_two,
                online_order=restaurant.online_order,
                book_table=restaurant.book_table,
                url=restaurant.url,
                rank=rank,
                explanation=str(explanation),
                backfilled=False
            )
            rec_items.append(rec_item)
    else:
        logger.error(f"Failed to parse LLM JSON: {parse_error}")
        # If we had a parse error, all LLM rankings are dropped
        validation_drops = len(rankings) if rankings else 1
        
    # Sort validated items by rank
    rec_items.sort(key=lambda x: x.rank)
    
    # Backfill if list is shorter than requested top_k
    if len(rec_items) < prefs.top_k and backfill_allowed:
        # Find candidates not already included
        remaining_candidates = [r for r in candidates if r.restaurant_id not in seen_ids]
        backfill_count = prefs.top_k - len(rec_items)
        
        for i, restaurant in enumerate(remaining_candidates[:backfill_count]):
            rank = len(rec_items) + 1
            # Generate a nice template explanation
            explanation = "Recommended based on top ratings and matching criteria in your area."
            if restaurant.aggregate_rating:
                explanation = f"Highly rated at {restaurant.aggregate_rating}/5. Mapped as matching option for your area."
                
            rec_item = RecommendationItem(
                restaurant_id=restaurant.restaurant_id,
                name=restaurant.name,
                city=restaurant.city,
                location=restaurant.location,
                address=restaurant.address,
                cuisines=restaurant.cuisines,
                aggregate_rating=restaurant.aggregate_rating,
                cost_for_two=restaurant.cost_for_two,
                online_order=restaurant.online_order,
                book_table=restaurant.book_table,
                url=restaurant.url,
                rank=rank,
                explanation=explanation,
                backfilled=True
            )
            rec_items.append(rec_item)
            
    return rec_items, summary, validation_drops
