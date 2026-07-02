"""服装助手 API 的 HTTP 契约模型。

这些 Pydantic 模型定义了 Java `assistant-service` 和 Python LangGraph 工作流之间的边界。
字段描述是契约的一部分，因为 FastAPI 会通过 OpenAPI 暴露它们，
并且 Java 开发者在构建 DTO 时会使用这些描述。
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatHistoryItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_query: str = Field(default="", description="单次对话中用户的提问。")
    assistant_answer: str = Field(default="", description="与用户提问配对的助手回答。")


class UserContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    user_id: int | str | None = Field(default=None, description="当会话登录时，Java 层传入的用户 ID。")
    height_cm: float | None = Field(default=None, description="用户身高（厘米）。")
    weight_kg: float | None = Field(default=None, description="用户体重（公斤）。")
    gender: str | None = Field(default=None, description="Java 层提供的用户性别标签。")
    preferred_fit: str | None = Field(default=None, description="偏好的服装版型，如宽松(loose)或修身(slim)。")
    preferred_styles: list[str] = Field(default_factory=list, description="用户偏好的风格标签。")
    preferred_colors: list[str] = Field(default_factory=list, description="用户偏好的颜色。")
    disliked_colors: list[str] = Field(default_factory=list, description="用户希望避免的颜色。")
    preferred_categories: list[str] = Field(default_factory=list, description="用户偏好的商品分类。")
    budget_min: float | None = Field(default=None, description="预算下限（人民币）。")
    budget_max: float | None = Field(default=None, description="预算上限（人民币）。")


class ProductCandidate(BaseModel):
    model_config = ConfigDict(extra="allow")

    spu_id: int | str = Field(..., description="候选商品的 Java SPU ID。")
    sku_id: int | str = Field(..., description="可售卖候选商品的 Java SKU ID。")
    name: str = Field(..., description="候选商品的展示名称。")
    spu_code: str | None = Field(default=None, description="可选的 Java SPU 编码。")
    sku_code: str | None = Field(default=None, description="可选的 Java SKU 编码。")
    category: str | None = Field(default=None, description="候选商品分类。")
    brand: str | None = Field(default=None, description="候选商品品牌。")
    color: str | None = Field(default=None, description="候选 SKU 颜色。")
    size: str | None = Field(default=None, description="候选 SKU 尺码。")
    sale_price: float | None = Field(default=None, description="用于展示参考的当前 Java 售价。")
    stock_status: str | None = Field(default=None, description="Java 层提供的库存状态，如 in_stock 或 low_stock。")
    available_stock: int | None = Field(default=None, description="Java 层提供的可用库存数量。")
    material: str | None = Field(default=None, description="候选商品材质。")
    fit_type: str | None = Field(default=None, description="候选商品版型，如 regular 或 slim。")
    season: list[str] = Field(default_factory=list, description="候选商品的季节标签。")
    style_tags: list[str] = Field(default_factory=list, description="用于推荐推理的风格标签。")
    attribute_tags: list[str] = Field(default_factory=list, description="Java 商品属性标签，如 厚度:常规 或 适用场景:通勤。")
    main_image_url: str | None = Field(default=None, description="用于 Java 或前端展示的主图 URL。")


class ProductRef(BaseModel):
    spu_id: int | str = Field(..., description="助手回复中所引用的 Java SPU ID。")
    sku_id: int | str = Field(..., description="助手回复中所引用的 Java SKU ID。")
    reason: str = Field(..., description="对用户可见的该商品推荐理由。")
    rank_score: float | None = Field(default=None, description="来自 Python 工作流的可选排名得分。")


class DemandIntent(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: str | None = Field(default=None, description="Java DemandIntent 契约版本。")
    source: str | None = Field(default=None, description="意图解析来源，如 java-rule。")
    rawQuery: str | None = Field(default=None, description="Java 解析时使用的原始用户问题。")
    targetGender: str | None = Field(default=None, description="目标穿着性别，male 或 female。")
    category: str | None = Field(default=None, description="Java 归一化后的硬筛选类目。")
    scene: list[str] = Field(default_factory=list, description="场景偏好，如 commute。")
    style: list[str] = Field(default_factory=list, description="风格偏好，如 minimal。")
    budgetMax: float | None = Field(default=None, description="Java 解析出的预算上限。")
    attributes: list[str] = Field(default_factory=list, description="显高、显瘦等属性偏好。")
    hardFilters: list[str] = Field(default_factory=list, description="Java 已用于硬过滤的字段名。")
    softPreferences: list[str] = Field(default_factory=list, description="Python 可用于排序解释的字段名。")
    confidence: float | None = Field(default=None, description="Java 解析置信度。")
    missingSlots: list[str] = Field(default_factory=list, description="仍缺失的关键槽位。")


class SuggestedAction(BaseModel):
    type: str = Field(..., description="建议 Java 或前端执行的动作类型。")
    spu_id: int | str | None = Field(default=None, description="针对特定商品动作的可选 SPU ID。")
    sku_id: int | str | None = Field(default=None, description="针对特定商品动作的可选 SKU ID。")


class PythonChatRequest(BaseModel):
    request_id: str = Field(..., min_length=1, description="Java 生成的请求 ID，将在响应中原样返回。")
    session_id: str = Field(..., min_length=1, description="Java 会话 ID。")
    thread_id: str | None = Field(default=None, description="可选的 LangGraph 线程 ID；默认与 session_id 相同。")
    query: str = Field(..., min_length=1, description="当前需要回答的用户消息。")
    chat_history: list[ChatHistoryItem] = Field(default_factory=list, description="来自 Java 的只读对话历史。")
    user_context: UserContext = Field(default_factory=UserContext, description="来自 Java 的只读用户画像上下文。")
    candidates: list[ProductCandidate] = Field(default_factory=list, description="Java 为此轮对话过滤出的 SKU 候选列表。")
    demand_intent: DemandIntent | None = Field(default=None, description="Java 统一解析出的需求意图。")
    debug: bool = Field(default=False, description="是否包含内部 LangGraph 调试数据。")

    @field_validator("request_id", "session_id", "query")
    @classmethod
    def value_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("字段值不能为空")

        return value

    def chat_history_dicts(self) -> list[dict[str, Any]]:
        return [item.model_dump(exclude_none=True, exclude_unset=True) for item in self.chat_history]

    def user_context_dict(self) -> dict[str, Any]:
        return self.user_context.model_dump(exclude_none=True, exclude_unset=True)

    def candidate_dicts(self) -> list[dict[str, Any]]:
        return [item.model_dump(exclude_none=True, exclude_unset=True) for item in self.candidates]

    def demand_intent_dict(self) -> dict[str, Any] | None:
        if self.demand_intent is None:
            return None

        return self.demand_intent.model_dump(exclude_none=True, exclude_unset=True)


class PythonChatResponse(BaseModel):
    request_id: str = Field(..., description="从 Java 请求中原样返回的请求 ID。")
    answer: str = Field(..., description="对用户可见的助手回答。")
    intent: str = Field(..., description="Python 工作流检测到的用户意图。")
    product_refs: list[ProductRef] = Field(default_factory=list, description="Python 选择的商品引用列表。")
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, description="建议 Java/前端执行的动作列表。")
    debug: dict[str, Any] | None = Field(default=None, description="仅在请求要求时才包含的内部调试负载。")


class LegacyChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="用于本地旧版端点的当前用户消息。")
    chat_history: list[dict[str, Any]] = Field(default_factory=list, description="本地旧版对话历史记录。")
    thread_id: str | None = Field(default=None, description="用于本地调试的可选 LangGraph 线程 ID。")
    debug: bool = Field(default=False, description="是否在旧版响应中包含调试负载。")

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("查询字符串不能为空")

        return value


class FeedbackRequest(BaseModel):
    """从 Java 层接收用户点赞/踩反馈的数据模型。"""
    userId: str = Field(..., description="Java 用户 ID。")
    sessionId: str = Field(..., description="聊天会话 ID。")
    messageId: str = Field(..., description="正在被评价的消息 ID。")
    feedbackType: str = Field(..., description="反馈类型：'LIKE' (点赞) 或 'DISLIKE' (踩)。")
    timestamp: str = Field(..., description="来自 Java 的 ISO-8601 标准时间戳。")
