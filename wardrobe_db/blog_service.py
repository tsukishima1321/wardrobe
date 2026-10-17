"""Database-aware services for the blog domain.

The HTTP layer stays thin; content parsing lives in blog_content.py.
"""

import datetime
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from wardrobe_db.models import (
    BlankPictures,
    BlogPost,
    BlogPostImage,
    BlogPostTag,
    BlogTag,
    CollectionItems,
    Keywords,
    Pictures,
    PicturesOcr,
)

from wardrobe_db.blog_content import (
    auto_title,
    coerce_json,
    collect_image_refs,
    count_words,
    extract_text_from_tiptap,
    make_excerpt,
    normalize_image_href,
    normalize_text,
    plain_text_to_doc,
    plain_text_to_html,
    sanitize_html,
    strip_tags,
    validate_image_href,
)

VALID_KINDS = {"note", "article"}
VALID_STATUSES = {"draft", "published"}


def parse_date(value: Any, default: Optional[datetime.date] = None) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.datetime.strptime(value.strip()[:10], "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("日期格式应为 YYYY-MM-DD") from exc
    return default or datetime.date.today()


def normalize_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in value.replace("，", ",").split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw = [str(part).strip() for part in value]
    else:
        raw = [str(value).strip()]

    result: List[str] = []
    seen = set()
    for tag in raw:
        if not tag:
            continue
        tag = tag[:50]
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
        if len(result) >= 20:
            break
    return result


def _tag_objects(tags: Sequence[str]) -> List[BlogTag]:
    objects = []
    for name in tags:
        tag = BlogTag.objects.filter(name__iexact=name).first()
        if tag is None:
            tag = BlogTag.objects.create(name=name)
        objects.append(tag)
    return objects


def set_post_tags(post: BlogPost, tags: Sequence[str]) -> None:
    BlogPostTag.objects.filter(post=post).delete()
    for tag in _tag_objects(tags):
        BlogPostTag.objects.create(post=post, tag=tag)


def post_tag_names(post: BlogPost) -> List[str]:
    return [tag.name for tag in post.tags.all()]


def serialize_post(post: BlogPost, detail: bool = False) -> Dict[str, Any]:
    tags = post_tag_names(post)
    data: Dict[str, Any] = {
        "id": post.id,
        "title": post.title,
        "kind": post.kind,
        "status": post.status,
        "date": post.date.strftime("%Y-%m-%d") if post.date else None,
        "excerpt": post.excerpt,
        "coverImageHref": post.cover_image_href,
        "wordCount": post.word_count,
        "isPinned": post.is_pinned,
        "tags": tags,
        "createdAt": post.created_at.isoformat() if post.created_at else None,
        "updatedAt": post.updated_at.isoformat() if post.updated_at else None,
        "publishedAt": post.published_at.isoformat() if post.published_at else None,
    }
    if detail:
        data.update({
            "contentJson": post.content_json or {},
            "contentHtml": post.content_html,
            "contentText": post.content_text,
            "images": [
                {
                    "href": link.image_href,
                    "collectionHref": link.collection_href,
                    "role": link.role,
                    "origin": link.origin,
                    "sortOrder": link.sort_order,
                }
                for link in post.image_links.all()
            ],
        })
    return data


def _image_file_exists(href: str) -> bool:
    return os.path.exists(os.path.join(settings.IMAGE_STORAGE_PATH, href))


def _ensure_picture(href: str, title: str, date_value: datetime.date, tags: Sequence[str]) -> Tuple[Optional[Pictures], Optional[str], bool]:
    """Return (picture, collection_href, created).

    Existing collection items deliberately do not get a new standalone
    Pictures row: after a merge the file remains on disk but the source
    Pictures row is gone.
    """
    picture = Pictures.objects.filter(href=href).first()
    if picture is not None:
        return picture, None, False

    collection_item = (
        CollectionItems.objects.filter(image_href=href)
        .select_related("collection")
        .first()
    )
    if collection_item is not None:
        return None, collection_item.collection_id, False

    if not _image_file_exists(href):
        return None, None, False

    description = (title or "").strip()[:100]
    picture = Pictures.objects.create(
        href=href,
        description=description,
        date=date_value,
        is_collection=False,
    )
    BlankPictures.objects.filter(href=href).delete()
    PicturesOcr.objects.get_or_create(href=picture, defaults={"ocr_result": ""})
    for tag in tags:
        if tag:
            Keywords.objects.get_or_create(href=picture, keyword=tag[:50])
    return picture, None, True


def sync_post_images(post: BlogPost, content_json: Any, warnings: Optional[List[str]] = None) -> List[str]:
    warnings = warnings if warnings is not None else []
    refs = collect_image_refs(content_json)
    tags = post_tag_names(post)

    ordered: List[Dict[str, Any]] = []
    seen = set()
    cover = normalize_image_href(post.cover_image_href or "")
    if cover:
        ordered.append({"href": cover, "role": "cover", "alt": "", "caption": ""})
        seen.add(cover)

    for ref in refs:
        href = ref.get("href")
        if not href or href in seen:
            continue
        seen.add(href)
        ordered.append(ref)

    kept_hrefs: List[str] = []
    for index, ref in enumerate(ordered):
        href = ref["href"]
        if not validate_image_href(href):
            warnings.append(f"图片地址不合法，已跳过：{href}")
            continue
        picture, collection_href, created = _ensure_picture(
            href,
            ref.get("alt") or ref.get("caption") or post.title,
            post.date,
            tags,
        )
        if picture is None and not collection_href:
            warnings.append(f"图片文件不存在，已跳过：{href}")
            continue
        BlogPostImage.objects.update_or_create(
            post=post,
            image_href=href,
            defaults={
                "collection_href": collection_href,
                "role": ref.get("role") or "inline",
                "origin": "auto" if created else "library",
                "sort_order": index,
            },
        )
        kept_hrefs.append(href)

    post.image_links.exclude(image_href__in=kept_hrefs).delete()
    return warnings


def save_blog_post(post: BlogPost, data: Dict[str, Any], create: bool = False, warnings: Optional[List[str]] = None) -> BlogPost:
    warnings = warnings if warnings is not None else []

    raw_json = data.get("contentJson", data.get("content_json"))
    content_json = coerce_json(raw_json) if raw_json is not None else coerce_json(post.content_json)
    raw_html = data.get("contentHtml", data.get("content_html"))
    raw_text = data.get("contentText", data.get("content_text"))

    text = extract_text_from_tiptap(content_json)
    if not text and raw_text:
        text = normalize_text(str(raw_text))
    if not content_json and text:
        content_json = plain_text_to_doc(text)

    if raw_html is None:
        content_html = post.content_html if not create and raw_json is None else ""
    else:
        content_html = str(raw_html)
    if not content_html and content_json:
        content_html = plain_text_to_html(text)
    content_html = sanitize_html(content_html)
    if not text and content_html:
        text = normalize_text(strip_tags(content_html))

    date_value = parse_date(
        data.get("date"),
        default=post.date if not create and post.date else datetime.date.today(),
    )

    kind = str(data.get("kind", post.kind if not create else "note") or "note").strip()
    if kind not in VALID_KINDS:
        raise ValueError("文章类型必须是 note 或 article")

    status = str(data.get("status", post.status if not create else "draft") or "draft").strip()
    if status not in VALID_STATUSES:
        raise ValueError("文章状态必须是 draft 或 published")

    title = str(data.get("title", post.title if not create else "") or "").strip()[:200]
    if not title and kind == "note":
        title = auto_title(text, date_value.strftime("%Y-%m-%d"))
    if status == "published" and kind == "article" and not title:
        raise ValueError("长文发布前必须填写标题")

    excerpt_value = data.get("excerpt")
    excerpt = str(excerpt_value).strip()[:500] if excerpt_value is not None else make_excerpt(text, 500)
    if not excerpt:
        excerpt = make_excerpt(text, 500) or title[:500]

    if "coverImageHref" in data or "cover_image_href" in data:
        cover_raw = data.get("coverImageHref", data.get("cover_image_href"))
        cover = normalize_image_href(str(cover_raw or ""))
        if cover_raw and not cover:
            warnings.append("封面图片地址不合法，已清空")
        post.cover_image_href = cover
    elif create:
        post.cover_image_href = None

    post.title = title
    post.kind = kind
    post.status = status
    post.date = date_value
    post.content_json = content_json
    post.content_html = content_html
    post.content_text = text
    post.excerpt = excerpt
    post.word_count = count_words(text)
    pinned_value = data.get("isPinned", post.is_pinned if not create else False)
    if isinstance(pinned_value, str):
        pinned_value = pinned_value.strip().lower() in {"1", "true", "yes", "on"}
    post.is_pinned = bool(pinned_value)
    if status == "published" and not post.published_at:
        post.published_at = timezone.now()
    if status == "draft":
        post.published_at = None

    post.save()

    if "tags" in data:
        set_post_tags(post, normalize_tags(data.get("tags")))
    elif create:
        set_post_tags(post, [])

    sync_post_images(post, content_json, warnings)
    return post


def create_note_from_text(date_value: Any, text: str, tags: Optional[Sequence[str]] = None) -> BlogPost:
    data = {
        "kind": "note",
        "status": "published",
        "date": date_value,
        "contentJson": plain_text_to_doc(text),
        "contentHtml": plain_text_to_html(text),
        "contentText": text,
        "tags": list(tags or []),
    }
    post = BlogPost()
    save_blog_post(post, data, create=True)
    return post


def update_note_from_text(post: BlogPost, text: str, date_value: Any = None) -> BlogPost:
    data: Dict[str, Any] = {
        "contentJson": plain_text_to_doc(text),
        "contentHtml": plain_text_to_html(text),
        "contentText": text,
    }
    if date_value is not None:
        data["date"] = date_value
    if not post.title or post.title.endswith("随手一记"):
        data["title"] = auto_title(text, parse_date(date_value, post.date).strftime("%Y-%m-%d"))
    return save_blog_post(post, data)


def get_image_usage(href: str, limit: int = 20) -> List[Dict[str, Any]]:
    if not href:
        return []
    links = (
        BlogPostImage.objects.filter(Q(image_href=href) | Q(collection_href=href))
        .select_related("post")
        .order_by("-post__date", "-post_id")[: limit * 2]
    )
    seen = set()
    rows = []
    for link in links:
        post = link.post
        if post.id in seen:
            continue
        seen.add(post.id)
        rows.append({
            "id": post.id,
            "title": post.title or auto_title(post.content_text, post.date.strftime("%Y-%m-%d")),
            "date": post.date.strftime("%Y-%m-%d") if post.date else None,
            "status": post.status,
            "kind": post.kind,
            "role": link.role,
        })
        if len(rows) >= limit:
            break
    return rows


def is_image_referenced(href: str) -> bool:
    if not href:
        return False
    return BlogPostImage.objects.filter(Q(image_href=href) | Q(collection_href=href)).exists()
