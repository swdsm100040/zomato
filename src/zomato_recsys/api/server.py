import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from zomato_recsys.data.ingestion import find_repo_root, run_ingestion, load_app_config
from zomato_recsys.data.catalog import InMemoryCatalog
from zomato_recsys.data.models import UserPreferences
from zomato_recsys.llm.adapter import load_groq_settings
from zomato_recsys.orchestrator import run_recommendation
from zomato_recsys.validation.response import RecommendationResponse

# Load environment variables from .env
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("zomato_recsys.api")

catalog = None
filter_cfg = {}
groq_settings = {}
api_cfg = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load config and ingest dataset on startup."""
    global catalog, filter_cfg, groq_settings, api_cfg
    repo_root = find_repo_root()
    
    logger.info(f"Loading config from {repo_root}")
    cfg = load_app_config(repo_root / "config" / "app.toml")
    filter_cfg = cfg.get("filter", {})
    groq_settings = load_groq_settings(repo_root)
    api_cfg = cfg.get("api", {})
    
    max_rows = int(api_cfg.get("ingest_max_rows", 40000))
    logger.info(f"Running startup ingestion (max_rows={max_rows})...")
    
    try:
        restaurants, metrics = run_ingestion(repo_root, max_rows=max_rows)
        catalog = InMemoryCatalog(restaurants)
        logger.info(f"Catalog loaded successfully with {len(restaurants)} restaurants.")
        logger.info(f"Ingestion metrics: {metrics}")
    except Exception as e:
        logger.error(f"Failed to load catalog during startup: {e}")
        # Initialize empty catalog so server doesn't crash but returns errors on calls
        catalog = InMemoryCatalog([])
        
    yield

app = FastAPI(
    title="Zomato RecSys API",
    description="AI-assisted restaurant discovery and recommendation engine",
    version="0.1.0",
    lifespan=lifespan
)

@app.post("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(prefs: UserPreferences, include_debug: bool = False):
    """Get personalized restaurant recommendations."""
    if not catalog or len(catalog.get_all()) == 0:
        raise HTTPException(
            status_code=503,
            detail="Catalog is currently empty or failed to load. Please check server logs."
        )
        
    try:
        # Run orchestration
        response = run_recommendation(
            catalog=catalog,
            filter_cfg=filter_cfg,
            groq_settings=groq_settings,
            preferences=prefs,
            include_debug=include_debug
        )
        return response
    except Exception as e:
        logger.error(f"Error during recommendation generation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while generating recommendations: {str(e)}"
        )

@app.get("/locations")
async def get_locations():
    """Retrieve all unique cities/neighborhoods for form dropdowns."""
    if not catalog:
        return []
    return catalog.get_all_locations()

@app.get("/cuisines")
async def get_cuisines():
    """Retrieve all unique cuisines for form dropdowns."""
    if not catalog:
        return []
    return catalog.get_all_cuisines()

# Setup static files mounting
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    
    @app.get("/", response_class=HTMLResponse)
    async def get_index():
        return FileResponse(static_dir / "index.html")

def start():
    """Start the FastAPI development server."""
    import uvicorn
    uvicorn.run("zomato_recsys.api.server:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    start()
