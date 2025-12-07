from django.http import HttpResponse
from wardrobe_db.models import Pictures, Keywords, Properties, SavedSearch
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
import json
from .common import _extract_body

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search(request):
    body = _extract_body(request)
    searchKey = body.get('searchKey', '')
    byName = body.get('byName', True)
    byFullText = body.get('byFullText', False)
    orderBy = body.get('orderBy', 'href')
    order = body.get('order', 'asc')
    pageSize = body.get('pageSize', 20)
    page = body.get('page', 1)
    dateFrom = body.get('dateFrom', '')
    dateTo = body.get('dateTo', '')
    keywords = body.get('keywords', [])
    properties = body.get('properties', [])
    excludedKeywords = body.get('excludedKeywords', [])
    excludedProperties = body.get('excludedProperties', [])
    propertiesPrecise = body.get('propertiesPrecise', False)

    pictures = Pictures.objects.all()
    if byName and not byFullText:
        keys = searchKey.split(' ')
        for k in keys:
            pictures = pictures.filter(description__contains=k) | pictures.filter(keywords__keyword=k)
    if byFullText and not byName:
        keys = searchKey.split(' ')
        for k in keys:
            pictures = pictures.filter(picturesocr__ocr_result__contains=k)
    if byName and byFullText:
        keys = searchKey.split(' ')
        for k in keys:
            pictures = pictures.filter(description__contains=k) | pictures.filter(picturesocr__ocr_result__contains=k)
    if not byName and not byFullText:
        return HttpResponse('Invalid search method', status=400)

    for kw in keywords:
        pictures = pictures.filter(keywords__keyword=kw)
    for prop in properties:
        if propertiesPrecise:
            pictures = pictures.filter(properties__property_name=prop['name'], properties__value=prop['value'])
        else:
            pictures = pictures.filter(properties__property_name=prop['name'], properties__value__contains=prop['value'])

    for kw in excludedKeywords:
        pictures = pictures.exclude(keywords__keyword=kw)
    for prop in excludedProperties:
        if propertiesPrecise:
            pictures = pictures.exclude(properties__property_name=prop['name'], properties__value=prop['value'])
        else:
            pictures = pictures.exclude(properties__property_name=prop['name'], properties__value__contains=prop['value'])

    if dateFrom:
        pictures = pictures.filter(date__gte=dateFrom)
    if dateTo:
        pictures = pictures.filter(date__lte=dateTo)
    if order == 'asc':
        pictures = pictures.order_by(orderBy, 'href')
    else:
        pictures = pictures.order_by('-' + orderBy, 'href')

    totalPage = len(pictures) // pageSize + 1
    total = len(pictures)
    if page > totalPage:
        return HttpResponse('Invalid page number', status=400)
    pictures = pictures.distinct()
    pictures = pictures[(page - 1) * pageSize:page * pageSize]
    #hrefList = [{'src' = picture.href,'title' = picture.description} for picture in pictures]
    hrefList = []
    for picture in pictures:
        hrefList.append({'src': picture.href, 'title': picture.description,'date':picture.date.strftime('%Y-%m-%d')})
    response = {'total':total,'totalPage': totalPage, 'hrefList': hrefList}

    return HttpResponse(json.dumps(response), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def searchHint(request):
    keywords = (
        Keywords.objects.values('keyword')
        .annotate(count=Count('keyword'))
        .order_by('-count')[:10]
    )
    keywordList = [k['keyword'] for k in keywords]

    properties = (
        Properties.objects.values('property_name')
        .annotate(count=Count('property_name'))
        .order_by('-count')[:5]
    )
    propertyList = [p['property_name'] for p in properties]
    return HttpResponse(json.dumps({'keywords': keywordList, 'properties': propertyList}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def saveSearchFilter(request):
    body = _extract_body(request)
    name = (body.get('name') or '').strip()
    searchparams = body.get('searchparams', {})
    if not name or not searchparams:
        return HttpResponse('Missing name or searchparams', status=400)
    searchparams_json = json.dumps(searchparams)
    saved_search = SavedSearch(name=name, searchparams=searchparams_json)
    saved_search.save()
    return HttpResponse(json.dumps({'id': saved_search.id}), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def listSavedSearchFilters(request):
    saved_searches = SavedSearch.objects.all()
    data = [{'id': s.id, 'name': s.name} for s in saved_searches]
    return HttpResponse(json.dumps(data), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getSavedSearchFilter(request):
    body = _extract_body(request)
    search_id = body.get('id', None)
    if search_id is None:
        return HttpResponse('Missing id', status=400)
    saved_search = SavedSearch.objects.filter(id=search_id).first()
    if not saved_search:
        return HttpResponse('Saved search not found', status=404)
    data = saved_search.searchparams
    return HttpResponse(json.dumps(data), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteSavedSearch(request):
    body = _extract_body(request)
    search_id = body.get('id', None)
    if search_id is None:
        return HttpResponse('Missing id', status=400)
    deleted_count, _ = SavedSearch.objects.filter(id=search_id).delete()
    if not deleted_count:
        return HttpResponse('Saved search not found', status=404)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
