from typing import List, Optional, Tuple, Set, Any, Dict
from pydantic import BaseModel
from zomato_recsys.data.models import Restaurant, UserPreferences

class CandidateSet(BaseModel):
    restaurants: List[Restaurant]
    total_after_hard_filters: int
    capped_to: Optional[int] = None

def filter_by_location(restaurant: Restaurant, search_loc: str) -> bool:
    """
    Check if restaurant location matches search location.
    Flexible case-insensitive substring match.
    """
    if not search_loc:
        return True
        
    search_loc = search_loc.lower().strip()
    city = (restaurant.city or "").lower().strip()
    loc = (restaurant.location or "").lower().strip()
    
    return (search_loc in city) or (city in search_loc) or (search_loc in loc) or (loc in search_loc)

def filter_by_rating(restaurant: Restaurant, min_rating: float, null_rating_policy: str = "exclude") -> bool:
    """
    Enforce minimum rating filter.
    Policy: If min_rating > 0 and rating is null, exclude.
    If min_rating <= 0, allow null ratings.
    """
    rating = restaurant.aggregate_rating
    if rating is None:
        if min_rating > 0.0 or null_rating_policy == "exclude":
            return False
        return True
    return rating >= min_rating

def filter_by_cuisine(restaurant: Restaurant, pref_cuisines: List[str]) -> bool:
    """
    Match cuisine preferences.
    If list is empty, matches any. Else, performs case-insensitive any-of matching.
    """
    if not pref_cuisines:
        return True
        
    pref_set = {c.lower().strip() for c in pref_cuisines if c.strip()}
    if not pref_set:
        return True
        
    rest_set = {c.lower().strip() for c in restaurant.cuisines}
    return len(pref_set.intersection(rest_set)) > 0

def get_budget_band(cost: Optional[float], low_max: float, medium_max: float) -> str:
    """Determine the budget band for a cost value."""
    if cost is None:
        return "unknown"
    if cost <= low_max:
        return "low"
    elif cost <= medium_max:
        return "medium"
    else:
        return "high"

def filter_by_budget(restaurant: Restaurant, budget_band: Optional[str], budget_cfg: Dict[str, Any]) -> bool:
    """
    Enforce budget band matching.
    If no preference is set, matches any.
    If preference is set, excludes restaurants with missing cost.
    """
    if not budget_band:
        return True
        
    band = budget_band.lower().strip()
    if band not in ("low", "medium", "high"):
        return True
        
    cost = restaurant.cost_for_two
    if cost is None:
        return False
        
    low_max = float(budget_cfg.get("low_max", 500))
    medium_max = float(budget_cfg.get("medium_max", 1200))
    
    r_band = get_budget_band(cost, low_max, medium_max)
    return r_band == band

def calculate_pre_score(
    restaurant: Restaurant, 
    prefs: UserPreferences, 
    budget_cfg: Dict[str, Any]
) -> Tuple[int, float, float]:
    """
    Generate sorting key components for heuristic ranking.
    Sort fields in order:
    1. Cuisine overlap count (higher is better) -> -cuisine_overlap
    2. Rating (higher is better) -> -rating
    3. Distance to budget band midpoint (smaller is better) -> cost_distance
    """
    # 1. Cuisine overlap
    cuisine_overlap = 0
    if prefs.cuisines:
        pref_set = {c.lower().strip() for c in prefs.cuisines if c.strip()}
        rest_set = {c.lower().strip() for c in restaurant.cuisines}
        cuisine_overlap = len(pref_set.intersection(rest_set))
        
    # 2. Rating
    rating = restaurant.aggregate_rating if restaurant.aggregate_rating is not None else 0.0
    
    # 3. Distance to budget midpoint
    cost_distance = 0.0
    if restaurant.cost_for_two is not None and prefs.budget_band:
        low_max = float(budget_cfg.get("low_max", 500))
        medium_max = float(budget_cfg.get("medium_max", 1200))
        
        # Midpoint calculation
        band = prefs.budget_band.lower().strip()
        if band == "low":
            midpoint = low_max / 2.0
        elif band == "medium":
            midpoint = (low_max + medium_max) / 2.0
        else:
            midpoint = medium_max * 1.5
            
        cost_distance = abs(restaurant.cost_for_two - midpoint)
        
    return (-cuisine_overlap, -rating, cost_distance)

def apply_filters(
    restaurants: List[Restaurant],
    prefs: UserPreferences,
    app_cfg: Dict[str, Any]
) -> CandidateSet:
    """
    Apply hard filters, sort remaining candidates by heuristic pre-rank, and cap candidates.
    """
    filter_cfg = app_cfg.get("filter", {})
    budget_cfg = app_cfg.get("budget", {}).get("fixed_bands", {})
    
    candidate_cap = int(filter_cfg.get("candidate_cap", 60))
    null_rating_policy = filter_cfg.get("null_rating_policy", "exclude")
    
    filtered: List[Restaurant] = []
    
    for r in restaurants:
        # Enforce Location Hard Filter (Required)
        if not filter_by_location(r, prefs.location):
            continue
            
        # Enforce Rating Hard Filter
        if not filter_by_rating(r, prefs.min_rating, null_rating_policy):
            continue
            
        # Enforce Cuisine Hard Filter
        if not filter_by_cuisine(r, prefs.cuisines):
            continue
            
        # Enforce Budget Hard Filter
        if not filter_by_budget(r, prefs.budget_band, budget_cfg):
            continue
            
        filtered.append(r)
        
    total_after_filters = len(filtered)
    
    # Pre-rank the candidates
    # Sort key: (score_tuple, restaurant_id) for deterministic tie-breaking
    scored_candidates = []
    for r in filtered:
        score = calculate_pre_score(r, prefs, budget_cfg)
        scored_candidates.append((score, r.restaurant_id, r))
        
    scored_candidates.sort(key=lambda item: (item[0], item[1]))
    
    final_candidates = [item[2] for item in scored_candidates]
    
    capped_to = None
    if len(final_candidates) > candidate_cap:
        final_candidates = final_candidates[:candidate_cap]
        capped_to = candidate_cap
        
    return CandidateSet(
        restaurants=final_candidates,
        total_after_hard_filters=total_after_filters,
        capped_to=capped_to
    )
