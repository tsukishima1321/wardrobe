import datetime

from django.test import SimpleTestCase

from wardrobe_db.views.stat_views import _build_report_match_query, _build_timeline_report, _normalize_match_mode, _tokenize_title_for_report


class TimelineReportHelpersTests(SimpleTestCase):
    def test_normalize_match_mode_defaults_to_title_only(self):
        self.assertEqual(_normalize_match_mode(None), 'title_only')
        self.assertEqual(_normalize_match_mode(''), 'title_only')
        self.assertEqual(_normalize_match_mode('TITLE_KEYWORD_PROPERTY'), 'title_keyword_property')

    def test_build_report_match_query_supports_both_modes(self):
        title_only_query = _build_report_match_query('春天', 'title_only')
        combined_query = _build_report_match_query('春天', 'title_keyword_property')

        self.assertEqual(title_only_query.children, [('description__contains', '春天')])
        self.assertEqual(combined_query.connector, 'OR')
        self.assertIn(('description__contains', '春天'), combined_query.children)
        self.assertIn(('keywords__keyword', '春天'), combined_query.children)
        self.assertIn(('properties__value', '春天'), combined_query.children)

    def test_build_timeline_report_groups_by_month(self):
        pictures = [
            {'href': '1.jpg', 'description': '春天的猫在窗边', 'date': datetime.date(2026, 1, 3)},
            {'href': '2.jpg', 'description': '春天和花一起出现', 'date': datetime.date(2026, 1, 20)},
            {'href': '3.jpg', 'description': '春天旅行穿搭', 'date': datetime.date(2026, 2, 2)},
        ]
        keyword_map = {
            '1.jpg': ['猫咪', '室内'],
            '2.jpg': ['花朵'],
            '3.jpg': ['旅行'],
        }
        property_map = {
            '1.jpg': [('地点', '家里')],
            '2.jpg': [('颜色', '绿色')],
            '3.jpg': [('地点', '上海')],
        }

        report = _build_timeline_report(
            term='春天',
            pictures=pictures,
            keyword_map=keyword_map,
            property_map=property_map,
            granularity='month',
            top_n=5,
        )

        self.assertEqual(report['summary']['matchedImageCount'], 3)
        self.assertEqual(report['summary']['bucketCount'], 2)
        self.assertEqual(report['summary']['firstDate'], '2026-01-03')
        self.assertEqual(report['summary']['lastDate'], '2026-02-02')
        self.assertEqual(report['timeline'][0]['period'], '2026-01')
        self.assertEqual(report['timeline'][0]['matchedImageCount'], 2)
        self.assertEqual(report['timeline'][1]['period'], '2026-02')
        self.assertEqual(report['timeline'][1]['matchedImageCount'], 1)
        self.assertIn({'keyword': '猫咪', 'count': 1}, report['timeline'][0]['keywordRelations'])

    def test_build_timeline_report_counts_relations_once_per_picture(self):
        pictures = [
            {'href': '1.jpg', 'description': '猫和猫在春天玩耍', 'date': datetime.date(2026, 3, 1)},
            {'href': '2.jpg', 'description': '春天猫咪晒太阳', 'date': datetime.date(2026, 3, 5)},
        ]
        keyword_map = {
            '1.jpg': ['宠物', '宠物'],
            '2.jpg': ['宠物'],
        }
        property_map = {
            '1.jpg': [('地点', '客厅'), ('地点', '客厅')],
            '2.jpg': [('地点', '阳台')],
        }

        report = _build_timeline_report(
            term='春天',
            pictures=pictures,
            keyword_map=keyword_map,
            property_map=property_map,
            granularity='month',
            top_n=5,
        )

        timeline_item = report['timeline'][0]
        self.assertEqual(timeline_item['keywordRelations'][0], {'keyword': '宠物', 'count': 2})
        self.assertIn({'propertyName': '地点', 'value': '客厅', 'count': 1}, timeline_item['propertyRelations'])

    def test_tokenize_title_for_report_excludes_target_word_and_noise(self):
        tokens = _tokenize_title_for_report('春天!春天? 和 花 2026 一起散步', '春天')

        self.assertNotIn('春天', tokens)
        self.assertIn('一起', tokens)
        self.assertIn('2026', tokens)
        self.assertNotIn('和', tokens)
