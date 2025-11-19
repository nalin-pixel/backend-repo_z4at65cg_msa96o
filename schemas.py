"""
Database Schemas for Lost & Found

Each Pydantic model maps to a MongoDB collection. The collection name is the
lowercased class name.

Collections:
- LostItem -> "lostitem"
- Claim -> "claim"
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class LostItem(BaseModel):
    """
    Lost and found item schema
    Collection name: "lostitem"
    """
    title: str = Field(..., description="Short name of the item")
    description: Optional[str] = Field(None, description="Details about the item")
    category: str = Field(..., description="Category e.g., Electronics, Apparel, ID, Other")
    location: str = Field(..., description="Where it was lost or found")
    date: Optional[str] = Field(None, description="Date when item was lost/found (ISO string)")
    status: str = Field("lost", description="lost | found | claimed")
    image_url: Optional[str] = Field(None, description="Public URL of the item image")
    reporter_name: str = Field(..., description="Name of the person reporting")
    reporter_email: EmailStr = Field(..., description="Contact email of the reporter")

class Claim(BaseModel):
    """
    Claim submission for an item
    Collection name: "claim"
    """
    item_id: str = Field(..., description="LostItem document id being claimed")
    claimant_name: str = Field(..., description="Full name of claimant")
    claimant_email: EmailStr = Field(..., description="Email of claimant")
    message: Optional[str] = Field(None, description="Details to help verify ownership")
    status: str = Field("pending", description="pending | approved | rejected")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
