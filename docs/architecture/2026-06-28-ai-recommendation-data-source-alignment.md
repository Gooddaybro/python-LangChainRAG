# AI 推荐数据源对齐改造设计

## 一句话结论

当前 AI 推荐问题的核心不是向量库本身，而是 Python AI 服务中仍存在本地商品事实源 `product_catalog.json`，它和 Java 后端数据库存在数据不对称风险。

生产链路应以 Java 数据库为唯一商品事实来源。Python 只负责意图识别、RAG 解释、尺码推理、候选排序和推荐理由生成，不应长期维护第二套商品、价格、库存、SKU 数据。

## 背景

当前系统分为两个项目：

- Java 商城后端：负责用户、会话、商品、SKU、价格、库存、购物车、订单、支付和前端 API。
- Python AI 服务：负责意图识别、LangGraph 编排、RAG 检索、尺码工具、推荐排序和自然语言生成。

Java 正式聊天链路已经会组装用户上下文、会话历史和推荐候选商品 `candidates` 后传给 Python。Python 生成 `product_refs` 时也已经限制为只能引用 Java 传入的候选商品。

但是 Python 内部仍保留 `clothing_assistant/data/product_catalog.json`，并且结构化价格、库存查询仍会读取这个本地 JSON。随着 Java 数据库商品持续扩展，这会形成事实源不一致。

## 当前问题

### 1. Python 本地商品库与 Java 数据库不一致

Python 本地 `product_catalog.json` 目前只包含少量 demo 商品，而 Java 数据库迁移脚本已经维护了更多 SPU、SKU、价格、库存和商品属性。

风险：

- 用户询问 Java 新增商品价格时，Python 本地 JSON 查不到。
- 用户询问库存时，Python 可能返回本地 JSON 的旧库存。
- 前端商品列表来自 Java，AI 回答的商品事实来自 Python JSON，用户看到的内容不一致。
- 后续改价、补货、下架只发生在 Java 数据库时，Python 仍可能给出过期回答。

### 2. RAG 不应承担商品强事实查询

RAG 适合回答解释性、语义型、非强一致知识：

- 颜色搭配。
- 洗涤养护。
- 风格建议。
- 材质解释。
- 场景穿搭说明。

RAG 不适合回答强一致业务事实：

- 价格。
- 库存。
- SKU。
- 可购买尺码。
- 商品是否上架。
- 订单、支付、售后状态。

这些事实必须来自 Java 结构化数据，并在加购、下单、支付前由 Java 再次校验。

### 3. Java 推荐候选目前不是严格 SKU 级候选

当前 Java `findRecommendationCandidates` SQL 按 SPU 聚合，然后用 `MIN(sku.id)`、`MIN(color)`、`MIN(size)` 取代表 SKU 字段。

风险：

- Python 收到的候选 SKU 可能不是用户需要的尺码。
- 用户需要 L 码，但 Java 代表 SKU 可能是 M 码，Python 按尺码筛选时会误杀候选。
- 一个 SPU 下有多个颜色/尺码/价格时，聚合字段不能代表真实可售 SKU。
- 推荐卡片需要 SKU 级引用时，当前候选粒度不够稳定。

### 4. Java 传给 Python 的候选字段不完整

Python API 契约里已经定义了 `available_stock`，但 Java `PythonProductCandidate` 当前没有传这个字段。

风险：

- Python 只能用 `stock_status` 粗略判断库存。
- 推荐理由无法说明真实可售库存。
- 排序无法区分低库存和充足库存。
- 契约和 Java 实际 DTO 不完全一致。

### 5. 共享契约目录在当前工作区缺失

两个项目的 `AGENTS.md` 都要求修改 Java-Python API 或推荐链路前读取共享契约目录：

```text
../outfit-project-contract
```

但当前工作区下未找到该目录。

风险：

- 开发时可能只改一侧项目，遗漏跨服务契约同步。
- IDE 中看不到共享契约，容易产生字段命名、响应结构、边界规则不一致。

## 改造目标

1. 生产环境中，商品事实只以 Java 数据库为准。
2. Python 不再用本地 JSON 回答生产价格、库存、SKU。
3. Python 的 `product_refs` 必须只来自 Java 传入的 `candidates`。
4. Java 给 Python 的候选应尽量改为 SKU 级候选。
5. Java 候选字段补齐 `available_stock`、`sku_code`、`spu_code` 等契约字段。
6. RAG 只保留解释性知识，不承载价格、库存、SKU 等强事实。
7. 无候选或候选不足时，Python 保守回答或追问，不编造商品引用。

