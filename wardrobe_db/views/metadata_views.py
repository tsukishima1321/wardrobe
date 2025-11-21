from django.http import HttpResponse
from wardrobe_db.models import Pictures, Keywords, Properties
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from .common import _extract_body

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
