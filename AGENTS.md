# TIU MEDIA HUB

Backend service for DAM system

## Infrastructure

 - `Postgres 17+` - Main database
 - `RustFS` - S3 compatible object storage
 - `RabbitMQ` - Tasks broker
 - `Keycloak` - Identity & Auth
 - `Qdrant` - Vector store & Multi-modal search (clip embeddings)
 - [`Infinity`](https://github.com/michaelfeil/infinity.git) - Embeddings inference (CLIP)
 - [`Whisper ASR Web Service`](https://github.com/ahmetoner/whisper-asr-webservice.git) - STT model inference
 - `Nginx` - local CDN

## Technology stack

 - [`py-ddd-framework`](https://github.com/Andr171p/py-ddd-framework.git) - [docs](https://andr171p.github.io/py-ddd-framework/)
 - `FastAPI` - included in DDF
 - `SQLAlchemy` - included in DDF
 - `TaskIQ` - tasks management
 - `OpenAI SDK`

## Architecture

```

```text
project/
├── src/
│   ├── api/
│   │   ├── routers/
│   │   │   ├── admin/             # Admin API level
│   │   │   ├── user/              # User API level
│   │   │   ├── service/           # Service2Service API level
│   │   │   └── mcp/               # Model Context Protocol
│   │   ├── dependencies/          # FastAPI Depends, auth, permissions, db
│   │   ├── middlewares/           # HTTP middleware
│   │   ├── lifespan.py            # Lifecycle
│   │   └── __init__.py
│   │
│   ├── application/               # Orchestration, use cases, DTOs, protocols, ...
│   │   ├── auth/
│   │   ├── assets/
│   │   ├── collections/
│   │   └── search/
│   │
│   ├── domain/
│   │   ├── media/
│   │   ├── assets/
│   │   ├── collections/
│   │
│   ├── infra/
│   │   ├── database/             # SQLAlchemy (Postgres), ORMs models, repositories impl
│   │   ├── qdrant/
│   │   ├── whisper/
│   │   ├── broker/               # TaskIQ tasks
```

## Rules

# Engineering Rules — DDF Applications

## 1. Core Philosophy

- Follow **Pythonic DDD** and pragmatic Clean Architecture.
- Prefer simple, explicit, readable and strongly typed Python.
- Optimize for maintainability, correctness and clear architectural boundaries, not maximum abstraction.
- Apply DDD patterns only when they solve actual domain problems.
- Prefer composition over inheritance.
- Avoid speculative abstractions, premature generalization and unnecessary boilerplate.
- Reuse existing project components and DDF capabilities before introducing new implementations.
- Do not introduce architecture that is more complicated than the business problem.
- Follow established repository conventions unless there is a clear reason to improve them.

**Primary principle:** Use the simplest design that preserves domain invariants, testability and architectural boundaries.

## 2. Architecture

Use a modular monolith by default. Extract independent services only when justified by ownership, deployment or scaling requirements.

Preferred application structure:

```text
src/
├── api/
│   ├── routers/
│   │   ├── admin/
│   │   ├── user/
│   │   ├── service/
│   │   └── mcp/
│   ├── dependencies/
│   ├── middlewares/
│   └── lifespan.py
├── application/
├── domain/
├── infra/
```

### Layer responsibilities

**Domain**

- Contains aggregates, entities, value objects, domain services, invariants and domain events.
- Must not depend on application, infrastructure or API layers.
- Must not perform database, network or filesystem I/O.
- Must not know about FastAPI, SQLAlchemy, HTTP, messaging or external SDKs.

**Application**

- Contains use cases, application DTOs, ports and orchestration.
- Coordinates domain operations and infrastructure capabilities through abstractions.
- Owns application workflows and transaction boundaries.
- Must not depend on FastAPI, ORM models or concrete infrastructure implementations.

**Infrastructure**

- Implements application ports and persistence contracts.
- Contains repositories, data mappers, database integrations, external clients, messaging adapters and workers.
- Must not make domain-specific business decisions.

**API**

- Adapts HTTP, MCP and other transports to application use cases.
- Handles transport validation, authentication dependencies, request/response mapping and error translation.
- Must not contain domain logic or perform direct database operations.

### Dependency composition

- Use FastAPI `Depends` for HTTP dependency injection.
- Use explicit dependency factories for non-HTTP execution contexts.
- Do not introduce a DI container unless the existing composition becomes genuinely difficult to maintain.
- Keep `api/dependencies` focused on HTTP-related dependencies.
- The same application use cases must be reusable from HTTP handlers, MCP tools, background jobs and CLI.

Organize business code by bounded context or cohesive feature. Avoid giant `services.py`, `models.py` and `utils.py` modules shared by unrelated features.

## 3. Pythonic DDD

### Domain models

- Use `dataclass` for entities, aggregates and value objects, following existing DDF conventions.
- Prefer `AggregateRoot` and `Entity` from DDF where their semantics are required.
- Use immutable value objects where appropriate.
- Encapsulate business invariants in aggregate methods or domain functions.
- Do not create methods that only wrap trivial field assignments without adding business meaning.
- Keep references between aggregates by identifier when possible.
- Do not introduce an aggregate for every database table.

### Domain behavior

- An aggregate method should manage its own state and invariants.
- Domain functions are appropriate for rules involving multiple objects.
- Application use cases coordinate operations but should not duplicate domain invariants.
- Model meaningful state transitions explicitly.
- Reject invalid transitions rather than silently correcting invalid state.

### Avoid overengineering

Do not automatically introduce:

- Factories for simple constructors.
- Domain services for trivial operations.
- Interfaces for every class.
- Separate handlers for every getter/setter.
- Wrapper classes that only delegate to another component.
- Generic frameworks for functionality used by one concrete scenario.

## 4. Application Layer

### Use cases

Prefer functions for stateless application use cases.

```python
async def do_something(
    uid: UUID,
    *,
    repository: SomethingRepository,
    uow: UnitOfWork,
) -> None:
    ...
```

- Use explicit, typed dependencies.
- Prefer keyword-only infrastructure dependencies.
- Create use case classes only when shared state, lifecycle or cohesive behavior justifies them.
- Keep each use case focused on one meaningful business operation.
- Split complicated algorithms into small, cohesive helpers.
- Do not create service classes merely to group related functions.
- Do not hide dependencies inside large generic context objects.

### DTOs

- Use Pydantic v2 for application DTOs and validation at boundaries.
- Keep DTOs separate from domain and persistence models.
- Create DTOs only when they add meaningful contracts.
- Prefer explicit types over `Any` or unstructured dictionaries.
- Avoid unnecessary chains of equivalent DTO conversions.
- Keep transport-only DTOs in the API layer.
- Do not expose persistence models directly to application consumers.
- Avoid using `model_validator` and `field_validator`

### Ports

- Use `typing.Protocol` for meaningful application-to-infrastructure boundaries.
- Define ports by the capabilities required by the consumer.
- Prefer small, cohesive interfaces.
- Do not design interfaces around hypothetical future implementations.
- Do not introduce an adapter that merely delegates methods without providing useful isolation.

## 5. DDF Usage

DDF is the default reusable foundation for common architectural primitives.

Before implementing a common capability, check whether DDF already provides it.

### Use existing DDF components

- `AggregateRoot`, `Entity`, domain events and repository contracts.
- `UnitOfWork` and persistence utilities.
- `Crud` for straightforward CRUD scenarios.
- Filtering DSL, sorting and pagination where suitable.
- `CachedRepository` and caching abstractions when caching is required.
- Transactional Outbox and event infrastructure for reliable integration messaging.
- Existing infrastructure adapters where they satisfy the application's needs.

### CRUD

- Prefer DDF `Crud` for standard create/read/update/delete operations with simple behavior.
- Use custom application use cases for operations with meaningful invariants, workflows or cross-resource coordination.
- Do not force complex workflows into generic CRUD.
- Do not implement another generic CRUD abstraction in the application.

### DDF boundaries

- Keep DDF business-agnostic.
- Move reusable technical capabilities into DDF only when real reuse or a clear framework responsibility exists.
- Keep application-specific policies, roles, principals and business rules outside DDF.
- Do not modify DDF to accommodate a single business exception when an application adapter would suffice.
- Verify APIs against the installed DDF version and implementation; do not assume a documented or proposed API exists.

## 6. Persistence & Transactions

- Use SQLAlchemy 2.x with async sessions for PostgreSQL persistence.
- Separate domain objects from persistence representations when domain complexity justifies it.
- Use Data Mappers when necessary to preserve domain independence.
- Prefer DDF repository contracts and implementations where appropriate.
- Keep SQL expressions and ORM concerns inside infrastructure.
- Create specialized repository operations for complex, performance-sensitive queries.
- Avoid N+1 queries and unnecessary relationship loading.
- Enforce database-level constraints for persistence invariants.

### Transaction management

- Use Unit of Work to define transaction boundaries.
- Each transaction must have one clearly defined owner of `commit`.
- Repositories must not perform hidden commits.
- Use `flush` when database-generated values are required before commit.
- Persist related changes atomically when they represent one business operation.
- Never rely solely on an application-level uniqueness pre-check; handle database constraint violations.
- Consider concurrent updates and optimistic locking where relevant.

### Queries

- Prefer DDF filtering DSL for supported generic filtering requirements.
- Whitelist user-accessible filter and sort fields.
- Prefer cursor pagination for large or frequently changing lists.
- Use offset pagination when page numbers and totals are meaningful.
- Ensure cursor ordering is stable and deterministic.
- Use explicit indexes informed by actual query patterns.

## 7. API Design

- Group API routes by consumer: `user`, `admin`, `service`, `mcp`.
- Reuse the same application layer across all API types.
- Keep HTTP concerns out of domain and application code.
- Validate request boundaries with Pydantic DTOs.
- Use consistent response DTOs and error mapping.
- Return appropriate HTTP status codes.
- Use `202 Accepted` for genuinely asynchronous operations that are not yet completed.
- Keep API contracts independent of persistence implementation.
- Provide idempotency mechanisms for externally retried operations when needed.
- Do not expose sensitive infrastructure errors to clients.

### Authentication & Authorization

- Separate token verification, authentication principal resolution and authorization.
- Use DDF infrastructure integrations for reusable Keycloak/JWT verification.
- Keep application-specific `Auth`, roles, permissions and memberships in the application.

Principal example (just dto design example, it shouldn't be taken in this form):
```python
class AuthType(StrEnum):
    USER = "user"
    SERVICE = "service"


class Auth(BaseModel):
    model_config = ConfigDict(frozen=True)

    class User(BaseModel):
        model_config = ConfigDict(frozen=True)

        id: UUID
        email: EmailStr
        roles: frozenset[str] = Field(default_factory=frozenset)

    id: UUID
    type: AuthType

    user: User | None = None


class AuthUser(Auth):
    user: Auth.User

```

## 8. Infrastructure & Integrations

- Encapsulate external systems behind cohesive clients or adapters.
- Prefer the official SDK or existing DDF integration before creating a new abstraction.
- Use asynchronous I/O for async applications.
- Configure timeouts and resource limits.
- Reuse HTTP sessions and connection pools when justified.
- Manage resource lifecycle explicitly.
- Prefer lazy initialization when it simplifies lifecycle without compromising correctness.
- Convert provider-specific errors to stable boundary exceptions where useful.
- Retry only safe, idempotent or explicitly retryable operations.
- Never log credentials, access tokens or sensitive payloads.

### Object storage

- Store stable storage identifiers instead of temporary access URLs.
- Generate presigned URLs only when required.
- Authorize access before issuing temporary credentials.
- Keep provider-specific S3 details inside infrastructure.
- Stream large media files without loading entire contents into memory.

### Keycloak

- Keep token verification independent of application principals.
- Verify JWT signature, issuer, audience, expiration and required claims.
- Return verified claims to an application-specific resolver.
- Do not determine business permissions inside a generic Keycloak client.
- Keep Admin API, OAuth operations and JWT verification as separate responsibilities.

## 9. Events & Background Processing

- Use domain events for meaningful business facts.
- Name domain events in the past tense.
- Keep event payloads focused on business data.
- Keep transport metadata and delivery state separate from event payloads.
- Use Transactional Outbox for events requiring reliable external delivery.
- Persist domain changes and outbox messages in the same transaction.
- Assume at-least-once delivery and design consumers to be idempotent.
- Use stable event/message identifiers for deduplication.
- Do not assume strict ordering without an explicit guarantee.

### Background execution

- Use TaskIQ or existing workers for relatively independent background jobs.
- Avoid embedding business rules directly in worker or activity bootstrap code.
- Avoid adding a workflow engine to simple tasks.

## 10. Caching

- Treat cache as an optimization, not a business source of truth.
- Prefer existing DDF caching primitives when they match the required semantics.
- Use appropriate TTL and invalidation policies.
- Include tenant and resource context in cache keys where necessary.
- Never use cached permissions without considering revocation and staleness.
- Do not introduce Redis simply because an in-memory cache is insufficiently generic.
- Measure the need for caching before adding complexity.

## 11. Code Style

- Follow the existing Ruff and type-checker configuration.
- Use modern Python typing and standard-library features.
- Prefer explicit, descriptive names.
- Avoid redundant comments and excessive docstrings.
- Use docstrings for non-obvious behavior, invariants and public contracts.
- Keep functions and modules cohesive.
- Use `StrEnum` for string-valued enums when appropriate.
- Prefer typed exceptions to generic error handling.
- Do not silently suppress exceptions.
- Avoid unnecessary dependencies, magic decorators, reflection and dynamic dispatch.
- Refactor repetitive code only when the extracted abstraction improves clarity.

## 12. Testing

Every meaningful behavior change should include appropriate tests.

### Unit tests

- Test domain invariants without databases or external services.
- Test application use cases with small fakes or stubs.
- Avoid excessive `MagicMock` usage when a simple fake expresses behavior more clearly.

### Integration tests

- Test database repositories against the actual database technology.
- Verify transactions, rollbacks, database constraints and concurrency.
- Test infrastructure adapters against their expected external contracts.
- Test authorization and tenant isolation.
- Test retries, duplicate events and idempotency.

### Test quality

- Keep tests deterministic.
- Avoid arbitrary sleeps and timing-dependent assertions.
- Cover successful operations, invalid inputs, failures and edge cases.
- Do not weaken tests to hide implementation defects.
- Do not call an integration test a unit test when it requires external infrastructure.

## 13. Working With Existing Code

Before implementing a feature:

1. Inspect neighboring modules and existing conventions.
2. Identify the domain responsibility and affected layer.
3. Check whether DDF already provides the needed capability.
4. Find existing DTOs, repositories, use cases and integration clients.
5. Choose the smallest coherent change that satisfies the requirement.

During implementation:

- Preserve existing behavior unless changing it is intentional.
- Avoid unrelated refactoring.
- Prefer improving an existing component over duplicating it.
- Do not introduce abstractions without explaining the concrete problem they solve.
- Keep dependencies explicit.
- Respect the existing project structure.

After implementation:

- Run applicable formatting, linting and type checks.
- Run relevant tests.
- Add or update tests for changed behavior.
- Update documentation when contracts or architecture change.
- Clearly report what was changed, what was verified and what remains unverified.

## 14. Decision-Making Principles

When multiple designs are possible:

1. Prefer correctness and domain invariants.
2. Preserve clear architectural boundaries.
3. Reuse existing DDF capabilities.
4. Minimize accidental complexity.
5. Prefer explicit code over hidden framework magic.
6. Optimize only where measurements or requirements justify it.
7. Avoid premature generalization.

**Do not confuse architectural quality with the number of abstractions.**

The preferred solution is the smallest maintainable implementation that correctly expresses business requirements and fits the existing architecture.