## 当前代码位置

### Java 后端

#### AI 上下文组装

文件：

```text
IntelligentOutfitRecommendationSystem/backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/service/AssistantContextService.java
```

当前职责：

- 读取用户画像。
- 读取身体数据和偏好。
- 读取会话历史。
- 调用 `ProductCatalogService.findRecommendationCandidates` 获取 Java 候选商品。

关注点：

- 这里是 Java 候选池进入 Python 的入口。
- 后续应确保所有生产推荐都经过这里，而不是 Python 自己查本地 JSON。

#### Java 到 Python 候选转换

文件：

```text
IntelligentOutfitRecommendationSystem/backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/service/AssistantService.java
```

当前方法：

```text
toPythonCandidates
```

需要关注：

- 当前传了 `spu_id`、`sku_id`、`name`、`category`、`sale_price`、`stock_status`、`color`、`size`、`material`、`fit_type`、`season`、`style_tags`、`main_image_url`。
- 当前没有传 `available_stock`。
- 当前没有传 `sku_code`、`spu_code`。

#### PythonProductCandidate DTO

文件：

```text
IntelligentOutfitRecommendationSystem/backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/dto/PythonProductCandidate.java
```

需要关注：

- 补齐契约字段。
- 字段命名必须和 Python Pydantic schema 一致，例如 `available_stock`。

#### 推荐候选查询

文件：

```text
IntelligentOutfitRecommendationSystem/backend/src/main/resources/mapper/product/ProductMapper.xml
```

当前问题：

- `findRecommendationCandidates` 按 SPU 聚合。
- 使用 `MIN(sku.id)`、`MIN(co.name)`、`MIN(so.code)` 取代表 SKU、颜色、尺码。

建议方向：

- 改成 SKU 级候选。
- 每条候选对应一个真实可售 SKU。
- 保留上架、有库存、预算、品类、风格、季节、材质、版型过滤。
- 返回真实 `available_stock`。

#### RecommendationCandidate 模型

文件：

```text
IntelligentOutfitRecommendationSystem/backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/product/model/RecommendationCandidate.java
```

建议新增字段：

- `skuCode`
- `availableStock`

可选保留字段：

- `spuCode`
- `minPrice`
- `maxPrice`
- `totalAvailableStock`

如果候选改为 SKU 级，`totalAvailableStock` 仍可作为 SPU 汇总参考，但不应替代 SKU 自身库存。

### Python AI 服务

#### 本地商品事实查询

文件：

```text
AI-Clothing-Shopping-Assistant-System/clothing_assistant/tools/product_catalog.py
```

当前问题：

- `run_structured_lookup` 读取 `product_catalog.json`。
- 价格回答使用 `price_cny`。
- 库存回答使用 JSON 内的 `colors.stock`。

建议方向：

- 保留该文件作为 demo/test fallback。
- 增加明确配置开关，例如：

```text
ENABLE_JSON_PRODUCT_FACT_FALLBACK=false
```

- 生产请求中禁用 JSON fallback。
- 优先从 Java 传入的 `candidates` 或 Java internal API 获取商品事实。

#### 结构化查询节点

文件：

```text
AI-Clothing-Shopping-Assistant-System/clothing_assistant/agent/nodes.py
```

当前相关函数：

- `missing_info_gate_node`
- `run_catalog_lookup`
- `structured_lookup_node`
- `build_structured_draft`
- `answer_validator_node`

当前问题：

- 缺商品、颜色、尺码判断会调用本地 `find_matching_product`。
- 结构化价格和库存查询会调用本地 `run_structured_lookup`。

建议方向：

- 新增基于 Java `candidates` 的结构化 lookup。
- 有候选时，从候选中匹配商品、颜色、尺码、价格、库存。
- 无候选时，不回退生产 JSON，不编造。
- 候选不足时返回追问或保守提示。

#### 推荐排序和 product_refs

文件：

```text
AI-Clothing-Shopping-Assistant-System/clothing_assistant/application/recommendation_service.py
```

当前优势：

- `build_product_refs` 已经只从 Java `candidates` 生成引用。
- 会跳过缺少 `spu_id` 或 `sku_id` 的候选。
- 会跳过重复 SKU。

建议增强：

- 使用 `available_stock` 精确判断库存。
- 区分 `low_stock`、`in_stock`、真实库存数量。
- SKU 级候选改造后，根据尺码、颜色、预算、库存、场景标签排序。

