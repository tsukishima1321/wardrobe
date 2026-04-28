from typing import Dict, Any
from django.http import HttpRequest, HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, OcrMission, Keywords, Properties, BlankPictures, CollectionItems
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
import requests
import random as rand
from django.conf import settings
from .common import LOCALHOST, _extract_body
from wardrobe_db.nlp.model import nlp_engine

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getImageDetail(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src: str = body.get('src', '')
    picture = Pictures.objects.get(href=src)
    ocr_result = PicturesOcr.objects.filter(href=src)
    if ocr_result:
        ocr_result = ocr_result[0].ocr_result
    else:
        ocr_result = ''
    response = {'src': picture.href, 'title': picture.description, 'date': picture.date.strftime('%Y-%m-%d') if picture.date else None, 'text': ocr_result, 'is_collection': picture.is_collection}
    if picture.is_collection:
        items = CollectionItems.objects.filter(collection=picture)
        response['items'] = [{'image_href': item.image_href, 'sort_order': item.sort_order, 'liked': item.liked} for item in items]
    return HttpResponse(json.dumps(response), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setImageDetail(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src: str = body.get('src', '')
    title: str = body.get('title', '')
    date: str = body.get('date', '')
    picture = Pictures.objects.get(href=src)
    if not picture:
        return HttpResponse('Invalid picture', status=400)
    if title:
        picture.description = title
    if date:
        picture.date = date
    picture.save()
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteImage(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src: str = body.get('src', '')
    picture = Pictures.objects.filter(href=src).first()
    if not picture:
        return HttpResponse('Invalid picture', status=400)
    if picture.is_collection:
        return HttpResponse('Use collection/delete/ endpoint for collections', status=400)
    picture.delete()
    ocr_result = PicturesOcr.objects.filter(href=src)
    if ocr_result:
        ocr_result.delete()
    url = LOCALHOST + '/api/deletefile/'
    headers = {'Authorization': request.headers['Authorization']}
    res = requests.post(url, data={'imageName': src}, headers=headers)
    if res.status_code != 200:
        return HttpResponse(res.text, status=400)
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setImageText(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src: str = body.get('src', '')
    text: str = body.get('text', '')
    ocr_result = PicturesOcr.objects.filter(href=src).first()
    if ocr_result:
        ocr_result.ocr_result = text
    else:
        ocr_result = PicturesOcr(href=Pictures.objects.get(href=src), ocr_result=text)
    ocr_result.save()
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def random(request: HttpRequest) -> HttpResponse:
    keywordFilter: str = request.query_params.get('keyword', '')
    includeCollections: bool = request.query_params.get('includeCollections', 'false').lower() == 'true'
    if keywordFilter:
        pictures = Pictures.objects.filter(keywords__keyword=keywordFilter)
    else:
        pictures = Pictures.objects.all()
    if not includeCollections:
        pictures = pictures.filter(is_collection=False)
    picture = rand.choice(pictures)
    response = {'src': picture.href, 'title': picture.description}
    return HttpResponse(json.dumps(response), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def newImage(request: HttpRequest) -> HttpResponse:
    url = LOCALHOST + '/api/upload/'
    headers = {'Authorization': request.headers['Authorization']}
    res = requests.post(url, files=request.FILES, headers=headers)
    if res.status_code == 200:
        data = json.loads(res.text)
        src: str = data['md5']
        title: str = request.POST.get('title', '')
        date: str = request.POST.get('date', '')
        unprocessed: str = request.POST.get('unprocessed', 'false')
        if not title or not date or unprocessed.lower() == 'true':
            if not title:
                title = ''
            if not date:
                date = None
            picture = Pictures(href=src, description=title, date=date)
            picture.save()
            flag = BlankPictures(href=src)
            flag.save()
            return HttpResponse(json.dumps({'status':'Success','md5':src}), content_type='application/json')
        picture = Pictures(href=src, description=title, date=date)
        picture.save()
        doOCR = request.POST.get('doOCR', False)
        if doOCR and doOCR != 'false' and doOCR != 'False':
            ocrmission = OcrMission(href=Pictures.objects.get(href=src), status='waiting')
            ocrmission.save()
        else:
            ocr_result = PicturesOcr(href=Pictures.objects.get(href=src), ocr_result='')
            ocr_result.save()

        keywords = request.POST.get('keywords', '')
        if keywords:
            keywordList = json.loads(keywords)
            for kw in keywordList:
                keyword = Keywords(href=Pictures.objects.get(href=src), keyword=kw)
                keyword.save()
        properties = request.POST.get('properties', '')
        prop_update_dict: Dict[str, Any] = {}
        if properties:
            propertyList = json.loads(properties)
            for prop in propertyList:
                property = Properties(href=Pictures.objects.get(href=src), property_name=prop['name'], value=prop['value'])
                property.save()
                if prop['name'] not in prop_update_dict:
                    prop_update_dict[prop['name']] = []
                prop_update_dict[prop['name']].append(prop['value'])

        if title:
            kw_list = json.loads(keywords) if keywords else []
            nlp_engine.update(title, keywords=kw_list, properties=prop_update_dict, mode='add', update_word_counts=True)

        return HttpResponse(json.dumps({'status':'Success','md5':src}), content_type='application/json')
    else:
        return HttpResponse(res.text, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listBlankImages(request: HttpRequest) -> HttpResponse:
    blanks = BlankPictures.objects.all()
    blank_list = [blank.href for blank in blanks]
    return HttpResponse(json.dumps(blank_list), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reprocessImage(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src: str = (body.get('src') or '').strip()
    if not src:
        return HttpResponse('Missing src', status=400)
    picture = BlankPictures.objects.filter(href=src).first()
    if not picture:
        return HttpResponse('Picture is not marked as blank', status=404)
    picture.delete()
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
