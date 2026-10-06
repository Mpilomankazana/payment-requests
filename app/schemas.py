from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CreateRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    requesterName: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=12)
    description: str = Field(min_length=1, max_length=500)


class RejectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    reason: str = Field(min_length=1, max_length=500)