#### Python API Schema

文件：

```text
AI-Clothing-Shopping-Assistant-System/clothing_assistant/api/schemas.py
```

当前状态：

- `ProductCandidate` 已包含 `available_stock`。
- 需要确认 Java 实际传入后增加契约测试。

## 推荐改造方案

### 方案 A：短期最小修复

目标：

- 先止住生产事实源不一致。
- 不大改 Java SQL。

改动：

1. Java `PythonProductCandidate` 增加 `available_stock`。
2. Java `toPythonCandidates` 传入候选可售库存。
3. Python 生产路径禁用 `product_catalog.json` fallback。
4. Python 无 Java 候选时不返回具体商品 `product_refs`。
5. 价格/库存问题如果候选不足，返回“当前缺少商品候选，请补充商品或稍后由 Java 商品库确认”。

优点：

- 改动小。
- 能快速避免 Python 本地 JSON 返回过期事实。

缺点：

- 如果 Java 候选仍是 SPU 聚合，推荐尺码和 SKU 精度仍有限。

### 方案 B：中期推荐方案

目标：

- 把 Java 推荐候选改为 SKU 级。
- 让 Python 推荐引用更准确。

改动：

1. Java `findRecommendationCandidates` 改为 SKU 级查询。
2. Java `RecommendationCandidate` 增加 `skuCode`、`availableStock`。
3. Java `PythonProductCandidate` 增加 `spu_code`、`sku_code`、`available_stock`。
4. Python 基于 SKU 级候选做尺码、颜色、库存、预算排序。
5. 前端继续根据 `spu_id`、`sku_id` 展示推荐卡片。

优点：

- 推荐结果可追溯到具体 SKU。
- 尺码推荐和商品推荐可以闭环。
- 更接近真实电商生产链路。

缺点：

- Java SQL、模型、测试改动更多。

### 方案 C：长期生产方案

目标：

- Python 完全通过 provider 访问商品事实。
- 支持 Java internal API 或请求候选 provider。

建议 provider 优先级：

```text
RequestCandidatesProvider
-> JavaApiProductFactProvider
-> JsonProductFactProvider
```

生产配置：

```text
ENABLE_JSON_PRODUCT_FACT_FALLBACK=false
JAVA_PRODUCT_FACT_PROVIDER_ENABLED=true
```

开发/测试配置：

```text
ENABLE_JSON_PRODUCT_FACT_FALLBACK=true
JAVA_PRODUCT_FACT_PROVIDER_ENABLED=false
```

优点：

- 生产和本地测试边界清晰。
- Python 不耦合具体数据源。
- 后续可替换 Java internal API、缓存或消息同步。

缺点：

- 抽象和配置更多，适合在短期修复后再做。

## 模糊画像推荐能力改造

### 问题定义

前端快捷词和用户自然语言里会出现大量模糊画像，例如：

- `学生党`
- `显高显瘦`
- `平价百搭`
- `上班通勤`
- `约会穿搭`
- `秋冬保暖`
- `我想找一套适合春天通勤的穿搭，显瘦一点，预算500以内`

这些词不是商品事实，而是导购语义。它们不能直接交给 RAG 猜商品，也不能让 Python 编造商品。正确做法是先把模糊需求映射成结构化偏好，再用 Java 候选池和 Python 排序执行推荐。

### 当前能力判断

当前 Python 只能部分支持模糊画像：

- `通勤`、`日常`、`显瘦`、`宽松`、`修身`、`春/夏/秋/冬` 已在推荐排序里有少量关键词匹配。
- `学生党` 没有稳定画像定义。
- `显高` 没有独立映射规则。
- `平价百搭` 没有被拆成预算、基础款、多场景、低饱和颜色等偏好。
- `预算500以内` 如果只写在消息里，Java 当前不会自动提取成 `budgetMax=500`。
- 前端快捷按钮当前主要是填入输入框，不会同步设置结构化筛选字段。

因此，当前系统可以给出部分泛化建议，但还不能称为稳定的“模糊画像推荐”。

### 推荐新增 Preference Parser

建议在 Python 增加一层需求解析：

```text
user_query
-> preference_parser
-> structured_preferences
-> Java candidates / Python ranking
-> product_refs
```

建议新增文件：

```text
AI-Clothing-Shopping-Assistant-System/clothing_assistant/application/preference_parser.py
```

输出结构示例：

