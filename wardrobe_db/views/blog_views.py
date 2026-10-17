import logging
from typing import Any, Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.db.models.functions import TruncMonth
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from wardrobe_db.blog_content import highlight_snippet
from wardrobe_db.blog_service import (
    normalize_tags,
    parse_date,
    save_blog_post,
    serialize_post,
    sync_post_images,
)
from wardrobe_db.models import BlogPost, BlogTag
from wardrobe_db.views.common import _extract_body

logger = logging.getLogger("db")

ORDER_FIELDS = {
    "date": "date",
    "createdAt": "created_at",
    "updatedAt": "updated_at",
    "publishedAt": "published_at",
    "title": "title",
}


def _json_error(message: str, status: int = 400, **extra: Any) -> JsonResponse:
    payload: Dict[str, Any] = {"error": {"message": message}}
    payload.update(extra)
    return JsonResponse(payload, status=status)


def _body(request: HttpRequest) -> Dict[str, Any]:
    body = _extract_body(request)
    return body if isinstance(body, dict) else dict(body)


def _get_post(post_id: int) -> Optional[BlogPost]:
    return (
        BlogPost.objects.filter(pk=post_id)
        .prefetch_related("tags", "image_links")
        .first()
    )


def _page_params(request: HttpRequest) -> Tuple[int, int]:
    try:
        page = max(1, int(request.GET.get("page", 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = min(100, max(1, int(request.GET.get("pageSize", request.GET.get("page_size", 20)))))
    except (TypeError, ValueError):
        page_size = 20
    return page, page_size


def _apply_text_filter(posts, query: str):
    for term in [part for part in query.split() if part.strip()]:
        posts = posts.filter(
            Q(title__icontains=term)
            | Q(content_text__icontains=term)
            | Q(tags__name__icontains=term)
        )
    return posts.distinct()


def _apply_common_filters(request_or_body: Any, posts, is_body: bool = False):
    get = (lambda key, default="": request_or_body.get(key, default)) if is_body else (
        lambda key, default="": request_or_body.GET.get(key, default)
    )
    status = str(get("status", "") or "").strip()
    if status and status != "all":
        if status not in {"draft", "published"}:
            raise ValueError("状态参数不合法")
        posts = posts.filter(status=status)
    elif not status:
        posts = posts.filter(status="published")

    kind = str(get("kind", "") or "").strip()
    if kind:
        if kind not in {"note", "article"}:
            raise ValueError("类型参数不合法")
        posts = posts.filter(kind=kind)

    tag = str(get("tag", "") or "").strip()
    if tag:
        posts = posts.filter(tags__name=tag).distinct()

    date_from = str(get("dateFrom", "") or "").strip()
    date_to = str(get("dateTo", "") or "").strip()
    if date_from:
        posts = posts.filter(date__gte=parse_date(date_from))
    if date_to:
        posts = posts.filter(date__lte=parse_date(date_to))

    return posts

def list_posts(request: HttpRequest) -> JsonResponse:
    try:
        posts = BlogPost.objects.all()
        posts = _apply_common_filters(request, posts)
        query = str(request.GET.get("q", "") or "").strip()
        if query:
            posts = _apply_text_filter(posts, query)

        order_by = ORDER_FIELDS.get(str(request.GET.get("orderBy", "date")), "date")
        order = str(request.GET.get("order", "desc")).lower()
        prefix = "" if order == "asc" else "-"
        posts = posts.order_by("-is_pinned", f"{prefix}{order_by}", f"{prefix}id")

        page, page_size = _page_params(request)
        total = posts.count()
        total_page = (total + page_size - 1) // page_size if total else 0
        if total_page and page > total_page:
            page = total_page
        start = (page - 1) * page_size
        rows = list(posts.select_related().prefetch_related("tags")[start:start + page_size])

        return JsonResponse({
            "items": [serialize_post(post) for post in rows],
            "totalItems": total,
            "totalPage": total_page,
            "page": page,
            "pageSize": page_size,
        })
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("list blog posts failed")
        return _json_error("加载文章列表失败", 500, detail=str(exc))

def create_post(request: HttpRequest) -> JsonResponse:
    body = _body(request)
    try:
        with transaction.atomic():
            post = BlogPost()
            warnings: List[str] = []
            save_blog_post(post, body, create=True, warnings=warnings)
            post.refresh_from_db()
        return JsonResponse({"post": serialize_post(post, detail=True), "warnings": warnings}, status=201)
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("create blog post failed")
        return _json_error("创建文章失败", 500, detail=str(exc))

def get_post(request: HttpRequest, post_id: int) -> JsonResponse:
    post = _get_post(post_id)
    if post is None:
        return _json_error("文章不存在", 404)
    return JsonResponse({"post": serialize_post(post, detail=True)})

def update_post(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    body = _body(request)
    try:
        with transaction.atomic():
            warnings: List[str] = []
            save_blog_post(post, body, create=False, warnings=warnings)
            post.refresh_from_db()
        post = _get_post(post_id)
        return JsonResponse({"post": serialize_post(post, detail=True), "warnings": warnings})
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("update blog post failed")
        return _json_error("更新文章失败", 500, detail=str(exc))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def publish_post(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    if post.kind == "article" and not (post.title or "").strip():
        return _json_error("长文发布前必须填写标题")
    try:
        with transaction.atomic():
            post.status = "published"
            if not post.published_at:
                post.published_at = timezone.now()
            post.save(update_fields=["status", "published_at", "updated_at"])
        post = _get_post(post_id)
        return JsonResponse({"post": serialize_post(post, detail=True)})
    except Exception as exc:
        logger.exception("publish blog post failed")
        return _json_error("发布文章失败", 500, detail=str(exc))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unpublish_post(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    post.status = "draft"
    post.published_at = None
    post.save(update_fields=["status", "published_at", "updated_at"])
    return JsonResponse({"post": serialize_post(post, detail=True)})


@api_view(["PATCH", "POST"])
@permission_classes([IsAuthenticated])
def autosave_post(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    body = _body(request)
    body.setdefault("status", post.status)
    try:
        with transaction.atomic():
            warnings: List[str] = []
            save_blog_post(post, body, create=False, warnings=warnings)
            post.refresh_from_db()
        return JsonResponse({"post": serialize_post(post), "warnings": warnings})
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("autosave blog post failed")
        return _json_error("自动保存失败", 500, detail=str(exc))

def delete_post(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    post.delete()
    return JsonResponse({"status": "Success"})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def search_posts(request: HttpRequest) -> JsonResponse:
    body = _body(request)
    query = str(body.get("q", body.get("query", "")) or "").strip()
    terms = [term for term in query.split() if term.strip()]
    try:
        posts = BlogPost.objects.all()
        posts = _apply_common_filters(body, posts, is_body=True)
        tags = normalize_tags(body.get("tags"))
        for tag in tags:
            posts = posts.filter(tags__name=tag)
        if query:
            posts = _apply_text_filter(posts, query)
            if terms:
                primary = terms[0]
                posts = posts.annotate(
                    relevance=Case(
                        When(title__iexact=primary, then=Value(100)),
                        When(title__icontains=primary, then=Value(60)),
                        When(content_text__icontains=primary, then=Value(20)),
                        default=Value(0),
                        output_field=IntegerField(),
                    )
                ).order_by("-relevance", "-date", "-id")
            else:
                posts = posts.order_by("-date", "-id")
        else:
            posts = posts.order_by("-date", "-id")

        try:
            page = max(1, int(body.get("page", 1)))
            page_size = min(100, max(1, int(body.get("pageSize", 20))))
        except (TypeError, ValueError):
            page, page_size = 1, 20

        total = posts.count()
        total_page = (total + page_size - 1) // page_size if total else 0
        if total_page and page > total_page:
            page = total_page
        start = (page - 1) * page_size
        rows = list(posts.prefetch_related("tags")[start:start + page_size])

        items = []
        for post in rows:
            item = serialize_post(post)
            item["snippet"] = highlight_snippet(post.content_text, terms)
            items.append(item)

        return JsonResponse({
            "items": items,
            "totalItems": total,
            "totalPage": total_page,
            "page": page,
            "pageSize": page_size,
            "query": query,
        })
    except ValueError as exc:
        return _json_error(str(exc))
    except Exception as exc:
        logger.exception("search blog posts failed")
        return _json_error("搜索文章失败", 500, detail=str(exc))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_tags(request: HttpRequest) -> JsonResponse:
    rows = (
        BlogTag.objects.annotate(
            count=Count(
                "post_tags",
                filter=Q(post_tags__post__status="published"),
            )
        )
        .filter(count__gt=0)
        .order_by("-count", "name")
    )
    return JsonResponse({
        "items": [{"id": tag.id, "name": tag.name, "count": tag.count} for tag in rows]
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_archive(request: HttpRequest) -> JsonResponse:
    rows = (
        BlogPost.objects.filter(status="published")
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("-month")
    )
    items = []
    for row in rows:
        month = row["month"]
        if not month:
            continue
        items.append({
            "year": month.year,
            "month": month.month,
            "count": row["count"],
            "label": f"{month.year}-{month.month:02d}",
        })
    return JsonResponse({"items": items})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_post_images(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    return JsonResponse({
        "items": [
            {
                "href": link.image_href,
                "collectionHref": link.collection_href,
                "role": link.role,
                "origin": link.origin,
                "sortOrder": link.sort_order,
            }
            for link in post.image_links.all()
        ]
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def sync_post_image_links(request: HttpRequest, post_id: int) -> JsonResponse:
    post = BlogPost.objects.filter(pk=post_id).first()
    if post is None:
        return _json_error("文章不存在", 404)
    warnings: List[str] = []
    sync_post_images(post, post.content_json, warnings)
    return JsonResponse({"status": "Success", "warnings": warnings})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def posts_collection(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return list_posts(request)
    return create_post(request)


@api_view(["GET", "PATCH", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def post_detail(request: HttpRequest, post_id: int) -> JsonResponse:
    if request.method == "GET":
        return get_post(request, post_id)
    if request.method == "DELETE":
        return delete_post(request, post_id)
    return update_post(request, post_id)
