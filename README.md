# Zomato RecSys: AI-Assisted Restaurant Discovery

An AI-assisted restaurant discovery and recommendation system that combines structured Zomato restaurant data with large language models (LLMs) via the Groq API. It enforces hard constraints (location, budget, cuisine, and rating floors) deterministically and ranks/explains the top matches using Llama-3 models.

## Setup Instructions

### 1. Prerequisites
- Python 3.11+
- A Groq API Key

### 2. Installation
Clone the repository, navigate to this folder, and set up the virtual environment:
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On macOS/Linux
source .venv/bin/activate

# Install dependencies and the local package in editable mode
pip install -r requirements.txt
```

### 3. Environment Variables
Copy `.env.example` to `.env` and add your Groq API Key:
```bash
cp .env.example .env
```
Inside `.env`:
```text
GROQ_API_KEY=your-gsk-key
```

### 4. Running the Application
The project supports multiple presentation layers:

#### A. Streamlit Production UI (Recommended)
```bash
streamlit run streamlit_app.py
```

#### B. FastAPI Web Service
```bash
# Starts the server at http://localhost:8000
python -m zomato_recsys.api.server
```

#### C. Command Line Interface (CLI)
You can interact with the system via the `zomato-recsys` CLI:
```bash
# Check version/health
zomato-recsys status

# Force ingestion/downloading of the dataset
zomato-recsys ingest --max-rows 1000

# Perform deterministic filtering
zomato-recsys filter --location "Indiranagar" --budget medium --min-rating 4.0
```

## Running Tests
To run all tests (excluding live network integration tests):
```bash
pytest tests/
```
To run the full suite including Hugging Face integration:
```bash
ZOMATO_RUN_HF_INTEGRATION=1 pytest tests/
```
