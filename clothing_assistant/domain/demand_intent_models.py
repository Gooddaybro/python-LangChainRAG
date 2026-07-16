"""Strict domain contract for LLM-proposed demand intent patches."""

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ParseAction(StrEnum):
    MERGE = "MERGE"
    CLARIFY = "CLARIFY"


class EvidenceSource(StrEnum):
    CURRENT_MESSAGE = "CURRENT_MESSAGE"
    PENDING_CLARIFICATION = "PENDING_CLARIFICATION"


class TargetGender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    UNISEX = "UNISEX"


class Category(StrEnum):
    OUTERWEAR = "OUTERWEAR"
    SKIRT = "SKIRT"
    SHORTS = "SHORTS"
    SHIRT = "SHIRT"
    TOP = "TOP"
    PANTS = "PANTS"


class Scene(StrEnum):
    COMMUTE = "COMMUTE"
    DATE = "DATE"
    CAMPUS = "CAMPUS"
    DAILY = "DAILY"
    TRAVEL = "TRAVEL"
    SPORT = "SPORT"


class Style(StrEnum):
    MATURE = "MATURE"
    RUGGED = "RUGGED"
    MINIMAL = "MINIMAL"
    CASUAL = "CASUAL"


class Attribute(StrEnum):
    TALLER = "TALLER"
    SLIMMING = "SLIMMING"
    COVERING = "COVERING"
    HIGH_WAIST = "HIGH_WAIST"
    DRAPED = "DRAPED"
    STRUCTURED = "STRUCTURED"
    WARM = "WARM"
    THICK = "THICK"
    AFFORDABLE = "AFFORDABLE"


class SlotEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    source: EvidenceSource


class DemandIntentSlots(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    target_gender: TargetGender | None = Field(default=None, alias="targetGender")
    category: Category | None = None
    scene: Annotated[list[Scene], Field(min_length=1)] | None = None
    style: Annotated[list[Style], Field(min_length=1)] | None = None
    budget_max: int | None = Field(default=None, alias="budgetMax", ge=0)
    attributes: Annotated[list[Attribute], Field(min_length=1)] | None = None

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
    clarification_candidate_value: str | int | None = Field(
        default=None, alias="clarificationCandidateValue"
    )
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
            if slots or self.slot_confidence or self.evidence:
                raise ValueError("CLARIFY cannot contain merge slots")
            if len(self.clarification_question) > 200:
                raise ValueError("clarification question is too long")
            self._validate_clarification_candidate()
        elif (
            self.needs_clarification
            or self.clarification_slot is not None
            or self.clarification_candidate_value is not None
            or self.clarification_question is not None
        ):
            raise ValueError("MERGE cannot contain clarification state")
        elif not slots:
            raise ValueError("MERGE requires at least one slot")
        return self

    def _validate_clarification_candidate(self) -> None:
        slot: Literal[
            "targetGender", "category", "scene", "style", "budgetMax", "attributes"
        ] | str = self.clarification_slot or ""
        value = self.clarification_candidate_value
        if value is None:
            return
        validators = {
            "targetGender": TargetGender,
            "category": Category,
            "scene": Scene,
            "style": Style,
            "attributes": Attribute,
        }
        if slot == "budgetMax":
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError("budgetMax clarification candidate must be non-negative integer")
            return
        enum_type = validators.get(slot)
        if enum_type is None:
            raise ValueError("unsupported clarification slot")
        try:
            enum_type(value)
        except ValueError as error:
            raise ValueError("illegal clarification candidate enum") from error

    def to_api_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)