```json
{
  "scene": ["commute"],
  "persona": ["student"],
  "visual_goals": ["taller", "slimmer"],
  "price_preference": "budget",
  "budget_max": 500,
  "season": ["spring"],
  "style_tags": ["commute", "minimal", "casual"],
  "preferred_colors": ["黑色", "藏青色", "灰色", "白色"],
  "fit_preference": ["regular", "straight"],
  "avoid_tags": ["bulky", "low_waist", "overly_formal"]
}
```

### 是否可以使用大模型做模糊映射

可以使用大模型，但边界必须清楚：

```text
大模型只做“模糊需求 -> 结构化偏好”的映射
不能直接决定商品事实
不能直接返回商品 ID
不能编造价格、库存、SKU
```

推荐链路：

```text
用户自然语言
-> LLM preference mapper
-> JSON schema 校验
-> 白名单归一化
-> Java 候选池筛选
-> Python 确定性排序
-> product_refs 只引用候选池商品
```

大模型适合处理：

- `学生党` 映射为低预算、基础款、耐穿、百搭、休闲通勤。
- `显高` 映射为高腰、短上衣、直筒/微锥、同色系、避免低腰拖沓。
- `显瘦` 映射为深色、垂感、合身、直线条、避免膨胀色和过度宽松。
- `平价百搭` 映射为预算优先、基础色、多场景、基础款。
- `约会穿搭` 映射为柔和颜色、轻正式、干净、有质感。

大模型不应该处理：

- 商品是否真实存在。
- 商品当前库存。
- 商品当前价格。
- 商品是否可购买。
- 下单、购物车、支付行为。

### LLM 输出约束

LLM mapper 必须输出严格 JSON，不能输出自然语言解释。

建议 schema：

```json
{
  "intent": "recommendation",
  "budget_max": 500,
  "category": null,
  "season": ["spring"],
  "style_tags": ["commute", "minimal"],
  "persona_tags": ["student"],
  "visual_goals": ["slimmer"],
  "preferred_colors": ["black", "navy", "gray"],
  "avoid_tags": ["bulky"],
  "confidence": 0.82,
  "missing_slots": []
}
```

校验规则：

- 所有 tag 必须来自白名单。
- `budget_max` 必须是数字，且来自用户明确表达或合理保守解析。
- `confidence` 低于阈值时，不强行筛选，只用于回答中说明偏好不确定。
- 未识别字段进入 `missing_slots`，必要时追问。
- LLM 输出不能直接进入 SQL，只能进入白名单映射后的查询对象。

### 确定性 fallback

即使接入大模型，也要保留规则版 fallback：

- 大模型不可用时，使用关键词词典解析。
- 大模型输出 JSON 无法校验时，丢弃该次映射结果。
- 大模型输出不在白名单内的 tag 时，丢弃非法 tag。
- 没有足够偏好时，Java 返回默认候选，Python 做保守排序。

建议词典示例：

| 用户词 | 结构化偏好 |
| --- | --- |
| 学生党 | `persona=student`, `price_preference=budget`, `style_tags=casual,basic` |
| 显高 | `visual_goals=taller`, `avoid_tags=low_waist,bulky` |
| 显瘦 | `visual_goals=slimmer`, `preferred_colors=black,navy`, `avoid_tags=oversized,bulky` |
| 平价 | `price_preference=budget` |
| 百搭 | `style_tags=basic,minimal`, `preferred_colors=black,white,gray,navy` |
| 通勤 | `scene=commute`, `style_tags=commute,minimal` |
| 秋冬保暖 | `season=autumn,winter`, `functional_tags=warm` |

### 不能依赖固定关键词

如果 parser 只写成下面这种形式：

```python
if "学生党" in normalized:
    ...

if "显高" in normalized:
    ...
```

用户就必须说中这些固定词，系统才能理解。这不适合真实导购场景，因为用户可能会说：

- `适合大学生日常上课`
- `别太成熟`
- `预算有限`
- `看起来腿长一点`
- `不显胖`
- `遮肉`
- `胯宽怎么穿`
- `日常都能搭`

这些表达和 `学生党`、`显高`、`显瘦`、`平价百搭` 是同一类需求，但字面不一样。因此推荐解析需要分三层：

```text
用户自然语言
-> 规则 signal dictionary 快速兜底
-> LLM preference mapper 做语义归一
-> schema 校验 + 白名单过滤
-> Java 商品库返回真实 candidates
-> Python 根据结构化偏好打分
-> 只返回 candidates 里的 product_refs
```

第一层是规则词典，不是单个硬编码词。示例：

