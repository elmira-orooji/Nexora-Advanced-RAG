# نمودار موجودیت و رابطهٔ Nexora

این نمودار بر اساس مدل‌های پایگاه‌دادهٔ بک‌اند در `backend/app/models` تهیه شده است. هر نمودار بخشی از یک پایگاه‌دادهٔ PostgreSQL واحد را نشان می‌دهد. جدول‌های واسط، رابطه‌های چندبه‌چند را به‌صورت صریح نگه می‌دارند.

## راهنمای روابط

در نمودارهای Mermaid، `||` یعنی «دقیقاً یک»، `o|` یعنی «صفر یا یک»، `o{` یعنی «صفر تا چند» و `|{` یعنی «یک تا چند». برای نمونه، `ORGANIZATIONS ||--o{ USERS` یعنی هر کاربر دقیقاً به یک سازمان تعلق دارد و هر سازمان می‌تواند صفر یا چند کاربر داشته باشد.

| نوع رابطه | موجودیت‌ها | پیاده‌سازی در پایگاه‌داده |
| --- | --- | --- |
| یک‌به‌چند | Organization → User، DocumentSet، Document، Assistant و ProcessingJob | کلید خارجی `organization_id` در موجودیت فرزند |
| یک‌به‌چند | Document → Chunk | کلید خارجی `chunks.document_id` |
| یک‌به‌چند | Conversation → Message | کلید خارجی `messages.conversation_id` |
| یک‌به‌چند | AnswerRecord → AnswerFeedback | کلید خارجی `answer_feedback.answer_id` |
| یک‌به‌چند | DocumentSet → Connector | کلید خارجی `connectors.document_set_id` |
| یک‌به‌چند | Connector → ConnectorItem | کلید خارجی `connector_items.connector_id` |
| یک‌به‌چند | User → AuthSession، Notification، ChatShare و LLMUsage | کلید خارجی کاربر در جدول فرزند |
| یک‌به‌یک اختیاری | Document ↔ ProcessingJob | `processing_jobs.document_id` هم کلید خارجی و هم یکتا است؛ یک سند حداکثر یک کار پردازش فعال دارد |
| یک‌به‌یک اختیاری | Document ↔ ConnectorItem | `connector_items.document_id` یکتا است؛ سندِ حاصل از Connector حداکثر یک نمایندهٔ Connector دارد |
| چندبه‌چند | DocumentSet ↔ Document | جدول واسط `document_set_documents` با کلید مرکب |
| چندبه‌چند | Assistant ↔ DocumentSet | جدول واسط `assistant_document_sets` با کلید مرکب |
| چندبه‌چند با ویژگی رابطه | User ↔ DocumentSet | جدول واسط `document_set_permissions`؛ سطح دسترسی و اعطاکننده را نگه می‌دارد |

رابطه‌های `Conversation → Document`، `Conversation → DocumentSet` و `Conversation → Assistant` اختیاری‌اند؛ هر گفتگو بسته به scope خود می‌تواند به یک سند، یک مجموعهٔ دانش، یک دستیار یا فضای کاری متصل باشد. همین وضعیت برای `AnswerRecord → Assistant` و `AnswerRecord → DocumentSet` نیز برقرار است.

