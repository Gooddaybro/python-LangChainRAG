# Java 电商后端与 Python AI 导购服务架构设计

## 1. 项目定位

本项目不是普通服装商城后面简单接一个 AI 问答接口，而是一个以“衣服推荐”为核心的服装电商系统。
Java 后端负责稳定的业务事实和交易闭环，
Python 服务负责 AI 导购、自然语言理解、RAG 知识问答和 LangGraph 编排。

核心业务链路：

```text
用户画像
-> AI 导购对话
-> 商品推荐
-> 商品卡片
-> 加入购物车
-> 下单
-> 购买行为反哺推荐
```

系统边界：

```text
Java 后端：
用户、登录、权限、商品、SKU、价格、库存、购物车、订单、会话、日志、推荐结果沉淀。

Python AI 服务：
自然语言理解、意图识别、尺码推荐、穿搭建议、RAG 知识问答、LangGraph 工具编排。
```

设计原则：

- 商品、价格、库存、订单等精确业务事实以 Java 数据库为准。
- Python 不长期维护独立商品库，当前 `product_catalog.json` 只作为本地 demo 或测试数据。
- Python 需要商品事实时，通过 Java internal API 查询。
- 普通商城能力即使 AI 服务不可用，也应保持可用。
- AI 推荐结果要结构化保存，支持后续分析推荐转化。

## 2. 总体架构

第一版采用 Spring Boot 模块化单体，而不是一开始拆成多个独立微服务。模块化单体可以保持边界清晰，同时降低部署、事务和调试复杂度。

```text
前端 / App
  -> Java Spring Boot 后端
      -> user-service
      -> product-service
      -> inventory-service
      -> cart-service
      -> order-service
      -> conversation-service
      -> assistant-service
          -> Python FastAPI AI 服务
              -> LangGraph Agent
              -> RAG
              -> Java internal product API
```

当前 Java 项目基础：

```text
语言：Java 21
框架：Spring Boot 4.0.6
构建：Maven
数据库：MySQL 8.0
数据访问：MyBatis Mapper + XML
数据库迁移：Flyway
```

技术栈时效性说明：

```text
Spring Boot 4.0.6 属于 Boot 4 版本线，基于 Spring Framework 7，并进入 Jakarta EE 11 / Jackson 3 体系。
第三方依赖必须优先确认 Boot 4 / Spring Framework 7 兼容性。
MyBatis 使用 Spring Boot Starter 4.0.0 路线。
接口文档优先使用 Spring REST Docs 4.0；Swagger UI/OpenAPI 作为后续增强，接入前需确认 springdoc-openapi 的 Boot 4 兼容版本。
```

工程化能力目标：

```text
统一响应 ApiResponse
统一异常 GlobalExceptionHandler
参数校验 @Validated
操作日志 / 登录日志
Testcontainers + MySQL 集成测试
Docker Compose 本地依赖启动
GitHub Actions 自动化测试
Reqable 手动接口验证
```

当前 Phase 2 已落地的能力：

```text
Docker Compose 本地 MySQL 8 环境
MDC requestId 日志链路追踪
GitHub Actions Maven 测试
Testcontainers MySQL Flyway 迁移测试
Spring REST Docs auth 接口片段
conversation-service 会话和消息历史
assistant-service 同步 HTTP 调 Python /chat
```

仍保留到后续阶段的能力：

```text
购物车
订单
支付
SSE / WebSocket 流式返回
MQ 异步推荐任务
推荐结果独立结构化沉淀表
```

建议包结构：

```text
com.recommendation.intelligentoutfitrecommendationsystem
  user
  product
  inventory
  cart
  order
  conversation
  assistant
  common
```

后续如果系统变大，可以从模块化单体演进为真实微服务，优先拆分 `product`、`order`、`assistant`。

## 3. 模块职责

### 3.1 user-service

负责用户账号、登录、权限、身体信息和穿衣偏好。

普通商城通常只需要账号和地址，但本项目的核心是衣服推荐，所以用户身体信息和风格偏好是一等数据。

