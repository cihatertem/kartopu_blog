from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from blog.cache_keys import (
    DIVIDEND_WIDGET_KEY,
    GOAL_WIDGET_KEY,
    NAV_CATEGORIES_KEY,
    NAV_POPULAR_POSTS_KEY,
    NAV_PORTFOLIO_POSTS_KEY,
    NAV_RECENT_POSTS_KEY,
    NAV_TAGS_KEY,
    STAFF_PENDING_NOTIFICATIONS_KEY,
)
from blog.models import BlogPost, Category, Tag
from comments.models import Comment
from core.context_processors import (
    CACHE_TIMEOUT,
    CACHE_TIMEOUT_JITTER,
    DIVIDEND_WIDGET_2025_TRY_TOTAL,
    DIVIDEND_WIDGET_2025_USD_TOTAL,
    DIVIDEND_WIDGET_EMPTY_CACHE_VALUE,
    DIVIDEND_WIDGET_TEMPLATE_NAME,
    GOAL_WIDGET_EMPTY_CACHE_VALUE,
    _cache_timeout_with_jitter,
    _calculate_tag_cloud_sizes,
    _get_dividend_widget_snapshot,
    _get_goal_widget_snapshot,
    _get_has_pending_messages_or_comments,
    _get_nav_archives,
    _get_nav_categories,
    _get_nav_popular_posts,
    _get_nav_portfolio_posts,
    _get_nav_recent_posts,
    _get_nav_tags,
    _get_or_set_with_stampede_lock,
    breadcrumbs_context,
    categories_tags_context,
    google_analytics_context,
    sidebar_widgets_context,
    site_metadata_context,
    site_settings_context,
)
from core.models import ContactMessage, SidebarWidget, SiteSettings
from portfolio.models import DividendSnapshot, Portfolio, PortfolioSnapshot

User = get_user_model()


class ContextProcessorsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

        self._create_users()
        self._create_blog_data()
        self._create_portfolio_data()
        self._create_site_data()

    def _create_users(self):
        self.staff_user = User.objects.create_user(
            email="staff@test.com", password="password", is_staff=True
        )
        self.normal_user = User.objects.create_user(
            email="normal@test.com", password="password"
        )

    def _create_blog_data(self):
        self.cat1 = Category.objects.create(name="Cat 1", slug="cat-1")
        self.cat_portfolio = Category.objects.create(name="Portföy", slug="portfoy")
        self.tag1 = Tag.objects.create(name="Tag 1", slug="tag-1")

        self.post1 = BlogPost.objects.create(
            title="Post 1",
            slug="post-1",
            author=self.staff_user,
            category=self.cat1,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.make_aware(datetime(2023, 1, 15)),
            view_count=100,
        )
        self.post1.tags.add(self.tag1)

        self.post_port = BlogPost.objects.create(
            title="Portfolio Post",
            slug="portfolio-post",
            author=self.staff_user,
            category=self.cat_portfolio,
            status=BlogPost.Status.PUBLISHED,
            published_at=timezone.make_aware(datetime(2023, 2, 20)),
        )

        Comment.objects.create(
            post=self.post1,
            author=self.normal_user,
            body="Great post",
            status=Comment.Status.APPROVED,
        )

    def _create_portfolio_data(self):
        self.portfolio = Portfolio.objects.create(
            owner=self.staff_user, name="My Portfolio", target_value=Decimal("100000")
        )
        self.snapshot = PortfolioSnapshot.objects.create(
            portfolio=self.portfolio,
            is_featured=True,
            snapshot_date=datetime(2023, 1, 1).date(),
            total_value=Decimal("50000"),
            total_cost=Decimal("20000"),
            target_value=Decimal("100000"),
            total_return_pct=Decimal("150"),
        )

    def _create_site_data(self):
        self.contact_msg = ContactMessage.objects.create(
            name="Bob",
            subject="Hello",
            email="bob@test.com",
            message="Hi",
            is_read=False,
        )

        SiteSettings.objects.create(is_comments_enabled=False)
        SidebarWidget.objects.create(
            title="Widget 1",
            template_name="includes/sidebar_1.html",
            is_active=True,
            order=1,
        )

    def test_breadcrumbs_context_blog(self):
        request = self.factory.get("/blog/")
        request.resolver_match = resolve("/blog/")

        context = breadcrumbs_context(request)

        self.assertEqual(len(context["breadcrumbs"]), 1)
        self.assertEqual(context["breadcrumbs"][0]["label"], "Blog")

    def test_breadcrumbs_context_non_blog(self):
        request = self.factory.get("/")
        request.resolver_match = resolve("/")

        context = breadcrumbs_context(request)

        self.assertEqual(len(context["breadcrumbs"]), 0)

    def test_get_nav_categories(self):
        cats = _get_nav_categories()

        self.assertTrue(len(cats) > 0)
        self.assertEqual(cats[0]["name"], "Cat 1")
        self.assertEqual(cache.get(NAV_CATEGORIES_KEY), cats)

    def test_get_nav_tags(self):
        tags = _get_nav_tags()

        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["name"], "Tag 1")
        self.assertIn("get_absolute_url", tags[0])
        self.assertIn("/tag-1/", tags[0]["get_absolute_url"])
        self.assertIn("cloud_size", tags[0])
        self.assertEqual(tags[0]["cloud_size"], 1.0)
        self.assertEqual(tags[0]["cloud_size_class"], "tag-cloud__item--size-2")
        self.assertEqual(cache.get(NAV_TAGS_KEY), tags)

    def test_get_nav_archives(self):
        archives = _get_nav_archives()

        self.assertEqual(len(archives), 2)  # Two months: Jan 2023 and Feb 2023
        self.assertTrue(
            any(
                a["label"] == "Ocak 2023" or a["label"] == "January 2023"
                for a in archives
            )
        )

    def test_get_nav_recent_posts(self):
        posts = _get_nav_recent_posts()

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["slug"], "portfolio-post")
        self.assertEqual(cache.get(NAV_RECENT_POSTS_KEY), posts)

    def test_get_nav_popular_posts(self):
        posts = _get_nav_popular_posts()

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["slug"], "post-1")
        self.assertEqual(cache.get(NAV_POPULAR_POSTS_KEY), posts)

    def test_get_nav_portfolio_posts(self):
        posts = _get_nav_portfolio_posts()

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["slug"], "portfolio-post")
        self.assertEqual(cache.get(NAV_PORTFOLIO_POSTS_KEY), posts)

    def test_get_goal_widget_snapshot(self):
        snapshot = _get_goal_widget_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["current_value"], Decimal("50000"))
        self.assertEqual(snapshot["target_value"], Decimal("100000"))
        self.assertEqual(snapshot["remaining_pct"]["display"], 50)
        self.assertEqual(
            snapshot["remaining_pct"]["fill_class"], "goal-widget__fill--50"
        )

    def test_get_goal_widget_snapshot_uses_min_fill_for_tiny_progress(self):
        PortfolioSnapshot.objects.filter(pk=self.snapshot.pk).update(
            total_value=Decimal("984"),
            target_value=Decimal("24000000"),
        )

        snapshot = _get_goal_widget_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["remaining_pct"]["value"], 0)
        self.assertEqual(
            snapshot["remaining_pct"]["fill_class"], "goal-widget__fill--1"
        )

    def test_get_goal_widget_snapshot_target_zero(self):
        PortfolioSnapshot.objects.filter(pk=self.snapshot.pk).update(
            target_value=Decimal("0"),
            total_value=Decimal("100"),
        )

        snapshot = _get_goal_widget_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["remaining_pct"]["value"], 100)
        self.assertEqual(snapshot["remaining_pct"]["display"], 0)

    def test_get_goal_widget_snapshot_completed(self):
        PortfolioSnapshot.objects.filter(pk=self.snapshot.pk).update(
            target_value=Decimal("10000"),
            total_value=Decimal("15000"),
        )

        snapshot = _get_goal_widget_snapshot()

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["remaining_pct"]["value"], 100)
        self.assertEqual(snapshot["remaining_pct"]["display"], 0)

    def test_get_goal_widget_snapshot_caching(self):
        # 1. First call - populates cache
        snapshot1 = _get_goal_widget_snapshot()
        self.assertIsNotNone(snapshot1)
        self.assertEqual(cache.get(GOAL_WIDGET_KEY), snapshot1)

        # 2. Update DB without clearing cache (directly via update)
        PortfolioSnapshot.objects.filter(pk=self.snapshot.pk).update(
            total_value=Decimal("99999")
        )

        # 3. Second call - should still return old value from cache
        snapshot2 = _get_goal_widget_snapshot()
        self.assertEqual(snapshot2["current_value"], Decimal("50000"))

        # 4. Save the instance - should trigger signal and clear cache
        self.snapshot.total_value = Decimal("99999")
        self.snapshot.save()

        self.assertIsNone(cache.get(GOAL_WIDGET_KEY))

        # 5. Third call - should return new value
        snapshot3 = _get_goal_widget_snapshot()
        self.assertEqual(snapshot3["current_value"], Decimal("99999"))

    def test_get_goal_widget_snapshot_caches_empty_result(self):
        PortfolioSnapshot.objects.all().delete()
        cache.clear()

        with self.assertNumQueries(1):
            snapshot = _get_goal_widget_snapshot()

        self.assertIsNone(snapshot)
        self.assertEqual(cache.get(GOAL_WIDGET_KEY), GOAL_WIDGET_EMPTY_CACHE_VALUE)

        with self.assertNumQueries(0):
            self.assertIsNone(_get_goal_widget_snapshot())

    def test_goal_widget_cache_invalidated_when_featured_snapshot_demoted(self):
        snapshot = _get_goal_widget_snapshot()
        self.assertIsNotNone(snapshot)
        self.assertEqual(cache.get(GOAL_WIDGET_KEY), snapshot)

        self.snapshot.is_featured = False
        self.snapshot.save()

        self.assertIsNone(cache.get(GOAL_WIDGET_KEY))

    def test_get_dividend_widget_snapshot_uses_2025_try_fallback_when_previous_not_selected(
        self,
    ):
        curr_snap = DividendSnapshot.objects.create(
            year=2026,
            currency="TRY",
            total_amount=Decimal("25000.00"),
            snapshot_date=date(2026, 11, 16),
        )
        SidebarWidget.objects.create(
            title="Temettü Geliri",
            template_name=DIVIDEND_WIDGET_TEMPLATE_NAME,
            current_dividend_snapshot=curr_snap,
            previous_dividend_snapshot=None,
            is_active=True,
            order=2,
        )
        cache.clear()

        with self.assertNumQueries(1):
            data = _get_dividend_widget_snapshot()

        self.assertIsNotNone(data)
        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["currency"], "TRY")
        self.assertEqual(data["currency_symbol"], "₺")
        self.assertEqual(data["current_value"], Decimal("25000.00"))
        self.assertEqual(data["current_display"], "25.000,00 ₺")
        self.assertEqual(data["previous_year"], 2025)
        self.assertEqual(data["previous_value"], DIVIDEND_WIDGET_2025_TRY_TOTAL)
        self.assertEqual(data["previous_display"], "19.967,52 ₺")
        self.assertEqual(data["change_pct_display"], "+%25,2")
        self.assertTrue(data["is_positive"])

    def test_get_dividend_widget_snapshot_uses_2025_usd_fallback_when_previous_not_selected(
        self,
    ):
        curr_snap = DividendSnapshot.objects.create(
            year=2026,
            currency="USD",
            total_amount=Decimal("600.48"),
            snapshot_date=date(2026, 11, 16),
        )
        SidebarWidget.objects.create(
            title="Temettü Geliri",
            template_name=DIVIDEND_WIDGET_TEMPLATE_NAME,
            current_dividend_snapshot=curr_snap,
            previous_dividend_snapshot=None,
            is_active=True,
            order=2,
        )
        cache.clear()

        data = _get_dividend_widget_snapshot()

        self.assertIsNotNone(data)
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["currency_symbol"], "$")
        self.assertEqual(data["current_display"], "600,48 $")
        self.assertEqual(data["previous_year"], 2025)
        self.assertEqual(data["previous_value"], DIVIDEND_WIDGET_2025_USD_TOTAL)
        self.assertEqual(data["previous_display"], "522,16 $")
        self.assertEqual(data["change_pct_display"], "+%15,0")
        self.assertTrue(data["is_positive"])

    def test_get_dividend_widget_snapshot_uses_selected_previous_snapshot_from_2027(
        self,
    ):
        snap_2026 = DividendSnapshot.objects.create(
            year=2026,
            currency="USD",
            total_amount=Decimal("2810.40"),
            snapshot_date=date(2026, 12, 31),
        )
        snap_2027 = DividendSnapshot.objects.create(
            year=2027,
            currency="USD",
            total_amount=Decimal("3245.80"),
            snapshot_date=date(2027, 11, 16),
        )
        SidebarWidget.objects.create(
            title="Temettü Geliri",
            template_name=DIVIDEND_WIDGET_TEMPLATE_NAME,
            current_dividend_snapshot=snap_2027,
            previous_dividend_snapshot=snap_2026,
            is_active=True,
            order=2,
        )
        cache.clear()

        data = _get_dividend_widget_snapshot()

        self.assertIsNotNone(data)
        self.assertEqual(data["year"], 2027)
        self.assertEqual(data["current_display"], "3.245,80 $")
        self.assertEqual(data["previous_year"], 2026)
        self.assertEqual(data["previous_display"], "2.810,40 $")
        self.assertEqual(data["change_pct_display"], "+%15,5")
        self.assertEqual(data["change_arrow"], "↗")
        self.assertTrue(data["is_positive"])

    def test_get_dividend_widget_snapshot_caching_and_invalidation(self):
        curr_snap = DividendSnapshot.objects.create(
            year=2026,
            currency="TRY",
            total_amount=Decimal("25000.00"),
            snapshot_date=date(2026, 11, 16),
        )
        widget = SidebarWidget.objects.create(
            title="Temettü Geliri",
            template_name=DIVIDEND_WIDGET_TEMPLATE_NAME,
            current_dividend_snapshot=curr_snap,
            is_active=True,
            order=2,
        )
        cache.clear()

        data1 = _get_dividend_widget_snapshot()
        self.assertEqual(cache.get(DIVIDEND_WIDGET_KEY), data1)

        # Direct DB update without signals should serve cached value
        DividendSnapshot.objects.filter(pk=curr_snap.pk).update(
            total_amount=Decimal("30000.00")
        )
        with self.assertNumQueries(0):
            data2 = _get_dividend_widget_snapshot()
        self.assertEqual(data2["current_value"], Decimal("25000.00"))

        # Saving DividendSnapshot invalidates cache
        curr_snap.total_amount = Decimal("30000.00")
        curr_snap.save()
        self.assertIsNone(cache.get(DIVIDEND_WIDGET_KEY))

        data3 = _get_dividend_widget_snapshot()
        self.assertEqual(data3["current_value"], Decimal("30000.00"))

        # Saving SidebarWidget (changing selected snapshot) invalidates cache
        new_snap = DividendSnapshot.objects.create(
            year=2026,
            currency="USD",
            total_amount=Decimal("1000.00"),
            snapshot_date=date(2026, 12, 1),
        )
        _get_dividend_widget_snapshot()
        self.assertIsNotNone(cache.get(DIVIDEND_WIDGET_KEY))

        widget.current_dividend_snapshot = new_snap
        widget.save()
        self.assertIsNone(cache.get(DIVIDEND_WIDGET_KEY))

        data4 = _get_dividend_widget_snapshot()
        self.assertEqual(data4["currency"], "USD")
        self.assertEqual(data4["current_value"], Decimal("1000.00"))

    def test_get_dividend_widget_snapshot_caches_empty_result(self):
        DividendSnapshot.objects.all().delete()
        cache.clear()

        snapshot = _get_dividend_widget_snapshot()
        self.assertIsNone(snapshot)
        self.assertEqual(
            cache.get(DIVIDEND_WIDGET_KEY), DIVIDEND_WIDGET_EMPTY_CACHE_VALUE
        )

        with self.assertNumQueries(0):
            self.assertIsNone(_get_dividend_widget_snapshot())

    def test_get_has_pending_messages_or_comments_only_unread_message(self):
        request = self.factory.get("/")
        request.user = self.staff_user

        with self.assertNumQueries(1):
            has_pending = _get_has_pending_messages_or_comments(request)

        self.assertTrue(has_pending)

    def test_get_has_pending_messages_or_comments_only_pending_comment(self):
        request = self.factory.get("/")
        request.user = self.staff_user
        self.contact_msg.is_read = True
        self.contact_msg.save()

        Comment.objects.create(
            post=self.post1,
            author=self.normal_user,
            body="Pending comment",
            status=Comment.Status.PENDING,
        )

        with self.assertNumQueries(2):
            has_pending = _get_has_pending_messages_or_comments(request)

        self.assertTrue(has_pending)

    def test_get_has_pending_messages_or_comments_both_exist(self):
        request = self.factory.get("/")
        request.user = self.staff_user

        Comment.objects.create(
            post=self.post1,
            author=self.normal_user,
            body="Pending comment",
            status=Comment.Status.PENDING,
        )

        has_pending = _get_has_pending_messages_or_comments(request)

        self.assertTrue(has_pending)

    def test_get_has_pending_messages_or_comments_none_exist(self):
        request = self.factory.get("/")
        request.user = self.staff_user
        self.contact_msg.is_read = True
        self.contact_msg.save()

        with self.assertNumQueries(2):
            has_pending = _get_has_pending_messages_or_comments(request)

        self.assertFalse(has_pending)

    def test_get_has_pending_messages_or_comments_caching(self):
        request = self.factory.get("/")
        request.user = self.staff_user

        # 1. First call - populates cache (contact message exists)
        has_pending1 = _get_has_pending_messages_or_comments(request)
        self.assertTrue(has_pending1)

        cache_key = STAFF_PENDING_NOTIFICATIONS_KEY.format(user_id=self.staff_user.id)
        self.assertTrue(cache.get(cache_key))

        # 2. Update DB - mark as read
        self.contact_msg.is_read = True
        self.contact_msg.save()

        # 3. Second call - should still return True from cache
        has_pending2 = _get_has_pending_messages_or_comments(request)
        self.assertTrue(has_pending2)

        # 4. Clear cache and call again
        cache.clear()
        has_pending3 = _get_has_pending_messages_or_comments(request)
        self.assertFalse(has_pending3)

    def test_get_has_pending_messages_or_comments_normal_user(self):
        request = self.factory.get("/")
        request.user = self.normal_user

        has_pending = _get_has_pending_messages_or_comments(request)

        self.assertFalse(has_pending)

    def test_categories_tags_context(self):
        request = self.factory.get("/")
        request.user = self.normal_user

        context = categories_tags_context(request)

        self.assertIn("nav_categories", context)
        self.assertIn("nav_tags", context)
        self.assertIn("nav_archives", context)
        self.assertIn("nav_recent_posts", context)
        self.assertIn("nav_popular_posts", context)
        self.assertIn("nav_portfolio_posts", context)
        self.assertIn("goal_widget_snapshot", context)
        self.assertIn("dividend_widget_snapshot", context)
        self.assertIn("has_pending_messages_or_comments", context)

    @override_settings(GOOGLE_ANALYTICS_ID="UA-12345678-1")
    def test_google_analytics_context(self):
        request = self.factory.get("/")
        context = google_analytics_context(request)
        self.assertEqual(context["GOOGLE_ANALYTICS_ID"], "UA-12345678-1")

    @override_settings(SITE_NAME="Test Site", SITE_BASE_URL="http://test.com/")
    def test_site_metadata_context(self):
        request = self.factory.get("/")
        context = site_metadata_context(request)
        self.assertEqual(context["site_name"], "Test Site")
        self.assertEqual(context["site_base_url"], "http://test.com")

    def test_site_settings_context(self):
        request = self.factory.get("/")
        context = site_settings_context(request)
        self.assertFalse(context["site_settings"].is_comments_enabled)

    def test_sidebar_widgets_context(self):
        request = self.factory.get("/")
        context = sidebar_widgets_context(request)
        self.assertEqual(len(context["sidebar_widgets"]), 1)
        self.assertEqual(
            context["sidebar_widgets"][0]["template_name"], "includes/sidebar_1.html"
        )


