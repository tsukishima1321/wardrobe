from django.http import HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, Types, Statistics, StatisticsByType, OcrMission
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json

from django.conf import settings
LOCALHOST = settings.LOCALHOST

import logging

logger = logging.getLogger('db')

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
        hrefList.append({'src': picture.href, 'title': picture.description,'date':picture.date.strftime('%Y-%m-%d')})
    response = {'totalPage': totalPage, 'hrefList': hrefList}

    return HttpResponse(json.dumps(response), content_type='application/json')

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
    statisticsByType = StatisticsByType.objects.all()
    typeList = []
    for s in statisticsByType:
        typename = Types.objects.get(typename=s.typename).typename
        typeList.append({'type': typename, 'totalAmount': s.totalamount, 'lastYearAmount': s.lastyearamount, 'lastMonthAmount': s.lastmonthamount})
    response = {'overall': overall, 'types': typeList}
    return HttpResponse(json.dumps(response), content_type='application/json')

import random as rand
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def random(request):
    typeFilter = request.query_params.get('type', '')
    if typeFilter:
        pictures = Pictures.objects.filter(type=typeFilter)
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
    statisticsByType = StatisticsByType.objects.filter(typename=oldName)
    if statisticsByType:
        statisticsByType.delete()
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
        statisticsByType = StatisticsByType.objects.filter(typename=typename)
        statisticsByType.delete()
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