```python
STUDENT_SIGNALS = [
    "学生党", "学生", "大学生", "校园", "上课", "上学",
    "宿舍", "社团", "年轻一点", "别太成熟", "日常上课",
]

SLIMMER_SIGNALS = [
    "显瘦", "遮肉", "藏肉", "不显胖", "修饰身材",
    "梨形", "微胖", "腿粗", "胯宽", "肚子", "肉肉",
]

TALLER_SIGNALS = [
    "显高", "小个子", "拉长比例", "显腿长", "比例好",
    "腿短", "不压个子", "精神一点",
]

BUDGET_SIGNALS = [
    "平价", "便宜", "不贵", "性价比", "预算有限",
    "学生预算", "别太贵", "划算", "入门款",
]

VERSATILE_SIGNALS = [
    "百搭", "好搭", "一衣多穿", "通用", "日常都能穿",
    "不挑场合", "基础款", "耐看",
]
```

第二层是 LLM mapper。它更适合处理没有命中词典的表达，例如：

```text
我想找适合大学生日常上课穿的，别太贵，看起来显腿长一点
```

期望 LLM 只输出结构化偏好：

```json
{
  "persona_tags": ["student"],
  "scene": ["campus", "daily"],
  "visual_goals": ["taller"],
  "price_preference": "budget",
  "style_tags": ["casual", "basic"],
  "avoid_tags": ["overly_formal", "bulky"],
  "confidence": 0.86
}
```

第三层是商品属性打分。LLM 和规则 parser 只负责理解用户需求，不能判断商品事实。真正推荐时仍然只看 Java 返回的候选商品字段，例如：

- `style_tags`
- `fit_type`
- `season`
- `material`
- `attribute_tags`
- `sale_price`
- `available_stock`
- `color`
- `size`

示例打分策略：

- `显高`：优先中高腰、短款上衣、直筒、同色系、拉长比例；降低低腰、拖沓、膨胀廓形分数。
- `显瘦`：优先直筒、垂顺、合身、深色、黑色、藏青色、直线条；降低过度宽松、膨胀色、厚重材质分数。
- `学生党`：优先预算友好、基础款、休闲、校园、耐穿；降低过度正式或价格过高商品分数。
- `平价百搭`：优先预算内、基础色、多场景、基础款；降低强风格、难搭配、超预算商品分数。

推荐理由也不要写成“命中关键词”。建议输出用户能理解的依据：

- `直筒版型更利于拉长腿部线条。`
- `黑色和直线条剪裁更适合显瘦需求。`
- `价格在预算内，适合学生党日常穿搭。`
- `基础色和简洁版型更容易一衣多穿。`

### Java 候选字段增强

为了让模糊画像推荐更准确，Java 商品候选需要补充更多可解释属性。

建议后续增加或利用现有 `product_attribute`：

- `occasion_tags`：通勤、约会、运动、旅行、校园。
- `visual_effect_tags`：显高、显瘦、遮肉、拉长比例。
- `silhouette`：直筒、A 字、锥形、修身、廓形。
- `waistline`：高腰、中腰、低腰。
- `length`：短款、常规、长款。
- `thickness`：轻薄、常规、厚实、保暖。
- `versatility`：基础款、百搭、多场景。

第一阶段可以先用 `style_tags`、`fit_type`、`season`、`material`、`sale_price` 做粗排；后续再补商品属性。

### Java 商品属性补数计划

当前 Python 已经可以读取 Java 候选里的 `attribute_tags`，但推荐质量取决于 Java 商品库是否真的有这些属性。如果商品库没有“腰线、版型、视觉效果、场景、百搭程度”等标签，Python 即使理解了 `显高`、`显瘦`、`学生党`，也只能做粗排。

建议优先使用现有 `product_attribute` 表承载这些标签，不先新增复杂表结构。第一阶段把属性以 `属性名:属性值` 的形式聚合进候选 `attribute_tags`：

```text
腰线:中高腰
腰线:低腰
下装版型:直筒
版型:修身
版型:过度宽松
视觉效果:显高
视觉效果:显瘦
视觉效果:遮肉
场景:校园
场景:通勤
风格:基础款
风格:百搭
厚度:保暖
长度:短款
```

推荐先补这些属性分组：