主要能力：

- 用户注册、登录、退出。
- Access JWT + Refresh Token 双 Token 鉴权。
- Refresh Token 数据库撤销与多端登录追踪。
- 登录日志审计。
- 用户基础资料维护。
- 收货地址维护。
- 用户身体数据维护。
- 用户风格、颜色、预算、品类偏好维护。
- 权限和角色控制。

推荐相关数据：

```text
身高、体重、性别、肩宽、胸围、腰围、臀围、偏好版型。
通勤、休闲、运动、韩系等风格偏好。
偏好颜色、不喜欢颜色、偏好品类、预算范围。
```

### 3.2 product-service

负责服装商品建模、商品属性、SKU、价格和推荐候选查询。

服装商品必须区分 SPU 和 SKU：

```text
SPU：商品主体，例如“基础款纯棉T恤”。
SKU：具体可售规格，例如“基础款纯棉T恤 / 黑色 / L码”。
```

推荐主要围绕 SPU，库存、价格和下单主要围绕 SKU。

主要能力：

- 商品分类管理。
- 商品 SPU 管理。
- 商品 SKU 管理。
- 商品图片管理。
- 颜色、尺码、材质、版型、季节、风格标签管理。
- 商品推荐候选查询。
- 给 Python 提供 internal product API。

AI 推荐需要结构化查询这些字段：

```text
分类、材质、版型、季节、风格标签、颜色、尺码、价格区间、是否上架、库存状态。
```

### 3.3 inventory-service

负责库存查询、库存锁定、库存扣减和库存流水。

库存不要直接放在商品表里。库存有交易语义，需要支持锁定、释放、扣减和审计。

主要能力：

- 查询 SKU 可售库存。
- 创建订单时锁定库存。
- 支付成功后扣减库存。
- 订单取消后释放库存。
- 记录库存变更流水。

### 3.4 cart-service

负责购物车。

AI 推荐返回商品卡片后，前端可以直接把推荐 SKU 加入购物车。购物车模块不关心商品为什么被推荐，只关心用户、SKU、数量和选中状态。

主要能力：

- 加入购物车。
- 修改数量。
- 勾选或取消勾选。
- 删除购物车商品。
- 查询当前用户购物车。

### 3.5 order-service

负责订单、订单明细、支付记录、发货和售后扩展。

第一版可以先实现普通订单闭环，支付可以先用模拟支付或待支付状态。订单明细必须保存商品快照，避免商品后续改名、改价影响历史订单。

主要能力：

- 从购物车或立即购买创建订单。
- 保存订单明细和商品快照。
- 锁定库存。
- 支付成功后扣减库存。
- 取消订单释放库存。
- 查询订单列表和订单详情。

### 3.6 conversation-service

负责 AI 会话、消息历史、thread_id 和推荐结果沉淀。

这个模块是 Java 后端和 Python Agent 联动的关键。AI 推荐不能只返回一句文本，应该沉淀成可分析的推荐数据。

主要能力：

- 创建 AI 会话。
- 保存用户消息和助手消息。
- 维护 `thread_id`。
- 保存推荐结果。
- 保存推荐商品明细。
- 查询历史会话。
- 为 Python 请求组装 `chat_history`。

推荐转化分析依赖这些数据：

```text
用户问了什么。
AI 推荐了哪些商品。
用户点击了哪些商品。
哪些推荐加入购物车。
哪些推荐最终下单。
```

### 3.7 assistant-service

负责 Java 调用 Python AI 服务，是 Java 系统内部的 AI 网关。

assistant-service 不实现推荐算法，不直接替代 Python Agent。它负责把 Java 业务上下文整理成 Python 能理解的请求，并把 Python 返回结果保存成 Java 业务数据。

主要能力：

- 组装 AI 请求。
- 查询用户画像和会话历史。
- 调用 Python `/chat`。
- 调用 Python `/chat/stream`。
- 解析 Python 返回的回答和商品引用。
- 保存 AI 请求日志。
- 保存推荐结果。
- 对外提供前端可用的 AI 聊天接口。

