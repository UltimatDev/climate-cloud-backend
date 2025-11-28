from fastapi import FastAPI
from pydantic import BaseModel
from google.cloud import firestore, storage
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import requests

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.options("/{path:path}")
def preflight_handler(path: str):
    return {}

# ------------ Google Cloud Clients ------------
firestore_client = firestore.Client()
storage_client = storage.Client()

BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
RULES_FILE = os.environ.get("RULES_BLOB_NAME", "crop_rules.json")
CLIMATE_FILE = "climate_data.json"
# ----------------------------------------------


# ------------ Load Crop Rules ------------
crop_rules = {}
def load_crop_rules():
    global crop_rules
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(RULES_FILE)
    crop_rules = json.loads(blob.download_as_text())

load_crop_rules()
# --------------------------------------------------------


def load_climate():
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(CLIMATE_FILE)
    return json.loads(blob.download_as_text())

climate_data = load_climate()


class SimulationInput(BaseModel):
    crop: str  # ONLY crop now

@app.post("/simulate")
def simulate(input: SimulationInput):

    crop = input.crop.lower()

    # ---------------- REAL CLIMATE DATA ----------------
    rainfall = climate_data["avg_rainfall"]                  # mm
    temperature = climate_data["avg_temperature_celsius"]    # °C
    ndvi = climate_data["avg_ndvi"]                          # 0–1
    # ----------------------------------------------------

    base_yield = crop_rules.get(crop, {}).get("base_yield", 50)

    # -------- Yield Logic Using REAL Climate --------
    modifier = 0

    # Use real rainfall
    if rainfall < 50:
        modifier -= 20
    elif rainfall < 100:
        modifier += 5
    else:
        modifier += 10

    # Use real temperature
    if temperature < 20:
        modifier -= 10
    elif temperature < 30:
        modifier += 10
    else:
        modifier -= 5

    # NDVI contribution (scaled)
    modifier += ndvi * 20
    # ------------------------------------------------
    
    #yield_score = max(0, min(100, base_yield + modifier))
    yield_score = get_ml_prediction(rainfall, temperature, ndvi)

    # Advice
    if yield_score >= 75:
        advice = "High yield expected. Climate conditions are favorable."
    elif yield_score >= 50:
        advice = "Moderate yield expected. Monitor field conditions closely."
    else:
        advice = "Low yield expected. Environmental stress detected."

    # SAVE TO FIRESTORE
    firestore_client.collection("experimentations").add({
        "crop": crop,
        "yield_score": yield_score,
        "rainfall": rainfall,
        "temperature": temperature,
        "ndvi": ndvi,
        "advice": advice,
        "timestamp": datetime.utcnow()
    })

    return {
        "yield_score": yield_score,
        "advice": advice,
        "climate_used": {
            "rainfall": rainfall,
            "temperature": temperature,
            "ndvi": ndvi
        }
    }
import requests

ML_URL = "https://climate-ml-service-309428167154.asia-south2.run.app/predict"

def get_ml_prediction(rainfall, temperature, ndvi):
    body = {
        "rainfall_mm": rainfall,
        "temperature_c": temperature,
        "ndvi": ndvi
    }
    res = requests.post(ML_URL, json=body)
    return res.json()["predicted_yield"]


@app.get("/health")
def health():
    return {"status": "ok"}