| 属性组 | 建议属性名 | 建议属性值 | 服务的模糊需求 |
| --- | --- | --- | --- |
| 腰线 | `腰线` | `高腰`、`中高腰`、`中腰`、`低腰` | 显高、小个子、显腿长、不压个子 |
| 下装版型 | `下装版型` | `直筒`、`锥形`、`阔腿`、`A字`、`修身`、`宽松` | 显高、显瘦、遮肉、腿粗、胯宽 |
| 上装版型 | `上装版型` | `短款`、`常规`、`长款`、`修身`、`宽松`、`廓形` | 显高、显瘦、百搭、通勤 |
| 视觉效果 | `视觉效果` | `显高`、`显瘦`、`遮肉`、`拉长比例`、`修饰身材` | 显高显瘦、遮肉、梨形、微胖 |
| 场景 | `场景` | `校园`、`通勤`、`约会`、`日常`、`运动`、`旅行` | 学生党、上班通勤、约会穿搭 |
| 风格 | `风格` | `基础款`、`百搭`、`休闲`、`简洁`、`轻正式`、`甜美` | 平价百搭、学生党、约会、通勤 |
| 颜色倾向 | `颜色倾向` | `深色`、`基础色`、`低饱和`、`亮色` | 显瘦、百搭、通勤 |
| 厚度 | `厚度` | `轻薄`、`常规`、`厚实`、`保暖` | 秋冬保暖、夏季透气 |
| 材质特征 | `材质特征` | `垂顺`、`挺括`、`柔软`、`透气`、`有弹力` | 显瘦、通勤、夏季 |
| 搭配难度 | `搭配难度` | `好搭`、`一衣多穿`、`强风格` | 百搭、学生党、预算有限 |

第一批补数优先级：

1. 裤装和半身裙先补 `腰线`、`下装版型`、`视觉效果`，因为它们直接影响 `显高`、`显瘦`。
2. 上衣、外套先补 `上装版型`、`长度`、`厚度`、`场景`，因为它们影响通勤、保暖和比例。
3. 全部商品补 `风格`、`场景`、`搭配难度`，因为它们影响 `学生党`、`平价百搭`、`约会穿搭`。
4. 对颜色已有字段的商品，额外补 `颜色倾向`，例如黑色、藏青色、深灰色可以补 `颜色倾向:深色`。

Java 侧开发点：

- `product_attribute`：补充上述属性数据，先从核心商品和推荐候选高频商品开始。
- `ProductMapper.xml`：继续把 `product_attribute` 聚合为 `attribute_tags`，保证 Python candidates 能收到这些标签。
- `RecommendationCandidate`：保留 `attributeTags` 字段，后续如要强类型化，再增加 `visualEffectTags`、`occasionTags` 等字段。
- `PythonProductCandidate`：继续输出 `attribute_tags`，字段名保持 snake_case。
- `AssistantService.toPythonCandidates`：确认 Java `attributeTags` 到 Python `attribute_tags` 不丢失。

建议不要一开始就把所有属性强类型化成多个 Java 字段。第一阶段用 `attribute_tags` 快速补齐推荐可用信息；等推荐效果稳定后，再把高频属性拆成结构化字段。

补数质量规则：

- 不写无法从商品信息判断的标签，例如没有证据不要打 `视觉效果:显瘦`。
- 不把价格、库存、SKU、是否可购买写进 `attribute_tags`。
- 同一属性组尽量只选 1 到 2 个核心值，避免一个商品标签过多导致排序噪声。
- 用户体型相关词只作为推荐目标，不直接写成商品事实。例如商品可以写 `视觉效果:遮肉`，不要写 `适合梨形身材`，除非商品运营明确维护该结论。
- 属性值命名要稳定，避免同时出现 `中高腰`、`中/高腰`、`中高腰款` 三种写法。

Java 商品属性补数验收示例：

```json
{
  "spuId": 1001,
  "skuId": 2001,
  "name": "黑色中高腰直筒裤",
  "attributeTags": [
    "腰线:中高腰",
    "下装版型:直筒",
    "视觉效果:显高",
    "视觉效果:显瘦",
    "颜色倾向:深色",
    "场景:校园",
    "风格:基础款",
    "搭配难度:好搭"
  ]
}
```

这类候选进入 Python 后，面对 `大学生日常上课，别太贵，显腿长，还要遮肉`，应该比 `腰线:低腰`、`版型:过度宽松`、`风格:强风格` 的候选排序更靠前。

### 前端快捷词处理建议

前端快捷词不要只填输入框。建议两种方式二选一：

1. 仍然只传 `message`，由 Python `preference_parser` 解析全部模糊词。
2. 快捷词点击时同时传隐藏结构化偏好，例如 `style=casual`、`season=winter`、`budgetMax=500`。

