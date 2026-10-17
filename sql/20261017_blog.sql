-- Blog redesign DDL for PostgreSQL.
-- Run this manually against the "wardrobe" business database.
-- It is intentionally idempotent; review before applying in production.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS blog_posts (
    id              bigserial PRIMARY KEY,
    title           varchar(200) NOT NULL DEFAULT '',
    kind            varchar(20) NOT NULL DEFAULT 'note',
    status          varchar(20) NOT NULL DEFAULT 'draft',
    date            date NOT NULL DEFAULT CURRENT_DATE,
    content_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_html    text NOT NULL DEFAULT '',
    content_text    text NOT NULL DEFAULT '',
    excerpt         varchar(500) NOT NULL DEFAULT '',
    cover_image_href varchar(200),
    word_count      integer NOT NULL DEFAULT 0,
    is_pinned       boolean NOT NULL DEFAULT false,
    legacy_diary_id integer UNIQUE,
    created_at      timestamp NOT NULL DEFAULT now(),
    updated_at      timestamp NOT NULL DEFAULT now(),
    published_at    timestamp
);

CREATE INDEX IF NOT EXISTS blog_status_date_idx ON blog_posts (status, date DESC, id DESC);
CREATE INDEX IF NOT EXISTS blog_date_idx ON blog_posts (date DESC, id DESC);
CREATE INDEX IF NOT EXISTS blog_posts_title_trgm_idx ON blog_posts USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS blog_posts_content_trgm_idx ON blog_posts USING GIN (content_text gin_trgm_ops);
-- Django icontains generates UPPER(column::text) LIKE UPPER(pattern); these expression indexes match it.
CREATE INDEX IF NOT EXISTS blog_posts_title_upper_trgm_idx ON blog_posts USING GIN (UPPER(title) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS blog_posts_content_upper_trgm_idx ON blog_posts USING GIN (UPPER(content_text) gin_trgm_ops);

CREATE TABLE IF NOT EXISTS blog_tags (
    id          bigserial PRIMARY KEY,
    name        varchar(50) NOT NULL UNIQUE,
    created_at  timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS blog_post_tags (
    id       bigserial PRIMARY KEY,
    post_id  bigint NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
    tag_id   bigint NOT NULL REFERENCES blog_tags(id) ON DELETE CASCADE,
    CONSTRAINT uniq_blog_post_tag UNIQUE (post_id, tag_id)
);

CREATE INDEX IF NOT EXISTS blog_tag_post_idx ON blog_post_tags (tag_id, post_id);
CREATE INDEX IF NOT EXISTS blog_post_tags_post_idx ON blog_post_tags (post_id);

CREATE TABLE IF NOT EXISTS blog_post_images (
    id              bigserial PRIMARY KEY,
    post_id         bigint NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
    image_href      varchar(200) NOT NULL,
    collection_href varchar(200),
    role            varchar(20) NOT NULL DEFAULT 'inline',
    origin          varchar(20) NOT NULL DEFAULT 'library',
    sort_order      integer NOT NULL DEFAULT 0,
    created_at      timestamp NOT NULL DEFAULT now(),
    CONSTRAINT uniq_blog_post_image UNIQUE (post_id, image_href)
);

CREATE INDEX IF NOT EXISTS blog_image_href_idx ON blog_post_images (image_href);
CREATE INDEX IF NOT EXISTS blog_image_post_idx ON blog_post_images (post_id);
CREATE INDEX IF NOT EXISTS blog_image_collection_idx ON blog_post_images (collection_href);

CREATE TABLE IF NOT EXISTS blog_post_revisions (
    id           bigserial PRIMARY KEY,
    post_id      bigint NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
    title        varchar(200) NOT NULL DEFAULT '',
    content_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_html text NOT NULL DEFAULT '',
    created_at   timestamp NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS blog_revision_post_idx ON blog_post_revisions (post_id, created_at DESC);
