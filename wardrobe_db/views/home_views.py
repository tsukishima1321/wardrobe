import datetime
import random
from collections import Counter, defaultdict

from django.db.models import Max
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import json

from wardrobe_db.models import (
    BackupRecords,
    BlankPictures,
    DiaryTexts,
    Keywords,
    Messages,
    Pictures,
    Properties,
)


HOME_DISCOVERY_WINDOW_DAYS = 3
HOME_HERO_PICTURE_LIMIT = 3
HOME_HERO_DIARY_LIMIT = 2
HOME_REMIX_PICTURE_LIMIT = 4
HOME_REMIX_DIARY_LIMIT = 2


def _as_json(payload):
    return HttpResponse(json.dumps(payload, ensure_ascii=False), content_type='application/json')


def _day_distance_ignoring_year(date_value, target_date):
    source = datetime.date(2000, date_value.month, date_value.day).timetuple().tm_yday
    target = datetime.date(2000, target_date.month, target_date.day).timetuple().tm_yday
    direct_distance = abs(source - target)
    return min(direct_distance, 366 - direct_distance)


def _serialize_picture(picture, keyword_map=None, property_map=None):
    return {
        'src': picture.href,
        'title': picture.description or '',
        'date': picture.date.strftime('%Y-%m-%d') if picture.date else None,
        'isCollection': picture.is_collection,
        'keywords': list((keyword_map or {}).get(picture.href, [])),
        'properties': [
            {'name': property_name, 'value': value}
            for property_name, value in (property_map or {}).get(picture.href, [])
        ],
    }


def _serialize_diary(diary):
    preview = (diary.text or '').strip()
    if len(preview) > 140:
        preview = preview[:137] + '...'
    return {
        'id': diary.id,
        'date': diary.date.strftime('%Y-%m-%d'),
        'text': diary.text,
        'preview': preview,
    }

FIXED_BY_DATE = False


def _build_daily_rng(target_date, salt):
    if FIXED_BY_DATE:
        return random.Random(f'{target_date.isoformat()}:{salt}')
    return random.Random()


def _fetch_context_maps(hrefs):
    if not hrefs:
        return {}, {}
    keyword_map = defaultdict(list)
    for item in Keywords.objects.filter(href_id__in=hrefs).values('href_id', 'keyword'):
        keyword_map[item['href_id']].append(item['keyword'])
    property_map = defaultdict(list)
    for item in Properties.objects.filter(href_id__in=hrefs).values('href_id', 'property_name', 'value'):
        property_map[item['href_id']].append((item['property_name'], item['value']))
    return dict(keyword_map), dict(property_map)


def _pick_daily_sample(items, limit, rng, sort_key, year_key=None):
    if len(items) <= limit:
        return sorted(items, key=sort_key)

    if year_key is None:
        def year_key(candidate):
            item = candidate[0] if isinstance(candidate, (tuple, list)) and candidate else candidate
            date_value = getattr(item, 'date', None)
            return date_value.year if date_value else None
    buckets_by_year = defaultdict(list)

    for item in items:
        item_year = year_key(item)
        buckets_by_year[item_year].append(item)

    selected = []
    years = list(buckets_by_year.keys())
    if len(years) >= limit:
        for year in rng.sample(years, limit):
            exact_match = any(item[1] == 0 for item in buckets_by_year[year])
            if exact_match:
                selected.append(rng.choice(list(item for item in buckets_by_year[year] if item[1] == 0)))
            else:
                selected.append(rng.choice(buckets_by_year[year]))
    else:
        for year in years:
            exact_match = any(item[1] == 0 for item in buckets_by_year[year])
            if exact_match:
                selected.append(rng.choice(list(item for item in buckets_by_year[year] if item[1] == 0)))
            else:
                selected.append(rng.choice(buckets_by_year[year]))

    remaining_slots = limit - len(selected)
    if remaining_slots > 0:
        remaining_pool = []
        for year in years:
            remaining_pool.extend(buckets_by_year[year])

        for picked in selected:
            remaining_pool.remove(picked)

        if remaining_slots >= len(remaining_pool):
            selected.extend(remaining_pool)
        else:
            selected.extend(rng.sample(remaining_pool, remaining_slots))

    return sorted(selected, key=sort_key)


