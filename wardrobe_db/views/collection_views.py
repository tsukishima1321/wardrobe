from django.http import HttpResponse
from wardrobe_db.models import Pictures, CollectionItems, Keywords, Properties, PicturesOcr
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
import uuid
import os
import threading
import requests
from django.conf import settings
from PIL import Image, ImageDraw
from .common import LOCALHOST, _extract_body
from wardrobe_db.nlp.model import nlp_engine

# ---------------------------------------------------------------------------
# Collection thumbnail generator – magazine-style collage
# ---------------------------------------------------------------------------

_CANVAS = 600          # Final composite is _CANVAS x _CANVAS pixels
_GAP = 4               # Gap between cells (pixels)
_RADIUS = 12           # Corner radius for the overall composite
_BG = (245, 245, 245)  # Light-grey background visible through gaps
_MAX_IMAGES = 7        # Use up to this many images


def _center_crop_fill(img, target_w, target_h):
    """Resize *img* so it fully covers (target_w, target_h), then center-crop."""
    src_ratio = img.width / img.height
    dst_ratio = target_w / target_h
    if src_ratio > dst_ratio:
        # Wider than needed – match height, crop width
        new_h = target_h
        new_w = int(target_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / src_ratio) if src_ratio else target_h
    img = img.resize((max(new_w, 1), max(new_h, 1)), Image.LANCZOS)
    left = (img.width - target_w) // 2
    top = (img.height - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def _round_corners(img, radius):
    """Apply rounded corners to an RGBA or RGB image, returning RGBA."""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    mask = Image.new('L', img.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), img.size], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def _classify_orientation(images):
    """Return 'portrait', 'landscape', or 'mixed'."""
    portraits = sum(1 for im in images if im.height > im.width)
    landscapes = sum(1 for im in images if im.width > im.height)
    total = len(images)
    if portraits >= total * 0.7:
        return 'portrait'
    if landscapes >= total * 0.7:
        return 'landscape'
    return 'mixed'


