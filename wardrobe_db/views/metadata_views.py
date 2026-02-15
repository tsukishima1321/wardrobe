from django.http import HttpResponse
from wardrobe_db.models import Pictures, Keywords, Properties
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
import json
from .common import _extract_body
from wardrobe_db.nlp.model import nlp_engine

@api_view(['POST'])
@permission_classes([AllowAny]) # Allow localhost or internal calls without token
def reloadModel(request):
    """
    Force reload the NLP model from disk.
    This is usually called by management command after retraining.
    """
    # Simple security check: only allow localhost or internal IPs
    client_ip = request.META.get('REMOTE_ADDR')
    if client_ip not in ['127.0.0.1', 'localhost', '::1']:
        # If behind proxy (like nginx), check X-Real-IP if configured trustworthily
        # For now, simplistic check. 
        # Better: use a shared secret in headers
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
def predictMetadata(request):
    """
    Predict keywords and properties based on natural language description
    """
    body = _extract_body(request)
    description = (body.get('description') or '').strip()
    
    if not description:
        return HttpResponse(json.dumps({'error': 'Missing description'}), status=400, content_type='application/json')
    
    try:
        if not nlp_engine.vocab_loaded:
            # Try reloading if not ready (e.g. freshly restarted worker)
            nlp_engine.load()
            
        result = nlp_engine.predict(description)
        return HttpResponse(json.dumps(result, ensure_ascii=False), content_type='application/json')
    except Exception as e:
        return HttpResponse(json.dumps({'error': str(e)}), status=500, content_type='application/json')

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
    
    # Update NLP model incrementally
    if picture.description:
        nlp_engine.update(picture.description, keywords=[keyword], mode='add')
        
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteKeyword(request):
    body = _extract_body(request)
    src = (body.get('src') or '').strip()
    keyword = (body.get('keyword') or '').strip()
    if not src or not keyword:
        return HttpResponse('Missing src or keyword', status=400)
    
    picture = Pictures.objects.filter(href=src).first()
    deleted_count, _ = Keywords.objects.filter(href=src, keyword=keyword).delete()
    
    if not deleted_count:
        return HttpResponse('Keyword does not exist', status=404)
        
    # Update NLP model incrementally
    if picture and picture.description:
        nlp_engine.update(picture.description, keywords=[keyword], mode='remove')

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
    
    # Update NLP model incrementally
    if picture.description:
        nlp_engine.update(picture.description, properties={name: [value]}, mode='add')
        
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
    
    picture = Pictures.objects.filter(href=src).first()
    deleted_count, _ = Properties.objects.filter(href=src, property_name=name, value=value).delete()
    
    if not deleted_count:
        return HttpResponse('Property does not exist', status=404)
        
    # Update NLP model incrementally
    if picture and picture.description:
        nlp_engine.update(picture.description, properties={name: [value]}, mode='remove')

    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
