from pydantic import AliasChoices, BaseModel, Field

class TransactionPayload(BaseModel):
    amount_paise :int = Field(...,description="Transaction amount in local currency paise subunits")
    device_id: str = Field(..., description="Hardware identifier fingerprint token")
    card_id: str = Field(..., description="Unique token hash identifying the plastic card entity")
    merchant_id: str = Field(...,description="Merchant category for each transaction")