def _layout_cells(count, orientation):
    """Return a list of (x, y, w, h) tuples describing cell positions.

    All coordinates are in a normalised 0-based pixel grid of size
    (_CANVAS x _CANVAS).  Gaps are baked in.
    """
    S = _CANVAS
    G = _GAP
    half = (S - G) // 2
    third = (S - 2 * G) // 3

    if count == 1:
        return [(0, 0, S, S)]

    if count == 2:
        if orientation == 'portrait':
            # Two tall columns side by side
            return [(0, 0, half, S), (half + G, 0, half, S)]
        else:
            # Two wide rows stacked
            return [(0, 0, S, half), (0, half + G, S, half)]

    if count == 3:
        if orientation == 'portrait':
            # One big left column + two stacked on the right
            big_w = int(S * 0.6)
            small_w = S - big_w - G
            return [
                (0, 0, big_w, S),
                (big_w + G, 0, small_w, half),
                (big_w + G, half + G, small_w, half),
            ]
        elif orientation == 'landscape':
            # One big top row + two side-by-side bottom
            big_h = int(S * 0.6)
            small_h = S - big_h - G
            return [
                (0, 0, S, big_h),
                (0, big_h + G, half, small_h),
                (half + G, big_h + G, half, small_h),
            ]
        else:
            # T-layout: big left, two stacked right
            big_w = int(S * 0.55)
            small_w = S - big_w - G
            return [
                (0, 0, big_w, S),
                (big_w + G, 0, small_w, half),
                (big_w + G, half + G, small_w, half),
            ]

    if count == 4:
        # 2x2 grid – works well for any orientation
        return [
            (0, 0, half, half),
            (half + G, 0, half, half),
            (0, half + G, half, half),
            (half + G, half + G, half, half),
        ]

    if count == 5:
        if orientation == 'portrait':
            # Top row: 2 portrait slots, bottom row: 3 narrower
            top_h = int(S * 0.55)
            bot_h = S - top_h - G
            return [
                (0, 0, half, top_h),
                (half + G, 0, half, top_h),
                (0, top_h + G, third, bot_h),
                (third + G, top_h + G, third, bot_h),
                (2 * (third + G), top_h + G, third, bot_h),
            ]
        elif orientation == 'landscape':
            # Left column: 2 landscape rows, right: 3 rows
            left_w = int(S * 0.55)
            right_w = S - left_w - G
            return [
                (0, 0, left_w, half),
                (0, half + G, left_w, half),
                (left_w + G, 0, right_w, third),
                (left_w + G, third + G, right_w, third),
                (left_w + G, 2 * (third + G), right_w, third),
            ]
        else:
            # L-shape: big top-left, 2 stacked right, 2 side-by-side bottom
            big = int(S * 0.6)
            right_w = S - big - G
            right_h = (big - G) // 2
            bot_h = S - big - G
            bot_w = (S - G) // 2
            return [
                (0, 0, big, big),
                (big + G, 0, right_w, right_h),
                (big + G, right_h + G, right_w, right_h),
                (0, big + G, bot_w, bot_h),
                (bot_w + G, big + G, bot_w, bot_h),
            ]

    if count == 6:
        # 3x2 or 2x3 depending on orientation
        if orientation == 'landscape':
            row_h = (S - G) // 2
            col_w = third
            cells = []
            for r in range(2):
                for c in range(3):
                    cells.append((c * (third + G), r * (row_h + G), third, row_h))
            return cells
        else:
            col_w = (S - G) // 2
            row_h = third
            cells = []
            for r in range(3):
                for c in range(2):
                    cells.append((c * (col_w + G), r * (third + G), col_w, third))
            return cells

    # count >= 7: hero image on top + 3 on each side below (grid of 6)
    hero_h = int(S * 0.45)
    bot_h = S - hero_h - G
    bot_third = (S - 2 * G) // 3
    cells = [(0, 0, S, hero_h)]
    # Bottom two rows of 3
    remaining = min(count - 1, 6)
    cols = 3
    rows = (remaining + cols - 1) // cols  # 1 or 2 rows
    row_h = (bot_h - (rows - 1) * G) // rows if rows else bot_h
    idx = 0
    for r in range(rows):
        items_in_row = min(cols, remaining - idx)
        cw = (S - (items_in_row - 1) * G) // items_in_row
        for c in range(items_in_row):
            cells.append((c * (cw + G), hero_h + G + r * (row_h + G), cw, row_h))
            idx += 1
    return cells


