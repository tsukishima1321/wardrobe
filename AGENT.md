# AGENT Guide: Wardrobe Django Backend

This document is a fast onboarding reference for agent-driven development in this repository.

## 1. Project Overview

Wardrobe is a Django backend for a personal image knowledge base system, with these core capabilities:

- Image bed services: upload, delete, and on-demand thumbnail generation.
- Media archive CRUD: image metadata, OCR text, keyword/property tagging.
- Full-text and structured search with saved filters.
- OCR task queue management and batch execution.
- NLP-assisted metadata prediction (keyword/property inference from description text).
- Collection feature: grouped images with generated collage cover images.
- Diary and message center (including SSE stream for near-real-time notifications).
- Statistics and monthly report generation.
- Timeline report generation for a selected word, including time-bucketed picture counts and related title words / keywords / property values.
- Encrypted PostgreSQL backup and backup record management.

There is a separate frontend repository (see `readme.md`). This repo is backend-only.

## 2. Runtime Architecture

### 2.1 Entry Points

- Django bootstrap: `manage.py`
- Project settings: `wardrobe/settings.py`
- Root URL config: `wardrobe/urls.py`
- ASGI app: `wardrobe/asgi.py`

### 2.2 App Composition

Installed custom apps:

- `wardrobe_image`: image bed/auth/token/thumbnail endpoints.
- `wardrobe_db`: business domain API and data models.

### 2.3 Database Layout

Configured in `wardrobe/settings.py` and routed via `wardrobe/dbrouters.py`.

- `default` DB: SQLite (`db.sqlite3`) for Django internal data.
- `business` DB: PostgreSQL for all `wardrobe_db` models.

Router rule (`BusinessDBRouter`):

- Models from app label `wardrobe_db` read/write/migrate on `business`.
- Other apps default to `default`.

## 3. URL Map and API Domains

### 3.1 Root URL Dispatch (`wardrobe/urls.py`)

- `/imagebed/` -> `wardrobe_image.urls`
- `/` -> `wardrobe_db.urls`

### 3.2 Imagebed APIs (`wardrobe_image/urls.py`)

- `auth/`: token-auth check endpoint used by Nginx `auth_request`.
- `token/`, `refresh/`: JWT issue/refresh (IP bound in token payload).
- `upload/`: image file upload and MD5-based naming.
- `deletefile/`: image file and thumbnail deletion.
- `thumbnails/<imageName>`: lazy thumbnail generation and return.

### 3.3 Business APIs (`wardrobe_db/urls.py`)

Main endpoint groups:

- Search: `/search/`, `/searchhint/`, saved search CRUD.
- Image detail CRUD: `/image/get/`, `/image/set/`, `/image/delete/`, `/image/new/`, `/text/set/`, blank image workflow.
- Metadata: keyword/property CRUD, user dictionary CRUD, NLP predict/reload.
- OCR mission queue: create/reset/list/execute/executeall/clean.
- Statistics and tips/report generation, including `/report/timeline/` for word-based timeline reports.
- Backup records and backup file operations.
- Message center list/read/delete/clear and stream (SSE-like endpoint).
- Diary CRUD and search.
- Collection CRUD and like/list operations.

## 4. Core Data Model (`wardrobe_db/models.py`)

Key business entities:

- `Pictures`: primary media record (`href` as PK), metadata (`description`, `date`), `is_collection` flag.
- `CollectionItems`: collection-image membership, order, liked state.
- `PicturesOcr`: one-to-one OCR text with `Pictures`.
- `Keywords`: image keyword tags.
- `Properties`: structured metadata key/value pairs.
- `OcrMission`: OCR task queue with status (`waiting/processing/finished`).
- `SavedSearch`: named search filter presets.
- `BackupRecords`: backup timestamp + comment ledger.
- `Messages`: notification center entries.
- `DiaryTexts`: diary records.
- `BlankPictures`: images marked as unprocessed.
- `UserDictionary`: custom segmentation dictionary for NLP.
- `Statistics` + `StatisticsByKeyword`: summary and keyword dimensions.

## 5. Module Responsibilities

## 5.1 `wardrobe_image/views.py`

Responsibilities:

- JWT access check endpoint for Nginx-authenticated static file access.
- Token issue/refresh with custom serializers:
  - Access/refresh token binds source IP on login.
  - Refresh rejects mismatched IP.
- Raw file operations:
  - Upload stores file in `IMAGE_STORAGE_PATH` with `md5.ext` naming.
  - Delete removes original and corresponding thumbnail.
  - Thumbnail endpoint lazily creates JPG thumbnail in `THUMBNAILS_STORAGE_PATH`.

