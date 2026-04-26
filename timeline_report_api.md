# Timeline Report API

This document describes the backend contract for the timeline report feature, for frontend integration.

## Overview

The timeline report generates structured data for a selected word.

The backend only returns report data.
Timeline layout, charts, cards, and other visual rendering should be handled by the frontend.

Current relationship data is split into three groups:

- `titleRelations`: words that co-occur with the selected word in the picture title/description.
- `keywordRelations`: keywords attached to the matched pictures.
- `propertyRelations`: property name + value pairs attached to the matched pictures.

## Endpoint

- Backend route: `POST /report/timeline/`
- Under the recommended Nginx setup in [readme.md](/home/shima/wardrobe/django/readme.md), the frontend will usually call: `POST /api/report/timeline/`
- Auth: JWT required
- Content-Type: `application/json`

## Request Body

```json
{
  "word": "春天",
  "granularity": "month",
  "matchMode": "title_only",
  "topN": 8
}
```

## Request Fields

| Field | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `word` | `string` | yes | none | The target word used to generate the report. `term` is also accepted as an alias. |
| `granularity` | `"day" \| "month" \| "year"` | no | `"month"` | Time bucket granularity. |
| `matchMode` | `"title_only" \| "title_keyword_property"` | no | `"title_only"` | Controls how matched pictures are selected. |
| `topN` | `number` | no | `8` | Max number of items returned in each relation list. Valid range is `1` to `20`. |

## Match Modes

### `title_only`

Current default behavior.

A picture is matched only when:

- `Pictures.description` contains the selected word

### `title_keyword_property`

A picture is matched when any of these conditions is true:

- `Pictures.description` contains the selected word
- the selected word is one of the picture keywords
- the selected word exactly equals a property value on the picture

Shared rules for both modes:

- Only pictures with a non-empty `date` are included.
- Collection cover images are excluded.

## Success Response

```json
{
  "word": "春天",
  "granularity": "month",
  "matchMode": "title_only",
  "summary": {
    "matchedImageCount": 6,
    "bucketCount": 3,
    "firstDate": "2026-01-03",
    "lastDate": "2026-03-11",
    "topTitleRelations": [
      { "word": "花", "count": 3 },
      { "word": "旅行", "count": 2 }
    ],
    "topKeywordRelations": [
      { "keyword": "穿搭", "count": 4 },
      { "keyword": "户外", "count": 2 }
    ],
    "topPropertyRelations": [
      { "propertyName": "地点", "value": "上海", "count": 2 },
      { "propertyName": "颜色", "value": "绿色", "count": 2 }
    ]
  },
  "timeline": [
    {
      "period": "2026-01",
      "startDate": "2026-01-01",
      "endDate": "2026-01-31",
      "matchedImageCount": 2,
      "titleRelations": [
        { "word": "花", "count": 1 },
        { "word": "窗边", "count": 1 }
      ],
      "keywordRelations": [
        { "keyword": "穿搭", "count": 1 },
        { "keyword": "室内", "count": 1 }
      ],
      "propertyRelations": [
        { "propertyName": "地点", "value": "家里", "count": 1 }
      ],
      "sampleTitles": [
        "春天的猫在窗边",
        "春天和花一起出现"
      ]
    }
  ]
}
```

## Response Fields

### Top-level fields

| Field | Type | Description |
| --- | --- | --- |
| `word` | `string` | The requested target word. |
| `granularity` | `string` | The actual granularity used by the backend. |
| `matchMode` | `string` | The actual picture matching mode used by the backend. |
| `summary` | `object` | Overall report summary across all matched pictures. |
| `timeline` | `array` | Timeline buckets in ascending time order. |

### `summary`

| Field | Type | Description |
| --- | --- | --- |
| `matchedImageCount` | `number` | Total matched pictures in the full report range. |
| `bucketCount` | `number` | Number of returned time buckets. |
| `firstDate` | `string \| null` | Earliest matched picture date in `YYYY-MM-DD`. |
| `lastDate` | `string \| null` | Latest matched picture date in `YYYY-MM-DD`. |
| `topTitleRelations` | `array` | Most common title co-occurrence words across all matched pictures. |
| `topKeywordRelations` | `array` | Most common keywords across all matched pictures. |
| `topPropertyRelations` | `array` | Most common property pairs across all matched pictures. |

### `timeline[]`

| Field | Type | Description |
| --- | --- | --- |
| `period` | `string` | Bucket label. Format depends on granularity: `YYYY-MM-DD`, `YYYY-MM`, or `YYYY`. |
| `startDate` | `string` | Start date of the bucket in `YYYY-MM-DD`. |
| `endDate` | `string` | End date of the bucket in `YYYY-MM-DD`. |
| `matchedImageCount` | `number` | Number of matched pictures in the bucket. |
| `titleRelations` | `array` | Top title co-occurrence words for this bucket. |
| `keywordRelations` | `array` | Top keyword relations for this bucket. |
| `propertyRelations` | `array` | Top property relations for this bucket. |
| `sampleTitles` | `array` | Up to 3 sample titles from the bucket, for tooltip or preview use. |

### `titleRelations[]`

```json
{ "word": "花", "count": 3 }
```

### `keywordRelations[]`

```json
{ "keyword": "穿搭", "count": 4 }
```

### `propertyRelations[]`

```json
{ "propertyName": "地点", "value": "上海", "count": 2 }
```

## Error Responses

### `400 Missing word`

Returned when neither `word` nor `term` is provided, or when the value is blank.

### `400 Invalid granularity`

Returned when `granularity` is not one of:

- `day`
- `month`
- `year`

### `400 Invalid matchMode`

Returned when `matchMode` is not one of:

- `title_only`
- `title_keyword_property`

### `400 Invalid topN`

Returned when `topN` is not a valid integer.

## Frontend Notes

- The backend does not fill missing empty time buckets. If the frontend needs a continuous timeline, it should generate empty buckets locally.
- `matchedImageCount` is the only built-in count metric per bucket.
- Relation lists are already sorted by descending `count`.
- Counts are picture-based, not raw token frequency based.
- If a related word appears multiple times in one title, it is still counted once for that picture.
- `sampleTitles` is meant for lightweight preview only, not full pagination or drill-down.
- If the frontend needs click-through search, it can combine `word` with `startDate` and `endDate` and call the existing search endpoint separately.
