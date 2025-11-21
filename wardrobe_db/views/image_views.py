from django.http import HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, OcrMission, Keywords, Properties
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
import requests
import random as rand
from django.conf import settings
from .common import LOCALHOST

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
    response = {'src': picture.href, 'title': picture.description, 'date': picture.date.strftime('%Y-%m-%d'), 'text': ocr_result}
    return HttpResponse(json.dumps(response), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def setImageDetail(request):
    if(request.content_type == 'application/json'):
        body = json.loads(request.body)
        src = body.get('src', '')
        title = body.get('title', '')
        date = body.get('date', '')
    else:
        src:str = request.POST.get('src', '')
        title:str = request.POST.get('title', '')
        date:str = request.POST.get('date', '')
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
        date:str = request.POST.get('date', '')
        if not title or not date:
            return HttpResponse('Invalid parameters', status=400)
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
        if properties:
            propertyList = json.loads(properties)
            for prop in propertyList:
                property = Properties(href=Pictures.objects.get(href=src), property_name=prop['name'], value=prop['value'])
                property.save()
        return HttpResponse(json.dumps({'status':'Success'}), content_type='application/json')
    else:
        return HttpResponse(res.text, status=400)
