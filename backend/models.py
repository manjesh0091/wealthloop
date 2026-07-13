"""Pydantic request/response schemas for the FastAPI routers."""

from typing import Optional

from pydantic import BaseModel


class AnalyzeRequest(BaseModel):
    # Either provide a known mock persona_id ("young_professional",
    # "conservative_near_retirement", "freelancer_irregular_income"), or a
    # full custom user_profile (+ optional transactions).
    persona_id: Optional[str] = None
    user_profile: Optional[dict] = None
    transactions: Optional[list[dict]] = None


class AnalyzeResponse(BaseModel):
    session_id: str


class ApproveRequest(BaseModel):
    approval_status: str  # "approved" | "rejected"
    rejection_reason: Optional[str] = None


class ApproveResponse(BaseModel):
    status: str
