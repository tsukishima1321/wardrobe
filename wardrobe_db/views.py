from django.shortcuts import render
from django.http import HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, Types, Statistics, StatisticsByType
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getImageDetail(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
    else:
        src:str = request.POST.get('src', '')
    picture = Pictures.objects.get(href=src)
    ocr_result = PicturesOcr.objects.filter(href=src)
    if ocr_result:
        ocr_result = ocr_result[0].ocr_result
    else:
        ocr_result = ''
    response = {'src': picture.href, 'title': picture.description, 'type': picture.type.typename, 'date': picture.date.strftime('%Y-%m-%d'), 'text': ocr_result}
    return HttpResponse(json.dumps(response), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setImageDetail(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
        title = body.get('title', '')
        type = body.get('type', '')
        date = body.get('date', '')
    else:
        src:str = request.POST.get('src', '')
        title:str = request.POST.get('title', '')
        type:str = request.POST.get('type', '')
        date:str = request.POST.get('date', '')
    picture = Pictures.objects.get(href=src)
    if not picture:
        return HttpResponse('Invalid picture', status=400)
    if title:
        picture.description = title
    if type:
        picture.type = Types.objects.get(typename=type)
    if date:
        picture.date = date
    picture.save()
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setImageText(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
        text = body.get('text', '')
    else:
        src:str = request.POST.get('src', '')
        text:str = request.POST.get('text', '')
    ocr_result = PicturesOcr.objects.get(href=src)
    if ocr_result:
        ocr_result.ocr_result = text
    else:
        ocr_result = PicturesOcr(href=Pictures.objects.get(href=src), ocr_result=text)
    ocr_result.save()
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

from django.db import connection
def updateStatistics():
    try:
        with connection.cursor() as cursor:
            cursor.callproc('updatestat')  
            return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')
    except:
        return HttpResponse('Failed to update statistics', status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getStatistics(request):
    updateStatistics()
    statistics = Statistics.objects.get()
    overall = {'totalAmount': statistics.totalamount, 'lastYearAmount': statistics.lastyearamount, 'lastMonthAmount': statistics.lastmonthamount}
    statisticsByType = StatisticsByType.objects.all()
    typeList = []
    for s in statisticsByType:
        typename = Types.objects.get(typename=s.typename).typename
        typeList.append({'type': typename, 'totalAmount': s.totalamount, 'lastYearAmount': s.lastyearamount, 'lastMonthAmount': s.lastmonthamount})
    response = {'overall': overall, 'types': typeList}
    return HttpResponse(json.dumps(response), content_type='application/json')