from collections import Counter, defaultdict
import calendar
import datetime
import json
import re
from typing import Any, Counter as CounterType, DefaultDict, Dict, List, Optional, Tuple

import jieba
from django.db import connections
from django.db.models import Max, Min, Q
from django.http import HttpRequest, HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from wardrobe_db.models import Statistics, StatisticsByKeyword, StatisticsExpanded, StatisticsByKeywordExpanded, DiaryTexts, BackupRecords, Pictures, CollectionItems, Keywords, Messages, Properties, BlankPictures
from .common import _extract_body, create_message

REPORT_GRANULARITIES = {'day', 'month', 'year'}
REPORT_MATCH_MODES = {'title_only', 'title_keyword_property'}
REPORT_TOKEN_PATTERN = re.compile(r'[\u4e00-\u9fffA-Za-z0-9]+')

def updateStatistics() -> None:
    connection = connections['business']
    with connection.cursor() as cursor:
        cursor.callproc('updatestat')
        cursor.callproc('updatestat_expanded')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generateTips(request: HttpRequest) -> HttpResponse:
    # 提醒用户写日记和备份
    lastDiaryDate = DiaryTexts.objects.aggregate(max_date=Max('date'))['max_date']
    if lastDiaryDate:
        daysSinceLastDiary = (datetime.datetime.now().date() - lastDiaryDate).days
        if daysSinceLastDiary >= 3:
            create_message(
                level='tips',
                message_type='Diary',
                text=f'It has been {daysSinceLastDiary} days since your last diary entry.', link='/diary'
            )

    lastBackupDate = BackupRecords.objects.aggregate(max_timestamp=Max('timestamp'))['max_timestamp']
    if lastBackupDate:
        lastBackupDatetime = datetime.datetime.strptime(lastBackupDate, '%Y%m%d%H%M%S')
        daysSinceLastBackup = (datetime.datetime.now() - lastBackupDatetime).days
        if daysSinceLastBackup >= 5:
            create_message(
                level='warning',
                message_type='Backup',
                text=f'It has been {daysSinceLastBackup} days since your last backup. Please check the auto backup status!', link='/manage'
            )

    # 查询BlankPictures，若数量较多或日期较久未清理则提醒用户
    blank_picture_count = BlankPictures.objects.count()
    if blank_picture_count > 0:
        blank_picture_hrefs = BlankPictures.objects.values_list('href', flat=True)
        oldest_blank_date = Pictures.objects.filter(
            href__in=blank_picture_hrefs,
            date__isnull=False
        ).aggregate(min_date=Min('date'))['min_date']

        reasons = []
        if blank_picture_count >= 10:
            reasons.append(f"{blank_picture_count} unprocessed pictures")

        if oldest_blank_date:
            days_since_oldest_blank = (datetime.datetime.now().date() - oldest_blank_date).days
            if days_since_oldest_blank >= 7:
                reasons.append(f"the oldest unprocessed one is {days_since_oldest_blank} days ago")

        if reasons:
            create_message(
                level='tips',
                message_type='BlankPictures',
                text=f"You have {' and '.join(reasons)}. Please process or remove them.",
                link='/upload'
            )

    # 每月七号生成上月月报
    if datetime.datetime.now().day == 7:
        today = datetime.date.today()
        first_day_of_current_month = today.replace(day=1)
        last_day_of_previous_month = first_day_of_current_month - datetime.timedelta(days=1)
        year = last_day_of_previous_month.year
        month = last_day_of_previous_month.month

        # Generate monthly report text
        report_title = f"## Monthly Report for {year}-{month:02d}\n"
        
        # Check if a report for the previous month already exists
        if not Messages.objects.filter(message_type='Report', text__startswith=report_title).exists():
            updateStatistics()
            
            report_lines = [report_title]

            # Pictures summary
            pictures = Pictures.objects.filter(date__year=year, date__month=month)
            total_pictures = pictures.count()
            expanded_pictures = pictures.filter(is_collection=False).count()
            expanded_pictures += CollectionItems.objects.filter(collection__is_collection=True, collection__date__year=year, collection__date__month=month).count()
            report_lines.append(f"### Pictures\n")
            report_lines.append(f"You added **{total_pictures}** new pictures in {year}-{month:02d} (with collections expanded: **{expanded_pictures}**).\n\n")
            
            # Keywords summary
            keyword_counts = {}
            for pic in pictures:
                keywords = Keywords.objects.filter(href=pic.href)
                for kw in keywords:
                    keyword_counts[kw.keyword] = keyword_counts.get(kw.keyword, 0) + 1
            
            if keyword_counts:
                report_lines.append("#### Top 5 Keywords:\n")
                sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
                for kw, count in sorted_keywords[:5]:
                    report_lines.append(f"- **{kw}**: {count} times\n")
                report_lines.append("\n")

            property_counts = {}
            property_name_counts = {}
            for pic in pictures:
                properties = Properties.objects.filter(href=pic.href)
                for prop in properties:
                    property_name_counts[prop.property_name] = property_name_counts.get(prop.property_name, 0) + 1
                    if prop.property_name not in property_counts:
                        property_counts[prop.property_name] = {}
                    property_counts[prop.property_name][prop.value] = property_counts[prop.property_name].get(prop.value, 0) + 1

            if property_counts:
                print(property_counts)
                # display top 1 value for top 2 property names
                sorted_property_names = sorted(property_name_counts.items(), key=lambda x: x[1], reverse=True)
                for prop_name, _ in sorted_property_names[:2]:
                    # report_lines.append(f"- **{prop_name}**:\n")
                    report_lines.append(f"Your most common **{prop_name}** is ")
                    sorted_values = sorted(property_counts[prop_name].items(), key=lambda x: x[1], reverse=True)
                    top_value, top_count = sorted_values[0]
                    report_lines.append(f"**{top_value}** for **{top_count}** times. \n")
                report_lines.append("\n")

            # Diary summary
            diary_count = DiaryTexts.objects.filter(date__year=year, date__month=month).count()
            report_lines.append(f"### Diary\n")
            report_lines.append(f"You wrote **{diary_count}** diary entries.\n")
            
            report_text = "".join(report_lines)
            
            create_message(
            level='tips',
            message_type='Report',
            text=report_text,
            link='/search?dateFrom={}-{:02d}-01&dateTo={}-{:02d}-{}'.format(year, month, year, month, last_day_of_previous_month.day)
            )
    return HttpResponse(json.dumps({'status': 'Success'}), content_type='application/json')

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def getStatistics(request: HttpRequest) -> HttpResponse:
    updateStatistics()
    statistics = Statistics.objects.get()
    overall = {'totalAmount': statistics.totalamount, 'lastYearAmount': statistics.lastyearamount, 'lastMonthAmount': statistics.lastmonthamount}
    statisticsByKeyword = StatisticsByKeyword.objects.all()
    typeList = []
    for s in statisticsByKeyword:
        typename = s.keyword
        typeList.append({'type': typename, 'totalAmount': s.totalamount, 'lastYearAmount': s.lastyearamount, 'lastMonthAmount': s.lastmonthamount})

    statisticsExpanded = StatisticsExpanded.objects.get()
    overallExpanded = {'totalAmount': statisticsExpanded.totalamount, 'lastYearAmount': statisticsExpanded.lastyearamount, 'lastMonthAmount': statisticsExpanded.lastmonthamount}
    statisticsByKeywordExpanded = StatisticsByKeywordExpanded.objects.all()
    typeListExpanded = []
    for s in statisticsByKeywordExpanded:
        typename = s.keyword
        typeListExpanded.append({'type': typename, 'totalAmount': s.totalamount, 'lastYearAmount': s.lastyearamount, 'lastMonthAmount': s.lastmonthamount})
    response = {'overall': overall, 'types': typeList, 'overallExpanded': overallExpanded, 'typesExpanded': typeListExpanded}
    return HttpResponse(json.dumps(response), content_type='application/json')


