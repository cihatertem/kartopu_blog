from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import resolve
from django.utils import timezone

from blog.cache_keys import (
    NAV_CATEGORIES_KEY,
    NAV_POPULAR_POSTS_KEY,
    NAV_PORTFOLIO_POSTS_KEY,
    NAV_RECENT_POSTS_KEY,
    NAV_TAGS_KEY,
)
from blog.models import BlogPost, Category, Tag
from comments.models import Comment
from core.context_processors import (
    _get_goal_widget_snapshot,
    _get_has_pending_messages_or_comments,
    _get_nav_archives,
    _get_nav_categories,
    _get_nav_popular_posts,
    _get_nav_portfolio_posts,
    _get_nav_recent_posts,
    _get_nav_tags,
    breadcrumbs_context,
    categories_tags_context,
    google_analytics_context,
    sidebar_widgets_context,
    site_metadata_context,
    site_settings_context,
)
from core.models import ContactMessage, SidebarWidget, SiteSettings
from portfolio.models import Portfolio, PortfolioSnapshot

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
        self.assertEqual(cats[0].name, "Cat 1")
        self.assertEqual(cache.get(NAV_CATEGORIES_KEY), cats)

    def test_get_nav_tags(self):
        tags = _get_nav_tags()

        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["name"], "Tag 1")
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
        self.assertEqual(posts[0].slug, "portfolio-post")
        self.assertEqual(cache.get(NAV_RECENT_POSTS_KEY), posts)

    def test_get_nav_popular_posts(self):
        posts = _get_nav_popular_posts()

        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0].slug, "post-1")
        self.assertEqual(cache.get(NAV_POPULAR_POSTS_KEY), posts)

    def test_get_nav_portfolio_posts(self):
        posts = _get_nav_portfolio_posts()

        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].slug, "portfolio-post")
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

    def test_get_has_pending_messages_or_comments_only_unread_message(self):
        request = self.factory.get("/")
        request.user = self.staff_user

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

        has_pending = _get_has_pending_messages_or_comments(request)

        self.assertFalse(has_pending)

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
        self.assertEqual(context["sidebar_widgets"][0].title, "Widget 1")
