from typing import Optional

from pydantic import BaseModel, Field


class TransactionPayload(BaseModel):
    amount_paise: int = Field(..., description="Transaction amount in subunits")
    device_id: str = Field(..., description="Hardware identifier fingerprint token")
    card_id: str = Field(..., description="Unique card entity token hash")
    merchant_id: str = Field(..., description="Merchant category code index")
    transaction_id: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Client-side correlation tracking anchor",
    )