class CalculateTagCloudSizesTests(TestCase):
    def test_empty_list_or_none(self):
        nav_tags = []
        _calculate_tag_cloud_sizes(nav_tags)
        self.assertEqual(nav_tags, [])

        _calculate_tag_cloud_sizes(None)

    def test_same_post_counts(self):
        nav_tags = [
            {"post_count": 5, "slug": "tag1"},
            {"post_count": 5, "slug": "tag2"},
        ]
        _calculate_tag_cloud_sizes(nav_tags)
        for t in nav_tags:
            self.assertEqual(t["cloud_size"], 1.0)
            self.assertEqual(t["cloud_size_class"], "tag-cloud__item--size-2")
            self.assertIn("color_class", t)

    def test_different_post_counts(self):
        nav_tags = [
            {"post_count": 1, "slug": "min-tag"},  # min
            {"post_count": 3, "slug": "mid-tag"},  # (3-1)/10 = 0.2 norm
            {"post_count": 11, "slug": "max-tag"},  # max, (11-1)/10 = 1.0 norm
        ]
        _calculate_tag_cloud_sizes(nav_tags)

        # min tag: normalized = 0.0 -> cloud_size = 0.85, size_level = min(6, max(1, int(round(0.0 * 5.0)) + 1)) = 1
        self.assertEqual(nav_tags[0]["cloud_size"], 0.85)
        self.assertEqual(nav_tags[0]["cloud_size_class"], "tag-cloud__item--size-1")

        # mid tag: normalized = 0.2 -> cloud_size = round(0.85 + 0.2 * 0.75, 2) = 1.0, size_level = min(6, max(1, int(round(0.2 * 5.0)) + 1)) = min(6, max(1, 1 + 1)) = 2
        self.assertEqual(nav_tags[1]["cloud_size"], 1.0)
        self.assertEqual(nav_tags[1]["cloud_size_class"], "tag-cloud__item--size-2")

        # max tag: normalized = 1.0 -> cloud_size = round(0.85 + 1.0 * 0.75, 2) = 1.6, size_level = min(6, max(1, int(round(1.0 * 5.0)) + 1)) = min(6, max(1, 5 + 1)) = 6
        self.assertEqual(nav_tags[2]["cloud_size"], 1.6)
        self.assertEqual(nav_tags[2]["cloud_size_class"], "tag-cloud__item--size-6")


