from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime, timezone


class LocationPing(BaseModel):
    """Incoming GPS ping from a worker device."""
    worker_id: str = Field(..., example="worker_001", description="Unique worker identifier")
    worker_name: str = Field(..., example="Aminu Bello", description="Display name")
    latitude: float = Field(..., ge=-90, le=90, example=9.0579)
    longitude: float = Field(..., ge=-180, le=180, example=7.4951)
    accuracy_meters: Optional[float] = Field(None, ge=0, example=5.0)
    battery_pct: Optional[int] = Field(None, ge=0, le=100, example=82)
    status: Optional[str] = Field("active", example="active", description="active | idle | offline")
    notes: Optional[str] = Field(None, example="Arrived at site B")

    model_config = {"json_schema_extra": {
        "example": {
            "worker_id": "worker_001",
            "worker_name": "Aminu Bello",
            "latitude": 9.0579,
            "longitude": 7.4951,
            "accuracy_meters": 5.0,
            "battery_pct": 82,
            "status": "active"
        }
    }}


class WorkerLocation(BaseModel):
    """A stored location record."""
    id: int
    worker_id: str
    worker_name: str
    latitude: float
    longitude: float
    accuracy_meters: Optional[float]
    battery_pct: Optional[int]
    status: str
    notes: Optional[str]
    timestamp: str
