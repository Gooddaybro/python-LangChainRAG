# User Feedback Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a lightweight user feedback loop that records commerce and AI recommendation behavior, summarizes recent user interests, and passes those signals into the Python recommendation context.

**Architecture:** Java remains the source of truth for behavior events. Version one writes events synchronously to MySQL through a single behavior module, then aggregates recent signals for `AssistantContextService`; MQ is documented as a later replacement behind the same service boundary. The frontend only records recommendation interaction events, and Python only consumes Java-provided context fields.

**Tech Stack:** Java 21, Spring Boot 4.0.6, MyBatis XML, Flyway, MySQL/H2 tests, JUnit 5, Mockito, React, TypeScript, Vitest, Playwright, FastAPI/Pydantic, Python unittest.

## Global Constraints

- Do not introduce RabbitMQ, Kafka, RocketMQ, or any real MQ dependency in version one.
- Do not let Python or the frontend write product, price, inventory, order, payment, or user ownership facts.
- Do not let the frontend create backend-owned behavior events such as `PAYMENT_SUCCESS`.
- Do not let behavior event recording roll back successful cart, favorite, order, or payment business flows.
- Use MySQL `behavior_event` as the behavior event fact store; Redis is not a long-term behavior event source.
- Keep Java-Python request fields backward compatible by adding optional behavior-context fields.
- Follow `AGENTS.md` and `docs/commenting-guidelines.md` before changing Java source, Mapper XML, or cross-service contracts.

---

## File Structure

### Java backend

- Create: `backend/src/main/resources/db/migration/V14__behavior_event_schema.sql`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/model/BehaviorEvent.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/model/BehaviorProductSignal.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/mapper/BehaviorMapper.java`
- Create: `backend/src/main/resources/mapper/behavior/BehaviorMapper.xml`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/dto/BehaviorEventRequest.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/dto/BehaviorEventResponse.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/dto/BehaviorSummaryResponse.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventType.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventSource.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventCommand.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventService.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorSummaryService.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/api/BehaviorController.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/favorite/service/FavoriteService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/cart/service/CartService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/order/service/OrderService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/payment/service/PaymentService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/service/AssistantContextService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/dto/AssistantContext.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/dto/PythonUserContext.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/service/AssistantService.java`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorMapperTests.java`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorEventServiceTests.java`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorControllerTests.java`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorSummaryServiceTests.java`
- Modify tests: `FavoriteServiceTests.java`, `CartServiceTests.java`, `OrderServiceTests.java`, `PaymentServiceTests.java`, `AssistantContextServiceTests.java`, `AssistantServiceTests.java`

### Frontend

- Modify: `frontend/src/shared/api/types.ts`
- Modify: `frontend/src/shared/api/client.ts`
- Modify: `frontend/src/features/commerce-action/commerceActions.ts`
- Modify: `frontend/src/features/commerce-action/useCommerceAction.ts`
- Modify: `frontend/src/features/catalog/ProductCard.tsx`
- Modify: `frontend/src/pages/AiShoppingPage.tsx`
- Modify tests: `frontend/src/shared/api/client.test.ts`
- Modify tests: `frontend/src/features/commerce-action/commerceActions.test.ts`
- Modify e2e fixture: `frontend/e2e/fixtures/api.ts`
- Modify e2e test: `frontend/e2e/ai-shopping.spec.ts`

### Python AI project

- Modify: `AI-Clothing-Shopping-Assistant-System/clothing_assistant/api/schemas.py`
- Modify: `AI-Clothing-Shopping-Assistant-System/clothing_assistant/application/recommendation_service.py`
- Modify tests: `AI-Clothing-Shopping-Assistant-System/tests/test_recommendation_service.py`
- Optional docs sync: `AI-Clothing-Shopping-Assistant-System/docs/superpowers/plans/2026-07-02-user-feedback-loop.md`

---

### Task 1: Java Behavior Event Persistence

**Files:**
- Create: `backend/src/main/resources/db/migration/V14__behavior_event_schema.sql`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/model/BehaviorEvent.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/model/BehaviorProductSignal.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/mapper/BehaviorMapper.java`
- Create: `backend/src/main/resources/mapper/behavior/BehaviorMapper.xml`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorMapperTests.java`