必须具备的工程能力：

- 超时控制。
- 重试策略。
- 熔断或降级。
- requestId 链路追踪。
- 内部服务鉴权。
- 错误日志和耗时统计。

## 4. 核心数据库表设计

### 4.1 用户与推荐画像

#### user

用户主表。

```text
id
username
phone
email
password_hash
status
created_at
updated_at
```

#### user_profile

用户基础资料。

```text
id
user_id
nickname
avatar_url
gender
birthday
created_at
updated_at
```

#### user_body_data

用户身体数据，用于尺码推荐。

```text
id
user_id
height_cm
weight_kg
gender
shoulder_width_cm
bust_cm
waist_cm
hip_cm
preferred_fit
created_at
updated_at
```

`preferred_fit` 示例：

```text
loose
regular
slim
```

#### user_preferences

用户穿衣偏好，用于个性化推荐。

```text
id
user_id
preferred_styles
preferred_colors
disliked_colors
preferred_categories
budget_min
budget_max
created_at
updated_at
```

第一版可以把多值字段存成 JSON 字符串，后续再拆成关系表。

#### refresh_token

Refresh Token 状态表。Access Token 保持短效无状态，Refresh Token 通过数据库控制撤销、过期和多端登录。

```text
id
user_id
token_hash
device_id
user_agent
ip_address
expires_at
revoked_at
created_at
last_used_at
```

#### login_log

登录审计日志。

```text
id
user_id
username
success
fail_reason
ip_address
user_agent
created_at
```

#### user_address

收货地址。

```text
id
user_id
receiver_name
receiver_phone
province
city
district
detail_address
is_default
created_at
updated_at
```

#### role / permission / user_role / role_permission

权限控制表。第一版至少区分普通用户和管理员。

```text
role:
  id
  code
  name

permission:
  id
  code
  name

user_role:
  user_id
  role_id

role_permission:
  role_id
  permission_id
```

### 4.2 商品与服装推荐属性

#### category

商品分类。

```text
id
parent_id
name
level
sort_order
status
```

示例：

```text
上衣 / T恤
上衣 / 外套
下装 / 长裤
```

#### product_spu

商品主体。

```text
id
spu_code
name
category_id
brand_id
description
main_image_url
fit_type_id
status
created_at
updated_at
```

`status` 示例：

```text
draft
on_sale
off_sale
deleted
```

#### product_sku

具体可售规格。

```text
id
sku_code
spu_id
color_id
size_id
sale_price
original_price
status
created_at
updated_at
```

唯一约束建议：

```text
spu_id + color_id + size_id
```

#### product_image

商品图片。

```text
id
spu_id
sku_id
image_url
image_type
sort_order
```

`image_type` 示例：

```text
main
detail
sku
model
```

#### color

颜色字典。

```text
id
name
color_family
hex_code
```

示例：

```text
黑色 / black / #000000
藏青色 / blue / #1F2A44
```

#### size

尺码字典。

```text
id
code
name
sort_order
```

示例：

```text
S
M
L
XL
```

#### size_rule

尺码规则。

```text
id
code
name
category_id
rule_json
description
```

`rule_json` 可以描述不同身高体重区间推荐尺码，后续可被 Python 尺码工具调用。

#### material

材质字典。

```text
id
name
description
```

示例：

```text
纯棉
聚酯纤维
羊毛
棉涤混纺
```

#### fit_type

版型字典。

```text
id
code
name
description
```

示例：

```text
loose / 宽松
regular / 合身
slim / 修身
straight / 直筒
```

#### season

季节字典。

```text
id
code
name
```

示例：

```text
spring
summer
autumn
winter
all_season
```

#### style_tag

风格标签。

```text
id
code
name
description
```

示例：

```text
commute / 通勤
casual / 休闲
sport / 运动
korean / 韩系
minimal / 极简
```

#### product_material

