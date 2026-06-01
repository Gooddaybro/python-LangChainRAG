"""HTTP contract models for the clothing assistant API.

These Pydantic models define the boundary between Java `assistant-service` and
the Python LangGraph workflow. Field descriptions are part of the contract
because FastAPI exposes them through OpenAPI and Java developers use them when
building DTOs.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_query: str = Field(default="", description="Previous user message in one dialogue turn.")
    assistant_answer: str = Field(default="", description="Assistant answer paired with the user query.")


class UserContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: int | str | None = Field(default=None, description="Java user id when the session is signed in.")
    height_cm: float | None = Field(default=None, description="User height in centimeters.")
    weight_kg: float | None = Field(default=None, description="User weight in kilograms.")
    gender: str | None = Field(default=None, description="User gender label supplied by Java.")
    preferred_fit: str | None = Field(default=None, description="Preferred clothing fit such as loose or slim.")
    preferred_styles: list[str] = Field(default_factory=list, description="Style tags preferred by the user.")
    preferred_colors: list[str] = Field(default_factory=list, description="Colors preferred by the user.")
    disliked_colors: list[str] = Field(default_factory=list, description="Colors the user wants to avoid.")
    preferred_categories: list[str] = Field(default_factory=list, description="Product categories preferred by the user.")
    budget_min: float | None = Field(default=None, description="Lower budget bound in CNY.")
    budget_max: float | None = Field(default=None, description="Upper budget bound in CNY.")


class ProductCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    spu_id: int | str = Field(..., description="Java SPU id for the product candidate.")
    sku_id: int | str = Field(..., description="Java SKU id for the sellable candidate.")
    name: str = Field(..., description="Display name of the candidate product.")
    spu_code: str | None = Field(default=None, description="Optional Java SPU code.")
    sku_code: str | None = Field(default=None, description="Optional Java SKU code.")
    category: str | None = Field(default=None, description="Candidate product category.")
    brand: str | None = Field(default=None, description="Candidate product brand.")
    color: str | None = Field(default=None, description="Candidate SKU color.")
    size: str | None = Field(default=None, description="Candidate SKU size.")
    sale_price: float | None = Field(default=None, description="Current Java sale price for display guidance.")
    stock_status: str | None = Field(default=None, description="Java stock status such as in_stock or low_stock.")
    available_stock: int | None = Field(default=None, description="Available stock count supplied by Java.")
    material: str | None = Field(default=None, description="Candidate product material.")
    fit_type: str | None = Field(default=None, description="Candidate fit type such as regular or slim.")
    season: list[str] = Field(default_factory=list, description="Season tags for the candidate.")
    style_tags: list[str] = Field(default_factory=list, description="Style tags for recommendation reasoning.")
    main_image_url: str | None = Field(default=None, description="Main image URL for Java or frontend display.")


class ProductRef(BaseModel):
    spu_id: int | str = Field(..., description="Java SPU id referenced by the assistant response.")
    sku_id: int | str = Field(..., description="Java SKU id referenced by the assistant response.")
    reason: str = Field(..., description="User-visible recommendation reason for this product.")
    rank_score: float | None = Field(default=None, description="Optional ranking score from the Python workflow.")


class SuggestedAction(BaseModel):
    type: str = Field(..., description="Action type suggested to Java or the frontend.")
    spu_id: int | str | None = Field(default=None, description="Optional SPU id for product-specific actions.")
    sku_id: int | str | None = Field(default=None, description="Optional SKU id for product-specific actions.")


class PythonChatRequest(BaseModel):
    request_id: str = Field(..., min_length=1, description="Java-generated request id echoed in the response.")
    session_id: str = Field(..., min_length=1, description="Java conversation session id.")
    thread_id: str | None = Field(default=None, description="Optional LangGraph thread id; defaults to session_id.")
    query: str = Field(..., min_length=1, description="Current user message to answer.")
    chat_history: list[ChatHistoryItem] = Field(default_factory=list, description="Read-only dialogue history from Java.")
    user_context: UserContext = Field(default_factory=UserContext, description="Read-only user profile context from Java.")
    candidates: list[ProductCandidate] = Field(default_factory=list, description="Java-filtered SKU candidates for this turn.")
    debug: bool = Field(default=False, description="Whether to include internal LangGraph debug data.")

    @field_validator("request_id", "session_id", "query")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
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
    request_id: str = Field(..., description="Request id echoed from the Java request.")
    answer: str = Field(..., description="User-visible assistant answer.")
    intent: str = Field(..., description="Intent detected by the Python workflow.")
    product_refs: list[ProductRef] = Field(default_factory=list, description="Product references selected by Python.")
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, description="Suggested Java/frontend actions.")
    debug: dict[str, Any] | None = Field(default=None, description="Internal debug payload included only on demand.")


class LegacyChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Current user message for local legacy endpoints.")
    chat_history: list[dict[str, Any]] = Field(default_factory=list, description="Legacy local dialogue history.")
    thread_id: str | None = Field(default=None, description="Optional LangGraph thread id for local debugging.")
    debug: bool = Field(default=False, description="Whether to include debug payload in legacy responses.")

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")

        return value
