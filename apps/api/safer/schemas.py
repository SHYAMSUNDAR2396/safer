import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Text120 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Text200 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Message = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
AMOUNT = r"^(0|[1-9][0-9]{0,15})(\.[0-9]{1,2})?$"
Field_ = Literal["bank_name", "bank_reference", "principal_amount", "issue_date", "maturity_date"]


def plain_text(value: str, newlines=False) -> str:
    if re.search(r"[\x00-\x09\x0b-\x1f\x7f]" if newlines else r"[\x00-\x1f\x7f]", value):
        raise ValueError("Control characters are not permitted")
    return value


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    obligation_id: UUID
    bank_name: Text120
    bank_reference: Text100
    principal_amount: Annotated[str, Field(strict=True, pattern=AMOUNT)]
    currency: Literal["INR"] = "INR"
    issue_date: date
    maturity_date: date

    @field_validator("bank_name", "bank_reference")
    @classmethod
    def no_control_characters(cls, value):
        if re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError("Control characters are not permitted")
        return value

    @model_validator(mode="after")
    def valid_values(self):
        if Decimal(self.principal_amount) <= 0:
            raise ValueError("Principal amount must be greater than zero")
        if self.maturity_date <= self.issue_date:
            raise ValueError("Maturity date must be after the issue date")
        return self


class EmptyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstrumentView(BaseModel):
    id: UUID
    institution_id: UUID
    obligation_id: UUID
    bank_name: str
    bank_reference: str
    principal_amount: str
    currency: Literal["INR"]
    issue_date: date
    maturity_date: date
    status: Literal["draft", "submitted"]
    verification_status: Literal["unverified"] = "unverified"
    row_version: int
    created_at: datetime


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Field_
    value: Text120
    source: Text200
    method: Literal["bank_portal", "bank_email", "bank_letter", "phone_callback"]
    observed_at: AwareDatetime
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""

    @field_validator("value", "source")
    @classmethod
    def single_line(cls, value):
        return plain_text(value)

    @field_validator("note")
    @classmethod
    def multi_line(cls, value):
        return plain_text(value, newlines=True)

    @model_validator(mode="after")
    def typed_value(self):
        if self.observed_at > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Observation time cannot be in the future")
        if self.field == "principal_amount":
            if not re.fullmatch(AMOUNT, self.value) or Decimal(self.value) <= 0:
                raise ValueError("Amount must be a positive rupee value with up to 2 decimals")
            self.value = f"{Decimal(self.value):.2f}"
        elif self.field.endswith("_date"):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", self.value):
                raise ValueError("Dates must be YYYY-MM-DD")
            self.value = date.fromisoformat(self.value).isoformat()
        return self


class DiscrepancyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: Field_ | None = None
    message: Message

    @field_validator("message")
    @classmethod
    def text(cls, value):
        return plain_text(value, newlines=True)


class ReplyInput(DiscrepancyInput):
    field: None = None
    resolve: Annotated[bool, Field(strict=True)] = False
