import sys
import argparse
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from zomato_recsys.data.ingestion import find_repo_root, run_ingestion, load_app_config
from zomato_recsys.data.catalog import InMemoryCatalog
from zomato_recsys.data.models import UserPreferences
from zomato_recsys.filters.engine import apply_filters
from zomato_recsys.llm.adapter import load_groq_settings, GroqChatClient
from zomato_recsys.llm.prompts import build_prompt_messages

# Load env variables from .env
load_dotenv()

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("zomato_recsys.cli")

def cmd_status(args):
    """Print health and package status."""
    print("Zomato RecSys CLI: Healthy")
    print("Version: 0.1.0")
    repo_root = find_repo_root()
    print(f"Repository Root: {repo_root}")
    
    config_path = repo_root / "config" / "app.toml"
    if config_path.exists():
        print(f"Config: Loaded from {config_path}")
    else:
        print("Config: Missing app.toml")
        
    groq_settings = load_groq_settings(repo_root)
    if groq_settings.get("api_key"):
        print("Groq API Authentication: Configured")
    else:
        print("Groq API Authentication: Missing (Set GROQ_API_KEY)")

def cmd_ingest(args):
    """Load the dataset and print ingestion statistics."""
    repo_root = find_repo_root()
    print(f"Ingesting dataset (max_rows={args.max_rows or 'all'})...")
    try:
        restaurants, metrics = run_ingestion(repo_root, max_rows=args.max_rows)
        print("\nIngestion Completed Successfully:")
        print(json.dumps(metrics, indent=2))
    except Exception as e:
        print(f"\nIngestion failed: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_filter(args):
    """Perform deterministic filtering based on preferences."""
    repo_root = find_repo_root()
    try:
        # Load catalog
        print("Loading catalog...")
        restaurants, ingest_metrics = run_ingestion(repo_root, max_rows=args.max_rows)
        catalog = InMemoryCatalog(restaurants)
        
        # Parse preferences
        cuisines = args.cuisines.split(",") if args.cuisines else []
        prefs = UserPreferences(
            location=args.location,
            budget_band=args.budget,
            cuisines=cuisines,
            min_rating=args.min_rating,
            top_k=args.top_k
        )
        
        app_cfg = load_app_config(repo_root / "config" / "app.toml")
        print("Applying filters...")
        candidate_set = apply_filters(catalog.get_all(), prefs, app_cfg)
        
        print(f"\nFiltered Candidate Set (Total after filters: {candidate_set.total_after_hard_filters}):")
        if candidate_set.capped_to:
            print(f"Capped to: {candidate_set.capped_to}")
            
        print("\nTop 5 Candidates (Heuristic Pre-Rank):")
        for i, r in enumerate(candidate_set.restaurants[:5]):
            print(f"{i+1}. {r.name} | Rating: {r.aggregate_rating} | Cost for two: INR {r.cost_for_two} | Area: {r.location} | Cuisines: {', '.join(r.cuisines)}")
            
    except Exception as e:
        print(f"Error during filtering: {e}", file=sys.stderr)
        sys.exit(1)

def cmd_groq_complete(args):
    """Test Groq Chat completion and optionally print prompt."""
    repo_root = find_repo_root()
    try:
        # Load catalog
        print("Loading catalog...")
        restaurants, _ = run_ingestion(repo_root, max_rows=args.max_rows)
        catalog = InMemoryCatalog(restaurants)
        
        # Parse preferences
        cuisines = args.cuisines.split(",") if args.cuisines else []
        prefs = UserPreferences(
            location=args.location,
            budget_band=args.budget,
            cuisines=cuisines,
            min_rating=args.min_rating,
            free_text=args.free_text,
            top_k=args.top_k
        )
        
        app_cfg = load_app_config(repo_root / "config" / "app.toml")
        candidate_set = apply_filters(catalog.get_all(), prefs, app_cfg)
        
        groq_settings = load_groq_settings(repo_root)
        max_chars = int(groq_settings.get("max_free_text_chars", 500))
        messages = build_prompt_messages(prefs, candidate_set.restaurants, max_free_text_chars=max_chars)
        
        if args.print_prompt:
            print("\n--- System Message ---")
            print(messages[0]["content"])
            print("\n--- User Message ---")
            print(messages[1]["content"])
            
        if not args.dry_run:
            print("\nCalling Groq Chat Completions API...")
            client = GroqChatClient(groq_settings)
            result = client.complete(messages)
            if result.error:
                print(f"LLM Error: {result.error}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"Latency: {result.latency_ms:.2f} ms")
                print("Response:")
                print(result.content)
                
    except Exception as e:
        print(f"Error during LLM test: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Zomato Recommendation System CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Status command
    subparsers.add_parser("status", help="Check CLI and environment status")
    
    # Ingest command
    parser_ingest = subparsers.add_parser("ingest", help="Run ingestion and profile data")
    parser_ingest.add_argument("--max-rows", type=int, default=None, help="Maximum number of rows to load")
    
    # Filter command
    parser_filter = subparsers.add_parser("filter", help="Run deterministic candidate filtering")
    parser_filter.add_argument("--location", required=True, help="Search location (metro city or neighborhood)")
    parser_filter.add_argument("--budget", choices=["low", "medium", "high"], default=None, help="Budget band constraint")
    parser_filter.add_argument("--cuisines", default=None, help="Comma-separated cuisines")
    parser_filter.add_argument("--min-rating", type=float, default=0.0, help="Minimum restaurant rating floor")
    parser_filter.add_argument("--top-k", type=int, default=5, help="Number of recommendations to request")
    parser_filter.add_argument("--max-rows", type=int, default=5000, help="Scan max rows of raw dataset")
    
    # LLM test command
    parser_llm = subparsers.add_parser("groq-complete", help="Test prompt generation and Groq LLM completions")
    parser_llm.add_argument("--location", required=True, help="Search location")
    parser_llm.add_argument("--budget", choices=["low", "medium", "high"], default=None, help="Budget band")
    parser_llm.add_argument("--cuisines", default=None, help="Comma-separated cuisines")
    parser_llm.add_argument("--min-rating", type=float, default=0.0, help="Minimum rating")
    parser_llm.add_argument("--free-text", default=None, help="Natural language preferences")
    parser_llm.add_argument("--top-k", type=int, default=5, help="Number of items to recommend")
    parser_llm.add_argument("--max-rows", type=int, default=5000, help="Scan max rows of raw dataset")
    parser_llm.add_argument("--print-prompt", action="store_true", help="Print constructed prompt to standard output")
    parser_llm.add_argument("--dry-run", action="store_true", help="Do not make HTTP request to Groq API")
    
    args = parser.parse_args()
    
    if args.command == "status":
        cmd_status(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "filter":
        cmd_filter(args)
    elif args.command == "groq-complete":
        cmd_groq_complete(args)

if __name__ == "__main__":
    main()