商品和材质关系。

```text
id
spu_id
material_id
percentage
```

#### product_season

商品和季节关系。

```text
id
spu_id
season_id
```

#### product_style_tag

商品和风格标签关系。

```text
id
spu_id
style_tag_id
```

#### product_attribute

商品扩展属性。

```text
id
spu_id
attr_name
attr_value
```

示例：

```text
厚度 = 薄款
弹力 = 微弹
透气性 = 高
领型 = 圆领
衣长 = 常规
```

这张表用于保存不适合单独建字典表、但对推荐有价值的服装属性。

### 4.3 库存与价格

#### inventory

SKU 当前库存。

```text
id
sku_id
available_stock
locked_stock
sold_stock
updated_at
```

可售库存以 `available_stock` 为准。

#### inventory_lock

库存锁定记录。

```text
id
order_id
sku_id
quantity
status
expired_at
created_at
updated_at
```

`status` 示例：

```text
locked
confirmed
released
expired
```

#### inventory_record

库存流水。

```text
id
sku_id
change_type
quantity
before_available_stock
after_available_stock
biz_type
biz_id
created_at
```

#### price_history

价格变更历史。

```text
id
sku_id
old_price
new_price
change_reason
created_at
```

### 4.4 购物车

#### cart_item

购物车条目。

```text
id
user_id
sku_id
quantity
selected
created_at
updated_at
```

购物车展示时，通过 `sku_id` 关联商品、图片、颜色、尺码、价格和库存。

### 4.5 订单

#### order

订单主表。

```text
id
order_no
user_id
total_amount
discount_amount
pay_amount
status
address_snapshot
created_at
updated_at
```

`status` 示例：

```text
pending_payment
paid
shipped
completed
cancelled
refunded
```

#### order_item

订单明细。

```text
id
order_id
spu_id
sku_id
product_name
sku_snapshot
image_url
price
quantity
total_amount
created_at
```

`sku_snapshot` 保存颜色、尺码、材质、版型等下单时信息，避免历史订单被商品后续变更影响。

#### payment

支付记录。

```text
id
order_id
payment_no
pay_channel
pay_amount
status
paid_at
created_at
```

第一版可以先做模拟支付。

#### shipment

发货记录。

```text
id
order_id
logistics_company
tracking_no
status
shipped_at
created_at
```

#### refund_order

售后退款记录。

```text
id
order_id
order_item_id
refund_amount
reason
status
created_at
updated_at
```

### 4.6 AI 会话与推荐结果

#### assistant_session

AI 会话。

```text
id
user_id
thread_id
title
status
created_at
updated_at
```

`thread_id` 用于关联 Python LangGraph 的会话上下文。

#### assistant_message

AI 会话消息。

```text
id
session_id
role
content
intent
request_id
created_at
```

`role` 示例：

```text
user
assistant
system
```

#### assistant_recommendation

一次推荐结果。

```text
id
session_id
message_id
query
answer
source
created_at
```

`source` 示例：

```text
python_agent
manual
rule
```

#### assistant_recommendation_item

推荐商品明细。

```text
id
recommendation_id
spu_id
sku_id
reason
rank_score
action_type
created_at
```

`action_type` 示例：

```text
view_product
add_to_cart
buy_now
ask_follow_up
```

#### ai_request_log

Java 调 Python 的请求日志。

```text
id
request_id
user_id
session_id
query
python_endpoint
status
latency_ms
error_message
created_at
```

这张表用于排查 AI 服务耗时、失败和请求链路问题。

## 5. Java 与 Python 的调用设计

### 5.1 普通聊天

普通聊天使用 HTTP JSON。

```text
前端
-> Java /api/assistant/chat
-> Java assistant-service 查询用户画像和历史消息
-> Python /chat
-> Python 调 Java internal API 查询商品事实
-> Python 返回回答和商品引用
-> Java 保存消息、推荐结果和日志
-> 前端展示回答和商品卡片
```

Java 对前端接口：

