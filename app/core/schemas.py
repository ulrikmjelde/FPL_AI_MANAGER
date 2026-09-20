from typing import Literal
from pydantic import BaseModel, Field


class CreatorTransfer(BaseModel):
    player_out: str | None = None
    player_in: str | None = None


class CreatorDecision(BaseModel):
    classification: Literal['COMMENTARY', 'IDEA', 'LEANING', 'LIKELY', 'CONFIRMED']
    source_confidence: float = Field(ge=0, le=1)
    ai_confidence: float = Field(ge=0, le=1)
    transfers: list[CreatorTransfer] = []
    intent: str = ''
    horizon: str = ''
    captaincy_relevance: bool = False
    notes: list[str] = []


class PlannedTransfer(BaseModel):
    element_out: int
    element_in: int
    rationale: str


class TransferPlan(BaseModel):
    action: Literal['NO_ACTION', 'TRANSFER']
    confidence: float = Field(ge=0, le=1)
    mirrors_creator: bool = False
    intent_preserved: bool = False
    transfers: list[PlannedTransfer] = []
    rationale: str = ''
