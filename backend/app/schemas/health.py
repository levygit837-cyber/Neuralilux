from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class RootResponse(BaseModel):
    message: str
    version: str
    docs: str | None = None