def _generate_collection_thumbnail(collection_href):
    """Generate a magazine-style composite image for a collection.

    Strategy:
    1. Prefer liked items; fall back to all items.
    2. Classify dominant orientation (portrait / landscape / mixed).
    3. Pick a layout template that flatters the orientation.
    4. Center-crop each image into its cell for a clean, gapless look.
    5. Apply rounded corners to the final composite.
    """
    liked_items = CollectionItems.objects.filter(
        collection_id=collection_href, liked=True
    ).order_by('sort_order')[:_MAX_IMAGES]
    items = (
        liked_items if liked_items.exists()
        else CollectionItems.objects.filter(
            collection_id=collection_href
        ).order_by('sort_order')[:_MAX_IMAGES]
    )

    composite_path = os.path.join(settings.IMAGE_STORAGE_PATH, collection_href)
    thumb_path = os.path.join(settings.THUMBNAILS_STORAGE_PATH, collection_href)

    if not items:
        for p in [composite_path, thumb_path]:
            if os.path.exists(p):
                os.remove(p)
        return

    images = []
    for item in items:
        p = os.path.join(settings.IMAGE_STORAGE_PATH, item.image_href)
        if os.path.exists(p):
            try:
                img = Image.open(p)
                if img.mode not in ('RGB', 'RGBA'):
                    img = img.convert('RGB')
                images.append(img)
            except Exception:
                pass

    if not images:
        return

    orientation = _classify_orientation(images)
    cells = _layout_cells(len(images), orientation)

    composite = Image.new('RGB', (_CANVAS, _CANVAS), _BG)

    for img, (cx, cy, cw, ch) in zip(images, cells):
        cropped = _center_crop_fill(img, cw, ch)
        composite.paste(cropped, (cx, cy))

    # Round the overall corners
    composite = _round_corners(composite, _RADIUS)

    # Flatten to RGB on white for JPEG saving
    flat = Image.new('RGB', composite.size, (255, 255, 255))
    flat.paste(composite, mask=composite.split()[3])
    flat.save(composite_path, 'JPEG', quality=88)

    # Remove cached thumbnail so it gets regenerated on next request
    if os.path.exists(thumb_path):
        os.remove(thumb_path)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createCollection(request):
    body = _extract_body(request)
    title = (body.get('title') or '').strip()
    date = body.get('date') or None
    keywords = body.get('keywords', [])
    properties = body.get('properties', [])

    href = 'col_' + uuid.uuid4().hex[:8] + '.jpg'
    while Pictures.objects.filter(href=href).exists():
        href = 'col_' + uuid.uuid4().hex[:8] + '.jpg'

    picture = Pictures(href=href, description=title, date=date, is_collection=True)
    picture.save()

    for kw in keywords:
        Keywords.objects.create(href=picture, keyword=kw)

    prop_update_dict = {}
    for prop in properties:
        Properties.objects.create(href=picture, property_name=prop['name'], value=prop['value'])
        if prop['name'] not in prop_update_dict:
            prop_update_dict[prop['name']] = []
        prop_update_dict[prop['name']].append(prop['value'])

    # Update NLP model
    if title:
        nlp_engine.update(title, keywords=keywords, properties=prop_update_dict, mode='add', update_word_counts=True)

    return HttpResponse(json.dumps({'status': 'Success', 'href': href}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def addCollectionItem(request):
    collection_href = request.POST.get('src', '').strip()
    if not collection_href:
        return HttpResponse('Missing collection src', status=400)

    collection = Pictures.objects.filter(href=collection_href, is_collection=True).first()
    if not collection:
        return HttpResponse('Collection not found', status=404)

    # Upload image via image bed
    url = LOCALHOST + '/api/upload/'
    headers = {'Authorization': request.headers['Authorization']}
    res = requests.post(url, files=request.FILES, headers=headers)

    if res.status_code == 200:
        data = json.loads(res.text)
        image_href = data['md5']
    elif res.status_code == 400:
        # Image may already exist, extract md5 if available
        try:
            data = json.loads(res.text)
            if 'md5' in data:
                image_href = data['md5']
            else:
                return HttpResponse(res.text, status=400)
        except json.JSONDecodeError:
            return HttpResponse(res.text, status=400)
    else:
        return HttpResponse(res.text, status=res.status_code)

    # Check if this image is already in the collection
    if CollectionItems.objects.filter(collection=collection, image_href=image_href).exists():
        return HttpResponse(json.dumps({'status': 'Already exists', 'image_href': image_href}), status=400, content_type='application/json')

    max_order = CollectionItems.objects.filter(collection=collection).order_by('-sort_order').values_list('sort_order', flat=True).first()
    sort_order = (max_order or 0) + 1

    CollectionItems.objects.create(collection=collection, image_href=image_href, sort_order=sort_order)

    threading.Thread(target=_generate_collection_thumbnail, args=(collection_href,), daemon=True).start()

    return HttpResponse(json.dumps({'status': 'Success', 'image_href': image_href, 'sort_order': sort_order}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def likeCollectionItem(request):
    body = _extract_body(request)
    collection_href = (body.get('src') or '').strip()
    image_href = (body.get('image_href') or '').strip()
    liked = body.get('liked', True)

    if not collection_href or not image_href:
        return HttpResponse('Missing src or image_href', status=400)

    collection = Pictures.objects.filter(href=collection_href, is_collection=True).first()
    if not collection:
        return HttpResponse('Collection not found', status=404)

    item = CollectionItems.objects.filter(collection=collection, image_href=image_href).first()
    if not item:
        return HttpResponse('Item not found in collection', status=404)

    item.liked = bool(liked)
    item.save()

    threading.Thread(target=_generate_collection_thumbnail, args=(collection_href,), daemon=True).start()

    return HttpResponse(json.dumps({'status': 'Success', 'liked': item.liked}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def removeCollectionItem(request):
    body = _extract_body(request)
    collection_href = (body.get('src') or '').strip()
    image_href = (body.get('image_href') or '').strip()

    if not collection_href or not image_href:
        return HttpResponse('Missing src or image_href', status=400)

    collection = Pictures.objects.filter(href=collection_href, is_collection=True).first()
    if not collection:
        return HttpResponse('Collection not found', status=404)

    deleted_count, _ = CollectionItems.objects.filter(collection=collection, image_href=image_href).delete()
    if not deleted_count:
        return HttpResponse('Item not found in collection', status=404)

    # Delete the image file only if not referenced elsewhere
    other_refs = CollectionItems.objects.filter(image_href=image_href).exists()
    is_standalone = Pictures.objects.filter(href=image_href).exists()
    if not other_refs and not is_standalone:
        image_path = os.path.join(settings.IMAGE_STORAGE_PATH, image_href)
        if os.path.exists(image_path):
            os.remove(image_path)
        thumb_path = os.path.join(settings.THUMBNAILS_STORAGE_PATH, image_href)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)

    threading.Thread(target=_generate_collection_thumbnail, args=(collection_href,), daemon=True).start()

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteCollection(request):
    body = _extract_body(request)
    collection_href = (body.get('src') or '').strip()

    if not collection_href:
        return HttpResponse('Missing src', status=400)

    collection = Pictures.objects.filter(href=collection_href, is_collection=True).first()
    if not collection:
        return HttpResponse('Collection not found', status=404)

    # Delete all item image files that are not referenced elsewhere
    items = CollectionItems.objects.filter(collection=collection)
    for item in items:
        other_refs = CollectionItems.objects.filter(image_href=item.image_href).exclude(collection=collection).exists()
        is_standalone = Pictures.objects.filter(href=item.image_href).exists()
        if not other_refs and not is_standalone:
            image_path = os.path.join(settings.IMAGE_STORAGE_PATH, item.image_href)
            if os.path.exists(image_path):
                os.remove(image_path)
            thumb_path = os.path.join(settings.THUMBNAILS_STORAGE_PATH, item.image_href)
            if os.path.exists(thumb_path):
                os.remove(thumb_path)

    # Delete the collection record (CASCADE handles CollectionItems, Keywords, Properties, etc.)
    collection.delete()

    # Delete the composite image and its thumbnail
    composite_path = os.path.join(settings.IMAGE_STORAGE_PATH, collection_href)
    if os.path.exists(composite_path):
        os.remove(composite_path)
    thumb_path = os.path.join(settings.THUMBNAILS_STORAGE_PATH, collection_href)
    if os.path.exists(thumb_path):
        os.remove(thumb_path)

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listCollectionItems(request):
    body = _extract_body(request)
    collection_href = (body.get('src') or '').strip()

    if not collection_href:
        return HttpResponse('Missing src', status=400)

    collection = Pictures.objects.filter(href=collection_href, is_collection=True).first()
    if not collection:
        return HttpResponse('Collection not found', status=404)

    items = CollectionItems.objects.filter(collection=collection)
    data = [{'image_href': item.image_href, 'sort_order': item.sort_order, 'liked': item.liked} for item in items]

    return HttpResponse(json.dumps(data), content_type='application/json')
