from urllib.parse import quote_plus

from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings
from password_validator import PasswordValidator
from typing import Optional, Any

from os import path, environ


class Settings(BaseSettings):
    PROJECT_ROOT: str = path.dirname(path.dirname(path.realpath(__file__)))

    # PARCHE CNTA: solo obligatorias con REPORTING_USING_GATEKEEPER (ver el
    # validador al final). Sin GateKeeper el servicio no las necesita.
    REPORTING_GATEKEEPER_USERNAME: str = ""
    REPORTING_GATEKEEPER_PASSWORD: str = ""
    REPORTING_BACKEND_CORS_ORIGINS: Any

    REPORTING_POSTGRES_USER: str
    REPORTING_POSTGRES_PASSWORD: str
    REPORTING_POSTGRES_DB: str
    REPORTING_POSTGRES_HOST: str
    REPORTING_POSTGRES_PORT: int
    REPORTING_SERVICE_NAME: str
    REPORTING_SERVICE_PORT: int
    REPORTING_USING_GATEKEEPER: bool = True
    REPORTING_GATEKEEPER_BASE_URL: str = ""
    REPORTING_FARMCALENDAR_BASE_URL: str = "api/proxy/farmcalendar/api/v1"
    REPORTING_FARMCALENDAR_URLS: dict = {
        "irrigations": "/IrrigationOperations/",
        "fertilization": "/FertilizationOperations/",
        "pesticides": "/CropProtectionOperations/",
        "pest": "/Pesticides/",
        "activity_types": "/FarmCalendarActivityTypes/",
        "observations": "/Observations/",
        "operations": "/CompostOperations/",
        "turning_operations": "/CompostTurningOperations/",
        "activities": "/FarmCalendarActivities/",
        "crops": "/FarmCrops/",
        "parcel": "/FarmParcels/",
        "animals": "/FarmAnimals/",
        "materials": "/AddRawMaterialOperations/",
        "machines": "/AgriculturalMachines/",
        "farm": "/Farm/"
    }

    REPORTING_FORECASTING_BASE_URL: str = ""
    REPORTING_FORECASTING_URLS: dict = {
        "pest_risk": "/PestRisk/",
    }

    PDF_DIRECTORY: str = "user_reports/"
    # PARCHE CNTA: borrado de los PDF generados. 0 = no se borra nada (upstream).
    REPORTING_PDF_RETENTION_HOURS: float = 0
    REPORTING_PDF_CLEANUP_INTERVAL_MINUTES: float = 30
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    def assemble_db_connection(cls, v: Optional[str], values) -> Any:
        if isinstance(v, str):
            return v

        # PARCHE CNTA: usuario y contrasena codificados. Una contrasena con '/',
        # '@' o ':' rompia la URL de conexion.
        url = "postgresql://{}:{}@{}:{}/{}".format(
            quote_plus(environ.get("REPORTING_POSTGRES_USER", "")),
            quote_plus(environ.get("REPORTING_POSTGRES_PASSWORD", "")),
            environ.get("REPORTING_POSTGRES_HOST"),
            environ.get("REPORTING_POSTGRES_PORT", 5439),
            environ.get("REPORTING_POSTGRES_DB"),
        )

        return url

    PASSWORD_SCHEMA_OBJ: PasswordValidator = PasswordValidator()
    PASSWORD_SCHEMA_OBJ.min(8).max(
        100
    ).has().uppercase().has().lowercase().has().digits().has().no().spaces()
    JWT_ACCESS_TOKEN_EXPIRATION_TIME: int
    JWT_SIGNING_KEY: str

    @model_validator(mode="after")
    def gatekeeper_requerido_si_se_usa(self):
        if self.REPORTING_USING_GATEKEEPER and not (
            self.REPORTING_GATEKEEPER_BASE_URL
            and self.REPORTING_GATEKEEPER_USERNAME
            and self.REPORTING_GATEKEEPER_PASSWORD
        ):
            raise ValueError(
                "REPORTING_USING_GATEKEEPER esta activo: hacen falta "
                "REPORTING_GATEKEEPER_BASE_URL, _USERNAME y _PASSWORD."
            )
        return self


settings = Settings()
