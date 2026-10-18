"""Pure helpers for the blog rich-text pipeline.

This module intentionally has no Django model imports so it can be tested
without a database.
"""

import html
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import nh3

IMAGE_HREF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
INTERNAL_IMAGE_URL_RE = re.compile(r"/imagebed/(?:thumbnails/(?:large/|medium/|small/)?)?([A-Za-z0-9][A-Za-z0-9._-]{0,199})")
WORD_RE = re.compile(r"[A-Za-z0-9_]+")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")

ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "code", "del", "em", "figcaption", "figure",
    "h1", "h2", "h3", "h4", "hr", "i", "img", "li", "mark", "ol", "p", "pre",
    "s", "span", "strong", "table", "tbody", "td", "th", "thead", "tr", "u", "ul",
}

ALLOWED_ATTRIBUTES = {
    "*": {"class"},
    "a": {"href", "title", "target", "data-image-ref"},
    "img": {"src", "alt", "title", "width", "height", "style", "data-image-href", "data-caption"},
    "p": {"style"},
    "h1": {"style"},
    "h2": {"style"},
    "h3": {"style"},
    "h4": {"style"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class", "data-image-ref"},
}

ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def _attribute_filter(tag: str, attribute: str, value: str) -> Optional[str]:
    if tag == "img" and attribute == "src":
        if not value:
            return None
        if not value.startswith("/imagebed/"):
            return None
        return value
    if tag == "img" and attribute == "data-image-href":
        return value if validate_image_href(value) else None
    if tag == "a" and attribute == "data-image-ref":
        return value if validate_image_href(value) else None
    if tag == "a" and attribute == "href":
        lowered = value.strip().lower()
        if lowered.startswith(("http://", "https://", "mailto:", "/", "#")):
            return value
        return None
    if tag == "a" and attribute == "target":
        return "_blank" if value == "_blank" else None
    if attribute == "class":
        # Classes are only used for editor/read rendering, not for scripts.
        return " ".join(part for part in value.split() if part)[:200]
    return value


def sanitize_html(value: str) -> str:
    if not value:
        return ""
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes=ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer",
        attribute_filter=_attribute_filter,
        filter_style_properties={"text-align", "width"},
        strip_comments=True,
    )


def validate_image_href(href: str) -> bool:
    return bool(href and IMAGE_HREF_RE.match(href.strip()))


def normalize_image_href(value: str) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    match = INTERNAL_IMAGE_URL_RE.search(value)
    if match:
        value = match.group(1)
    if validate_image_href(value):
        return value
    return None


def coerce_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _node_text(node: Any) -> str:
    if not isinstance(node, dict):
        return ""
    node_type = node.get("type")
    attrs = node.get("attrs") or {}
    if node_type == "text":
        return str(node.get("text") or "")
    if node_type in {"hardBreak", "hard_break"}:
        return "\n"
    if node_type == "image":
        return str(attrs.get("caption") or attrs.get("alt") or "")
    if node_type == "imageRef":
        return str(attrs.get("label") or attrs.get("alt") or "")
    if node_type == "gallery":
        items = attrs.get("items") or []
        labels = []
        for item in items:
            if isinstance(item, dict):
                labels.append(str(item.get("caption") or item.get("alt") or ""))
        return " ".join(label for label in labels if label)
    children = node.get("content") or []
    text = "".join(_node_text(child) for child in children)
    if node_type in {"paragraph", "heading", "blockquote", "codeBlock", "listItem", "taskItem"}:
        return text + "\n"
    if node_type == "horizontalRule":
        return "\n"
    return text


def normalize_text(value: str) -> str:
    value = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_text_from_tiptap(doc: Any) -> str:
    doc = coerce_json(doc)
    if not doc:
        return ""
    if doc.get("type") != "doc":
        return normalize_text(_node_text(doc))
    return normalize_text(_node_text(doc))


def _split_plain_text_blocks(text: str) -> List[str]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)*", "\n\n", normalized)
    normalized = normalized.strip("\n")
    if not normalized.strip():
        return []
    return [block for block in normalized.split("\n\n") if block.strip()]