def _normalize_report_term(term: Optional[str]) -> str:
    return (term or '').strip()


def _normalize_match_mode(match_mode: Optional[str]) -> str:
    normalized = (match_mode or 'title_only').strip().lower()
    return normalized or 'title_only'


def _build_report_match_query(term: str, match_mode: str) -> Q:
    if match_mode == 'title_only':
        return Q(description__contains=term)
    if match_mode == 'title_keyword_property':
        return (
            Q(description__contains=term) |
            Q(keywords__keyword=term) |
            Q(properties__value=term)
        )
    raise ValueError('Invalid match mode')


def _bucket_start(date_value: datetime.date, granularity: str) -> datetime.date:
    if granularity == 'year':
        return date_value.replace(month=1, day=1)
    if granularity == 'month':
        return date_value.replace(day=1)
    return date_value


def _bucket_label(date_value: datetime.date, granularity: str) -> str:
    if granularity == 'year':
        return date_value.strftime('%Y')
    if granularity == 'month':
        return date_value.strftime('%Y-%m')
    return date_value.strftime('%Y-%m-%d')


def _bucket_end(date_value: datetime.date, granularity: str) -> datetime.date:
    if granularity == 'year':
        return date_value.replace(month=12, day=31)
    if granularity == 'month':
        last_day = calendar.monthrange(date_value.year, date_value.month)[1]
        return date_value.replace(day=last_day)
    return date_value