## سازمان، کاربران و دانش

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ USERS : has
    ORGANIZATIONS ||--o{ DOCUMENT_SETS : owns
    ORGANIZATIONS ||--o{ DOCUMENTS : owns
    ORGANIZATIONS ||--o{ ASSISTANTS : owns
    USERS ||--o{ DOCUMENT_SETS : creates
    USERS ||--o{ ASSISTANTS : creates
    USERS ||--o{ DOCUMENT_SET_PERMISSIONS : receives
    USERS ||--o{ DOCUMENT_SET_PERMISSIONS : grants
    DOCUMENT_SETS ||--o{ DOCUMENT_SET_DOCUMENTS : contains
    DOCUMENTS ||--o{ DOCUMENT_SET_DOCUMENTS : belongs_to
    DOCUMENT_SETS ||--o{ DOCUMENT_SET_PERMISSIONS : controls_access
    DOCUMENT_SETS ||--o{ ASSISTANT_DOCUMENT_SETS : assigned_to
    ASSISTANTS ||--o{ ASSISTANT_DOCUMENT_SETS : uses

    ORGANIZATIONS {
        UUID id PK
        string name
        string slug UK
        datetime created_at
    }
    USERS {
        UUID id PK
        UUID organization_id FK
        string username
        string role
        boolean is_active
        datetime created_at
    }
    DOCUMENT_SETS {
        UUID id PK
        UUID organization_id FK
        UUID created_by_id FK
        string name
        int child_chunk_size
        int chunk_overlap
        int parent_chunk_size
    }
    DOCUMENTS {
        UUID id PK
        UUID organization_id FK
        string filename
        string content_type
        string status
        int processing_progress
        string processing_stage
    }
    DOCUMENT_SET_DOCUMENTS {
        UUID document_set_id PK,FK
        UUID document_id PK,FK
    }
    DOCUMENT_SET_PERMISSIONS {
        UUID user_id PK,FK
        UUID document_set_id PK,FK
        UUID granted_by_id FK
        string permission
    }
    ASSISTANTS {
        UUID id PK
        UUID organization_id FK
        UUID created_by_id FK
        string name
        string model_id
        string answer_mode
        boolean is_active
    }
    ASSISTANT_DOCUMENT_SETS {
        UUID assistant_id PK,FK
        UUID document_set_id PK,FK
    }
```

## گفتگو، پاسخ و بازخورد

```mermaid
erDiagram
    USERS ||--o{ AUTH_SESSIONS : authenticates_with
    USERS ||--o{ CONVERSATIONS : owns
    DOCUMENTS o|--o{ CONVERSATIONS : scopes
    DOCUMENT_SETS o|--o{ CONVERSATIONS : scopes
    ASSISTANTS o|--o{ CONVERSATIONS : serves
    CONVERSATIONS ||--o{ MESSAGES : contains
    USERS ||--o{ ANSWER_RECORDS : asks
    ASSISTANTS o|--o{ ANSWER_RECORDS : answers_with
    DOCUMENT_SETS o|--o{ ANSWER_RECORDS : grounds
    ANSWER_RECORDS o|--o{ MESSAGES : represented_by
    ANSWER_RECORDS ||--o{ ANSWER_FEEDBACK : receives
    USERS ||--o{ ANSWER_FEEDBACK : submits
    DOCUMENT_SETS ||--o{ EVALUATION_CASES : validates
    USERS ||--o{ EVALUATION_CASES : creates
    EVALUATION_CASES o|--o{ ANSWER_FEEDBACK : classifies
    USERS ||--o{ CHAT_SHARES : publishes

    AUTH_SESSIONS {
        UUID id PK
        UUID user_id FK
        datetime expires_at
        datetime revoked_at
    }
    CONVERSATIONS {
        UUID id PK
        UUID user_id FK
        UUID document_id FK
        UUID document_set_id FK
        UUID assistant_id FK
        string title
        boolean workspace_scope
    }
    MESSAGES {
        UUID id PK
        UUID conversation_id FK
        UUID answer_id FK
        string role
        text content
        JSON sources
        string answer_basis
    }
    ANSWER_RECORDS {
        UUID id PK
        UUID user_id FK
        UUID assistant_id FK
        UUID document_set_id FK
        boolean grounded
        int citation_count
    }
    ANSWER_FEEDBACK {
        UUID id PK
        UUID answer_id FK
        UUID user_id FK
        UUID evaluation_case_id FK
        int rating
        string reason
    }
    EVALUATION_CASES {
        UUID id PK
        UUID document_set_id FK
        UUID created_by_id FK
        text question
        JSON relevant_chunk_ids
    }
    CHAT_SHARES {
        UUID id PK
        UUID owner_id FK
        string visibility
        string token_hash UK
        boolean is_active
        datetime expires_at
    }
```

## پردازش اسناد، همگام‌سازی و عملیات

```mermaid
erDiagram
    DOCUMENTS ||--o{ CHUNKS : is_split_into
    DOCUMENTS ||--o| PROCESSING_JOBS : is_processed_by
    DOCUMENTS ||--o{ INDEXING_OUTBOX : queues_indexing
    PROCESSING_JOBS o|--o{ INDEXING_OUTBOX : originates
    ORGANIZATIONS ||--o{ PROCESSING_JOBS : owns
    USERS o|--o{ PROCESSING_JOBS : requests
    DOCUMENT_SETS ||--o{ CONNECTORS : syncs_from
    USERS ||--o{ CONNECTORS : creates
    CONNECTORS ||--o{ CONNECTOR_ITEMS : discovers
    DOCUMENTS ||--o| CONNECTOR_ITEMS : represents
    USERS ||--o{ LLM_USAGE : incurs
    DOCUMENT_SETS o|--o{ LLM_USAGE : measures
    ORGANIZATIONS ||--o{ NOTIFICATIONS : emits
    USERS ||--o{ NOTIFICATIONS : receives

    CHUNKS {
        UUID id PK
        UUID document_id FK
        int chunk_index
        int parent_index
        text content
        int token_count
        boolean is_active
    }
    PROCESSING_JOBS {
        UUID id PK
        UUID organization_id FK
        UUID requested_by_id FK
        UUID document_id FK,UK
        string status
        int progress
        string stage
        int attempts
    }
    INDEXING_OUTBOX {
        UUID id PK
        UUID document_id FK
        UUID job_id FK
        string action
        string status
        int attempts
    }
    CONNECTORS {
        UUID id PK
        UUID document_set_id FK
        UUID created_by_id FK
        string connector_type
        string source_url
        string status
        boolean schedule_enabled
    }
    CONNECTOR_ITEMS {
        UUID id PK
        UUID connector_id FK
        UUID document_id FK,UK
        string external_id
        string content_hash
        string source_url
    }
    LLM_USAGE {
        UUID id PK
        UUID user_id FK
        UUID document_set_id FK
        string operation
        string model
        int total_tokens
        float estimated_cost_usd
    }
    NOTIFICATIONS {
        UUID id PK
        UUID user_id FK
        UUID organization_id FK
        string kind
        string severity
        datetime read_at
    }
```

`messages.sources`، `chat_shares.messages`، برچسب‌ها و داده‌های تحلیلی به‌صورت JSON نگه‌داری می‌شوند و در مدل فعلی جدول رابطه‌ای جداگانه ندارند. بردارهای بازیابی‌شده نیز در Qdrant ذخیره می‌شوند؛ بنابراین در این ERD که مدل رابطه‌ای PostgreSQL را توصیف می‌کند، نمایش داده نشده‌اند.