def plain_text_to_doc(text: str) -> Dict[str, Any]:
    """Convert plain text while preserving single line breaks.

    A blank line separates paragraphs. Single newlines become hard breaks
    inside the same paragraph.
    """
    content = []
    for block in _split_plain_text_blocks(text):
        paragraph_content: List[Dict[str, Any]] = []
        for index, line in enumerate(block.split("\n")):
            if index:
                paragraph_content.append({"type": "hardBreak"})
            if line:
                paragraph_content.append({"type": "text", "text": line})
        content.append({
            "type": "paragraph",
            "content": paragraph_content,
        } if paragraph_content else {"type": "paragraph"})
    return {"type": "doc", "content": content or [{"type": "paragraph"}]}


def plain_text_to_html(text: str) -> str:
    parts = []
    for block in _split_plain_text_blocks(text):
        lines = block.split("\n")
        escaped = "<br>".join(html.escape(line) for line in lines)
        parts.append(f"<p>{escaped}</p>")
    return "".join(parts) or "<p></p>"


def make_excerpt(text: str, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


def count_words(text: str) -> int:
    cjk_count = len(CJK_RE.findall(text or ""))
    latin_count = len(WORD_RE.findall(text or ""))
    return cjk_count + latin_count


def auto_title(_text: str, date_value: str) -> str:
    """Default title for notes: a plain date string, e.g. 2026-10-17."""
    value = (date_value or "").strip()
    return value[:10] if value else "随手一记"


def _append_image_ref(refs: List[Dict[str, Any]], href: Any, role: str, attrs: Dict[str, Any]) -> None:
    normalized = normalize_image_href(str(href or ""))
    if not normalized:
        return
    refs.append({
        "href": normalized,
        "role": role,
        "alt": str(attrs.get("alt") or ""),
        "caption": str(attrs.get("caption") or attrs.get("label") or ""),
    })


def collect_image_refs(doc: Any) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        node_type = node.get("type")
        attrs = node.get("attrs") or {}
        if node_type == "image":
            _append_image_ref(refs, attrs.get("href") or attrs.get("src"), "inline", attrs)
        elif node_type == "imageRef":
            _append_image_ref(refs, attrs.get("href"), "reference", attrs)
        elif node_type == "collectionRef":
            _append_image_ref(refs, attrs.get("href"), "collection", attrs)
        elif node_type == "gallery":
            items = attrs.get("items") or attrs.get("images") or []
            if isinstance(items, (list, tuple)):
                for item in items:
                    if isinstance(item, dict):
                        _append_image_ref(refs, item.get("href") or item.get("src"), "gallery", item)
                    else:
                        _append_image_ref(refs, item, "gallery", {})
        for child in node.get("content") or []:
            walk(child)

    walk(doc)
    return refs


def _merge_ranges(ranges: Iterable[Tuple[int, int]]) -> List[Tuple[int, int]]:
    merged: List[Tuple[int, int]] = []
    for start, end in sorted(ranges):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def highlight_snippet(text: str, terms: Sequence[str], radius: int = 70, max_length: int = 220) -> Dict[str, Any]:
    text = text or ""
    terms = [term for term in terms if term]
    if not text:
        return {"text": "", "highlights": []}

    lower_text = text.lower()
    first_index = -1
    for term in terms:
        index = lower_text.find(term.lower())
        if index != -1 and (first_index == -1 or index < first_index):
            first_index = index

    if first_index == -1:
        snippet = text[:max_length]
        prefix = ""
        suffix = "…" if len(text) > max_length else ""
    else:
        start = max(0, first_index - radius)
        end = min(len(text), first_index + radius + max(len(term) for term in terms))
        if end - start > max_length:
            end = start + max_length
        snippet = text[start:end]
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""

    rendered = prefix + snippet + suffix
    offset = len(prefix)
    ranges = []
    lower_snippet = snippet.lower()
    for term in terms:
        term_lower = term.lower()
        if not term_lower:
            continue
        start = 0
        while True:
            index = lower_snippet.find(term_lower, start)
            if index == -1:
                break
            ranges.append((offset + index, offset + index + len(term)))
            start = index + max(1, len(term_lower))
    return {
        "text": rendered,
        "highlights": [[start, end] for start, end in _merge_ranges(ranges)],
    }


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "")
