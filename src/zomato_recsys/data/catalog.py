from typing import List, Dict, Optional, Set
from zomato_recsys.data.models import Restaurant

class InMemoryCatalog:
    def __init__(self, restaurants: List[Restaurant]):
        self._restaurants = restaurants
        self._restaurants_by_id: Dict[str, Restaurant] = {
            r.restaurant_id: r for r in restaurants
        }
        
    def get_restaurant_by_id(self, restaurant_id: str) -> Optional[Restaurant]:
        """Look up a restaurant by its stable ID."""
        return self._restaurants_by_id.get(restaurant_id)
        
    def get_all(self) -> List[Restaurant]:
        """Return all restaurants in the catalog."""
        return self._restaurants
        
    def get_all_locations(self) -> List[str]:
        """Return a sorted list of unique locations (cities/areas) available in the catalog."""
        locations: Set[str] = set()
        for r in self._restaurants:
            if r.city:
                locations.add(r.city)
            if r.location:
                locations.add(r.location)
        return sorted(list(locations))
        
    def get_all_cuisines(self) -> List[str]:
        """Return a sorted list of all unique cuisine tags in the catalog."""
        cuisines: Set[str] = set()
        for r in self._restaurants:
            cuisines.update(r.cuisines)
        return sorted(list(cuisines))
