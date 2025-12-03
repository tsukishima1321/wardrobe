from django.http import HttpResponse
from wardrobe_diary.models import Texts
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json
from datetime import datetime

from django.conf import settings
LOCALHOST = settings.LOCALHOST

import logging

logger = logging.getLogger('db')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search(request):
    """
    Search for diary texts based on the provided parameters.
    """
    try:
        if(request.content_type == 'application/json'):
            body = json.loads(request.body)
            searchKey = body.get('searchKey', '')
            dateFrom = body.get('dateFrom', '')
            dateTo = body.get('dateTo', '')
            orderBy = body.get('orderBy', 'date')
            order = body.get('order', 'desc')
            pageSize = body.get('pageSize', 20)
            page = body.get('page', 1)
        else:
            searchKey = request.POST.get('searchKey', '')
            dateFrom = request.POST.get('dateFrom', '')
            dateTo = request.POST.get('dateTo', '')
            orderBy = request.POST.get('orderBy', 'date')
            order = request.POST.get('order', 'desc')
            pageSize = int(request.POST.get('pageSize', 20))
            page = int(request.POST.get('page', 1))
        
        logger.info(f"Search parameters: searchKey={searchKey}, dateFrom={dateFrom}, dateTo={dateTo}")
        
        # Start with all diary texts
        texts = Texts.objects.all()
        
        # Filter by search key if provided
        if searchKey:
            keys = searchKey.split(' ')
            for k in keys:
                texts = texts.filter(text__contains=k)
        
        # Filter by date range if provided
        if dateFrom:
            texts = texts.filter(date__gte=dateFrom)
        if dateTo:
            texts = texts.filter(date__lte=dateTo)
        
        # Apply ordering
        if order == 'asc':
            texts = texts.order_by(orderBy)
        else:
            texts = texts.order_by('-' + orderBy)
        
        # Pagination
        totalPage = (len(texts) + pageSize - 1) // pageSize
        totalItems = len(texts)
        if page > totalPage and totalPage > 0:
            return HttpResponse('Invalid page number', status=400)
        
        texts = texts[(page - 1) * pageSize:page * pageSize]
        
        # Format response
        textList = []
        for text in texts:
            textList.append({
                'id': text.id,
                'date': text.date.strftime('%Y-%m-%d'),
                'text': text.text
            })
        
        results = {'totalPage': totalPage, 'textList': textList, 'totalItems': totalItems}
        
        return HttpResponse(json.dumps(results), content_type='application/json')
    
    except Exception as e:
        logger.error(f"Error in search: {e}")
        return HttpResponse(status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def getDiaryTexts(request):
    """
    Get diary texts. If ID is provided, return specific diary text. Otherwise, return all with optional filtering.
    """
    try:
        if request.content_type == 'application/json':
            body = json.loads(request.body)
            text_id = body.get('id', '')
        else:
            text_id = request.GET.get('id', '')
        
        # If ID is provided, return specific diary text
        if text_id:
            try:
                text_id = int(text_id)
                diary_text = Texts.objects.get(id=text_id)
                result = {
                    'id': diary_text.id,
                    'date': diary_text.date.strftime('%Y-%m-%d'),
                    'text': diary_text.text
                }
                return HttpResponse(json.dumps(result), content_type='application/json')
            except ValueError:
                return HttpResponse('Invalid ID format', status=400)
            except Texts.DoesNotExist:
                return HttpResponse('Diary text not found', status=404)
        else:
            # If no ID, return all diary texts
            texts = Texts.objects.all()
            textList = []
            for text in texts:
                textList.append({
                    'id': text.id,
                    'date': text.date.strftime('%Y-%m-%d'),
                    'text': text.text
                })
            return HttpResponse(json.dumps(textList), content_type='application/json')
    except Exception as e:
        logger.error(f"Error in getDiaryTexts: {e}")
        return HttpResponse(status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def newDiaryText(request):
    """
    Create a new diary text entry.
    """
    try:
        if(request.content_type == 'application/json'):
            body = json.loads(request.body)
            date = body.get('date', '')
            text = body.get('text', '')
        else:
            date = request.POST.get('date', '')
            text = request.POST.get('text', '')
        
        if not date or not text:
            return HttpResponse('Date and text are required', status=400)
        
        # Validate date format
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            return HttpResponse('Invalid date format. Use YYYY-MM-DD', status=400)
        
        # Create new diary text
        diary_text = Texts(date=date, text=text)
        diary_text.save()
        
        logger.info(f"New diary text created for date: {date}")
        
        return HttpResponse(json.dumps({'status': 'Success', 'id': diary_text.id}), content_type='application/json')
    
    except Exception as e:
        logger.error(f"Error in newDiaryText: {e}")
        return HttpResponse(status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def deleteDiaryText(request):
    """
    Delete a diary text entry.
    """
    try:
        if(request.content_type == 'application/json'):
            body = json.loads(request.body)
            text_id = body.get('id', '')
        else:
            text_id = request.POST.get('id', '')
        
        if not text_id:
            return HttpResponse('ID is required', status=400)
        
        try:
            text_id = int(text_id)
        except ValueError:
            return HttpResponse('Invalid ID format', status=400)
        
        # Find and delete the diary text
        diary_text = Texts.objects.filter(id=text_id)
        if not diary_text:
            return HttpResponse('Diary text not found', status=404)
        
        diary_text.delete()
        
        logger.info(f"Diary text with ID {text_id} deleted")
        
        return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
    
    except Exception as e:
        logger.error(f"Error in deleteDiaryText: {e}")
        return HttpResponse(status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def editDiaryText(request):
    """
    Edit an existing diary text entry.
    """
    try:
        if(request.content_type == 'application/json'):
            body = json.loads(request.body)
            text_id = body.get('id', '')
            date = body.get('date', '')
            text = body.get('text', '')
        else:
            text_id = request.POST.get('id', '')
            date = request.POST.get('date', '')
            text = request.POST.get('text', '')
        
        if not text_id:
            return HttpResponse('ID is required', status=400)

        try:
            text_id = int(text_id)
        except ValueError:
            return HttpResponse('Invalid ID format', status=400)
        
        # Find the diary text
        try:
            diary_text = Texts.objects.get(id=text_id)
        except Texts.DoesNotExist:
            return HttpResponse('Diary text not found', status=404)
        
        # Update fields if provided
        if date:
            try:
                datetime.strptime(date, '%Y-%m-%d')
                diary_text.date = date
            except ValueError:
                return HttpResponse('Invalid date format. Use YYYY-MM-DD', status=400)
        
        if text:
            diary_text.text = text
        
        diary_text.save()
        
        logger.info(f"Diary text with ID {text_id} updated")
        
        return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')
    
    except Exception as e:
        logger.error(f"Error in editDiaryText: {e}")
        return HttpResponse(status=500)