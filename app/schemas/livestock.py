from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class _FarmReportRequest(BaseModel):
    """Datos comunes de los informes de ganaderia.

    The caller supplies the data (the service does not query any database or
    Farm Calendar), so the reports can be produced from any source. The period
    is informative: it is printed in the header, the caller filters the data.
    """

    farm_name: str = Field(min_length=1)
    farm_municipality: str = ""
    from_date: Optional[date] = None
    to_date: Optional[date] = None

    @model_validator(mode="after")
    def _periodo_coherente(self):
        if self.from_date and self.to_date and self.to_date < self.from_date:
            raise ValueError("to_date must not be earlier than from_date")
        return self


# ── Estrus ───────────────────────────────────────────────────────────


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


class LivestockEstrusReportRequest(_FarmReportRequest):
    """Data for the livestock estrus report."""

    uploads: List[EstrusUpload] = []


# ── Milk quality (SCC) ───────────────────────────────────────────────


class SccClass(str, Enum):
    low = "low"      # normal somatic cell count
    high = "high"    # high somatic cell count


class MilkSample(BaseModel):
    sample_id: str = Field(min_length=1, description="Sample identifier")
    result: SccClass


class MilkQualityUpload(BaseModel):
    upload_date: datetime
    filename: str = ""
    samples: List[MilkSample] = []


class MilkQualityReportRequest(_FarmReportRequest):
    """Data for the milk quality (somatic cell count) report.

    Each sample is classified as `low` or `high` by the model; no numeric
    count is involved.
    """

    uploads: List[MilkQualityUpload] = []
