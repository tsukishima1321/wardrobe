from django.http import HttpResponse
from wardrobe_db.models import Pictures, CollectionItems, Keywords, Properties, PicturesOcr
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
import uuid
import os
import requests
from django.conf import settings
from PIL import Image
from .common import LOCALHOST, _extract_body
from wardrobe_db.nlp.model import nlp_engine


def _generate_collection_thumbnail(collection_href):
    """Generate a composite image for a collection from its first few items."""
    items = CollectionItems.objects.filter(collection_id=collection_href).order_by('sort_order')[:4]

    composite_path = os.path.join(settings.IMAGE_STORAGE_PATH, collection_href)
    thumb_path = os.path.join(settings.THUMBNAILS_STORAGE_PATH, collection_href)

    if not items:
        for path in [composite_path, thumb_path]:
            if os.path.exists(path):
                os.remove(path)
        return

    images = []
    for item in items:
        path = os.path.join(settings.IMAGE_STORAGE_PATH, item.image_href)
        if os.path.exists(path):
            try:
                img = Image.open(path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                images.append(img)
            except Exception:
                pass

    if not images:
        return

    cell = 200
    count = len(images)

    if count == 1:
        img = images[0].copy()
        img.thumbnail((cell * 2, cell * 2))
        composite = Image.new('RGB', (cell * 2, cell * 2), (255, 255, 255))
        composite.paste(img, ((cell * 2 - img.width) // 2, (cell * 2 - img.height) // 2))
    elif count == 2:
        composite = Image.new('RGB', (cell * 2, cell), (255, 255, 255))
        for i, img in enumerate(images):
            img.thumbnail((cell, cell))
            composite.paste(img, (i * cell + (cell - img.width) // 2, (cell - img.height) // 2))
    elif count == 3:
        composite = Image.new('RGB', (cell * 2, cell * 2), (255, 255, 255))
        images[0].thumbnail((cell * 2, cell))
        composite.paste(images[0], ((cell * 2 - images[0].width) // 2, (cell - images[0].height) // 2))
        for i in range(1, 3):
            images[i].thumbnail((cell, cell))
            composite.paste(images[i], ((i - 1) * cell + (cell - images[i].width) // 2, cell + (cell - images[i].height) // 2))
    else:
        composite = Image.new('RGB', (cell * 2, cell * 2), (255, 255, 255))
        for i, img in enumerate(images[:4]):
            img.thumbnail((cell, cell))
            row, col = divmod(i, 2)
            composite.paste(img, (col * cell + (cell - img.width) // 2, row * cell + (cell - img.height) // 2))

    composite.save(composite_path, 'JPEG')

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

    _generate_collection_thumbnail(collection_href)

    return HttpResponse(json.dumps({'status': 'Success', 'image_href': image_href, 'sort_order': sort_order}), content_type='application/json')


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

    _generate_collection_thumbnail(collection_href)

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

    items = CollectionItems.objects.filter(collection=collection).order_by('sort_order')
    data = [{'image_href': item.image_href, 'sort_order': item.sort_order} for item in items]

    return HttpResponse(json.dumps(data), content_type='application/json')
