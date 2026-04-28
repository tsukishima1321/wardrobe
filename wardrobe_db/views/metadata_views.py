from typing import Dict, Any
from django.http import HttpRequest, HttpResponse
from wardrobe_db.models import Pictures, Keywords, Properties, UserDictionary
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
import json
from .common import _extract_body
from wardrobe_db.nlp.model import nlp_engine

@api_view(['POST'])
@permission_classes([AllowAny])
def reloadModel(request: HttpRequest) -> HttpResponse:
    client_ip = request.META.get('REMOTE_ADDR')
    if client_ip not in ['127.0.0.1', 'localhost', '::1']:
        pass

    try:
        print("Reloading NLP model...")
        success = nlp_engine.load()
        if success:
            return HttpResponse(json.dumps({'status': 'Reloaded successfully'}), content_type='application/json')
        else:
            return HttpResponse(json.dumps({'error': 'Model file not found'}), status=500, content_type='application/json')
    except Exception as e:
        return HttpResponse(json.dumps({'error': str(e)}), status=500, content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predictMetadata(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    description = (body.get('description') or '').strip()
    
    if not description:
        return HttpResponse(json.dumps({'error': 'Missing description'}), status=400, content_type='application/json')
    
    try:
        if not nlp_engine.vocab_loaded:
            nlp_engine.load()
            
        result = nlp_engine.predict(description)
        return HttpResponse(json.dumps(result, ensure_ascii=False), content_type='application/json')
    except Exception as e:
        return HttpResponse(json.dumps({'error': str(e)}), status=500, content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listKeywords(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = (body.get('src') or '').strip()
    keywords = Keywords.objects.all()
    if src:
        keywords = keywords.filter(href=src)
    data = [kw.keyword for kw in keywords]
    return HttpResponse(json.dumps(data), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createKeyword(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
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
    
    if picture.description:
        nlp_engine.update(picture.description, keywords=[keyword], mode='add')
        
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteKeyword(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = (body.get('src') or '').strip()
    keyword = (body.get('keyword') or '').strip()
    if not src or not keyword:
        return HttpResponse('Missing src or keyword', status=400)
    
    picture = Pictures.objects.filter(href=src).first()
    deleted_count, _ = Keywords.objects.filter(href=src, keyword=keyword).delete()
    
    if not deleted_count:
        return HttpResponse('Keyword does not exist', status=404)
        
    if picture and picture.description:
        nlp_engine.update(picture.description, keywords=[keyword], mode='remove')

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listProperties(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = (body.get('src') or '').strip()
    props = Properties.objects.all()
    if src:
        props = props.filter(href=src)
    data = [{'name': prop.property_name, 'value': prop.value} for prop in props]
    return HttpResponse(json.dumps(data), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createProperty(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
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
    
    if picture.description:
        nlp_engine.update(picture.description, properties={name: [value]}, mode='add')
        
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteProperty(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    src = (body.get('src') or '').strip()
    name = (body.get('name') or body.get('property_name') or '').strip()
    value = (body.get('value') or '').strip()
    if not src or not name or not value:
        return HttpResponse('Missing src or name', status=400)
    
    picture = Pictures.objects.filter(href=src).first()
    deleted_count, _ = Properties.objects.filter(href=src, property_name=name, value=value).delete()
    
    if not deleted_count:
        return HttpResponse('Property does not exist', status=404)
        
    if picture and picture.description:
        nlp_engine.update(picture.description, properties={name: [value]}, mode='remove')

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def listUserDictionary(request: HttpRequest) -> HttpResponse:
    words = UserDictionary.objects.all().order_by('word').values_list('word', flat=True)
    return HttpResponse(json.dumps(list(words), ensure_ascii=False), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def createUserDictionaryWord(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    word = (body.get('word') or '').strip()
    if not word:
        return HttpResponse('Missing word', status=400)

    if len(word) > 50:
        return HttpResponse('Word is too long', status=400)

    _, created = UserDictionary.objects.get_or_create(word=word)
    if not created:
        return HttpResponse('Word already exists', status=400)

    nlp_engine.refresh_user_dict()
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteUserDictionaryWord(request: HttpRequest) -> HttpResponse:
    body: Dict[str, Any] = _extract_body(request)
    word = (body.get('word') or '').strip()
    if not word:
        return HttpResponse('Missing word', status=400)

    deleted_count, _ = UserDictionary.objects.filter(word=word).delete()
    if not deleted_count:
        return HttpResponse('Word does not exist', status=404)

    nlp_engine.refresh_user_dict()
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
