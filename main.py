from fastapi import FastAPI
from pydantic import BaseModel
from google.cloud import firestore, storage
from datetime import datetime
import json
import os

app = FastAPI()

# Firestore & Storage clients
firestore_client = firestore.Client()
storage_client = storage.Client()

BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
RULES_FILE = os.environ.get("RULES_BLOB_NAME", "crop_rules.json")

crop_rules = {}

def load_crop_rules():
    """Load crop rules JSON from Cloud Storage on startup."""
    global crop_rules
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(RULES_FILE)
    crop_rules = json.loads(blob.download_as_text())

load_crop_rules()

class SimulationInput(BaseModel):
    crop: str
    rainfall: str  # low, medium, high
    temperature: str  # low, medium, high

@app.post("/simulate")
def simulate(input: SimulationInput):

    crop = input.crop.lower()
    rainfall = input.rainfall.lower()
    temperature = input.temperature.lower()

    base_yield = crop_rules.get(crop, {}).get("base_yield", 50)

    # Simple logic
    modifier = 0

    if rainfall == "low":
        modifier -= 15
    elif rainfall == "medium":
        modifier += 0
    elif rainfall == "high":
        modifier += 10

    if temperature == "low":
        modifier -= 5
    elif temperature == "medium":
        modifier += 10
    elif temperature == "high":
        modifier -= 10

    yield_score = max(0, min(100, base_yield + modifier))

    # Advice text
    if yield_score >= 75:
        advice = "High yield expected. Maintain current practices and monitor pests."
    elif yield_score >= 50:
        advice = "Moderate yield expected. Optimize irrigation and nutrient management."
    else:
        advice = "Low yield expected. Consider drought/heat-resistant crops."

    # Save to Firestore
    firestore_client.collection("simulations").add({
        "crop": crop,
        "rainfall": rainfall,
        "temperature": temperature,
        "yield_score": yield_score,
        "advice": advice,
        "timestamp": datetime.utcnow()
    })

    return {
        "yield_score": yield_score,
        "advice": advice
    }

@app.get("/health")
def health():
    return {"status": "ok"}