**Interfaces:**
- Produces: `BehaviorMapper.insert(BehaviorEvent event): int`
- Produces: `BehaviorMapper.findRecentSignals(Long userId, LocalDateTime since, int limit): List<BehaviorProductSignal>`
- Produces: `BehaviorEvent` fields: `eventId`, `userId`, `eventType`, `source`, `spuId`, `skuId`, `threadId`, `requestId`, `orderNo`, `quantity`, `eventTime`, `metadataJson`

- [ ] **Step 1: Write failing mapper tests**

```java
@Test
void insertBehaviorEventIsIdempotentByEventId() {
    BehaviorEvent event = behaviorEvent("evt-1", userId, "RECOMMENDATION_CLICKED", 1001L, 2001L);

    assertThat(behaviorMapper.insert(event)).isEqualTo(1);
    assertThat(behaviorMapper.insert(behaviorEvent("evt-1", userId, "RECOMMENDATION_CLICKED", 1001L, 2001L))).isZero();
}

@Test
void findsRecentSignalsWithProductCategoryAndStyleTags() {
    behaviorMapper.insert(behaviorEvent("evt-interest", userId, "RECOMMENDATION_CLICKED", 1002L, 2102L));

    List<BehaviorProductSignal> signals = behaviorMapper.findRecentSignals(userId, LocalDateTime.now().minusDays(30), 20);

    assertThat(signals).extracting(BehaviorProductSignal::getSpuId).contains(1002L);
    assertThat(signals).extracting(BehaviorProductSignal::getCategoryName).contains("外套");
    assertThat(signals).anySatisfy(signal -> assertThat(signal.getStyleTags()).contains("commute"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/seekinward/Documents/推荐项目/IntelligentOutfitRecommendationSystem/backend
sh mvnw -q -Dtest=BehaviorMapperTests test
```

Expected: compilation failure because `BehaviorMapperTests`, `BehaviorMapper`, and behavior model classes do not exist.

- [ ] **Step 3: Add migration and mapper model classes**

Use this table definition:

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

Create `BehaviorEvent` and `BehaviorProductSignal` as simple Java model classes with class-level Javadocs explaining that behavior data is recommendation feedback, not a transaction fact.

- [ ] **Step 4: Add mapper interface and XML**

`BehaviorMapper.insert` must use MySQL-compatible idempotency:

```xml
<insert id="insert" parameterType="com.recommendation.intelligentoutfitrecommendationsystem.behavior.model.BehaviorEvent"
        useGeneratedKeys="true" keyProperty="id">
    INSERT INTO behavior_event (
        event_id, user_id, event_type, source, spu_id, sku_id,
        thread_id, request_id, order_no, quantity, event_time, metadata_json
    ) VALUES (
        #{eventId}, #{userId}, #{eventType}, #{source}, #{spuId}, #{skuId},
        #{threadId}, #{requestId}, #{orderNo}, #{quantity}, #{eventTime}, #{metadataJson}
    )
    ON DUPLICATE KEY UPDATE
        id = id
</insert>
```

`findRecentSignals` should join `product_spu`, `category`, and `product_style_tag/style_tag`, returning `GROUP_CONCAT(st.code ORDER BY st.id SEPARATOR ',') AS style_tags`.

- [ ] **Step 5: Run mapper test to verify it passes**

Run:

```bash
sh mvnw -q -Dtest=BehaviorMapperTests test
```

Expected: `BehaviorMapperTests` passes with 0 failures.

- [ ] **Step 6: Commit**

```bash
git add backend/src/main/resources/db/migration/V14__behavior_event_schema.sql \
  backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/model \
  backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/mapper \
  backend/src/main/resources/mapper/behavior/BehaviorMapper.xml \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorMapperTests.java
git commit -m "feat: add behavior event persistence"
```

---

### Task 2: Java Behavior Event API and Service

