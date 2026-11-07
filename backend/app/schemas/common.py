"""
Common schema models and standard response envelope.
"""
from typing import Generic, TypeVar, Optional, List, Any
import uuid
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class APIError(BaseModel):
    code: str
    message: str
    details: List[APIErrorDetail] = Field(default_factory=list)


class APIResponse(BaseModel, Generic[DataT]):
    success: bool
    data: Optional[DataT] = None
    error: Optional[APIError] = None
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    @classmethod
    def ok(cls, data: DataT, request_id: Optional[str] = None) -> "APIResponse[DataT]":
        return cls(
            success=True,
            data=data,
            error=None,
            request_id=request_id or str(uuid.uuid4()),
        )
