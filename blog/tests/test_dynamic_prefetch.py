from django.test import TestCase
from blog.models import BlogPost, Category
from blog.views import _get_post_for_detail
from django.contrib.auth import get_user_model
from portfolio.models import Portfolio, PortfolioSnapshot
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

class DynamicPrefetchTest(TestCase):
    def setUp(self):
        # Custom User model uses email as identifier and does not have username
        self.user = User.objects.create_user(
            email="test@example.com", 
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.category = Category.objects.create(name="Test Category")
        
    def test_content_dependencies_detection(self):
        """Test if content dependencies are detected correctly on save."""
        content = "Bu bir test yazısıdır. {{ portfolio_summary:1 }} ve {{ dividend_charts:1 }} içerir."
        post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Test Post",
            content=content,
            status=BlogPost.Status.PUBLISHED
        )
        
        # Dependencies should include 'portfolio' and 'dividend'
        self.assertIn("portfolio", post.content_dependencies)
        self.assertIn("dividend", post.content_dependencies)
        self.assertNotIn("cashflow", post.content_dependencies)

    def test_dynamic_prefetch_trigger(self):
        """Test if dynamic prefetch is triggered in the view helper."""
        # Create dependencies
        portfolio = Portfolio.objects.create(
            name="Test Portfolio", 
            owner=self.user,
            target_value=Decimal("10000.00")
        )
        snapshot = PortfolioSnapshot.objects.create(
            portfolio=portfolio, 
            total_value=Decimal("1000.00"),
            total_cost=Decimal("800.00"),
            target_value=Decimal("1200.00"),
            total_return_pct=Decimal("25.0"),
            period=PortfolioSnapshot.Period.MONTHLY,
            snapshot_date=timezone.now().date()
        )
        
        content = "{{ portfolio_summary:1 }}"
        post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Portfolio Post",
            content=content,
            status=BlogPost.Status.PUBLISHED
        )
        post.portfolio_snapshots.add(snapshot)
        
        # Reload post via helper
        fetched_post = _get_post_for_detail(post.slug, include_unpublished=False)
        
        # Check if portfolio_snapshots are prefetched
        self.assertTrue(hasattr(fetched_post, "_prefetched_objects_cache"))
        self.assertIn("portfolio_snapshots", fetched_post._prefetched_objects_cache)
        
    def test_no_unnecessary_prefetch(self):
        """Test that data is NOT prefetched if not in content."""
        content = "Sadece yazı var, marker yok."
        post = BlogPost.objects.create(
            author=self.user,
            category=self.category,
            title="Simple Post",
            content=content,
            status=BlogPost.Status.PUBLISHED
        )
        
        fetched_post = _get_post_for_detail(post.slug, include_unpublished=False)
        
        # If prefetched_objects_cache exists (it might due to other prefetches like tags, images), 
        # portfolio_snapshots should NOT be in it.
        if hasattr(fetched_post, "_prefetched_objects_cache"):
            self.assertNotIn("portfolio_snapshots", fetched_post._prefetched_objects_cache)