Notable behavior:

- Upload returns duplicate detection response if same MD5 already exists.
- Uses DRF `IsAuthenticated` for most endpoints except token endpoints.

## 5.2 `wardrobe_db/views/image_views.py`

Responsibilities:

- Create/read/update/delete for picture details.
- Create new picture records after delegating file upload to `wardrobe_image` internal API (`LOCALHOST + /api/upload/`).
- OCR text write-through to `PicturesOcr`.
- Random image selection with optional keyword and collection filters.
- Blank image workflow (`listBlankImages`, `reprocessImage`).
- Incremental NLP updates when new image metadata is saved.

## 5.3 `wardrobe_db/views/search_views.py`

Responsibilities:

- Composite search over description, OCR text, keywords, properties, date range.
- Inclusion/exclusion filters for keywords and properties.
- Pagination and ordering.
- Search hints (top keywords/property names by frequency).
- Saved search preset CRUD.

## 5.4 `wardrobe_db/views/metadata_views.py`

Responsibilities:

- Keyword/property CRUD per image.
- NLP metadata prediction endpoint (`predictMetadata`).
- NLP model reload endpoint (`reloadModel`, intended for internal call).
- User dictionary management for segmentation.

Notable behavior:

- On metadata create/delete, updates NLP model incrementally.
- User dictionary changes trigger `nlp_engine.refresh_user_dict()`.

## 5.5 `wardrobe_db/views/ocr_views.py`

Responsibilities:

- OCR mission queue API.
- Execute OCR in background threads.
- Collection-aware OCR: aggregate OCR text from collection items.
- Completion updates `PicturesOcr`, mission status, and emits message.

Depends on:

- `wardrobe_db/ocr.py` for OCR model loading and inference.

## 5.6 `wardrobe_db/views/collection_views.py`

Responsibilities:

- Collection entity creation/deletion.
- Add/remove/list/like collection items.
- Generate collection composite cover image (`_generate_collection_thumbnail`) with layout templates.
- Async thumbnail regeneration using Python threads.
- Cleanup of orphaned files when removing items/collections.

Notable behavior:

- Collection cover images are stored in main image storage path as regular image files.
- Thumbnail cache for collection cover is invalidated when content changes.

## 5.7 `wardrobe_db/views/stat_views.py`

Responsibilities:

- Call DB function `updatestat` for aggregate refresh.
- Serve overall and by-keyword statistics.
- Build timeline report data for a selected word, with day/month/year buckets and relation summaries.
- Generate reminder/report messages:
  - Diary inactivity reminders.
  - Backup inactivity warnings.
  - Blank image processing reminders.
  - Monthly report on day 7.

Notable behavior:

- Timeline report matching supports `title_only` and `title_keyword_property` modes.
- Timeline report currently analyzes `Pictures.description` as the title text source.
- Timeline report returns structured data only; chart/timeline rendering is expected to be handled by the frontend.

## 5.8 `wardrobe_db/views/backup_views.py`

Responsibilities:

- List/create/delete backup records.
- Trigger shell backup script (`db_dump.sh`) through subprocess.
- Serve backup archive download with JWT token query validation.

## 5.9 `wardrobe_db/views/message_views.py`

Responsibilities:

- CRUD-ish operations for messages (`list`, `read`, `delete`, `clear_read`).
- Async streaming endpoint (`streamMessages`) with keep-alive comments.

Notable behavior:

- Stream endpoint does manual JWT validation and returns `StreamingHttpResponse`.
- Polls DB every second for new messages.

## 5.10 `wardrobe_db/views/diary_views.py`

Responsibilities:

- Diary search and CRUD operations.
- Supports pagination and date range filtering.

## 5.11 Shared helpers (`wardrobe_db/views/common.py`)

- `_extract_body`: unified JSON/form payload extraction.
- `create_message`: de-duplicates same text in same day and persists message.
- `LOCALHOST` from settings used for internal API calls.

## 6. OCR Subsystem (`wardrobe_db/ocr.py`)

- Uses EasyOCR (`easyocr.Reader`) with Chinese+English models.
- Singleton-like global reader loaded lazily.
- Splits tall images into chunks before OCR for stability.
- Returns concatenated detected text.
- Runs CPU mode (`gpu=False`) and limits torch threads to 2.

## 7. NLP Subsystem (`wardrobe_db/nlp/model.py`)

Core class: `WardrobeNLP` (singleton instance: `nlp_engine`).

Capabilities:

- Builds co-occurrence-based probability counters between tokens and:
  - keywords,
  - property values per property name.
- Segmentation via jieba with custom vocabulary from DB.
- Supports full train, incremental update (`add`/`remove`), predict, save/load.
- Persists model to `wardrobe_db/nlp/data/model.pkl`.

