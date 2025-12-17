from django.http import HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, OcrMission, Messages
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from django.conf import settings
from wardrobe_db import ocr
from threading import Thread
from .common import logger, create_message

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

def performOcr(src:str):
    mission = OcrMission.objects.filter(href=Pictures.objects.get(href=src))[0]

    ocr_result = ocr.ocrImg(settings.IMAGE_STORAGE_PATH + src)
    PicturesOcr.objects.update_or_create(href=Pictures.objects.get(href=src), defaults={'ocr_result': ocr_result})
    
    mission.status = 'finished'
    mission.save()
    title = Pictures.objects.get(href=src).description
    # Messages.objects.create(level='info', message_type='OCR', text=f'Text extraction for "{title}" has been completed.', link='/detail/' + src)
    create_message(level='info', message_type='OCR', text=f'Text extraction for "{title}" has been completed.', link='/detail/' + src)

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