class StampedeLockTests(SimpleTestCase):
    """
    Bulgu 1 (Sidebar/Nav cache stampede) regresyon testleri.

    Cache stampede korumasının (atomik `cache.add` kilidi + TTL jitter)
    eşzamanlı recompute'u engellediğini doğrular.
    """

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_cache_timeout_with_jitter_range(self):
        for _ in range(50):
            timeout = _cache_timeout_with_jitter()
            self.assertGreaterEqual(timeout, CACHE_TIMEOUT)
            self.assertLessEqual(timeout, CACHE_TIMEOUT + CACHE_TIMEOUT_JITTER)

    def test_cached_value_skips_compute(self):
        cache.set("stampede_key", ["cached"])
        compute = mock.Mock()

        result = _get_or_set_with_stampede_lock("stampede_key", None, compute)

        self.assertEqual(result, ["cached"])
        compute.assert_not_called()

    def test_cached_data_dict_skips_compute(self):
        compute = mock.Mock()

        result = _get_or_set_with_stampede_lock(
            "stampede_key", {"stampede_key": ["from_get_many"]}, compute
        )

        self.assertEqual(result, ["from_get_many"])
        compute.assert_not_called()

    def test_miss_computes_caches_and_releases_lock(self):
        compute = mock.Mock(return_value=["computed"])

        result = _get_or_set_with_stampede_lock("stampede_key", None, compute)

        self.assertEqual(result, ["computed"])
        compute.assert_called_once()
        self.assertEqual(cache.get("stampede_key"), ["computed"])
        # Kilit recompute sonrası serbest bırakılmalı.
        self.assertIsNone(cache.get("stampede_key:lock"))

    def test_waiter_returns_value_set_by_winner_without_compute(self):
        # Kazanan thread kilidi tutuyor ve değeri set etmiş durumda.
        cache.add("stampede_key:lock", 1, 10)
        cache.set("stampede_key", ["winner_value"])
        compute = mock.Mock()

        result = _get_or_set_with_stampede_lock("stampede_key", None, compute)

        self.assertEqual(result, ["winner_value"])
        compute.assert_not_called()

    @mock.patch("core.context_processors.STAMPEDE_LOCK_WAIT", 0.2)
    @mock.patch("core.context_processors.STAMPEDE_POLL_INTERVAL", 0.05)
    def test_waiter_falls_back_to_compute_when_winner_stalls(self):
        # Kazanan thread kilidi tutuyor ama değeri zamanında üretmiyor.
        cache.add("stampede_key:lock", 1, 10)
        compute = mock.Mock(return_value=["fallback"])

        result = _get_or_set_with_stampede_lock("stampede_key", None, compute)

        self.assertEqual(result, ["fallback"])
        compute.assert_called_once()
        # Kilidi biz almadığımız için silmemeliyiz (kazanan thread'e ait).
        self.assertIsNotNone(cache.get("stampede_key:lock"))
