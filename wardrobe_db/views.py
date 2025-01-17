from django.shortcuts import render
from django.http import HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, Types
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        searchKey = body.get('searchKey', '')
        type = body.get('type', 'all')
        byName = body.get('byName', True)
        byFullText = body.get('byFullText', False)
        orderBy = body.get('orderBy', 'href')
        order = body.get('order', 'asc')
        pageSize = body.get('pageSize', 20)
        page = body.get('page', 1)
        dateFrom = body.get('dateFrom', '')
        dateTo = body.get('dateTo', '')
    else:
        searchKey:str = request.POST.get('searchKey', '')
        type:str = request.POST.get('type', 'all')
        byName:bool = request.POST.get('byName', True)
        byFullText:bool = request.POST.get('byFullText', False)
        orderBy:str = request.POST.get('orderBy', 'href')
        order:str = request.POST.get('order', 'asc')
        pageSize:int = request.POST.get('pageSize', 20)
        page:int = request.POST.get('page', 1)
        dateFrom:str = request.POST.get('dateFrom', '')
        dateTo:str = request.POST.get('dateTo', '')
    

    if type == 'all':
        pictures = Pictures.objects.all()
    else:
        types = type.split('^')
        pictures = Pictures.objects.none()
        for t in types:
            pictures = Pictures.objects.filter(type=t) | pictures
    if byName and not byFullText:
        keys = searchKey.split(' ')
        for k in keys:
            pictures = pictures.filter(description__contains=k)
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
    if dateFrom:
        pictures = pictures.filter(date__gte=dateFrom)
    if dateTo:
        pictures = pictures.filter(date__lte=dateTo)
    if order == 'asc':
        pictures = pictures.order_by(orderBy, 'href')
    else:
        pictures = pictures.order_by('-' + orderBy, 'href')

    totalPage = len(pictures) // pageSize + 1
    if page > totalPage:
        return HttpResponse('Invalid page number', status=400)
    pictures = pictures[(page - 1) * pageSize:page * pageSize]
    #hrefList = [{'src' = picture.href,'title' = picture.description} for picture in pictures]
    hrefList = []
    for picture in pictures:
        hrefList.append({'src': picture.href, 'title': picture.description})
    response = {'totalPage': totalPage, 'hrefList': hrefList}

    return HttpResponse(json.dumps(response), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getTypes(request):
    types = Types.objects.all()
    typeList = [t.typename for t in types]
    return HttpResponse(json.dumps(typeList), content_type='application/json')
    