def _build_on_this_day_titles(exact_match, picture_count, diary_count, window_days, years):
    if exact_match:
        title = '那年今日'
    elif picture_count and diary_count:
        title = '前后几天的旧回声'
    else:
        title = '今天附近的记忆'

    if years:
        year_text = f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0])
    else:
        year_text = '历史'
    if exact_match:
        subtitle = f'从 {year_text} 的今天，打捞出同一天的回忆。'
    else:
        subtitle = f'从 {year_text} 的今天，回看前后 {window_days} 天里的内容。'

    return title, subtitle


def _build_on_this_day_module(today):
    picture_candidates = []
    for picture in Pictures.objects.filter(date__isnull=False):
        if picture.date.year == today.year:
            continue
        day_distance = _day_distance_ignoring_year(picture.date, today)
        if day_distance <= HOME_DISCOVERY_WINDOW_DAYS:
            picture_candidates.append((picture, day_distance))

    diary_candidates = []
    for diary in DiaryTexts.objects.all():
        if diary.date.year == today.year:
            continue
        day_distance = _day_distance_ignoring_year(diary.date, today)
        if day_distance <= HOME_DISCOVERY_WINDOW_DAYS:
            diary_candidates.append((diary, day_distance))

    picture_candidates.sort(key=lambda item: (item[1], -item[0].date.year, item[0].href))
    diary_candidates.sort(key=lambda item: (item[1], -item[0].date.year, item[0].id))

    #picture_exact_match = any(distance == 0 for _, distance in picture_candidates)
    #diary_exact_match = any(distance == 0 for _, distance in diary_candidates)
    #exact_match = picture_exact_match

    daily_rng = _build_daily_rng(today, 'on-this-day')
    selected_pictures = _pick_daily_sample(
        picture_candidates,
        HOME_HERO_PICTURE_LIMIT,
        daily_rng,
        lambda item: (item[1], -item[0].date.year, item[0].href),
    )
    selected_diaries = _pick_daily_sample(
        diary_candidates,
        HOME_HERO_DIARY_LIMIT,
        daily_rng,
        lambda item: (item[1], -item[0].date.year, item[0].id),
    )

    exact_match = any(distance == 0 for _, distance in selected_pictures)

    selected_picture_objs = [picture for picture, _ in selected_pictures]
    picture_map, property_map = _fetch_context_maps([picture.href for picture in selected_picture_objs])
    years = sorted({item.date.year for item in selected_picture_objs} | {item.date.year for item, _ in selected_diaries})
    title, subtitle = _build_on_this_day_titles(
        exact_match,
        len(selected_pictures),
        len(selected_diaries),
        HOME_DISCOVERY_WINDOW_DAYS,
        years,
    )

    return {
        'type': 'on_this_day',
        'title': title,
        'subtitle': subtitle,
        'windowDays': HOME_DISCOVERY_WINDOW_DAYS,
        'exactMatch': exact_match,
        'stats': {
            'matchedPictures': len(picture_candidates),
            'matchedDiaries': len(diary_candidates),
            'yearRange': years,
        },
        'pictures': [
            {
                **_serialize_picture(picture, picture_map, property_map),
                'distanceDays': distance,
            }
            for picture, distance in selected_pictures
        ],
        'diaries': [
            {
                **_serialize_diary(diary),
                'distanceDays': distance,
            }
            for diary, distance in selected_diaries
        ],
        'empty': not picture_candidates and not diary_candidates,
    }


def _build_theme_candidates(anchor, keyword_map, property_map):
    themes = []
    for keyword in keyword_map.get(anchor.href, []):
        related_count = Pictures.objects.filter(
            keywords__keyword=keyword,
            date__isnull=False,
        ).exclude(href=anchor.href).distinct().count()
        if related_count > 0:
            themes.append({
                'kind': 'keyword',
                'label': keyword,
                'relatedCount': related_count,
            })
    for property_name, value in property_map.get(anchor.href, []):
        related_count = Pictures.objects.filter(
            properties__property_name=property_name,
            properties__value=value,
            date__isnull=False,
        ).exclude(href=anchor.href).distinct().count()
        if related_count > 0:
            themes.append({
                'kind': 'property',
                'label': value,
                'propertyName': property_name,
                'relatedCount': related_count,
            })
    if anchor.date:
        same_month_count = Pictures.objects.filter(
            date__month=anchor.date.month,
            date__isnull=False,
        ).exclude(href=anchor.href).distinct().count()
        if same_month_count > 0:
            themes.append({
                'kind': 'month',
                'label': f'{anchor.date.month}月',
                'relatedCount': same_month_count,
            })
    return themes