更推荐第一种作为主路径，因为用户自然输入也需要同样能力。第二种可作为快捷按钮的辅助增强。

### 模糊画像验收标准

- 输入 `学生党 平价百搭` 时，推荐结果优先低价、基础款、休闲或通勤商品。
- 输入 `显高显瘦` 时，推荐理由能说明比例、版型、颜色或线条依据。
- 输入 `春天通勤 预算500以内` 时，`budget_max=500` 能被解析并参与候选筛选或排序。
- LLM mapper 不可用时，规则 fallback 仍能给出保守推荐。
- LLM mapper 输出非法 tag 时，不影响主流程。
- 最终 `product_refs` 仍必须来自 Java 候选池。
- 模糊画像不能让 RAG 或 LLM 编造价格、库存、SKU。

## 建议开发顺序

### 第一阶段：数据源边界止血

1. 明确生产环境禁用 Python `product_catalog.json` fallback。
2. Java 候选补齐 `available_stock`。
3. Python 无候选时不返回具体 `product_refs`。
4. Python 价格/库存查询不再读取生产 JSON。
5. 增加测试覆盖无候选、候选外引用、价格/库存边界。

### 第二阶段：SKU 级候选

1. Java SQL 改成 SKU 级候选。
2. Java 模型补齐 `skuCode`、`availableStock`。
3. Java 到 Python DTO 补齐 `spu_code`、`sku_code`、`available_stock`。
4. Python 排序使用 SKU 级字段。
5. 补充 Java Mapper 测试和 Python 推荐排序测试。

### 第三阶段：ProductFactProvider 抽象

1. 在 Python 增加 `ProductFactProvider` 接口。
2. 实现 `RequestCandidatesProvider`。
3. 保留 `JsonProductFactProvider` 仅用于 demo/test。
4. 后续再接 `JavaApiProductFactProvider`。
5. 在文档中写清楚生产配置和本地配置差异。

### 第四阶段：RAG 边界清理

1. 检查向量库源文件，只保留解释性知识。
2. 不把价格、库存、SKU、订单状态写入 RAG 文档。
3. 增加知识库重建说明。
4. 增加 RAG 回答验收测试，确保不输出强事实。

### 第五阶段：模糊画像推荐

1. 重构 Python `preference_parser`，把固定 `if "学生党"` 改成 signal dictionary，例如 `STUDENT_SIGNALS`、`SLIMMER_SIGNALS`、`TALLER_SIGNALS`。
2. 增加 `contains_any_signal()`、`append_unique()` 等小工具，保证同义词扩展不影响主流程。
3. 增加可选 LLM mapper，让大模型作为主语义映射层；规则词典作为失败、关闭或低置信度时的 fallback。
4. 对 LLM 输出做 JSON schema 校验和白名单归一化，非法字段直接丢弃。
5. 将结构化偏好接入推荐排序，特别是 `visual_goals`、`persona_tags`、`price_preference`、`avoid_tags`。
6. 增强推荐理由模板，避免输出“命中关键词”，改为解释版型、颜色、价格、场景等推荐依据。
7. 增强 Java 候选商品属性，逐步补齐视觉效果、场景、版型、长度、厚度等字段。
8. 前端快捷词复用同一套 parser，不另写一套推荐规则。

### 第六阶段：Java 商品属性补数

1. 盘点现有 `product_attribute` 数据，确认哪些商品已经有版型、场景、材质、季节等属性。
2. 建立第一批属性枚举：`腰线`、`下装版型`、`上装版型`、`视觉效果`、`场景`、`风格`、`颜色倾向`、`厚度`、`材质特征`、`搭配难度`。
3. 先给推荐候选高频商品补 `attribute_tags`，优先覆盖裤装、裙装、外套、基础上衣。
4. 调整或确认 `ProductMapper.xml` 聚合 `product_attribute` 为 `attribute_tags`。
5. 增加 Java Mapper 测试，断言 `attributeTags` 包含 `腰线:中高腰`、`视觉效果:显瘦` 等标签。
6. 增加 Java 到 Python DTO 测试，断言 `attribute_tags` 能传到 Python。
7. 增加 Python 排序测试，断言有高质量 `attribute_tags` 的候选在 `显高`、`显瘦`、`学生党` 场景中排序更靠前。

## 验收标准

### 数据源验收

- 生产路径中，Python 不用本地 JSON 回答价格、库存。
- 商品事实以 Java 传入候选或 Java internal API 为准。
- Java 未提供候选时，Python 不编造具体商品引用。

