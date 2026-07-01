# 用户反馈闭环设计

## 1. 背景

当前项目已经具备智能穿搭电商的主链路：

- Java 后端负责用户、商品、库存、购物车、订单、支付、收藏、会话和 AI 接口编排。
- Python AI 服务负责 LangGraph Agent、RAG、推荐回答和工具调用。
- 前端已经支持商品浏览、AI 导购、推荐卡片、购物车和订单支付流程。
- Redis 第一版已经用于商品详情、推荐候选、用户画像缓存和 AI 接口限流。

现在缺少的是“用户反馈闭环”。也就是系统还没有系统性记录用户对推荐结果和商品的真实行为，AI 推荐仍主要依赖用户主动填写的画像、当前问题和商品候选池。

用户反馈闭环的目标不是堆新技术，而是让项目主线变成：

```text
用户画像
-> AI 导购推荐
-> 用户曝光、点击、收藏、加购、下单、支付
-> 行为事件沉淀
-> Java 汇总用户近期偏好
-> AI 下一次推荐参考行为上下文
```

这样项目既能在面试中讲清楚推荐系统闭环，也能在真实体验中让推荐更贴近用户行为。

## 2. 目标

第一版目标：

1. 建立统一的用户行为事件模型，记录业务行为和 AI 推荐交互行为。
2. 将收藏、加购、下单、支付等后端已有业务动作沉淀为行为事件。
3. 将 AI 推荐卡片曝光、点击、从推荐卡片加购、从推荐卡片收藏沉淀为行为事件。
4. 提供用户行为摘要查询能力，为 Java 构建 AI 上下文提供输入。
5. 在 AI 请求 Python 前，将轻量行为摘要加入 `user_context` 或上下文对象。
6. 在设计上预留 MQ 异步化演进路径，但第一版不强行引入 RabbitMQ 或 Kafka。

面试表达目标：

> 这个项目不是只做一次性 AI 问答，而是把用户对推荐结果的真实反馈记录下来，再作为下一轮推荐的上下文。第一版先用同步事件落库保证链路稳定，后续可以把行为事件发布到 MQ，由异步消费者做用户画像更新、热门商品统计和推荐特征沉淀。

## 3. 非目标

第一版不做以下内容：

- 不引入真实 RabbitMQ、Kafka 或 RocketMQ。
- 不做复杂推荐算法训练。
- 不做实时特征工程平台。
- 不做埋点大数据看板。
- 不改变订单、支付、库存的事实源设计。
- 不让 Python 直接写 Java 数据库。
- 不把 Redis 当作行为事件的长期事实源。

这些内容可以作为第二阶段或面试扩展点，而不是第一版实现范围。

## 4. 第一版范围

第一版采用轻量闭环：

```text
后端业务动作
-> BehaviorEventService 同步记录行为事件
-> MySQL behavior_event 表保存事件事实
-> BehaviorSummaryService 聚合用户近期行为
-> AssistantContextService 构建 AI 上下文时读取行为摘要
-> Python AI 服务收到近期偏好和行为线索
```

同时新增一个前端可调用的推荐交互事件接口：

```text
AI 推荐卡片曝光 / 点击
-> 前端调用 Java 行为事件 API
-> Java 校验当前用户身份和商品 ID
-> 同步写入 behavior_event
```

第一版重点是“能闭环、能演示、能讲清楚”，而不是追求事件系统完整度。

## 5. 行为事件类型

### 5.1 业务行为事件

业务行为来自后端已有接口或服务，不依赖前端额外埋点。

```text
FAVORITE_ADD
CART_ADD
ORDER_CREATED
PAYMENT_SUCCESS
```

建议含义：

- `FAVORITE_ADD`：用户收藏商品，代表强兴趣。
- `CART_ADD`：用户加入购物车，代表购买意图。
- `ORDER_CREATED`：用户创建订单，代表明确转化。
- `PAYMENT_SUCCESS`：用户支付成功，代表最终正反馈。

### 5.2 AI 推荐交互事件

AI 推荐交互行为主要由前端触发，反映用户对推荐结果的反应。

```text
RECOMMENDATION_EXPOSED
RECOMMENDATION_CLICKED
RECOMMENDATION_CART_ADD
RECOMMENDATION_FAVORITE_ADD
```