def _pick_anchor_picture(today):
    pictures = list(
        Pictures.objects.filter(date__isnull=False)
        .exclude(description__isnull=True)
        .exclude(description='')
    )
    if not pictures:
        return None
    rng = _build_daily_rng(today, 'memory-remix-anchor')
    pictures.sort(key=lambda picture: (picture.date, picture.href))
    return rng.choice(pictures)


def _build_remix_title(theme, anchor, related_pictures):
    if theme['kind'] == 'keyword':
        return f'记忆重组: {theme["label"]}'
    if theme['kind'] == 'property':
        return f'记忆重组: {theme["propertyName"]}里的 {theme["label"]}'
    if anchor.date:
        return f'记忆重组: {anchor.date.month}月的你'
    return '记忆重组'


def _build_remix_subtitle(theme, anchor, related_pictures):
    years = sorted({picture.date.year for picture in related_pictures if picture.date} | ({anchor.date.year} if anchor.date else set()))
    year_text = f'{years[0]}-{years[-1]}' if len(years) > 1 else (str(years[0]) if years else '过去几年')
    if theme['kind'] == 'keyword':
        return f'同一个关键词在 {year_text} 反复出现，像一条被悄悄重复的线索。'
    if theme['kind'] == 'property':
        return f'围绕同一种 {theme["propertyName"]}，系统为你重新拼起几段旧内容。'
    return f'从不同年份的 {theme["label"]} 里，抽出几张彼此呼应的照片。'


def _build_related_diaries(theme, anchor):
    if theme['kind'] in {'keyword', 'property'}:
        diaries = list(DiaryTexts.objects.filter(text__contains=theme['label']).order_by('-date')[:HOME_REMIX_DIARY_LIMIT])
        if diaries:
            return diaries
    if not anchor.date:
        return []
    diaries = list(DiaryTexts.objects.filter(date__month=anchor.date.month).order_by('-date')[:HOME_REMIX_DIARY_LIMIT])
    return diaries


def _build_memory_remix_module(today):
    anchor = _pick_anchor_picture(today)
    if not anchor:
        return {
            'type': 'memory_remix',
            'title': '记忆重组',
            'subtitle': '还没有足够的历史图片来生成这张卡片。',
            'empty': True,
            'anchor': None,
            'pictures': [],
            'diaries': [],
            'theme': None,
        }

    anchor_keywords, anchor_properties = _fetch_context_maps([anchor.href])
    theme_candidates = _build_theme_candidates(anchor, anchor_keywords, anchor_properties)
    if not theme_candidates:
        theme_candidates = [{'kind': 'month', 'label': f'{anchor.date.month}月', 'relatedCount': 1}] if anchor.date else []

    theme_candidates.sort(key=lambda item: (-item['relatedCount'], item['kind'], item['label']))
    # Use a daily RNG to introduce controlled randomness when picking the theme:
    # 50% chance to pick the top candidate, otherwise pick a random candidate from the list.
    theme = None
    if theme_candidates:
        theme_rng = _build_daily_rng(today, 'memory-remix-theme')
        if theme_rng.random() < 0.2:
            theme = theme_candidates[0]
        else:
            theme = theme_rng.choice(theme_candidates)
    else:
        theme = {'kind': 'month', 'label': '往日片段', 'relatedCount': 0}

    if theme['kind'] == 'keyword':
        queryset = Pictures.objects.filter(
            keywords__keyword=theme['label'],
            date__isnull=False,
        )
    elif theme['kind'] == 'property':
        queryset = Pictures.objects.filter(
            properties__property_name=theme['propertyName'],
            properties__value=theme['label'],
            date__isnull=False,
        )
    else:
        queryset = Pictures.objects.filter(
            date__month=anchor.date.month,
            date__isnull=False,
        ) if anchor.date else Pictures.objects.filter(href=anchor.href)

    related_pictures = list(queryset.exclude(href=anchor.href).distinct().order_by('-date', 'href')[:HOME_REMIX_PICTURE_LIMIT - 1])
    all_pictures = [anchor] + related_pictures
    keyword_map, property_map = _fetch_context_maps([picture.href for picture in all_pictures])
    diaries = _build_related_diaries(theme, anchor)

    return {
        'type': 'memory_remix',
        'title': _build_remix_title(theme, anchor, related_pictures),
        'subtitle': _build_remix_subtitle(theme, anchor, related_pictures),
        'empty': False,
        'theme': theme,
        'anchor': _serialize_picture(anchor, keyword_map, property_map),
        'pictures': [_serialize_picture(picture, keyword_map, property_map) for picture in all_pictures],
        'diaries': [_serialize_diary(diary) for diary in diaries],
    }