```text
POST /api/assistant/chat
```

请求示例：

```json
{
  "sessionId": "s-001",
  "message": "我 175cm 70kg，想买一件适合通勤的外套"
}
```

Java 调 Python 请求示例：

```json
{
  "query": "我 175cm 70kg，想买一件适合通勤的外套",
  "chat_history": [],
  "thread_id": "s-001",
  "user_context": {
    "height_cm": 175,
    "weight_kg": 70,
    "preferred_fit": "regular",
    "preferred_styles": ["commute"],
    "preferred_colors": ["black", "navy"],
    "budget_min": 100,
    "budget_max": 400
  },
  "debug": false
}
```

Python 返回建议结构：

```json
{
  "answer": "可以优先看通勤轻薄外套，黑色和藏青色都比较适合日常通勤。",
  "intent": "recommendation",
  "product_refs": [
    {
      "spu_id": 1001,
      "sku_id": 2001,
      "reason": "符合通勤风格，颜色百搭，预算范围内。"
    }
  ],
  "suggested_actions": [
    {
      "type": "view_product",
      "sku_id": 2001
    }
  ]
}
```

### 5.2 流式聊天

需要类似 ChatGPT 的逐字输出体验时，使用 SSE。

```text
前端
-> Java /api/assistant/chat/stream
-> Python /chat/stream
-> Python SSE event
-> Java SSE 转发
-> 前端逐步渲染
```

建议事件类型：

```text
message_start
token
tool_event
product_refs
message_end
error
```

第一版可以先实现普通 HTTP，确认主流程稳定后再加 SSE。

### 5.3 长任务异步

不是所有 AI 能力都走同步聊天。长任务使用 MQ。

适合异步的任务：

- RAG 知识库重建。
- 批量商品文案生成。
- 批量商品标签补全。
- AI 推荐评测报告。
- 用户画像定时刷新。

异步链路：

```text
Java 创建 ai_task
-> Java 发送 MQ: ai.task.requested
-> Python 消费任务
-> Python 执行任务
-> Python 发送 MQ: ai.task.completed
-> Java 保存任务结果
-> 前端轮询或 SSE 获取完成状态
```

第一版如果项目规模有限，可以暂不引入 MQ，只保留接口设计和表结构扩展点。

## 6. Python 调 Java internal API

Python 需要商品事实时，不直接读本地商品 JSON，而是调用 Java internal API。

建议 internal API：

```text
GET /internal/products/search
GET /internal/products/{spuId}
GET /internal/skus/search
GET /internal/inventory
GET /internal/recommendation-candidates
GET /internal/size-rules/{ruleId}
```

### 6.1 商品搜索

```text
GET /internal/products/search?keyword=基础款纯棉T恤
```

返回商品 SPU 和基础属性。

### 6.2 SKU 搜索

```text
GET /internal/skus/search?spuId=1001&color=黑色&size=L
```

返回精确 SKU、价格和状态。

### 6.3 库存查询

```text
GET /internal/inventory?skuId=2001
```

返回可售库存。

### 6.4 推荐候选查询

```text
GET /internal/recommendation-candidates?category=外套&style=commute&season=autumn&budgetMax=400
```

返回符合筛选条件的商品候选，供 Python Agent 生成推荐理由。

internal API 要求：

- 只允许内部服务访问。
- 使用内部 token 或签名鉴权。
- Python 只能读商品事实，不能直接改库存、下订单、改价格。
- 所有真正业务动作必须回到 Java 完成。

## 7. AI 推荐闭环

AI 推荐不只是回答一句自然语言，而是要形成完整闭环。

```text
用户输入
-> Java 保存用户消息
-> Python 理解需求
-> Python 查询 Java 商品候选
-> Python 生成推荐答案和商品引用
-> Java 保存助手消息
-> Java 保存推荐结果
-> 前端展示商品卡片
-> 用户点击 / 加购 / 下单
-> Java 记录行为
-> 后续推荐使用这些行为
```

推荐闭环需要记录：

