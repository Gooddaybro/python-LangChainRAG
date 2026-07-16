"""Strict domain contract for LLM-proposed demand intent patches."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParseAction(StrEnum):
    MERGE = "MERGE"
    CLARIFY = "CLARIFY"


class EvidenceSource(StrEnum):
    CURRENT_MESSAGE = "CURRENT_MESSAGE"
    PENDING_CLARIFICATION = "PENDING_CLARIFICATION"


class SlotEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    source: EvidenceSource


class DemandIntentSlots(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target_gender: str | None = Field(default=None, alias="targetGender")
    category: str | None = None
    scene: list[str] | None = None
    style: list[str] | None = None
    budget_max: int | None = Field(default=None, alias="budgetMax", ge=0)
    attributes: list[str] | None = None

    def present_aliases(self) -> set[str]:
        return {
            field.alias or name
            for name, field in type(self).model_fields.items()
            if getattr(self, name) is not None
        }


class DemandIntentParseCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion", pattern=r"^1\.0$")
    action: ParseAction
    slots: DemandIntentSlots
    slot_confidence: dict[str, float] = Field(alias="slotConfidence")
    evidence: dict[str, list[SlotEvidence]]
    needs_clarification: bool = Field(alias="needsClarification")
    clarification_slot: str | None = Field(default=None, alias="clarificationSlot")
    clarification_question: str | None = Field(default=None, alias="clarificationQuestion")

    @model_validator(mode="after")
    def validate_sparse_metadata(self):
        slots = self.slots.present_aliases()
        if set(self.slot_confidence) != slots or set(self.evidence) != slots:
            raise ValueError("confidence and evidence must exactly match present slots")
        if any(not 0 <= value <= 1 for value in self.slot_confidence.values()):
            raise ValueError("slot confidence must be between zero and one")
        if any(not items for items in self.evidence.values()):
            raise ValueError("each slot must contain evidence")

        if self.action is ParseAction.CLARIFY:
            if not self.needs_clarification:
                raise ValueError("CLARIFY requires needsClarification")
            if not self.clarification_slot or not self.clarification_question:
                raise ValueError("CLARIFY requires one slot and one question")
            if self.clarification_slot not in slots:
                raise ValueError("clarification slot must be present in slots")
        elif (
            self.needs_clarification
            or self.clarification_slot is not None
            or self.clarification_question is not None
        ):
            raise ValueError("MERGE cannot contain clarification state")
        return self

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)