**Files:**
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/dto/BehaviorEventRequest.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/dto/BehaviorEventResponse.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventType.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventSource.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventCommand.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorEventService.java`
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/api/BehaviorController.java`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorEventServiceTests.java`
- Test: `backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorControllerTests.java`

**Interfaces:**
- Consumes: `BehaviorMapper.insert(BehaviorEvent event): int`
- Produces: `BehaviorEventService.recordRecommendationInteraction(Long userId, BehaviorEventRequest request): BehaviorEventResponse`
- Produces: `BehaviorEventService.recordBusinessEvent(BehaviorEventCommand command): void`
- Produces: `POST /api/behavior/events`

- [ ] **Step 1: Write failing service tests**

```java
@Test
void frontendCannotRecordBackendOnlyEvents() {
    BehaviorEventRequest request = new BehaviorEventRequest(
            "evt-payment-forged",
            "PAYMENT_SUCCESS",
            "ASSISTANT_RECOMMENDATION",
            1001L,
            null,
            "thread-1",
            null,
            Map.of()
    );

    assertThatThrownBy(() -> service.recordRecommendationInteraction(10L, request))
            .isInstanceOf(BadRequestException.class)
            .hasMessage("eventType is not allowed for frontend behavior events: PAYMENT_SUCCESS");
}