- 推荐曝光。
- 商品点击。
- 加入购物车。
- 下单。
- 取消或退款。

后续可以增加用户行为表：

```text
user_product_behavior:
  id
  user_id
  spu_id
  sku_id
  behavior_type
  source
  session_id
  created_at
```

`behavior_type` 示例：

```text
view
click
add_to_cart
order
favorite
```

第一版可以先不做复杂行为分析，但表设计要为推荐闭环留出空间。

## 8. MVP 实施范围

第一阶段优先实现能跑通“AI 推荐到下单”的最小闭环。

必做模块：

```text
user-service
product-service
inventory-service
cart-service
order-service
conversation-service
assistant-service
```

必做表：

```text
user_account
user_profile
user_body_data
user_preferences
refresh_token
login_log
user_address

category
product_spu
product_sku
product_image
color
size
size_rule
material
fit_type
season
style_tag
product_material
product_season
product_style_tag
product_attribute

inventory
inventory_lock
inventory_record
price_history

cart_item

order
order_item
payment

assistant_session
assistant_message
assistant_recommendation
assistant_recommendation_item
ai_request_log
```

MVP 可以暂缓：

- 真实支付渠道。
- 复杂售后流程。
- MQ 异步任务。
- 多仓库存。
- 复杂优惠券。
- 精细化用户行为分析。

## 9. 开发顺序建议

建议按下面顺序推进：

1. 建立基础 Spring Boot 分包结构和通用响应、异常、时间字段规范。
2. 设计并落地商品、SKU、颜色、尺码、材质、版型、季节、风格标签表。
3. 实现商品查询和 internal product API。
4. 实现库存表和库存查询。
5. 实现用户注册登录、Access/Refresh Token、JWT 鉴权、登录日志。
6. 实现用户画像、身体数据和穿衣偏好。
7. 增加 Testcontainers、Docker Compose、GitHub Actions 和接口文档能力。
8. 实现 assistant-session 和 assistant-message。
9. 实现 Java 调 Python `/chat`。
10. 改造 Python structured lookup，让它调用 Java internal API。
11. 实现推荐结果保存和前端商品卡片所需返回结构。
12. 实现购物车。
13. 实现订单和库存锁定。
14. 增加 SSE 流式聊天。
15. 评估是否引入 MQ 处理长任务。

## 10. 风险与约束

### 10.1 数据一致性

风险：Python 继续使用 `product_catalog.json`，Java 数据库也维护一份商品数据，导致价格、库存、SKU 不一致。

处理方式：

```text
生产链路以 Java 数据库为准。
Python 的本地 JSON 只用于 demo、测试或 Java 服务不可用时的开发兜底。
```

### 10.2 AI 服务不可用

风险：Python 服务不可用会影响导购体验。

处理方式：

```text
Java 商城主流程不依赖 Python。
AI 不可用时返回明确降级提示。
商品浏览、购物车、下单继续可用。
```

### 10.3 长响应耗时

风险：复杂推荐或 RAG 回答耗时较长。

处理方式：

```text
普通请求设置超时。
需要实时体验时使用 SSE。
长任务使用 MQ 异步处理。
```

### 10.4 内部接口权限

风险：Python 调 Java internal API，如果没有鉴权，可能暴露商品和库存内部数据。

处理方式：

```text
internal API 使用内部 token 或签名。
限制调用来源。
记录 requestId 和调用日志。
```

## 11. 结论

本项目的后端应围绕衣服推荐建模，而不是普通商城后补 AI。
Java 后端作为业务主系统，维护用户、商品、库存、价格、订单和推荐结果；Python AI 服务作为推荐能力层，负责理解用户需求、调用工具和生成导购回答。

第一版采用 Spring Boot 模块化单体，先跑通“用户画像 -> AI 推荐 -> 商品卡片 -> 加购物车 -> 下单”的闭环。
后续再逐步加入 SSE 流式回答、MQ 异步任务、用户行为分析和更精细的推荐评测。
