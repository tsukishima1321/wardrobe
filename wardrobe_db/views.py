from django.http import HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, Types, Statistics, StatisticsByKeyword, OcrMission, Keywords, Properties
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json

from django.conf import settings
LOCALHOST = settings.LOCALHOST

import logging

logger = logging.getLogger('db')

def _extract_body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body)
        except json.JSONDecodeError:
            return {}
    return request.POST

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search(request):
    body = _extract_body(request)
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
    keywords = body.get('keywords', [])
    properties = body.get('properties', [])

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

    for kw in keywords:
        pictures = pictures.filter(keywords__keyword=kw)
    for prop in properties:
        pictures = pictures.filter(properties__property_name=prop['name'], properties__value=prop['value'])

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
        hrefList.append({'src': picture.href, 'title': picture.description,'date':picture.date.strftime('%Y-%m-%d')})
    response = {'totalPage': totalPage, 'hrefList': hrefList}

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
    

@api_view(['GET'])
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
def deleteImage(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
    else:
        src:str = request.POST.get('src', '')
    picture = Pictures.objects.filter(href=src)
    if not picture:
        return HttpResponse('Invalid picture', status=400)
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listKeywords(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    keywords = Keywords.objects.all()
    if src:
        keywords = keywords.filter(href=src)
    data = [kw.keyword for kw in keywords]
    return HttpResponse(json.dumps(data), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createKeyword(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    keyword = (body.get('keyword') or '').strip()
    if not src or not keyword:
        return HttpResponse('Missing src or keyword', status=400)
    picture = Pictures.objects.filter(href=src).first()
    if not picture:
        return HttpResponse('Picture does not exist', status=404)
    if Keywords.objects.filter(href=src, keyword=keyword).exists():
        return HttpResponse('Keyword already exists for picture', status=400)
    Keywords.objects.create(href=picture, keyword=keyword)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteKeyword(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    keyword = (body.get('keyword') or '').strip()
    if not src or not keyword:
        return HttpResponse('Missing src or keyword', status=400)
    deleted_count, _ = Keywords.objects.filter(href=src, keyword=keyword).delete()
    if not deleted_count:
        return HttpResponse('Keyword does not exist', status=404)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listProperties(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    props = Properties.objects.all()
    if src:
        props = props.filter(href=src)
    data = [{'name': prop.property_name, 'value': prop.value} for prop in props]
    return HttpResponse(json.dumps(data), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createProperty(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    name = (body.get('name') or body.get('property_name') or '').strip()
    value = (body.get('value') or '').strip()
    if not src or not name or not value:
        return HttpResponse('Missing src, name, or value', status=400)
    picture = Pictures.objects.filter(href=src).first()
    if not picture:
        return HttpResponse('Picture does not exist', status=404)
    if Properties.objects.filter(href=src, property_name=name, value=value).exists():
        return HttpResponse('Property already exists for picture', status=400)
    Properties.objects.create(href=picture, property_name=name, value=value)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteProperty(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    name = (body.get('name') or body.get('property_name') or '').strip()
    value = (body.get('value') or '').strip()
    if not src or not name or not value:
        return HttpResponse('Missing src or name', status=400)
    deleted_count, _ = Properties.objects.filter(href=src, property_name=name, value=value).delete()
    if not deleted_count:
        return HttpResponse('Property does not exist', status=404)
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

from django.db import connections
def updateStatistics():
    connection = connections['business']
    with connection.cursor() as cursor:
        cursor.callproc('updatestat')
        return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getStatistics(request):
    updateStatistics()
    statistics = Statistics.objects.get()
    overall = {'totalAmount': statistics.totalamount, 'lastYearAmount': statistics.lastyearamount, 'lastMonthAmount': statistics.lastmonthamount}
    statisticsByKeyword = StatisticsByKeyword.objects.all()
    typeList = []
    for s in statisticsByKeyword:
        typename = s.keyword
        typeList.append({'type': typename, 'totalAmount': s.totalamount, 'lastYearAmount': s.lastyearamount, 'lastMonthAmount': s.lastmonthamount})
    response = {'overall': overall, 'types': typeList}
    return HttpResponse(json.dumps(response), content_type='application/json')

import random as rand
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def random(request):
    keywordFilter = request.query_params.get('keyword', '')
    if keywordFilter:
        pictures = Pictures.objects.filter(keywords__keyword=keywordFilter)
    else:
        pictures = Pictures.objects.all()
    picture = rand.choice(pictures)
    response = {'src': picture.href, 'title': picture.description}
    return HttpResponse(json.dumps(response), content_type='application/json')

import requests
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def newImage(request):
    url = LOCALHOST + '/api/upload/'
    headers = {'Authorization': request.headers['Authorization']}
    res = requests.post(url, files=request.FILES, headers=headers)
    if res.status_code == 200:
        data = json.loads(res.text)
        src = data['name']
        title:str = request.POST.get('title', '')
        type:str = request.POST.get('type', '')
        date:str = request.POST.get('date', '')
        if not title or not type or not date:
            return HttpResponse('Invalid parameters', status=400)
        picture = Pictures(href=src, description=title, type=Types.objects.get(typename=type), date=date)
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
        if properties:
            propertyList = json.loads(properties)
            for prop in propertyList:
                property = Properties(href=Pictures.objects.get(href=src), property_name=prop['name'], value=prop['value'])
                property.save()
        return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')
    else:
        return HttpResponse(res.text, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def newType(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        typename:str = body.get('typename', '')
    else:
        typename:str = request.POST.get('typename', '')
    exist = Types.objects.filter(typename=typename)
    if exist:
        return HttpResponse('Type already exists', status=400)
    type = Types(typename=typename)
    type.save()
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def renameType(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        oldName:str = body.get('oldName', '')
        newName:str = body.get('newName', '')
    else:
        oldName:str = request.POST.get('oldName', '')
        newName:str = request.POST.get('newName', '')
    type = Types.objects.filter(typename=oldName)
    if not type:
        return HttpResponse('Type does not exist', status=400)
    if Types.objects.filter(typename=newName):
        return HttpResponse('New type name already exists', status=400)
    type = Types(typename=newName)
    type.save()
    Pictures.objects.filter(type=oldName).update(type=newName)
    type = Types.objects.get(typename=oldName)
    StatisticsByKeyword = StatisticsByKeyword.objects.filter(typename=oldName)
    if StatisticsByKeyword:
        StatisticsByKeyword.delete()
    type.delete()
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteType(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        typename:str = body.get('typename', '')
        altType = body.get('altType', '')
    else:
        typename:str = request.POST.get('typename', '')
        altType = request.POST.get('altType', '')
    type = Types.objects.filter(typename=typename)
    if not type:
        return HttpResponse('Type does not exist', status=400)
    
    if altType:
        altTypeObj = Types.objects.filter(typename=altType)
        if not altTypeObj:
            return HttpResponse('Alternative type does not exist', status=400)
        Pictures.objects.filter(type=typename).update(type=altTypeObj[0])
        StatisticsByKeyword = StatisticsByKeyword.objects.filter(typename=typename)
        StatisticsByKeyword.delete()
        type = type[0]
        type.delete()
    else:
        return HttpResponse('Alternative type is required', status=400)
    return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getOcrMission(request):
    missions = OcrMission.objects.all()
    missionList = [{'src': m.href.href, 'status': m.status} for m in missions]
    return HttpResponse(json.dumps(missionList), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def newOcrMission(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
    else:
        src:str = request.POST.get('src', '')
    
    if not Pictures.objects.filter(href=src):
        return HttpResponse('Picture does not exist', status=400)
    
    if OcrMission.objects.filter(href=Pictures.objects.get(href=src)):
        mission = OcrMission.objects.get(href=Pictures.objects.get(href=src))
        if mission.status != 'finished':
            return HttpResponse('Mission already exists', status=400)
        else:
            mission.status = 'waiting'
            mission.save()
            # Reset the OCR result if the mission is reset
            logger.info(f'OCR mission for {src} has been reset.')
        return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

    mission = OcrMission(href=Pictures.objects.get(href=src), status='waiting')
    mission.save()
    
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resetOcrMission(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
    else:
        src:str = request.POST.get('src', '')
    
    mission = OcrMission.objects.filter(href=Pictures.objects.get(href=src))
    if not mission:
        return HttpResponse('Mission does not exist', status=400)
    
    mission = mission[0]

    mission.status = 'waiting'
    mission.save()
    
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

from . import ocr
from threading import Thread
from django.db.models import Count


def performOcr(src:str):
    mission = OcrMission.objects.filter(href=Pictures.objects.get(href=src))[0]

    ocr_result = ocr.ocrImg(settings.IMAGE_STORAGE_PATH + src)
    PicturesOcr.objects.update_or_create(href=Pictures.objects.get(href=src), defaults={'ocr_result': ocr_result})
    
    mission.status = 'finished'
    mission.save()

def performAllOcr():
    missions = OcrMission.objects.filter(status='waiting')
    for mission in missions:
        mission.status = 'processing'
        mission.save()
    for mission in missions:
        performOcr(mission.href.href)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def excuteOcrMission(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
    else:
        src:str = request.POST.get('src', '')
    
    mission = OcrMission.objects.filter(href=Pictures.objects.get(href=src))
    if not mission:
        return HttpResponse('Mission does not exist', status=200)
    
    mission = mission[0]
    if mission.status != 'waiting':
        return HttpResponse('Mission is not waiting', status=200)

    mission.status = 'processing'
    mission.save()

    Thread(target=performOcr,args=(src,)).start()
    
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def excuteAllOcrMission(request):
    missions = OcrMission.objects.filter(status='waiting')
    if not missions:
        return HttpResponse('No waiting missions', status=400)

    Thread(target=performAllOcr).start()

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')