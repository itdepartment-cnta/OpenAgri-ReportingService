from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class EstrusResult(str, Enum):
    estrus = "estrus"
    no_estrus = "no_estrus"


class EstrusAnimal(BaseModel):
    animal_id: str = Field(min_length=1, description="Animal identifier (ear tag, name...)")
    result: EstrusResult
    confidence: Optional[float] = Field(
        None, ge=0, le=1, description="Model confidence, from 0 to 1"
    )


class EstrusUpload(BaseModel):
    upload_date: datetime
    filename: str = ""
    animals: List[EstrusAnimal] = []


class LivestockEstrusReportRequest(BaseModel):
    """Data for the livestock estrus report.

    The caller supplies the data (the service does not query any database or
    Farm Calendar), so the report can be produced from any source.
    """

    farm_name: str = Field(min_length=1)
    farm_municipality: str = ""
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    uploads: List[EstrusUpload] = []

    @model_validator(mode="after")
    def _periodo_coherente(self):
        if self.from_date and self.to_date and self.to_date < self.from_date:
            raise ValueError("to_date must not be earlier than from_date")
        return self