def _parse_backup_timestamp(timestamp):
    try:
        return datetime.datetime.strptime(timestamp, '%Y%m%d%H%M%S')
    except (TypeError, ValueError):
        return None


def _build_digest_module(today):
    total_pictures = Pictures.objects.filter(is_collection=False).count()
    pictures_this_month = Pictures.objects.filter(
        date__year=today.year,
        date__month=today.month,
    ).count()
    diaries_this_month = DiaryTexts.objects.filter(date__year=today.year, date__month=today.month).count()
    last_diary_date = DiaryTexts.objects.aggregate(max_date=Max('date'))['max_date']
    days_since_last_diary = (today - last_diary_date).days if last_diary_date else None
    blank_count = BlankPictures.objects.count()
    unread_messages = Messages.objects.filter(status='unread').count()
    backup_timestamp = BackupRecords.objects.aggregate(max_timestamp=Max('timestamp'))['max_timestamp']
    last_backup_at = _parse_backup_timestamp(backup_timestamp)

    recent_keyword_counter = Counter(
        Keywords.objects.filter(
            href__date__gte=today - datetime.timedelta(days=90),
        )
        .values_list('keyword', flat=True)
    )
    top_keywords = [
        {'keyword': keyword, 'count': count}
        for keyword, count in recent_keyword_counter.most_common(5)
    ]

    reminders = []
    if days_since_last_diary is not None and days_since_last_diary >= 3:
        reminders.append({
            'type': 'diary',
            'severity': 'tips',
            'text': f'已经有 {days_since_last_diary} 天没有写日记了。',
            'link': '/diary',
        })
    if blank_count >= 5:
        reminders.append({
            'type': 'blank_pictures',
            'severity': 'tips',
            'text': f'还有 {blank_count} 张待整理图片可以回头处理。',
            'link': '/upload',
        })
    if last_backup_at and (datetime.datetime.combine(today, datetime.time.min) - last_backup_at).days >= 5:
        reminders.append({
            'type': 'backup',
            'severity': 'warning',
            'text': '距离上次备份已经超过 5 天，适合检查一下备份状态。',
            'link': '/manage',
        })

    highlights = []
    if top_keywords:
        keyword_phrase = '、'.join(item['keyword'] for item in top_keywords[:3])
        highlights.append(f'最近 90 天里，你最常记录的主题是 {keyword_phrase}。')
    if pictures_this_month:
        highlights.append(f'这个月已经新增 {pictures_this_month} 张图片。')
    if diaries_this_month:
        highlights.append(f'这个月写了 {diaries_this_month} 篇日记。')
    if unread_messages:
        highlights.append(f'消息中心还有 {unread_messages} 条未读提醒。')

    return {
        'type': 'memory_digest',
        'title': '',
        'subtitle': '',
        'stats': {
            'totalPictures': total_pictures,
            'picturesThisMonth': pictures_this_month,
            'diariesThisMonth': diaries_this_month,
            'daysSinceLastDiary': days_since_last_diary,
            'blankPictures': blank_count,
            'unreadMessages': unread_messages,
            'lastBackupAt': last_backup_at.strftime('%Y-%m-%d %H:%M:%S') if last_backup_at else None,
        },
        'topKeywords': top_keywords,
        'highlights': highlights,
        'reminders': reminders,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def homeDiscovery(request):
    today = datetime.date.today()
    response = {
        'generatedAt': today.strftime('%Y-%m-%d'),
        'modules': {
            'hero': _build_on_this_day_module(today),
            'remix': _build_memory_remix_module(today),
            'digest': _build_digest_module(today),
        },
    }
    return _as_json(response)
