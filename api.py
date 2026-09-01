from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

# Enable CORS for Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StatusUpdate(BaseModel):
    status: str

@app.get("/leads")
def get_leads():
    # Fetch from database.py execution
    return [
        {"id": 1, "phone": "+923001234567", "name": "Kashif Ali", "intent": "BUY", "area": "DHA Phase 6", "budget_max": 250000},
        {"id": 2, "phone": "+923219876543", "name": "Usman Khan", "intent": "SELL", "area": "Gulberg", "budget_max": None}
    ]

@app.get("/properties")
def get_properties():
    # Fetch inventory from database
    return [
        {"id": 1, "title": "5 Marla Modern Villa", "price": 180000, "area": "DHA Phase 6", "bedrooms": 3, "status": "AVAILABLE"},
        {"id": 2, "title": "10 Marla Corner Plot", "price": 220000, "area": "Gulberg", "bedrooms": 0, "status": "SOLD"}
    ]

@app.patch("/properties/{property_id}/status")
def update_property_status(property_id: int, payload: StatusUpdate):
    # Execute database update / file purge lifecycle
    return {"success": True, "property_id": property_id, "new_status": payload.status}