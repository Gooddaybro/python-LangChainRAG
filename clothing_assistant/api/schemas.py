from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_query: str = ""
    assistant_answer: str = ""


class UserContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: int | str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    gender: str | None = None
    preferred_fit: str | None = None
    preferred_styles: list[str] = Field(default_factory=list)
    preferred_colors: list[str] = Field(default_factory=list)
    disliked_colors: list[str] = Field(default_factory=list)
    preferred_categories: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None


class ProductCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    spu_id: int | str
    sku_id: int | str
    name: str
    spu_code: str | None = None
    sku_code: str | None = None
    category: str | None = None
    brand: str | None = None
    color: str | None = None
    size: str | None = None
    sale_price: float | None = None
    stock_status: str | None = None
    available_stock: int | None = None
    material: str | None = None
    fit_type: str | None = None
    season: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    main_image_url: str | None = None


class ProductRef(BaseModel):
    spu_id: int | str
    sku_id: int | str
    reason: str
    rank_score: float | None = None


class SuggestedAction(BaseModel):
    type: str
    spu_id: int | str | None = None
    sku_id: int | str | None = None


class PythonChatRequest(BaseModel):
    request_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    thread_id: str | None = None
    query: str = Field(..., min_length=1)
    chat_history: list[ChatHistoryItem] = Field(default_factory=list)
    user_context: UserContext = Field(default_factory=UserContext)
    candidates: list[ProductCandidate] = Field(default_factory=list)
    debug: bool = False

    @field_validator("request_id", "session_id", "query")
    @classmethod
    def value_must_not_be_blank(cls, value):
        if not value.strip():
            raise ValueError("value must not be blank")

        return value

    def chat_history_dicts(self) -> list[dict[str, Any]]:
        return [item.model_dump(exclude_none=True, exclude_unset=True) for item in self.chat_history]

    def user_context_dict(self) -> dict[str, Any]:
        return self.user_context.model_dump(exclude_none=True, exclude_unset=True)

    def candidate_dicts(self) -> list[dict[str, Any]]:
        return [item.model_dump(exclude_none=True, exclude_unset=True) for item in self.candidates]


class PythonChatResponse(BaseModel):
    request_id: str
    answer: str
    intent: str
    product_refs: list[ProductRef] = Field(default_factory=list)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
    debug: dict[str, Any] | None = None


class LegacyChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    chat_history: list[dict[str, Any]] = Field(default_factory=list)
    thread_id: str | None = None
    debug: bool = False

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value):
        if not value.strip():
            raise ValueError("query must not be blank")

        return value