def _tokenize_title_for_report(text: Optional[str], target_word: str) -> List[str]:
    if not text:
        return []

    jieba.add_word(target_word, freq=20000)
    tokens = []
    for raw_token in jieba.lcut(text):
        token = raw_token.strip()
        if not token or token == target_word:
            continue
        if not REPORT_TOKEN_PATTERN.fullmatch(token):
            continue
        if len(token) == 1 and not token.isdigit() and not token.isascii():
            continue
        tokens.append(token)
    return tokens


def _sorted_counter_items(counter: CounterType[str], key_name: str, top_n: int) -> List[Dict[str, Any]]:
    return [
        {key_name: item_key, 'count': count}
        for item_key, count in counter.most_common(top_n)
    ]


def _sorted_property_items(counter: CounterType[Tuple[str, str]], top_n: int) -> List[Dict[str, Any]]:
    return [
        {'propertyName': property_name, 'value': value, 'count': count}
        for (property_name, value), count in counter.most_common(top_n)
    ]


def _build_timeline_report(
    term: str,
    pictures: List[Dict[str, Any]],
    keyword_map: DefaultDict[str, List[str]],
    property_map: DefaultDict[str, List[Tuple[str, str]]],
    granularity: str = 'month',
    top_n: int = 8,
) -> Dict[str, Any]:
    if granularity not in REPORT_GRANULARITIES:
        raise ValueError('Invalid granularity')

    timeline_map = defaultdict(lambda: {
        'matchedImageCount': 0,
        'titleRelationCounter': Counter(),
        'keywordRelationCounter': Counter(),
        'propertyRelationCounter': Counter(),
        'sampleTitles': [],
    })

    overall_title_relations = Counter()
    overall_keyword_relations = Counter()
    overall_property_relations = Counter()
    total_images = 0
    first_date = None
    last_date = None

    for picture in pictures:
        picture_date = picture.get('date')
        if picture_date is None:
            continue

        bucket_date = _bucket_start(picture_date, granularity)
        bucket = timeline_map[bucket_date]
        bucket['matchedImageCount'] += 1
        total_images += 1

        if first_date is None or picture_date < first_date:
            first_date = picture_date
        if last_date is None or picture_date > last_date:
            last_date = picture_date

        title = picture.get('description') or ''
        if title and len(bucket['sampleTitles']) < 3:
            bucket['sampleTitles'].append(title)

        title_tokens = set(_tokenize_title_for_report(title, term))
        for token in title_tokens:
            bucket['titleRelationCounter'][token] += 1
            overall_title_relations[token] += 1

        for keyword in set(keyword_map.get(picture['href'], [])):
            bucket['keywordRelationCounter'][keyword] += 1
            overall_keyword_relations[keyword] += 1

        for property_name, value in set(property_map.get(picture['href'], [])):
            key = (property_name, value)
            bucket['propertyRelationCounter'][key] += 1
            overall_property_relations[key] += 1

    timeline = []
    for bucket_date in sorted(timeline_map.keys()):
        bucket = timeline_map[bucket_date]
        matched_count = bucket['matchedImageCount']
        timeline.append({
            'period': _bucket_label(bucket_date, granularity),
            'startDate': bucket_date.isoformat(),
            'endDate': _bucket_end(bucket_date, granularity).isoformat(),
            'matchedImageCount': matched_count,
            'titleRelations': _sorted_counter_items(bucket['titleRelationCounter'], 'word', top_n),
            'keywordRelations': _sorted_counter_items(bucket['keywordRelationCounter'], 'keyword', top_n),
            'propertyRelations': _sorted_property_items(bucket['propertyRelationCounter'], top_n),
            'sampleTitles': bucket['sampleTitles'],
        })

    return {
        'word': term,
        'granularity': granularity,
        'summary': {
            'matchedImageCount': total_images,
            'bucketCount': len(timeline),
            'firstDate': first_date.isoformat() if first_date else None,
            'lastDate': last_date.isoformat() if last_date else None,
            'topTitleRelations': _sorted_counter_items(overall_title_relations, 'word', top_n),
            'topKeywordRelations': _sorted_counter_items(overall_keyword_relations, 'keyword', top_n),
            'topPropertyRelations': _sorted_property_items(overall_property_relations, top_n),
        },
        'timeline': timeline,
    }


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def timelineReport(request: HttpRequest) -> HttpResponse:
    body = _extract_body(request)
    term = _normalize_report_term(body.get('word') or body.get('term'))
    granularity = (body.get('granularity') or 'month').strip().lower()
    match_mode = _normalize_match_mode(body.get('match_mode'))
    top_n = body.get('topN', 8)

    if not term:
        return HttpResponse('Missing word', status=400)
    if granularity not in REPORT_GRANULARITIES:
        return HttpResponse('Invalid granularity', status=400)
    if match_mode not in REPORT_MATCH_MODES:
        return HttpResponse('Invalid matchMode', status=400)

    try:
        top_n = max(1, min(int(top_n), 20))
    except (TypeError, ValueError):
        return HttpResponse('Invalid topN', status=400)

    pictures_queryset = Pictures.objects.filter(
        _build_report_match_query(term, match_mode),
        date__isnull=False,
    ).distinct().order_by('date', 'href')
    pictures = list(pictures_queryset.values('href', 'description', 'date'))
    hrefs = [picture['href'] for picture in pictures]

    keyword_map = defaultdict(list)
    property_map = defaultdict(list)
    if hrefs:
        for keyword in Keywords.objects.filter(href__in=hrefs).values('href', 'keyword'):
            keyword_map[keyword['href']].append(keyword['keyword'])
        for prop in Properties.objects.filter(href__in=hrefs).values('href', 'property_name', 'value'):
            property_map[prop['href']].append((prop['property_name'], prop['value']))

    response = _build_timeline_report(
        term=term,
        pictures=pictures,
        keyword_map=keyword_map,
        property_map=property_map,
        granularity=granularity,
        top_n=top_n,
    )
    response['matchMode'] = match_mode
    return HttpResponse(json.dumps(response), content_type='application/json')