建议含义：

- `RECOMMENDATION_EXPOSED`：某次 AI 回答中的推荐卡片被展示。
- `RECOMMENDATION_CLICKED`：用户点击推荐卡片查看商品详情。
- `RECOMMENDATION_CART_ADD`：用户从推荐卡片触发加购。
- `RECOMMENDATION_FAVORITE_ADD`：用户从推荐卡片触发收藏。

其中 `RECOMMENDATION_CART_ADD` 和 `RECOMMENDATION_FAVORITE_ADD` 可以和业务事件同时存在：

```text
RECOMMENDATION_CART_ADD：说明加购来源是 AI 推荐
CART_ADD：说明用户完成了加购这个业务动作
```

这样既保留业务事实，也能分析推荐来源转化。

## 6. 数据模型

### 6.1 behavior_event

建议新增表：

```sql
CREATE TABLE behavior_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_id VARCHAR(64) NOT NULL,
    user_id BIGINT NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    source VARCHAR(32) NOT NULL,
    spu_id BIGINT NULL,
    sku_id BIGINT NULL,
    thread_id VARCHAR(64) NULL,
    request_id VARCHAR(64) NULL,
    order_no VARCHAR(64) NULL,
    quantity INT NULL,
    event_time DATETIME(6) NOT NULL,
    metadata_json JSON NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    UNIQUE KEY uk_behavior_event_id (event_id),
    KEY idx_behavior_user_time (user_id, event_time),
    KEY idx_behavior_user_type_time (user_id, event_type, event_time),
    KEY idx_behavior_spu_time (spu_id, event_time)
);
```

字段说明：

- `event_id`：幂等键，由调用方传入或后端生成，避免重复埋点导致重复记录。
- `user_id`：从 JWT 当前用户或业务上下文取，不能信任前端传入。
- `event_type`：行为类型。
- `source`：事件来源，例如 `COMMERCE`、`ASSISTANT_RECOMMENDATION`、`SYSTEM`。
- `spu_id` / `sku_id`：商品维度，推荐卡片通常至少应有 `spu_id`。
- `thread_id`：AI 会话 ID，用于追踪某次推荐回答后的行为。
- `request_id`：后端请求链路 ID，便于日志关联。
- `order_no`：订单相关事件可记录订单号。
- `quantity`：加购、下单等数量。
- `metadata_json`：保留扩展字段，例如推荐卡片位置、推荐批次、前端页面。
- `event_time`：事件发生时间。

### 6.2 行为摘要 DTO

不建议第一版直接给 Python 传所有事件。Java 应先聚合为轻量摘要。

建议摘要结构：

```json
{
  "recentInterestSpuIds": [1001, 1003],
  "recentCartSpuIds": [1002],
  "recentPurchasedSpuIds": [1005],
  "preferredCategories": ["外套", "裤子"],
  "preferredStyles": ["commute", "minimal"],
  "negativeSignals": []
}
```

第一版可以不做复杂负反馈；`negativeSignals` 保留字段即可。

## 7. 后端模块设计

建议新增包：

```text
behavior
├── api
├── dto
├── mapper
├── model
└── service
```

### 7.1 BehaviorEventService

职责：

- 接收业务服务或 Controller 传入的事件命令。
- 补齐 `userId`、`eventTime`、`requestId` 等服务端字段。
- 校验事件类型、商品 ID、数量等基础参数。
- 同步写入 `behavior_event`。
- 对重复 `event_id` 做幂等处理。

边界：

- 不负责推荐排序。
- 不直接调用 Python。
- 不修改订单、支付、库存事实。

### 7.2 BehaviorSummaryService

职责：

- 查询用户最近一段时间的行为事件。
- 聚合用户近期感兴趣商品、加购商品、购买商品、偏好分类、偏好风格。
- 输出给 `AssistantContextService` 使用的轻量摘要。

第一版建议聚合窗口：

```text
最近 30 天
每类最多 10 个商品
偏好分类和风格按出现次数排序，最多 5 个
```

### 7.3 BehaviorMapper

职责：

- 插入行为事件。
- 按用户和时间查询近期事件。
- 按用户和事件类型查询最近商品。
- 聚合分类、风格等轻量统计。