### 推荐引用验收

- `product_refs[*].spu_id` 必须存在于请求 `candidates`。
- `product_refs[*].sku_id` 必须存在于请求 `candidates`。
- 缺少 `spu_id` 或 `sku_id` 的候选不会被推荐。
- 重复 SKU 不会重复出现在 `product_refs`。

### 库存价格验收

- 用户问价格时，答案来自 Java 候选或 Java 商品接口。
- 用户问库存时，答案来自 Java `available_stock` 或明确提示缺少候选信息。
- 无库存 SKU 不应进入推荐结果。
- 低库存 SKU 可以推荐，但排序和理由应体现库存风险。

### RAG 验收

- RAG 只回答解释性知识。
- RAG 回答不包含商品价格、实时库存、SKU 可购买状态。
- 弱检索或无检索证据时进入保守兜底。

### 契约验收

- Java DTO、Python Pydantic schema、接口文档字段一致。
- `available_stock` 在 Java 请求和 Python debug 中可见。
- SSE `done` 事件仍只返回用户可见字段，不暴露内部 debug。

### 模糊画像验收

- `学生党` 能映射为预算友好、基础款、休闲/校园或通勤偏好。
- `显高显瘦` 能映射为视觉目标，并体现在排序和推荐理由中。
- `平价百搭` 能映射为预算优先、基础色、多场景、基础款。
- `预算500以内` 能解析成 `budget_max=500`。
- LLM mapper 输出失败时，规则 fallback 不影响主流程。
- LLM mapper 不直接返回商品 ID、价格、库存或 SKU。

## 需要增加或调整的测试

### Java 测试

建议覆盖：

- `findRecommendationCandidates` 返回 SKU 级候选。
- 无库存 SKU 不返回。
- 下架 SKU 不返回。
- `availableStock` 正确映射。
- `toPythonCandidates` 正确输出 `available_stock`。
- 预算过滤仍然生效。
- `findRecommendationCandidates` 返回 `attributeTags`。
- `attributeTags` 能包含 `腰线:中高腰`、`下装版型:直筒`、`视觉效果:显瘦`、`场景:校园`。
- Java 到 Python DTO 能输出 snake_case 的 `attribute_tags`。
- 缺少商品属性时，候选仍可返回，但不会伪造属性标签。

### Python 测试

建议覆盖：

- 无 `candidates` 时 `product_refs=[]`。
- 候选外商品不会被引用。
- `available_stock=0` 的候选不会被推荐。
- 尺码推荐只推荐匹配尺码或备选尺码的 SKU。
- 价格/库存问题在生产禁用 JSON fallback 时不会读取 `product_catalog.json`。
- RAG 不回答价格和库存。
- `preference_parser` 能解析 `学生党`、`显高显瘦`、`平价百搭`、`预算500以内`。
- LLM mapper 非法 JSON 或非法 tag 会被丢弃。
- 模糊画像排序不会引用候选池外商品。
- `大学生日常上课，别太贵，显腿长，还要遮肉` 能映射为 `student`、`budget`、`taller`、`slimmer`。
- 带 `腰线:中高腰`、`下装版型:直筒`、`颜色倾向:深色` 的候选排序高于 `腰线:低腰`、`版型:过度宽松` 的候选。
- 推荐理由能输出比例、显瘦、学生日常、百搭等用户可理解依据。

### 集成测试

建议覆盖：

- Java 调 Python `/chat`，传入候选后 Python 返回候选内 `product_refs`。
- Java 收到 Python `product_refs` 后再次按 Java 候选过滤。
- 前端推荐卡片展示的商品与 Java 商品库一致。
- 用户输入模糊画像后，Python 返回的推荐理由包含结构化偏好依据。

## 不做的事情

本次不做：

- 不引入新的向量数据库。
- 不把 Java 数据库完整同步到 Python。
- 不让 Python 直接修改库存、购物车、订单或支付。
- 不让 RAG 替代商品数据库。
- 不在 Python 长期维护第二套商品事实。
- 不绕过 Java 鉴权和会话归属校验。

## 决策建议

建议先按以下顺序执行：

1. 先做方案 A，快速消除 Python 本地 JSON 在生产路径中的事实污染。
2. 再做方案 B，把 Java 候选改为 SKU 级，解决推荐准确性问题。
3. 最后做方案 C，把商品事实访问抽象成 provider，降低后续维护成本。

如果只做一个阶段，优先做第一阶段。它能最快解决“资料库和 Java 后端数据库不对称”的核心风险。
