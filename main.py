from fastapi import FastAPI
from pydantic import BaseModel
from google.cloud import firestore, storage
from datetime import datetime
import json
import os

app = FastAPI()

# Initialize Firestore & Storage clients
firestore_client = firestore.Client()
storage_client = storage.Client()

BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
RULES_BLOB_NAME = os.environ.get("RULES_BLOB_NAME", "crop_rules.json")

# Load rules from Cloud Storage at startup
crop_rules = {}

def load_rules():
    global crop_rules
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(RULES_BLOB_NAME)
    data = blob.download_as_text()
    crop_rules = json.loads(data)

load_rules()


class SimulationInput(BaseModel):
    crop: str
    rainfall: str  # "low", "medium", "high"
    temperature: str  # "low", "medium", "high"


@app.post("/simulate")
def simulate(input: SimulationInput):
    crop = input.crop.lower()
    rainfall = input.rainfall.lower()
    temperature = input.temperature.lower()

    base_yield = crop_rules.get(crop, {}).get("base_yield", 50)

    # Very simple dummy logic
    modifier = 0

    # Rainfall effect
    if rainfall == "low":
        modifier -= 15
    elif rainfall == "medium":
        modifier += 0
    elif rainfall == "high":
        modifier += 10

    # Temperature effect
    if temperature == "low":
        modifier -= 5
    elif temperature == "medium":
        modifier += 10
    elif temperature == "high":
        modifier -= 10

    yield_score = max(0, min(100, base_yield + modifier))

    # Generate simple advice
    if yield_score >= 75:
        advice = "High yield expected. Maintain current practices and monitor pests."
    elif yield_score >= 50:
        advice = "Moderate yield expected. Consider optimizing irrigation and fertilization."
    else:
        advice = "Low yield expected. Explore drought/heat-resistant varieties and adjust planting schedule."

    # Save to Firestore
    doc_ref = firestore_client.collection("simulations").document()
    doc_ref.set({
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
