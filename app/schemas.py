from datetime import datetime
from pydantic import BaseModel, Field

class TransactionCreate(BaseModel):
    transaction_id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,30}$")
    customer_id: str = Field(pattern=r"^[A-Za-z0-9_-]{2,20}$")
    timestamp: datetime
    amount: float = Field(gt=0, le=10_000_000)
    merchant_category: str = "Other"
    location: str = "Unknown"
    device_id: str = "Unknown"
    transaction_type: str = "Card"
    account_age_days: int = Field(default=365, ge=0, le=50_000)
    status: str = "SUCCESS"

class ReviewCreate(BaseModel):
    outcome: str = Field(pattern=r"^(REVIEWED|FALSE_POSITIVE|ESCALATED)$")
    notes: str | None = Field(default=None, max_length=2000)
