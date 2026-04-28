from typing import Dict, Any, Optional
from django.http import HttpRequest, HttpResponse
from wardrobe_db.models import Pictures, PicturesOcr, OcrMission, Messages, CollectionItems
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from django.conf import settings
from wardrobe_db import ocr
from threading import Thread
from .common import logger, create_message, _extract_body

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getOcrMission(request: HttpRequest) -> HttpResponse:
    missions = OcrMission.objects.all()
    missionList = [{'src': m.href.href, 'status': m.status} for m in missions]
    return HttpResponse(json.dumps(missionList), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def newOcrMission(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = body.get('src', '')
    
    if not Pictures.objects.filter(href=src):
        return HttpResponse('Picture does not exist', status=400)
    
    if OcrMission.objects.filter(href=Pictures.objects.get(href=src)):
        mission = OcrMission.objects.get(href=Pictures.objects.get(href=src))
        if mission.status != 'finished':
            return HttpResponse('Mission already exists', status=400)
        else:
            mission.status = 'waiting'
            mission.save()
            logger.info(f'OCR mission for {src} has been reset.')
        return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

    mission = OcrMission(href=Pictures.objects.get(href=src), status='waiting')
    mission.save()
    
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def resetOcrMission(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = body.get('src', '')
    
    mission = OcrMission.objects.filter(href=Pictures.objects.get(href=src))
    if not mission:
        return HttpResponse('Mission does not exist', status=400)
    
    mission = mission[0]

    mission.status = 'waiting'
    mission.save()
    
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cleanOcrMission(request: HttpRequest) -> HttpResponse:
    missions = OcrMission.objects.filter(status='finished')
    count = missions.count()
    for mission in missions:
        mission.delete()
    return HttpResponse(json.dumps({'status': 'Success', 'deleted_count': count}), content_type='application/json')

def performOcr(src: str) -> None:
    picture = Pictures.objects.get(href=src)
    mission = OcrMission.objects.filter(href=picture)[0]

    if picture.is_collection:
        items = CollectionItems.objects.filter(collection=picture).order_by('sort_order')
        results = []
        for item in items:
            item_path = settings.IMAGE_STORAGE_PATH + item.image_href
            try:
                result = ocr.ocrImg(item_path)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning(f'OCR failed for collection item {item.image_href}: {e}')
        ocr_result = '\n'.join(results)
    else:
        ocr_result = ocr.ocrImg(settings.IMAGE_STORAGE_PATH + src)

    PicturesOcr.objects.update_or_create(href=picture, defaults={'ocr_result': ocr_result})
    
    mission.status = 'finished'
    mission.save()
    title = picture.description
    create_message(level='info', message_type='OCR', text=f'Text extraction for "{title}" has been completed.', link='/detail/' + src)

def performAllOcr() -> None:
    missions = OcrMission.objects.filter(status='waiting')
    for mission in missions:
        mission.status = 'processing'
        mission.save()
    for mission in missions:
        performOcr(mission.href.href)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def excuteOcrMission(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = body.get('src', '')
    
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
def excuteAllOcrMission(request: HttpRequest) -> HttpResponse:
    missions = OcrMission.objects.filter(status='waiting')
    if not missions:
        return HttpResponse('No waiting missions', status=400)

    Thread(target=performAllOcr).start()

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
