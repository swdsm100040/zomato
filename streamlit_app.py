import os
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from zomato_recsys.data.ingestion import find_repo_root, run_ingestion, load_app_config
from zomato_recsys.data.catalog import InMemoryCatalog
from zomato_recsys.data.models import UserPreferences
from zomato_recsys.llm.adapter import load_groq_settings
from zomato_recsys.orchestrator import run_recommendation

# Load local environment variables from .env
load_dotenv()

# Ensure secrets map to environment variables for cloud deploy
try:
    for key in ("GROQ_API_KEY", "GROQ_MODEL", "GROQ_BASE_URL", "HF_TOKEN"):
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
except Exception:
    # st.secrets is not initialized or throws when secrets.toml is missing
    pass

# Page configuration
st.set_page_config(
    page_title="Zomato AI Discovery",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply premium styling overrides
st.markdown("""
<style>
    /* Google Stitch & Material Design 3 Theme (Light Mode) */
    .stApp {
        background-color: #f8f9fa !important;
        color: #1f1f1f !important;
        font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif !important;
    }
    
    /* Hide the sidebar completely */
    section[data-testid="stSidebar"], div[data-testid="collapsedControl"] {
        display: none !important;
    }
    
    /* Ensure primary text is black/dark gray */
    h1, h2, h3, h4, h5, h6, label, p, span, div {
        color: #1f1f1f !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }
    
    h1, h2, h3, h4 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }
    
    /* Prevent card banner text from being blacked out */
    .card-banner * {
        color: #ffffff !important;
    }
    
    /* Custom style for inputs */
    div[data-baseweb="select"] > div, 
    div[data-baseweb="input"] > div, 
    div[data-baseweb="textarea"] > textarea,
    input, textarea, select {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        color: #1f1f1f !important;
        border-radius: 12px !important;
        font-size: 0.95rem !important;
        box-shadow: none !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    div[data-baseweb="select"] > div:hover, 
    div[data-baseweb="input"] > div:hover, 
    div[data-baseweb="textarea"] > textarea:hover {
        border-color: #ff1e56 !important;
        box-shadow: 0 0 0 3px rgba(255, 30, 86, 0.1) !important;
    }
    
    /* Primary buttons (Zomato brand gradient red-orange) */
    div.stButton > button {
        background: linear-gradient(135deg, #FF1E56 0%, #FF8E53 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 24px !important;
        padding: 0.75rem 2rem !important;
        font-weight: 700 !important;
        font-family: 'Outfit', sans-serif !important;
        box-shadow: 0 4px 15px rgba(255, 30, 86, 0.2) !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        width: 100% !important;
    }
    
    div.stButton > button:hover {
        background: linear-gradient(135deg, #e01245 0%, #e6753c 100%) !important;
        box-shadow: 0 8px 25px rgba(255, 30, 86, 0.35) !important;
        transform: translateY(-2px) !important;
        color: #ffffff !important;
    }

    /* Metric blocks */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        border-radius: 20px !important;
        padding: 1.25rem !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.02) !important;
        transition: all 0.2s ease !important;
    }
    
    div[data-testid="stMetric"]:hover {
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.05) !important;
        border-color: #ff1e56 !important;
    }
    
    div[data-testid="stMetricLabel"] {
        color: #5f6368 !important;
        font-weight: 600 !important;
    }
    
    div[data-testid="stMetricValue"] {
        color: #ff1e56 !important;
        font-weight: 800 !important;
    }

    /* Info / notification blocks */
    div[data-testid="stNotification"] {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        border-radius: 20px !important;
        color: #1f1f1f !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02) !important;
    }

    /* Streamlit Container / Border block styling */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff !important;
        border: 1px solid #dadce0 !important;
        border-radius: 24px !important;
        padding: 1.75rem !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02) !important;
    }

    /* Restaurant Card list grid layout */
    @keyframes slideUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .restaurant-card {
        background-color: #ffffff;
        border: 1px solid #dadce0;
        border-radius: 24px;
        padding: 0;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.03);
        animation: slideUp 0.45s cubic-bezier(0.16, 1, 0.3, 1);
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .restaurant-card:hover {
        transform: translateY(-6px);
        border-color: #ff1e56;
        box-shadow: 0 15px 35px rgba(255, 30, 86, 0.1);
    }
    
    /* Split-Card top half: Obsidian gradient header */
    .card-banner {
        height: 120px;
        width: 100%;
        position: relative;
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        background: linear-gradient(135deg, #1e1e24 0%, #111115 100%);
        background-size: cover !important;
        background-position: center !important;
        background-repeat: no-repeat !important;
    }
    
    .card-content {
        padding: 1.25rem;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
        justify-content: space-between;
    }
    
    .restaurant-name {
        font-size: 1.2rem !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        line-height: 1.3;
        margin: 0 !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.4);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    
    .rating-badge {
        position: absolute;
        top: 1rem;
        right: 1rem;
        background: rgba(255, 255, 255, 0.15);
        backdrop-filter: blur(12px) saturate(180%);
        -webkit-backdrop-filter: blur(12px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #ffffff !important;
        padding: 0.3rem 0.6rem;
        border-radius: 10px;
        font-weight: 800;
        font-size: 0.8rem;
        display: flex;
        align-items: center;
        gap: 0.25rem;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2);
    }
    
    .rating-badge.unrated {
        background: rgba(255, 255, 255, 0.08);
        color: rgba(255, 255, 255, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: none;
    }
    
    .meta-row {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-top: 0.25rem;
        margin-bottom: 0.75rem;
    }
    
    .meta-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: #444746;
        font-size: 0.85rem;
    }
    
    .meta-icon {
        width: 15px;
        height: 15px;
        flex-shrink: 0;
        color: #ff1e56;
    }
    
    .cuisine-row {
        margin-bottom: 0.75rem;
        min-height: 28px;
    }
    
    .cuisine-tag {
        background-color: #f1f3f4;
        border: 1px solid #e8eaed;
        color: #5f6368 !important;
        padding: 0.25rem 0.6rem;
        border-radius: 20px;
        font-size: 0.7rem;
        display: inline-block;
        margin-right: 0.25rem;
        margin-bottom: 0.25rem;
        text-transform: capitalize;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    
    .cuisine-tag:hover {
        background-color: #ffeef2;
        color: #ff1e56 !important;
        border-color: #ffcbd6;
    }
    
    .ai-box {
        background: linear-gradient(135deg, #fcfdff 0%, #f5f8ff 100%);
        border: 1px solid rgba(26, 115, 232, 0.1);
        padding: 0.85rem;
        border-radius: 16px;
        margin-top: auto;
        box-shadow: 0 2px 10px rgba(26, 115, 232, 0.02);
    }
    
    .ai-title-row {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        margin-bottom: 0.35rem;
    }
    
    .ai-sparkle-icon {
        width: 13px;
        height: 13px;
        color: #1a73e8;
    }
    
    .ai-title {
        font-size: 0.7rem;
        font-weight: 800;
        color: #1a73e8 !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    
    .ai-text {
        font-size: 0.82rem;
        line-height: 1.45;
        color: #3c4043 !important;
        margin: 0;
    }
    
    .backfill-badge {
        position: absolute;
        top: 1rem;
        left: 1rem;
        background: rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        color: #ffffff !important;
        font-size: 0.58rem;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }

    /* Skeleton Loader Styling */
    @keyframes pulse {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    .skeleton-card {
        background-color: #ffffff;
        border: 1px solid #dadce0;
        border-radius: 24px;
        padding: 0;
        margin-bottom: 1.5rem;
        height: 380px;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    
    .skeleton-banner {
        height: 120px;
        width: 100%;
        background: linear-gradient(-90deg, #f0f0f0 0%, #e5e5e5 50%, #f0f0f0 100%);
        background-size: 400% 400%;
        animation: pulse 1.5s ease infinite;
    }
    
    .skeleton-line {
        background: linear-gradient(-90deg, #f0f0f0 0%, #e5e5e5 50%, #f0f0f0 100%);
        background-size: 400% 400%;
        animation: pulse 1.5s ease infinite;
        border-radius: 6px;
        margin-bottom: 0.5rem;
    }
    
    .skeleton-title {
        height: 20px;
        width: 75%;
    }
    
    .skeleton-cuisine {
        height: 18px;
        width: 35%;
        display: inline-block;
        border-radius: 20px;
        margin-right: 0.35rem;
    }
</style>

""", unsafe_allow_html=True)

def get_obsidian_gradient(restaurant_name: str) -> str:
    gradients = [
        "linear-gradient(135deg, #1e1e24 0%, #111115 100%)",  # Charcoal Obsidian
        "linear-gradient(135deg, #1a237e 0%, #0d1b2a 100%)",  # Midnight Blue Obsidian
        "linear-gradient(135deg, #311b92 0%, #12005e 100%)",  # Deep Violet Obsidian
        "linear-gradient(135deg, #4a0006 0%, #1a0002 100%)",  # Maroon Obsidian
        "linear-gradient(135deg, #004d40 0%, #001a14 100%)"   # Emerald Obsidian
    ]
    h = 0
    for char in restaurant_name:
        h = (h * 31 + ord(char)) & 0xFFFFFFFF
    return gradients[h % len(gradients)]

def render_skeleton_loader():
    skeleton_cols = st.columns(4)
    for i in range(4):
        with skeleton_cols[i]:
            st.markdown("""
            <div class="skeleton-card">
                <div class="skeleton-banner"></div>
                <div class="card-content" style="padding: 1.25rem;">
                    <div class="skeleton-line skeleton-title"></div>
                    <div style="margin: 1rem 0;">
                        <div class="skeleton-line" style="width: 50%; height: 14px;"></div>
                        <div class="skeleton-line" style="width: 70%; height: 14px;"></div>
                        <div class="skeleton-line" style="width: 40%; height: 14px;"></div>
                    </div>
                    <div style="margin-bottom: 1rem;">
                        <div class="skeleton-line skeleton-cuisine"></div>
                        <div class="skeleton-line skeleton-cuisine" style="width: 25%;"></div>
                    </div>
                    <div class="skeleton-line" style="height: 60px; border-radius: 12px; margin-top: auto; width: 100%;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def get_cuisine_image(cuisines: list) -> str:
    cuisines_lower = [c.lower() for c in cuisines]
    mapping = {
        "pizza": "https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=400&auto=format&fit=crop&q=60",
        "italian": "https://images.unsplash.com/photo-1534308983496-4fabb1a015ee?w=400&auto=format&fit=crop&q=60",
        "biryani": "https://images.unsplash.com/photo-1585938338392-50a59970d8ee?w=400&auto=format&fit=crop&q=60",
        "north indian": "https://images.unsplash.com/photo-1585938338392-50a59970d8ee?w=400&auto=format&fit=crop&q=60",
        "chinese": "https://images.unsplash.com/photo-1526318896980-cf78c088247c?w=400&auto=format&fit=crop&q=60",
        "asian": "https://images.unsplash.com/photo-1526318896980-cf78c088247c?w=400&auto=format&fit=crop&q=60",
        "dessert": "https://images.unsplash.com/photo-1551024601-bec78aea704b?w=400&auto=format&fit=crop&q=60",
        "bakery": "https://images.unsplash.com/photo-1551024601-bec78aea704b?w=400&auto=format&fit=crop&q=60",
        "ice cream": "https://images.unsplash.com/photo-1551024601-bec78aea704b?w=400&auto=format&fit=crop&q=60",
        "burger": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400&auto=format&fit=crop&q=60",
        "fast food": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=400&auto=format&fit=crop&q=60",
        "cafe": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&auto=format&fit=crop&q=60",
        "coffee": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?w=400&auto=format&fit=crop&q=60",
        "seafood": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=400&auto=format&fit=crop&q=60",
        "fish": "https://images.unsplash.com/photo-1519708227418-c8fd9a32b7a2?w=400&auto=format&fit=crop&q=60"
    }
    for key, url in mapping.items():
        for cuisine in cuisines_lower:
            if key in cuisine:
                return url
    return "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=400&auto=format&fit=crop&q=60"

def clean_html(html_str: str) -> str:
    return "".join(line.strip() for line in html_str.splitlines())

# Find root and cache loader
@st.cache_resource(show_spinner="Loading restaurant database (first load may take longer)...")
def load_runtime():
    root = find_repo_root()
    cfg = load_app_config(root / "config" / "app.toml")
    
    # Read settings specifically for streamlit
    st_cfg = cfg.get("streamlit", {}) or cfg.get("api", {})
    max_rows = int(st_cfg.get("ingest_max_rows", 15000))
    
    # Load dataset
    restaurants, metrics = run_ingestion(root, max_rows=max_rows)
    catalog = InMemoryCatalog(restaurants)
    
    filter_cfg = cfg.get("filter", {})
    groq_settings = load_groq_settings(root)
    
    # Pre-extract unique sorted locations for easy drop-down choice
    locations = catalog.get_all_locations()
    
    return catalog, filter_cfg, groq_settings, locations, metrics

# Main application code
try:
    catalog, filter_cfg, groq_settings, locations, metrics = load_runtime()
except Exception as e:
    st.error(f"Catalog initialization failed: {e}")
    st.stop()

# Header banner
st.markdown("""
<div style="text-align: center; margin-top: 1rem; margin-bottom: 2rem;">
    <h1 style="background: linear-gradient(135deg, #FF1E56 0%, #FFAC41 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 3.2rem; font-weight: 800; margin-bottom: 0.5rem; letter-spacing: -0.02em;">Zomato AI Discovery</h1>
    <p style="color: #5f6368 !important; font-size: 1.05rem; font-weight: 500; max-width: 600px; margin: 0 auto;">Factual, grounded restaurant matches ranked and explained using Large Language Models via Groq</p>
</div>
""", unsafe_allow_html=True)
st.divider()

# Layout filters inside a styled border wrapper card
with st.container(border=True):
    st.subheader("🎯 Search Filters")
    
    # Row 1: 3 Columns
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        selected_loc = st.selectbox(
            "Location (Neighborhood or Metro Area)",
            options=["Indiranagar", "Koramangala", "Jayanagar", "BTM", "HSR", "JP Nagar", "Whitefield", "Bannerghatta Road"] + locations,
            index=0
        )
    with row1_col2:
        budget_band = st.selectbox(
            "Budget Band",
            options=["Any", "Low", "Medium", "High"],
            index=2 # Medium default
        )
        budget_val = None if budget_band == "Any" else budget_band.lower()
    with row1_col3:
        min_rating = st.slider(
            "Minimum Rating Floor",
            min_value=0.0,
            max_value=5.0,
            value=4.0,
            step=0.1
        )
    
    # Row 2: 3 Columns
    row2_col1, row2_col2, row2_col3 = st.columns(3)
    with row2_col1:
        all_cuisines = catalog.get_all_cuisines()
        selected_cuisines = st.multiselect(
            "Preferred Cuisines",
            options=all_cuisines,
            placeholder="e.g. North Indian, Chinese"
        )
    with row2_col2:
        free_text = st.text_input(
            "Special Occasion / Atmosphere / Vibe Hints",
            placeholder="e.g. rooftop romance date night, quick lunch under 20 mins, family friendly"
        )
    with row2_col3:
        top_k = st.number_input(
            "Number of recommendations",
            min_value=1,
            max_value=25,
            value=8 # 8 fills exactly 2 rows of 4 columns
        )
    
    # Debug checkbox and submit button
    col_btn, col_chk = st.columns([4, 1])
    with col_chk:
        include_debug = st.checkbox("Show Telemetry Logs", value=False)
    with col_btn:
        btn_clicked = st.button("Explore Recommendations 🚀", use_container_width=True)

st.divider()

# Trigger execution flow
if btn_clicked:
    prefs = UserPreferences(
        location=selected_loc,
        budget_band=budget_val,
        cuisines=selected_cuisines,
        min_rating=min_rating,
        free_text=free_text if free_text.strip() else None,
        top_k=top_k
    )
    
    # Render the gorgeous skeleton loader first
    st.subheader("✨ Searching for the perfect match...")
    skeleton_placeholder = st.empty()
    with skeleton_placeholder.container():
        render_skeleton_loader()
        
    # Now run the recommendation
    outcome = run_recommendation(
        catalog=catalog,
        filter_cfg=filter_cfg,
        groq_settings=groq_settings,
        preferences=prefs,
        include_debug=include_debug
    )
    
    # Clear the skeleton loader
    skeleton_placeholder.empty()
        
    # Render Slate Summary
    if outcome.summary:
        st.subheader("💡 AI Recommendations Overview")
        st.info(outcome.summary)
        
    # Render Recommendations List
    st.subheader(f"✨ Top Matches ({len(outcome.items)})")
    
    if outcome.items:
        # Lay out results in one row of 4 columns
        grid_cols = st.columns(4)
        for idx, item in enumerate(outcome.items):
            with grid_cols[idx % 4]:
                cuisine_img = get_cuisine_image(item.cuisines)
                # Combine solid fallback obsidian gradient overlay with the cover background image!
                banner_style = f"linear-gradient(to bottom, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.85) 100%), url('{cuisine_img}')"
                
                # Custom rating SVG integration
                if item.aggregate_rating:
                    star_svg = '<svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style="color: #ffc107; margin-right: 3px; display: inline-block; vertical-align: middle;"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>'
                    rating_text = f"{star_svg} {item.aggregate_rating}"
                    rating_class = ""
                else:
                    rating_text = "Not Rated"
                    rating_class = "unrated"
                    
                cost_text = f"INR {item.cost_for_two} for two" if item.cost_for_two else "Approx. cost unknown"
                cuisines_html = "".join(f'<span class="cuisine-tag">{c}</span>' for c in item.cuisines)
                backfill_html = '<div class="backfill-badge">Fallback</div>' if item.backfilled else ''
                
                # SVG icons
                loc_icon = '<svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path><circle cx="12" cy="10" r="3"></circle></svg>'
                cost_icon = '<svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2" ry="2"></rect><line x1="12" y1="1" x2="12" y2="23"></line><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>'
                address_icon = '<svg class="meta-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path><polyline points="9 22 9 12 15 12 15 22"></polyline></svg>'
                sparkles_icon = '<svg class="ai-sparkle-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M9 21.5L7.56 16.5L2.56 15.06L7.56 13.62L9 8.62L10.44 13.62L15.44 15.06L10.44 16.5L9 21.5ZM19 12.5L18.28 10L15.78 9.28L18.28 8.56L19 6.06L19.72 8.56L22.22 9.28L19.72 10L19 12.5ZM19 6L18.46 4.12L16.58 3.58L18.46 3.04L19 1.16L19.54 3.04L21.42 3.58L19.54 4.12L19 6Z"/></svg>'
                
                address_html = f"""
                <div class="meta-item" title="{item.address}">
                    {address_icon}
                    <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%;">{item.address}</span>
                </div>
                """ if item.address else ''
                
                card_html = f"""
                <div class="restaurant-card">
                    <div class="card-banner" style="background: {banner_style};">
                        {backfill_html}
                        <h3 class="restaurant-name">{item.name}</h3>
                        <span class="rating-badge {rating_class}">{rating_text}</span>
                    </div>
                    <div class="card-content">
                        <div class="meta-row">
                            <div class="meta-item">
                                {loc_icon}
                                <strong>{item.location}</strong>
                            </div>
                            <div class="meta-item">
                                {cost_icon}
                                <span>{cost_text}</span>
                            </div>
                            {address_html}
                        </div>
                        <div class="cuisine-row">
                            {cuisines_html}
                        </div>
                        <div class="ai-box">
                            <div class="ai-title-row">
                                {sparkles_icon}
                                <span class="ai-title">AI Rationale</span>
                            </div>
                            <p class="ai-text">{item.explanation}</p>
                        </div>
                    </div>
                </div>
                """
                st.markdown(clean_html(card_html), unsafe_allow_html=True)
    else:
        st.warning("No restaurants matched your filters. Try widening your criteria (e.g. lower rating, broader location, or other budget options).")
        
    # Show debug stats if checked
    if include_debug and outcome.debug:
        st.divider()
        st.subheader("⚙️ Technical Debug Telemetry")
        st.json(outcome.debug)
else:
    # Landing page info
    st.success("Configuration loaded successfully!")
    col1, col2, col3 = st.columns(3)
    col1.metric("Catalog size", len(catalog.get_all()))
    col2.metric("Locations available", len(locations))
    col3.metric("Cuisine tags", len(all_cuisines))
    
    st.info("💡 Enter your preferences above and click **Explore Recommendations** to search.")