@Test
void duplicateFrontendEventReturnsSuccess() {
    when(behaviorMapper.insert(any(BehaviorEvent.class))).thenReturn(0);

    BehaviorEventResponse response = service.recordRecommendationInteraction(
            10L,
            new BehaviorEventRequest("evt-click-1", "RECOMMENDATION_CLICKED", null, 1001L, 2001L, "thread-1", null, Map.of("position", 1))
    );

    assertThat(response.eventId()).isEqualTo("evt-click-1");
}
```

- [ ] **Step 2: Write failing controller tests**

```java
@Test
void loggedInUserCanRecordRecommendationClick() throws Exception {
    mockMvc.perform(post("/api/behavior/events")
            .with(jwt().jwt(jwt -> jwt.subject("10").claim("username", "demo")))
            .contentType(MediaType.APPLICATION_JSON)
            .content("""
                    {
                      "eventId":"evt-click-1",
                      "eventType":"RECOMMENDATION_CLICKED",
                      "spuId":1001,
                      "skuId":2001,
                      "threadId":"thread-1",
                      "metadata":{"position":1}
                    }
                    """))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.eventId").value("evt-click-1"));
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
sh mvnw -q -Dtest=BehaviorEventServiceTests,BehaviorControllerTests test
```

Expected: compilation failure because the DTOs, service, and controller do not exist.

- [ ] **Step 4: Implement DTOs and enums**

Create `BehaviorEventType` with exactly these values:

```java
FAVORITE_ADD,
CART_ADD,
ORDER_CREATED,
PAYMENT_SUCCESS,
RECOMMENDATION_EXPOSED,
RECOMMENDATION_CLICKED,
RECOMMENDATION_CART_ADD,
RECOMMENDATION_FAVORITE_ADD
```

Create `BehaviorEventSource` with `COMMERCE`, `ASSISTANT_RECOMMENDATION`, and `SYSTEM`.

`BehaviorEventRequest` should be a record with `eventId`, `eventType`, `source`, `spuId`, `skuId`, `threadId`, `quantity`, and `metadata`.

- [ ] **Step 5: Implement `BehaviorEventService`**

Rules:

```text
recordRecommendationInteraction:
  - userId must be positive
  - eventId must be nonblank or generated
  - eventType must be one of RECOMMENDATION_EXPOSED, RECOMMENDATION_CLICKED, RECOMMENDATION_CART_ADD, RECOMMENDATION_FAVORITE_ADD
  - source defaults to ASSISTANT_RECOMMENDATION
  - metadata map serializes to JSON string

recordBusinessEvent:
  - catches RuntimeException and logs warning
  - never throws into commerce flows
  - source defaults to COMMERCE
```

- [ ] **Step 6: Implement `BehaviorController`**

Controller:

```java
@RestController
@RequestMapping("/api/behavior/events")
public class BehaviorController {
    @PostMapping
    public ApiResponse<BehaviorEventResponse> recordEvent(
            Authentication authentication,
            @Valid @RequestBody BehaviorEventRequest request
    ) {
        CurrentUser currentUser = CurrentUser.from(authentication);
        return ApiResponse.ok(behaviorEventService.recordRecommendationInteraction(currentUser.userId(), request));
    }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run:

```bash
sh mvnw -q -Dtest=BehaviorEventServiceTests,BehaviorControllerTests test
```

Expected: both test classes pass with 0 failures.

- [ ] **Step 8: Commit**

```bash
git add backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorEventServiceTests.java \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/BehaviorControllerTests.java
git commit -m "feat: add behavior event api"
```

---

### Task 3: Record Commerce Behavior Events

**Files:**
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/favorite/service/FavoriteService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/cart/service/CartService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/order/service/OrderService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/payment/service/PaymentService.java`
- Modify tests: `FavoriteServiceTests.java`, `CartServiceTests.java`, `OrderServiceTests.java`, `PaymentServiceTests.java`

**Interfaces:**
- Consumes: `BehaviorEventService.recordBusinessEvent(BehaviorEventCommand command): void`
- Produces: backend business events `FAVORITE_ADD`, `CART_ADD`, `ORDER_CREATED`, `PAYMENT_SUCCESS`

- [ ] **Step 1: Write failing tests for each business service**

Favorite:

```java
@Test
void addFavoriteRecordsBehaviorOnlyWhenFavoriteIsNew() {
    when(favoriteMapper.selectByUserIdAndProductId(10L, 1001L)).thenReturn(null);
    when(favoriteMapper.selectByUserId(10L)).thenReturn(List.of(new UserFavorite()));

    service.addFavorite(10L, 1001L);

    verify(behaviorEventService).recordBusinessEvent(argThat(command ->
            "FAVORITE_ADD".equals(command.eventType())
                    && command.userId().equals(10L)
                    && command.spuId().equals(1001L)
    ));
}
```

Cart:

```java
@Test
void addItemRecordsCartAddBehaviorAfterUpsert() {
    when(cartMapper.existsSkuById(2102L)).thenReturn(1);
    when(cartMapper.findItemsByUserId(10L)).thenReturn(List.of(cartItemView(2102L, 1)));

    service.addItem(10L, 2102L, 1);

    verify(behaviorEventService).recordBusinessEvent(argThat(command ->
            "CART_ADD".equals(command.eventType())
                    && command.userId().equals(10L)
                    && command.skuId().equals(2102L)
                    && command.quantity().equals(1)
    ));
}
```

Payment:

```java
@Test
void successfulPaymentRecordsPaymentSuccessForEachOrderItem() {
    // Extend existing successful payment test and verify a PAYMENT_SUCCESS command
    verify(behaviorEventService).recordBusinessEvent(argThat(command ->
            "PAYMENT_SUCCESS".equals(command.eventType())
                    && command.orderNo().equals("ORDPAY1")
                    && command.spuId().equals(1002L)
                    && command.skuId().equals(2102L)
    ));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
sh mvnw -q -Dtest=FavoriteServiceTests,CartServiceTests,OrderServiceTests,PaymentServiceTests test
```

Expected: constructor or verification failures because services do not inject `BehaviorEventService` yet.

- [ ] **Step 3: Inject `BehaviorEventService` into commerce services**

Add constructor dependencies. Existing tests using `@InjectMocks` should get a `@Mock BehaviorEventService`.

- [ ] **Step 4: Record events**

Event ID strategy:

```text
favorite:add:{userId}:{spuId}
cart:add:{userId}:{skuId}:{requestId-or-current-nano-fallback}
order:created:{orderNo}:{skuId}
payment:success:{paymentNo}:{skuId}
```

For order and payment, record one event per order item so behavior summaries can aggregate `spuId`, `skuId`, category, and style.

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
sh mvnw -q -Dtest=FavoriteServiceTests,CartServiceTests,OrderServiceTests,PaymentServiceTests test
```

Expected: all four test classes pass with 0 failures.

- [ ] **Step 6: Commit**

```bash
git add backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/favorite/service/FavoriteService.java \
  backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/cart/service/CartService.java \
  backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/order/service/OrderService.java \
  backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/payment/service/PaymentService.java \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/favorite/FavoriteServiceTests.java \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/cart/CartServiceTests.java \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/order/OrderServiceTests.java \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/payment/PaymentServiceTests.java
git commit -m "feat: record commerce behavior events"
```

---

### Task 4: Behavior Summary and Java-Python Context

**Files:**
- Create: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/dto/BehaviorSummaryResponse.java`
- Create/modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/service/BehaviorSummaryService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior/api/BehaviorController.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/service/AssistantContextService.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/dto/AssistantContext.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/dto/PythonUserContext.java`
- Modify: `backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant/service/AssistantService.java`
- Test: `BehaviorSummaryServiceTests.java`
- Modify tests: `AssistantContextServiceTests.java`, `AssistantServiceTests.java`

**Interfaces:**
- Consumes: `BehaviorMapper.findRecentSignals(userId, since, limit)`
- Produces: `BehaviorSummaryService.getSummary(Long userId): BehaviorSummaryResponse`
- Produces: `GET /api/me/behavior-summary`
- Produces additional Python user-context fields: `recent_interest_spu_ids`, `recent_cart_spu_ids`, `recent_purchased_spu_ids`, `behavior_preferred_categories`, `behavior_preferred_styles`

- [ ] **Step 1: Write failing summary service test**

```java
@Test
void summaryGroupsRecentInterestCartPurchaseAndPreferences() {
    when(behaviorMapper.findRecentSignals(eq(10L), any(LocalDateTime.class), eq(200)))
            .thenReturn(List.of(
                    signal("RECOMMENDATION_CLICKED", 1001L, "外套", "commute,minimal"),
                    signal("CART_ADD", 1002L, "裤子", "casual"),
                    signal("PAYMENT_SUCCESS", 1003L, "外套", "commute")
            ));

    BehaviorSummaryResponse summary = service.getSummary(10L);

    assertThat(summary.recentInterestSpuIds()).containsExactly(1001L);
    assertThat(summary.recentCartSpuIds()).containsExactly(1002L);
    assertThat(summary.recentPurchasedSpuIds()).containsExactly(1003L);
    assertThat(summary.preferredCategories()).containsExactly("外套", "裤子");
    assertThat(summary.preferredStyles()).containsExactly("commute", "minimal", "casual");
}
```

- [ ] **Step 2: Write failing assistant context tests**

```java
@Test
void assistantContextIncludesBehaviorSummary() {
    BehaviorSummaryResponse summary = new BehaviorSummaryResponse(
            List.of(1001L),
            List.of(1002L),
            List.of(1003L),
            List.of("外套"),
            List.of("commute"),
            List.of()
    );
    when(behaviorSummaryService.getSummary(10L)).thenReturn(summary);

    AssistantContext context = service.buildContext(10L, "thread-behavior", request);

    assertThat(context.behaviorSummary()).isEqualTo(summary);
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
sh mvnw -q -Dtest=BehaviorSummaryServiceTests,AssistantContextServiceTests,AssistantServiceTests test
```

Expected: compilation failures because `BehaviorSummaryService` and new context fields do not exist.

- [ ] **Step 4: Implement summary service and debug endpoint**

`BehaviorSummaryService` rules:

```text
recentInterestSpuIds: RECOMMENDATION_CLICKED, RECOMMENDATION_FAVORITE_ADD, FAVORITE_ADD
recentCartSpuIds: RECOMMENDATION_CART_ADD, CART_ADD
recentPurchasedSpuIds: PAYMENT_SUCCESS
preferredCategories: category frequency desc, max 5
preferredStyles: style frequency desc, max 5
per list max: 10 spu IDs, preserve recency order
window: 30 days
```

`GET /api/me/behavior-summary` returns `ApiResponse<BehaviorSummaryResponse>`.

- [ ] **Step 5: Extend assistant context and Python DTO mapping**

Add `BehaviorSummaryResponse behaviorSummary` to `AssistantContext`.

Add optional fields to `PythonUserContext`:

```java
@JsonProperty("recent_interest_spu_ids") List<Long> recentInterestSpuIds,
@JsonProperty("recent_cart_spu_ids") List<Long> recentCartSpuIds,
@JsonProperty("recent_purchased_spu_ids") List<Long> recentPurchasedSpuIds,
@JsonProperty("behavior_preferred_categories") List<String> behaviorPreferredCategories,
@JsonProperty("behavior_preferred_styles") List<String> behaviorPreferredStyles
```

Update `AssistantService.toPythonUserContext(...)` so Java sends those fields from `context.behaviorSummary()`.

- [ ] **Step 6: Run tests to verify they pass**

Run:

```bash
sh mvnw -q -Dtest=BehaviorSummaryServiceTests,BehaviorControllerTests,AssistantContextServiceTests,AssistantServiceTests test
```

Expected: all selected tests pass with 0 failures.

- [ ] **Step 7: Commit**

```bash
git add backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior \
  backend/src/main/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/behavior \
  backend/src/test/java/com/recommendation/intelligentoutfitrecommendationsystem/assistant
git commit -m "feat: add behavior summary to assistant context"
```

---

### Task 5: Frontend Recommendation Interaction Events

**Files:**
- Modify: `frontend/src/shared/api/types.ts`
- Modify: `frontend/src/shared/api/client.ts`
- Modify: `frontend/src/features/commerce-action/commerceActions.ts`
- Modify: `frontend/src/features/commerce-action/useCommerceAction.ts`
- Modify: `frontend/src/features/catalog/ProductCard.tsx`
- Modify: `frontend/src/pages/AiShoppingPage.tsx`
- Modify: `frontend/src/shared/api/client.test.ts`
- Modify: `frontend/src/features/commerce-action/commerceActions.test.ts`
- Modify: `frontend/e2e/fixtures/api.ts`
- Modify: `frontend/e2e/ai-shopping.spec.ts`

**Interfaces:**
- Consumes: `POST /api/behavior/events`
- Produces: frontend events `RECOMMENDATION_EXPOSED`, `RECOMMENDATION_CLICKED`, `RECOMMENDATION_CART_ADD`, `RECOMMENDATION_FAVORITE_ADD`

- [ ] **Step 1: Write failing API client test**

```ts
it("records recommendation behavior events with bearer auth", async () => {
  localStorage.setItem("ior.accessToken", "token-1");
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    text: () => Promise.resolve(JSON.stringify({ data: { eventId: "evt-1" } }))
  });
  vi.stubGlobal("fetch", fetchMock);

  await api.recordBehaviorEvent({
    eventId: "evt-1",
    eventType: "RECOMMENDATION_CLICKED",
    spuId: 1001,
    skuId: 2001,
    threadId: "thread-1",
    metadata: { position: 1 }
  });

  expect(fetchMock).toHaveBeenCalledWith(
    "/api/behavior/events",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        eventId: "evt-1",
        eventType: "RECOMMENDATION_CLICKED",
        spuId: 1001,
        skuId: 2001,
        threadId: "thread-1",
        metadata: { position: 1 }
      })
    })
  );
});
```

- [ ] **Step 2: Write failing commerce action test**

```ts
it("preserves recommendation source metadata on commerce actions", () => {
  const action = buildAddToCartAction(candidate, 1, {
    source: "ASSISTANT_RECOMMENDATION",
    threadId: "thread-1"
  });

  expect(action.source).toBe("ASSISTANT_RECOMMENDATION");
  expect(action.spuId).toBe(1);
  expect(action.threadId).toBe("thread-1");
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
cd /Users/seekinward/Documents/推荐项目/IntelligentOutfitRecommendationSystem/frontend
npm test -- --run src/shared/api/client.test.ts src/features/commerce-action/commerceActions.test.ts
```

Expected: TypeScript failures because behavior event API and action metadata do not exist.

- [ ] **Step 4: Add frontend behavior types and API method**

Add:

```ts
export type BehaviorEventType =
  | "RECOMMENDATION_EXPOSED"
  | "RECOMMENDATION_CLICKED"
  | "RECOMMENDATION_CART_ADD"
  | "RECOMMENDATION_FAVORITE_ADD";

export type BehaviorEventRequest = {
  eventId: string;
  eventType: BehaviorEventType;
  spuId: number;
  skuId?: number;
  threadId?: string;
  quantity?: number;
  metadata?: Record<string, unknown>;
};
```

Add `api.recordBehaviorEvent(request)` using `POST /api/behavior/events`.

- [ ] **Step 5: Track AI recommendation exposure and click**

In `AiShoppingPage`, use a `useRef<Set<string>>` to dedupe exposure events:

```text
dedupe key: `${threadId}:${spuId}:${skuId}:exposed`
only send exposure when recommendationMeta.hasAiResult is true
ignore errors from api.recordBehaviorEvent
```

Pass `threadId`, `source`, and `onBehaviorEvent` into `ProductCard`.

In `ProductCard`, record click on the article and stop propagation from buttons.

- [ ] **Step 6: Record recommendation cart add after successful add-to-cart**

Extend `PendingCommerceAction` with `spuId`, optional `source`, and optional `threadId`.

In `useCommerceAction.confirm`, after `api.addCartItem` succeeds for an assistant recommendation action, call:

```ts
await api.recordBehaviorEvent({
  eventId: `recommendation-cart-add:${pendingAction.threadId}:${pendingAction.spuId}:${pendingAction.skuId}:${Date.now()}`,
  eventType: "RECOMMENDATION_CART_ADD",
  spuId: pendingAction.spuId,
  skuId: pendingAction.skuId,
  threadId: pendingAction.threadId,
  quantity: pendingAction.quantity
});
```

Catch and ignore tracking errors.

- [ ] **Step 7: Update e2e fixture and test**

In `frontend/e2e/fixtures/api.ts`, capture `behaviorEvents` for `**/api/behavior/events`.

Add e2e expectations:

```ts
expect(api.capturedBodies.behaviorEvents.some((event) => event.eventType === "RECOMMENDATION_EXPOSED")).toBe(true);
expect(api.capturedBodies.behaviorEvents.some((event) => event.eventType === "RECOMMENDATION_CART_ADD")).toBe(true);
```

- [ ] **Step 8: Run frontend tests**

Run:

```bash
npm test -- --run src/shared/api/client.test.ts src/features/commerce-action/commerceActions.test.ts
npm run test:e2e -- --project=chromium e2e/ai-shopping.spec.ts
```

Expected: unit and e2e tests pass.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/shared/api frontend/src/features/commerce-action frontend/src/features/catalog/ProductCard.tsx \
  frontend/src/pages/AiShoppingPage.tsx frontend/e2e
git commit -m "feat: track recommendation behavior events"
```

---

### Task 6: Python Behavior Context Consumption

**Files:**
- Modify: `AI-Clothing-Shopping-Assistant-System/clothing_assistant/api/schemas.py`
- Modify: `AI-Clothing-Shopping-Assistant-System/clothing_assistant/application/recommendation_service.py`
- Modify: `AI-Clothing-Shopping-Assistant-System/tests/test_recommendation_service.py`

**Interfaces:**
- Consumes: Java `user_context` fields `recent_interest_spu_ids`, `recent_cart_spu_ids`, `recent_purchased_spu_ids`, `behavior_preferred_categories`, `behavior_preferred_styles`
- Produces: deterministic score boosts and reason text for behavior-matched candidates

- [ ] **Step 1: Write failing Python test**

```python
def test_behavior_context_boosts_recent_interest_candidate(self):
    candidates = [
        {
            "spu_id": 1001,
            "sku_id": 2001,
            "name": "通勤轻薄外套",
            "category": "外套",
            "stock_status": "in_stock",
            "style_tags": ["commute"],
            "sale_price": 299,
        },
        {
            "spu_id": 1002,
            "sku_id": 2002,
            "name": "休闲卫衣",
            "category": "卫衣",
            "stock_status": "in_stock",
            "style_tags": ["casual"],
            "sale_price": 199,
        },
    ]

    refs = build_product_refs(
        candidates,
        {"intent": "recommendation"},
        "推荐一件外套",
        {
            "recent_interest_spu_ids": [1001],
            "behavior_preferred_categories": ["外套"],
            "behavior_preferred_styles": ["commute"],
        },
        {},
    )

    self.assertEqual(refs[0]["spu_id"], 1001)
    self.assertIn("近期行为显示你关注过类似商品", refs[0]["reason"])
```

- [ ] **Step 2: Run Python test to verify it fails**

Run:

```bash
cd /Users/seekinward/Documents/推荐项目/AI-Clothing-Shopping-Assistant-System
pytest tests/test_recommendation_service.py -q
```

Expected: new test fails because behavior-context scoring is not implemented.

- [ ] **Step 3: Extend Pydantic `UserContext`**

Add optional fields with default empty lists:

```python
recent_interest_spu_ids: list[int | str] = Field(default_factory=list, description="Java 汇总的近期兴趣 SPU。")
recent_cart_spu_ids: list[int | str] = Field(default_factory=list, description="Java 汇总的近期加购 SPU。")
recent_purchased_spu_ids: list[int | str] = Field(default_factory=list, description="Java 汇总的近期购买 SPU。")
behavior_preferred_categories: list[str] = Field(default_factory=list, description="Java 行为摘要中的偏好分类。")
behavior_preferred_styles: list[str] = Field(default_factory=list, description="Java 行为摘要中的偏好风格。")
```

- [ ] **Step 4: Add deterministic scoring**

In `recommendation_service.py`:

```text
candidate.spu_id in recent_interest_spu_ids: +0.12 and reason "近期行为显示你关注过类似商品"
candidate.spu_id in recent_cart_spu_ids: +0.16 and reason "你近期有类似加购意图"
candidate.spu_id in recent_purchased_spu_ids: +0.08 and reason "与你近期购买偏好相近"
candidate.category in behavior_preferred_categories: +0.08 and reason "匹配近期浏览或购买分类"
candidate style_tags intersects behavior_preferred_styles: +0.08 and reason "匹配近期偏好的风格"
```

Keep all scoring deterministic and only use Java candidates.

- [ ] **Step 5: Run Python tests to verify they pass**

Run:

```bash
pytest tests/test_recommendation_service.py -q
```

Expected: all tests in `test_recommendation_service.py` pass.

- [ ] **Step 6: Commit in Python project if desired**

The Python project may ignore `docs/superpowers`, but runtime files are tracked:

```bash
cd /Users/seekinward/Documents/推荐项目/AI-Clothing-Shopping-Assistant-System
git add clothing_assistant/api/schemas.py clothing_assistant/application/recommendation_service.py tests/test_recommendation_service.py
git commit -m "feat: use behavior context in recommendations"
```

---

### Task 7: Final Verification and Documentation Sync

**Files:**
- Modify if needed: `docs/backend-feature-mapping.md`
- Copy if desired: `AI-Clothing-Shopping-Assistant-System/docs/superpowers/plans/2026-07-02-user-feedback-loop.md`

**Interfaces:**
- Consumes: all previous task outputs
- Produces: verified Java/Python/frontend feedback loop

- [ ] **Step 1: Run Java backend targeted tests**

```bash
cd /Users/seekinward/Documents/推荐项目/IntelligentOutfitRecommendationSystem/backend
sh mvnw -q -Dtest=BehaviorMapperTests,BehaviorEventServiceTests,BehaviorControllerTests,BehaviorSummaryServiceTests,FavoriteServiceTests,CartServiceTests,OrderServiceTests,PaymentServiceTests,AssistantContextServiceTests,AssistantServiceTests test
```

Expected: selected tests pass with 0 failures.

- [ ] **Step 2: Run Java backend full verification if local environment supports it**

```bash
sh mvnw verify
```

Expected: Maven verify exits 0. If Testcontainers or Docker blocks this locally, capture the exact failure and keep targeted test evidence.

- [ ] **Step 3: Run frontend verification**

```bash
cd /Users/seekinward/Documents/推荐项目/IntelligentOutfitRecommendationSystem/frontend
npm test -- --run
npm run build
```

Expected: Vitest and Vite build pass.

- [ ] **Step 4: Run Python verification**

```bash
cd /Users/seekinward/Documents/推荐项目/AI-Clothing-Shopping-Assistant-System
pytest tests/test_recommendation_service.py tests/test_api.py -q
```

Expected: selected Python tests pass.

- [ ] **Step 5: Manual demo checklist**

```text
1. Start MySQL, Redis, Java backend, Python service, frontend.
2. Log in.
3. Ask AI for a commute outfit.
4. Confirm behavior_event has RECOMMENDATION_EXPOSED rows.
5. Click a recommendation card and confirm RECOMMENDATION_CLICKED.
6. Add from recommendation and confirm RECOMMENDATION_CART_ADD and CART_ADD.
7. Create order and mock pay; confirm ORDER_CREATED and PAYMENT_SUCCESS.
8. GET /api/me/behavior-summary returns recent interest/cart/purchased signals.
9. Next AI request includes behavior context fields in Java -> Python request.
```

- [ ] **Step 6: Commit final docs if changed**

```bash
git add docs/backend-feature-mapping.md docs/superpowers/plans/2026-07-02-user-feedback-loop.md
git commit -m "docs: document user feedback loop implementation"
```

---

## Self-Review

### Spec coverage

- Behavior event table: Task 1.
- Frontend recommendation event API: Tasks 2 and 5.
- Commerce behavior events: Task 3.
- Behavior summary: Task 4.
- AI Java context fields: Task 4.
- Python behavior context consumption: Task 6.
- MQ deferred to later: Global constraints and architecture header.
- Tests and demo path: Task 7.

### Placeholder scan

The plan contains no unresolved markers or unspecified implementation steps. Optional steps are explicitly marked as optional where the target project ignores `docs/superpowers`.

### Type consistency

The behavior event names match the design spec. Java context names use camelCase records with `@JsonProperty` snake_case for Python. Python `UserContext` consumes the same snake_case names sent by Java.
