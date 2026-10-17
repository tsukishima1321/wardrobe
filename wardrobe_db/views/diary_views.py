"""Compatibility endpoints for the legacy /api/diary/* API.

The new blog frontend uses /api/blog/*. These handlers keep old bookmarks,
the home page and external callers working while reading from BlogPost.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict

from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from wardrobe_db.blog_service import (
    create_note_from_text,
    parse_date,
    update_note_from_text,
)
from wardrobe_db.models import BlogPost
from wardrobe_db.views.common import _extract_body

logger = logging.getLogger("db")


def _legacy_item(post: BlogPost) -> Dict[str, Any]:
    return {
        "id": post.id,
        "date": post.date.strftime("%Y-%m-%d") if post.date else "",
        "text": post.content_text,
        "title": post.title,
        "kind": post.kind,
        "status": post.status,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def search(request: HttpRequest) -> HttpResponse:
    try:
        body: Dict[str, Any] = _extract_body(request)
        search_key = str(body.get("searchKey", "") or "").strip()
        date_from = str(body.get("dateFrom", "") or "").strip()
        date_to = str(body.get("dateTo", "") or "").strip()
        order = str(body.get("order", "desc") or "desc").lower()
        try:
            page_size = max(1, min(100, int(body.get("pageSize", 20))))
            page = max(1, int(body.get("page", 1)))
        except (TypeError, ValueError):
            page_size, page = 20, 1

        posts = BlogPost.objects.filter(status="published")
        if search_key:
            for term in [part for part in search_key.split() if part]:
                posts = posts.filter(
                    Q(title__icontains=term)
                    | Q(content_text__icontains=term)
                    | Q(tags__name__icontains=term)
                ).distinct()
        if date_from:
            posts = posts.filter(date__gte=parse_date(date_from))
        if date_to:
            posts = posts.filter(date__lte=parse_date(date_to))

        prefix = "" if order == "asc" else "-"
        posts = posts.order_by(f"{prefix}date", f"{prefix}id")
        total = posts.count()
        total_page = (total + page_size - 1) // page_size if total else 0
        if total_page and page > total_page:
            page = total_page
        start = (page - 1) * page_size
        rows = posts[start:start + page_size]

        return HttpResponse(json.dumps({
            "totalPage": total_page,
            "textList": [_legacy_item(post) for post in rows],
            "totalItems": total,
        }), content_type="application/json")
    except Exception as exc:
        logger.error("Error in legacy diary search: %s", exc)
        return HttpResponse("Search failed", status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def getDiaryTexts(request: HttpRequest) -> HttpResponse:
    try:
        body: Dict[str, Any] = _extract_body(request)
        text_id = body.get("id", "")
        if text_id:
            try:
                post = BlogPost.objects.get(id=int(text_id))
            except (TypeError, ValueError):
                return HttpResponse("Invalid ID format", status=400)
            except BlogPost.DoesNotExist:
                return HttpResponse("Diary text not found", status=404)
            return HttpResponse(json.dumps(_legacy_item(post)), content_type="application/json")

        posts = BlogPost.objects.filter(status="published").order_by("-date", "-id")
        return HttpResponse(json.dumps([_legacy_item(post) for post in posts]), content_type="application/json")
    except Exception as exc:
        logger.error("Error in legacy getDiaryTexts: %s", exc)
        return HttpResponse(status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def newDiaryText(request: HttpRequest) -> HttpResponse:
    try:
        body: Dict[str, Any] = _extract_body(request)
        date = str(body.get("date", "") or "").strip()
        text = str(body.get("text", "") or "")
        if not date or not text:
            return HttpResponse("Date and text are required", status=400)
        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return HttpResponse("Invalid date format. Use YYYY-MM-DD", status=400)

        post = create_note_from_text(date, text)
        return HttpResponse(json.dumps({"status": "Success", "id": post.id}), content_type="application/json")
    except Exception as exc:
        logger.error("Error in legacy newDiaryText: %s", exc)
        return HttpResponse(status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def deleteDiaryText(request: HttpRequest) -> HttpResponse:
    try:
        body: Dict[str, Any] = _extract_body(request)
        text_id = body.get("id", "")
        if not text_id:
            return HttpResponse("ID is required", status=400)
        try:
            post = BlogPost.objects.get(id=int(text_id))
        except (TypeError, ValueError):
            return HttpResponse("Invalid ID format", status=400)
        except BlogPost.DoesNotExist:
            return HttpResponse("Diary text not found", status=404)
        post.delete()
        return HttpResponse(json.dumps({"status": "Success"}), content_type="application/json")
    except Exception as exc:
        logger.error("Error in legacy deleteDiaryText: %s", exc)
        return HttpResponse(status=500)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def editDiaryText(request: HttpRequest) -> HttpResponse:
    try:
        body: Dict[str, Any] = _extract_body(request)
        text_id = body.get("id", "")
        date = str(body.get("date", "") or "").strip()
        text = str(body.get("text", "") or "")
        if not text_id:
            return HttpResponse("ID is required", status=400)
        try:
            post = BlogPost.objects.get(id=int(text_id))
        except (TypeError, ValueError):
            return HttpResponse("Invalid ID format", status=400)
        except BlogPost.DoesNotExist:
            return HttpResponse("Diary text not found", status=404)

        if date:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                return HttpResponse("Invalid date format. Use YYYY-MM-DD", status=400)
        update_note_from_text(post, text or post.content_text, date or post.date)
        return HttpResponse(json.dumps({"status": "Success"}), content_type="application/json")
    except Exception as exc:
        logger.error("Error in legacy editDiaryText: %s", exc)
        return HttpResponse(status=500)
