from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class Restaurant(BaseModel):
    restaurant_id: str
    name: str
    city: str
    location: str
    address: Optional[str] = None
    cuisines: List[str] = Field(default_factory=list)
    aggregate_rating: Optional[float] = None
    cost_for_two: Optional[float] = None
    votes: Optional[int] = 0
    online_order: Optional[str] = None
    book_table: Optional[str] = None
    url: Optional[str] = None
    raw: Optional[Dict[str, Any]] = Field(default_factory=dict)

class UserPreferences(BaseModel):
    location: str
    budget_band: Optional[str] = None  # "low", "medium", "high"
    cuisines: List[str] = Field(default_factory=list)
    min_rating: float = 0.0
    free_text: Optional[str] = None
    top_k: int = 5
