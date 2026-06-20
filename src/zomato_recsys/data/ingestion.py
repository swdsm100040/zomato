import os
import json
import hashlib
import logging
from typing import List, Dict, Any, Tuple
import tomllib
from pathlib import Path
from datasets import load_dataset
from zomato_recsys.data.models import Restaurant

logger = logging.getLogger(__name__)

def find_repo_root(start_path: Path = None) -> Path:
    """Walk up parent directories to find the repository root (containing pyproject.toml)."""
    if start_path is None:
        start_path = Path(__file__).resolve()
    for parent in [start_path] + list(start_path.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    # Default to current directory if not found
    return Path.cwd()

def load_app_config(config_path: Path) -> Dict[str, Any]:
    """Load application TOML configuration."""
    with open(config_path, "rb") as f:
        return tomllib.load(f)

def load_column_mapping(mapping_path: Path) -> Dict[str, str]:
    """Load JSON column mapping file."""
    with open(mapping_path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_rating(rate_val: Any) -> Optional[float]:
    """Parse Zomato rating string (e.g. '4.1/5', 'NEW', '-') into float or None."""
    if rate_val is None:
        return None
    rate_str = str(rate_val).strip()
    if not rate_str or rate_str in ("NEW", "-", "N/A"):
        return None
    try:
        if "/" in rate_str:
            rate_str = rate_str.split("/")[0].strip()
        return float(rate_str)
    except ValueError:
        return None

def clean_cost(cost_val: Any) -> Optional[float]:
    """Parse Zomato cost string (e.g. '1,200', '400') into float or None."""
    if cost_val is None:
        return None
    cost_str = str(cost_val).strip()
    if not cost_str or cost_str in ("-", "N/A"):
        return None
    # Remove commas and other non-numeric chars except decimal point
    cleaned = "".join(c for c in cost_str if c.isdigit() or c == ".")
    try:
        return float(cleaned)
    except ValueError:
        return None

def clean_cuisines(cuisines_val: Any) -> List[str]:
    """Split comma-separated cuisines and lowercase/strip them."""
    if not cuisines_val:
        return []
    if isinstance(cuisines_val, list):
        return [str(c).strip().lower() for c in cuisines_val if c]
    cuisines_str = str(cuisines_val).strip()
    if not cuisines_str:
        return []
    return [c.strip().lower() for c in cuisines_str.split(",") if c.strip()]

def generate_restaurant_id(row: Dict[str, Any], mapping: Dict[str, str], disambiguator: int = 0) -> str:
    """Generate a stable restaurant ID from key fields using SHA-256."""
    name = str(row.get(mapping.get("name", "name"), "")).strip()
    city = str(row.get(mapping.get("listed_in_city", "listed_in(city)"), "Unknown")).strip()
    location = str(row.get(mapping.get("location", "location"), "")).strip()
    address = str(row.get(mapping.get("address", "address"), "")).strip()
    url = str(row.get(mapping.get("url", "url"), "")).strip()
    
    fingerprint_parts = [name, city, location, address, url]
    fingerprint = "\x1f".join(fingerprint_parts)
    if disambiguator > 0:
        fingerprint += f"\x1f{disambiguator}"
        
    sha = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    return f"rec-{sha[:16]}"

def run_ingestion(repo_root: Path, offline: bool = False, max_rows: Optional[int] = None) -> Tuple[List[Restaurant], Dict[str, Any]]:
    """Load, clean, and map Hugging Face dataset to list of canonical Restaurants."""
    config_path = repo_root / "config" / "app.toml"
    mapping_path = repo_root / "config" / "column_mapping.json"
    
    config = load_app_config(config_path)
    mapping = load_column_mapping(mapping_path)
    
    dataset_id = config["dataset"]["id"]
    revision = config["dataset"]["revision"]
    
    logger.info(f"Loading HF dataset {dataset_id} at revision {revision}")
    
    # Load dataset
    if offline:
        # Enable offline mode for datasets
        os.environ["HF_DATASETS_OFFLINE"] = "1"
        
    ds = load_dataset(dataset_id, revision=revision, split="train")
    
    # Track statistics
    total_rows = len(ds)
    processed_count = 0
    dropped_empty_name = 0
    warning_count = 0
    
    restaurants: List[Restaurant] = []
    fingerprint_counts: Dict[str, int] = {}
    
    for i, row in enumerate(ds):
        if max_rows is not None and processed_count >= max_rows:
            break
            
        name_val = row.get(mapping.get("name", "name"))
        if not name_val or not str(name_val).strip():
            dropped_empty_name += 1
            continue
            
        # Standard cleaning
        name = str(name_val).strip()
        city = str(row.get(mapping.get("listed_in_city", "listed_in(city)"), "Unknown")).strip()
        location = str(row.get(mapping.get("location", "location"), "Unknown")).strip()
        address = str(row.get(mapping.get("address", "address"), "")).strip()
        url = str(row.get(mapping.get("url", "url"), "")).strip()
        
        # Calculate fingerprint for disambiguation
        base_fingerprint = "\x1f".join([name, city, location, address, url])
        disambiguator = fingerprint_counts.get(base_fingerprint, 0)
        fingerprint_counts[base_fingerprint] = disambiguator + 1
        
        restaurant_id = generate_restaurant_id(row, mapping, disambiguator)
        
        # Ratings and costs
        rate_raw = row.get(mapping.get("rate", "rate"))
        approx_cost_raw = row.get(mapping.get("approx_cost", "approx_cost(for two people)"))
        cuisines_raw = row.get(mapping.get("cuisines", "cuisines"))
        votes_raw = row.get(mapping.get("votes", "votes"))
        
        rating = clean_rating(rate_raw)
        cost = clean_cost(approx_cost_raw)
        cuisines = clean_cuisines(cuisines_raw)
        
        try:
            votes = int(votes_raw) if votes_raw is not None else 0
        except (ValueError, TypeError):
            votes = 0
            warning_count += 1
            
        online_order = str(row.get(mapping.get("online_order", "online_order"), "No")).strip()
        book_table = str(row.get(mapping.get("book_table", "book_table"), "No")).strip()
        
        # Keep raw row but clean up keys so it can be serialized easily
        raw_row = {str(k): v for k, v in row.items()}
        
        restaurant = Restaurant(
            restaurant_id=restaurant_id,
            name=name,
            city=city,
            location=location,
            address=address,
            cuisines=cuisines,
            aggregate_rating=rating,
            cost_for_two=cost,
            votes=votes,
            online_order=online_order,
            book_table=book_table,
            url=url,
            raw=raw_row
        )
        restaurants.append(restaurant)
        processed_count += 1
        
    metrics = {
        "total_rows_in_source": total_rows,
        "loaded_rows": processed_count,
        "dropped_empty_name": dropped_empty_name,
        "warnings": warning_count
    }
    
    return restaurants, metrics