第一版可以通过 MyBatis XML 写清楚 SQL，避免过早抽象。

## 8. 接口设计

### 8.1 推荐交互事件接口

新增接口：

```text
POST /api/behavior/events
```

认证：

```text
Authorization: Bearer <accessToken>
```

请求示例：

```json
{
  "eventId": "frontend-generated-uuid",
  "eventType": "RECOMMENDATION_CLICKED",
  "source": "ASSISTANT_RECOMMENDATION",
  "spuId": 1001,
  "skuId": null,
  "threadId": "thread_xxx",
  "quantity": null,
  "metadata": {
    "position": 1,
    "page": "ai-shopping"
  }
}
```

响应示例：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "eventId": "frontend-generated-uuid"
  }
}
```

接口约束：

- `eventType` 第一版只允许推荐交互事件，不能让前端伪造 `PAYMENT_SUCCESS`。
- `userId` 只能从当前登录用户取。
- `source` 如果为空，后端可默认为 `ASSISTANT_RECOMMENDATION`。
- 如果 `eventId` 已存在，接口返回成功，保证幂等。

### 8.2 内部行为摘要接口

第一版可以不对外暴露。若为了调试和演示，可以增加仅登录用户可见的接口：

```text
GET /api/me/behavior-summary
```

该接口用于本地演示“系统已经理解用户近期偏好”，不作为 Python 调用入口。

## 9. 前端埋点设计

前端第一版只在 AI 推荐卡片组件附近做轻量埋点：

```text
推荐结果渲染完成 -> 发送 RECOMMENDATION_EXPOSED
点击商品卡片 -> 发送 RECOMMENDATION_CLICKED
从推荐卡片加购成功 -> 发送 RECOMMENDATION_CART_ADD
从推荐卡片收藏成功 -> 发送 RECOMMENDATION_FAVORITE_ADD
```

注意：

- 曝光事件需要避免每次 React 重渲染都重复发送。
- 推荐卡片应携带 `threadId`，用于关联某轮 AI 对话。
- 加购和收藏事件应以业务操作成功后再记录推荐交互事件。
- 埋点失败不应阻断用户主流程，只记录前端日志或静默失败。

## 10. AI 推荐上下文接入

Java 的 `AssistantContextService` 当前负责组装用户画像、身体数据、偏好和推荐候选。第一版在这里补充行为摘要：

```text
AssistantContextService.buildContext(...)
-> userProfileService.getProfile(userId)
-> userProfileService.getBodyData(userId)
-> userProfileService.getPreferences(userId)
-> behaviorSummaryService.getSummary(userId)
-> productCatalogService.findRecommendationCandidates(...)
-> 组装 AssistantContext
```

传给 Python 的上下文应保持轻量，不直接发送完整行为流水。

建议 Python 侧新增或扩展 `user_context` 字段：

```json
{
  "recent_interest_spu_ids": [1001, 1003],
  "recent_cart_spu_ids": [1002],
  "recent_purchased_spu_ids": [1005],
  "behavior_preferred_categories": ["外套"],
  "behavior_preferred_styles": ["commute"]
}
```

如果第一版不想马上改 Python，可以先在 Java 内部生成摘要并写测试，后续再接入 Python 契约。但为了满足“真实推荐效果”目标，推荐至少完成 Java -> Python 请求 DTO 的字段扩展。

## 11. 异步事件 / MQ 演进路径

第一版采用同步落库：

```text
业务服务 / 前端埋点接口
-> BehaviorEventService
-> MySQL behavior_event
```

第二阶段可演进为 MQ：

```text
业务服务 / 前端埋点接口
-> DomainEventPublisher
-> RabbitMQ / Kafka topic
-> BehaviorEventConsumer
-> behavior_event
-> UserPreferenceAggregator
-> Redis / MySQL 行为摘要
```

演进价值：

- 收藏、加购、支付等主流程不被行为分析拖慢。
- 行为事件可被多个消费者复用，例如推荐画像、热门商品、运营统计。
- 面试中可以说明从同步闭环到异步事件驱动的演进路径。

第一版代码设计应避免把事件记录散落在各个 Service 中。建议通过统一 `BehaviorEventService` 或轻量 `DomainEventRecorder` 收口，这样以后替换为 MQ 发布器时改动小。

## 12. 错误处理与幂等

### 12.1 行为记录失败策略

行为事件是推荐优化数据，不是交易事实。

策略：

- 收藏、加购、下单、支付主流程成功后，行为事件记录失败不应回滚主流程。
- 行为事件失败需要打日志，包含 `userId`、`eventType`、`spuId`、`requestId`。
- 推荐交互事件接口失败可以返回错误，但前端不应影响用户继续购物。

### 12.2 幂等策略

幂等键来源：

- 前端推荐交互事件：前端生成 UUID 作为 `eventId`。
- 后端业务事件：后端可用业务维度生成稳定键，例如 `favorite:{userId}:{spuId}`、`cart:{userId}:{skuId}:{requestId}`、`payment:{orderNo}`。

重复事件处理：

```text
INSERT 成功 -> 返回成功
唯一键冲突 -> 视为已记录，返回成功
其他数据库异常 -> 记录日志，按事件来源决定是否返回错误
```

## 13. 测试策略

### 13.1 Mapper 测试

覆盖：

- 行为事件插入。
- `event_id` 唯一约束。
- 按用户和时间查询近期事件。
- 按行为类型聚合商品 ID。

### 13.2 Service 单元测试

覆盖：

- `BehaviorEventService` 补齐服务端字段。
- 不允许前端写入后端专属事件类型。
- 重复 `eventId` 幂等成功。
- 行为记录失败不影响主业务服务。
- `BehaviorSummaryService` 正确聚合近期偏好。

### 13.3 Controller 测试

覆盖：

- 未登录不能记录行为事件。
- 登录用户可以记录推荐点击。
- 前端不能伪造 `PAYMENT_SUCCESS`。
- 重复 `eventId` 返回成功。

### 13.4 Assistant 上下文测试

覆盖：

- 构建 AI 上下文时会读取行为摘要。
- 行为摘要为空时不影响 AI 请求。
- 行为摘要字段正确进入 Python 请求 DTO。

## 14. 演示路径

本地演示建议：

1. 登录用户。
2. 打开 AI 导购页，询问“推荐一套通勤穿搭”。
3. 前端展示推荐卡片，并记录 `RECOMMENDATION_EXPOSED`。
4. 点击某个推荐商品，记录 `RECOMMENDATION_CLICKED`。
5. 从推荐卡片加购，记录 `RECOMMENDATION_CART_ADD` 和 `CART_ADD`。
6. 创建订单并支付成功，记录 `ORDER_CREATED` 和 `PAYMENT_SUCCESS`。
7. 查询 `/api/me/behavior-summary`，看到近期感兴趣商品和偏好分类。
8. 再次询问 AI，Java 将行为摘要加入 Python 请求上下文。

验收标准：

```text
behavior_event 表能看到推荐曝光、点击、加购、支付等事件
重复 eventId 不会插入重复记录
用户行为摘要能反映近期点击、加购、购买
AI 请求上下文包含行为摘要字段
行为记录失败不影响加购、下单、支付主流程
```

## 15. 面试表达

可以这样讲：

> 我在项目里补了用户反馈闭环。AI 导购不只是根据用户当次输入推荐商品，还会记录用户对推荐卡片的曝光、点击、收藏、加购以及后续下单支付行为。Java 后端把这些行为统一沉淀到 behavior_event 表，再聚合成近期兴趣、购买偏好和风格倾向，下一次调用 Python AI 服务时作为用户上下文传过去。

继续补充：

> 第一版我没有直接上 MQ，而是先同步落库，把业务闭环跑通。因为行为事件不是交易事实，记录失败不会影响加购、下单、支付主流程。后续如果要提升解耦和吞吐，可以把 BehaviorEventService 后面替换成事件发布器，通过 RabbitMQ 或 Kafka 异步消费，分别服务用户画像更新、热门商品统计和推荐特征沉淀。

这个表达能同时体现：

- 推荐系统闭环意识。
- Java 后端边界意识。
- MySQL 事实源设计。
- 事件驱动和 MQ 演进思路。
- 对主流程稳定性的考虑。