Dictionary flow:

- Sources words from `Keywords`, `Properties`, and `UserDictionary`.
- Supports allowed single-char tokens from custom dictionary.

Initialization:

- In `wardrobe_db/apps.py` `ready()`, NLP and OCR models are loaded only when running server (`runserver` or `daphne`).

## 8. Management Commands (`wardrobe_db/management/commands`)

- `train_nlp`: train model from `training_data.json`.
- `retrain_and_reload`: train from DB and optionally call reload API.
- `export_training_data`: dump current training corpus JSON from DB.
- `export_model_json`: convert model pickle to inspectable JSON.
- `regen_collection_thumbnails`: rebuild collection cover images in batch.

Useful for maintenance and model lifecycle automation.

## 9. Backup and Ops Scripts

Root scripts:

- `db_dump.sh`: encrypted manual backup for PostgreSQL dump.
- `auto_db_dump.sh`: encrypted backup + insert backup record with comment "自动备份".

SQL utility:

- `updatestat.sql`: PostgreSQL function definition used by `/statistics/` and report generation.

Nginx reference:

- `nginx-ref.conf`: static file auth gate, API proxy, thumbnail fallback to Django, and backup static exposure.

## 10. Config and Environment Variables

Defined/used in settings and scripts:

- `django_secret_key`
- `wardrobe_db_password`
- `wardrobe_localhost`
- `wardrobe_backupdir`
- `wardrobe_db_name` (used by scripts)

Storage settings:

- `IMAGE_STORAGE_PATH = 'images/'`
- `THUMBNAILS_STORAGE_PATH = 'thumbnails/'`

Security/infra notes:

- JWT auth is default DRF auth class.
- Token refresh checks client IP against original token IP.
- `DEBUG=True` currently in settings (review for production).
- `download_backup` uses token in query string; keep TLS and log hygiene.

## 11. Typical Data Flows

### 11.1 New image upload

1. Client calls `/image/new/`.
2. Backend forwards file to `/api/upload/` (imagebed endpoint).
3. On success creates `Pictures` record.
4. Optionally creates OCR mission or empty OCR record.
5. Saves keywords/properties.
6. Incrementally updates NLP counters.

### 11.2 OCR execution

1. Client creates mission (`/ocrmission/new/`).
2. Client executes one/all missions (`/ocrmission/execute*`).
3. Background thread runs OCR.
4. Persists `PicturesOcr`, marks mission finished.
5. Creates completion message.

### 11.3 Collection cover regeneration

1. Collection item add/remove/like.
2. Background thread calls `_generate_collection_thumbnail`.
3. Composite image is regenerated.
4. Cached thumbnail file is deleted to force lazy re-gen.

### 11.4 NLP retrain pipeline

1. Run `python manage.py retrain_and_reload`.
2. Command builds training corpus from DB.
3. Train + save model.
4. Notify server reload endpoint (`/metadata/reload/`).

## 12. Extension Guide for Future Agents

When adding features, prefer placing logic by bounded context:

- Image storage/auth/JWT plumbing -> `wardrobe_image`.
- Business rules and domain APIs -> `wardrobe_db/views/*`.
- New business entities -> `wardrobe_db/models.py` + migration on `business` DB.
- Search/filter evolution -> `search_views.py`.
- Metadata intelligence -> `metadata_views.py` and `nlp/model.py`.
- Async notifications -> `message_views.py` + `common.create_message`.
- Operational automation -> management commands and shell scripts.

Recommended implementation checklist:

1. Confirm whether new model belongs to `wardrobe_db` (PostgreSQL) or Django default DB.
2. Add endpoint in corresponding view module and register in `wardrobe_db/urls.py`.
3. Reuse `_extract_body` for request parsing consistency.
4. If feature emits user-facing events, use `create_message`.
5. If metadata changes semantic labels, consider if NLP model incremental update or retrain is needed.
6. For file operations, handle both original and thumbnail cleanup.
7. Validate token/IP or internal-call constraints for sensitive endpoints.
8. Update docs and add/adjust management commands if batch maintenance is needed.

## 13. Known Risks / Technical Debt

- Several endpoints use broad exception handling and return generic 500s.
- Thread-based background work has no durable queue/retry semantics.
- Some APIs perform multiple DB queries per item (possible optimization target).
- `reloadModel` has placeholder security check logic.
- `DEBUG=True` and query-token download pattern should be reviewed for production hardening.
- Search pagination total-page math may overcount when exact division occurs.

This guide should be updated whenever endpoints, model topology, or deployment strategy changes.
