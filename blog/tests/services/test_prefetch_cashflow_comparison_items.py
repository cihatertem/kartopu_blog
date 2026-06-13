from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from blog.services import prefetch_cashflow_comparison_items


class TestPrefetchCashflowComparisonItems(SimpleTestCase):
    def test_empty_comparisons(self):
        prefetch_cashflow_comparison_items([])

    @patch("blog.services.prefetch_related_objects")
    def test_single_comparison(self, mock_prefetch):
        mock_snapshot = Mock()
        mock_snapshot.pk = 1
        mock_snapshot._meta = Mock()

        mock_comparison = Mock()
        mock_comparison.base_snapshot = mock_snapshot
        mock_comparison.compare_snapshot = mock_snapshot

        prefetch_cashflow_comparison_items([mock_comparison])
        mock_prefetch.assert_called_once_with([mock_snapshot], "items")

    @patch("blog.services.prefetch_related_objects")
    def test_multiple_comparisons_deduplication(self, mock_prefetch):
        mock_snapshot_1 = Mock()
        mock_snapshot_1.pk = 1
        mock_snapshot_1._meta = Mock()
        mock_snapshot_1._prefetched_objects_cache = {"items": [Mock()]}

        mock_snapshot_1_dup = Mock()
        mock_snapshot_1_dup.pk = 1
        mock_snapshot_1_dup._meta = Mock()
        mock_snapshot_1_dup._prefetched_objects_cache = {}

        mock_snapshot_2 = Mock()
        mock_snapshot_2.pk = 2
        mock_snapshot_2._meta = Mock()

        mock_comparison_1 = Mock()
        mock_comparison_1.base_snapshot = mock_snapshot_1
        mock_comparison_1.compare_snapshot = mock_snapshot_2

        mock_comparison_2 = Mock()
        mock_comparison_2.base_snapshot = mock_snapshot_1_dup
        mock_comparison_2.compare_snapshot = None

        prefetch_cashflow_comparison_items([mock_comparison_1, mock_comparison_2])

        mock_prefetch.assert_called_once()
        called_args = mock_prefetch.call_args[0][0]
        self.assertEqual(len(called_args), 2)
        self.assertIn(mock_snapshot_1, called_args)
        self.assertIn(mock_snapshot_2, called_args)

        self.assertIn("items", mock_snapshot_1_dup._prefetched_objects_cache)
        self.assertEqual(
            mock_snapshot_1_dup._prefetched_objects_cache["items"],
            mock_snapshot_1._prefetched_objects_cache["items"],
        )
