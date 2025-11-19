import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
from datetime import datetime, timezone

from database import db, create_document, get_documents
from schemas import LostItem, Claim

app = FastAPI(title="Lost & Found API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def serialize_doc(doc: dict):
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # Convert datetimes to isoformat strings
    for k, v in list(doc.items()):
        if hasattr(v, "isoformat"):
            try:
                doc[k] = v.isoformat()
            except Exception:
                pass
    return doc


@app.get("/")
def read_root():
    return {"message": "Lost & Found API is running"}


@app.get("/api/items")
def list_items(status: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    filt = {}
    if status:
        filt["status"] = status
    if q:
        filt["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"location": {"$regex": q, "$options": "i"}},
            {"category": {"$regex": q, "$options": "i"}},
        ]
    docs = db["lostitem"].find(filt).sort("created_at", -1).limit(limit)
    return [serialize_doc(d) for d in docs]


@app.post("/api/items", status_code=201)
def create_item(item: LostItem):
    inserted_id = create_document("lostitem", item)
    doc = db["lostitem"].find_one({"_id": ObjectId(inserted_id)})
    return serialize_doc(doc)


@app.get("/api/items/{item_id}")
def get_item(item_id: str):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="Invalid id")
    doc = db["lostitem"].find_one({"_id": ObjectId(item_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Item not found")
    return serialize_doc(doc)


class ClaimCreate(BaseModel):
    claimant_name: str
    claimant_email: EmailStr
    message: Optional[str] = None


@app.post("/api/items/{item_id}/claims", status_code=201)
def create_claim(item_id: str, payload: ClaimCreate):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="Invalid item id")
    item = db["lostitem"].find_one({"_id": ObjectId(item_id)})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    data = {
        "item_id": item_id,
        "claimant_name": payload.claimant_name,
        "claimant_email": payload.claimant_email,
        "message": payload.message,
        "status": "pending",
    }
    inserted_id = create_document("claim", data)
    claim = db["claim"].find_one({"_id": ObjectId(inserted_id)})
    return serialize_doc(claim)


@app.get("/api/items/{item_id}/claims")
def list_claims_for_item(item_id: str):
    if not ObjectId.is_valid(item_id):
        raise HTTPException(status_code=400, detail="Invalid item id")
    docs = db["claim"].find({"item_id": item_id}).sort("created_at", -1)
    return [serialize_doc(d) for d in docs]


class ClaimUpdate(BaseModel):
    status: str = Field(..., pattern="^(pending|approved|rejected)$")


@app.patch("/api/claims/{claim_id}")
def update_claim_status(claim_id: str, body: ClaimUpdate):
    if not ObjectId.is_valid(claim_id):
        raise HTTPException(status_code=400, detail="Invalid claim id")
    result = db["claim"].update_one(
        {"_id": ObjectId(claim_id)},
        {"$set": {"status": body.status, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = db["claim"].find_one({"_id": ObjectId(claim_id)})

    # If approved, mark item as claimed
    if claim and claim.get("status") == "approved":
        db["lostitem"].update_one(
            {"_id": ObjectId(claim.get("item_id")) if ObjectId.is_valid(claim.get("item_id", "")) else {"_id": None}},
            {"$set": {"status": "claimed", "updated_at": datetime.now(timezone.utc)}},
        )

    return serialize_doc(claim)


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
