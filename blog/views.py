from datetime import date

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.aggregates import StringAgg
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, F, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.formats import date_format
from django.views.decorators.http import require_POST

from comments.forms import CommentForm
from comments.models import MAX_COMMENT_LENGTH, Comment
from core import helpers
from core.tag_colors import build_tag_items
from portfolio.models import (
    CashFlowComparison,
    CashFlowSnapshot,
    DividendComparison,
    DividendSnapshot,
    PortfolioComparison,
    PortfolioSnapshot,
)

from .models import BlogPost, BlogPostReaction, Category, Tag

COMMENT_PAGE_SIZE = 10
POST_PAGE_SIZE = 10

REACTION_OPTIONS = [
    {"key": BlogPostReaction.Reaction.ALKIS.value, "label": "Alkış", "emoji": "👏"},
    {"key": BlogPostReaction.Reaction.ILHAM.value, "label": "İlham", "emoji": "🌱"},
    {"key": BlogPostReaction.Reaction.MERAK.value, "label": "Merak", "emoji": "🧐"},
    {"key": BlogPostReaction.Reaction.KALP.value, "label": "Sevgi", "emoji": "❤️"},
    {"key": BlogPostReaction.Reaction.ROKET.value, "label": "Gaz", "emoji": "🚀"},
    {
        "key": BlogPostReaction.Reaction.SURPRIZ.value,
        "label": "Şaşkın",
        "emoji": "😮",
    },
    {"key": BlogPostReaction.Reaction.MUTLU.value, "label": "Mutlu", "emoji": "😄"},
    {
        "key": BlogPostReaction.Reaction.DUYGULANDIM.value,
        "label": "Duygulandım",
        "emoji": "🥲",
    },
    {
        "key": BlogPostReaction.Reaction.DUSUNCELI.value,
        "label": "Düşünceli",
        "emoji": "😐",
    },
    {
        "key": BlogPostReaction.Reaction.HUZUNLU.value,
        "label": "Hüzünlü",
        "emoji": "😢",
    },
    {
        "key": BlogPostReaction.Reaction.RAHATSIZ.value,
        "label": "Rahatsız",
        "emoji": "🤢",
    },
    {"key": BlogPostReaction.Reaction.KORKU.value, "label": "Endişe", "emoji": "😨"},
]

SOCIAL_AVATAR_KEYS = (
    "picture",
    "pictureUrl",
    "avatar_url",
    "profile_image_url_https",
    "profile_image_url",
)


def _normalize_avatar_url(url):
    if not isinstance(url, str):
        return ""

    if url.startswith("http://pbs.twimg.com"):
        return url.replace("http://", "https://", 1)

    if url.startswith("http"):
        return url

    return ""


def _extract_social_avatar_url(extra_data):
    if not isinstance(extra_data, dict):
        return ""

    for key in SOCIAL_AVATAR_KEYS:
        value = _normalize_avatar_url(extra_data.get(key))
        if value:
            return value

    image_data = extra_data.get("image")
    if isinstance(image_data, dict):
        for key in ("url", "href"):
            value = _normalize_avatar_url(image_data.get(key))
            if value:
                return value

    return ""


def _build_reaction_context(request, post):
    counts = (
        BlogPostReaction.objects.filter(post=post)
        .values("reaction")
        .annotate(total=Count("id"))
    )
    reaction_counts = {item["reaction"]: item["total"] for item in counts}

    user_reaction = ""
    if request.user.is_authenticated:
        user_reaction = (
            BlogPostReaction.objects.filter(post=post, user=request.user)
            .values_list("reaction", flat=True)
            .first()
            or ""
        )

    reaction_options = [
        {
            **reaction,
            "count": reaction_counts.get(reaction["key"], 0),
        }
        for reaction in REACTION_OPTIONS
    ]

    user_reaction_label = ""
    if user_reaction:
        matched = next(
            (
                option["label"]
                for option in reaction_options
                if option["key"] == user_reaction
            ),
            "",
        )
        user_reaction_label = matched

    return {
        "reaction_options": reaction_options,
        "user_reaction": user_reaction,
        "user_reaction_label": user_reaction_label,
    }


def _build_comment_context(request, post):
    approved_comments = list(
        post.comments.filter(  # pyright: ignore[reportAttributeAccessIssue]
            status=Comment.Status.APPROVED
        )
        .select_related("author")
        .order_by("-created_at")
    )
    author_ids = {comment.author_id for comment in approved_comments}
    social_avatar_map = {}
    if author_ids:
        social_accounts = SocialAccount.objects.filter(user_id__in=author_ids)
        for account in social_accounts:
            avatar_url = _normalize_avatar_url(account.get_avatar_url())
            if not avatar_url:
                avatar_url = _extract_social_avatar_url(account.extra_data or {})
            if avatar_url and account.user_id not in social_avatar_map:  # pyright: ignore[reportAttributeAccessIssue]
                social_avatar_map[account.user_id] = avatar_url  # pyright: ignore[reportAttributeAccessIssue]

    replies_by_parent = {}
    for comment in approved_comments:
        replies_by_parent.setdefault(comment.parent_id, []).append(comment)
    for comment in approved_comments:
        comment.nested_replies = replies_by_parent.get(comment.id, [])  # type: ignore[attr-defined]
        comment.social_avatar_url = social_avatar_map.get(comment.author_id, "")  # type: ignore[attr-defined]
    top_level_comments = replies_by_parent.get(None, [])
    comment_form = CommentForm()
    has_social_account = (
        request.user.is_authenticated
        and SocialAccount.objects.filter(user=request.user).exists()
    )
    paginator = Paginator(top_level_comments, COMMENT_PAGE_SIZE)
    comment_page_obj = paginator.get_page(request.GET.get("comments_page"))

    return {
        "comment_form": comment_form,
        "comment_page_obj": comment_page_obj,
        "comment_total": len(approved_comments),
        "has_social_account": has_social_account,
    }


def archive_index(request):
    qs = BlogPost.objects.filter(
        status=BlogPost.Status.PUBLISHED, published_at__isnull=False
    )

    archives = (
        qs.annotate(
            year=F("published_at__year"),
            month=F("published_at__month"),
        )
        .values("year", "month")
        .annotate(count=Count("id"))
        .order_by("-year", "-month")
    )

    return render(
        request,
        "blog/archive_index.html",
        {
            "archives": archives,
            "active_nav": "blog",
        },
    )


def search_results(request):
    q = (request.GET.get("q") or "").strip()
    tokens = helpers.normalize_search_query(q)

    base_qs = (
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .prefetch_related("tags")
    )

    if not q or not tokens:
        qs = base_qs.none()
    else:
        base_qs = base_qs.annotate(
            tag_names=StringAgg(
                "tags__name",
                delimiter=" ",
                distinct=True,
            )
        )

        vector = (
            SearchVector("tag_names", weight="A", config="turkish")
            + SearchVector("title", weight="B", config="turkish")
            + SearchVector("excerpt", weight="C", config="turkish")
            + SearchVector("content", weight="D", config="turkish")
        )

        query = SearchQuery(
            " | ".join(tokens),
            search_type="raw",
            config="turkish",
        )

        qs = (
            base_qs.annotate(rank=SearchRank(vector, query))
            .filter(rank__isnull=False, rank__gt=0)
            .order_by("-rank", "-published_at")
        )

    paginator = Paginator(qs, POST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    breadcrumbs = [
        {"label": "Blog", "url": reverse("blog:post_list")},
        {"label": "Arama", "url": None},
    ]

    return render(
        request,
        "blog/search_results.html",
        {
            "page_obj": page_obj,
            "q": q,
            "active_nav": "blog",
            "breadcrumbs": breadcrumbs,
            "active_archive_key": "",
        },
    )


def post_list(request):
    qs = (
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .prefetch_related("tags")
        .order_by("-published_at", "-created_at")
    )

    paginator = Paginator(qs, POST_PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "blog/post_list.html",
        {
            "page_obj": page_obj,
            "active_category_slug": "",
            "active_nav": "blog",
            "active_tag_slug": "",
            "active_archive_key": "",
        },
    )


def post_detail(request, slug: str):
    post = get_object_or_404(
        BlogPost.objects.select_related(
            "category",
            "author",
        ).prefetch_related(
            "tags",
            "images",
            Prefetch(
                "portfolio_snapshots",
                queryset=PortfolioSnapshot.objects.select_related("portfolio").order_by(
                    "snapshot_date"
                ),
            ),
            Prefetch(
                "portfolio_comparisons",
                queryset=PortfolioComparison.objects.select_related(
                    "base_snapshot",
                    "compare_snapshot",
                    "base_snapshot__portfolio",
                    "compare_snapshot__portfolio",
                ).order_by("created_at"),
            ),
            Prefetch(
                "cashflow_snapshots",
                queryset=CashFlowSnapshot.objects.select_related("cashflow").order_by(
                    "snapshot_date"
                ),
            ),
            Prefetch(
                "cashflow_comparisons",
                queryset=CashFlowComparison.objects.select_related(
                    "base_snapshot",
                    "compare_snapshot",
                    "base_snapshot__cashflow",
                    "compare_snapshot__cashflow",
                ).order_by("created_at"),
            ),
            Prefetch(
                "dividend_snapshots",
                queryset=DividendSnapshot.objects.order_by("-year", "-created_at"),
            ),
            Prefetch(
                "dividend_comparisons",
                queryset=DividendComparison.objects.select_related(
                    "base_snapshot",
                    "compare_snapshot",
                ).order_by("created_at"),
            ),
        ),
        slug=slug,
        status=BlogPost.Status.PUBLISHED,
    )

    session_key = f"viewed_post_{post.pk}"
    if not request.session.get(session_key):
        BlogPost.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        request.session[session_key] = True

        post.view_count += 1

    breadcrumbs: list[dict[str, str | None]] = [
        {
            "label": "Blog",
            "url": reverse("blog:post_list"),
        }
    ]

    if post.category:
        breadcrumbs.append(
            {
                "label": post.category.name,
                "url": post.category.get_absolute_url(),
            }
        )

    breadcrumbs.append(
        {
            "label": post.title,
            "url": None,
        }
    )

    comment_context = _build_comment_context(request, post)
    has_social_account = comment_context["has_social_account"]

    reaction_context = _build_reaction_context(request, post)
    can_react = request.user.is_authenticated and has_social_account

    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "post_tag_items": build_tag_items(post.tags.all()),
            "active_nav": "blog",
            "active_category_slug": post.category.slug if post.category else "",
            "active_tag_slug": "",
            "active_archive_key": (
                f"{post.published_at.year:04d}-{post.published_at.month:02d}"
                if post.published_at
                else ""
            ),
            "breadcrumbs": breadcrumbs,
            "is_preview": False,
            "comment_form": comment_context["comment_form"],
            "can_comment": request.user.is_authenticated and has_social_account,
            "requires_social_auth": request.user.is_authenticated
            and not has_social_account,
            "MAX_COMMENT_LENGTH": MAX_COMMENT_LENGTH,
            "comment_page_obj": comment_context["comment_page_obj"],
            "comment_total": comment_context["comment_total"],
            "can_react": can_react,
            **reaction_context,
        },
    )


@login_required
def post_preview(request, slug: str):
    post = get_object_or_404(
        BlogPost.objects.select_related(
            "category",
            "author",
        ).prefetch_related(
            "tags",
            "images",
            Prefetch(
                "portfolio_snapshots",
                queryset=PortfolioSnapshot.objects.select_related("portfolio").order_by(
                    "snapshot_date"
                ),
            ),
            Prefetch(
                "portfolio_comparisons",
                queryset=PortfolioComparison.objects.select_related(
                    "base_snapshot",
                    "compare_snapshot",
                    "base_snapshot__portfolio",
                    "compare_snapshot__portfolio",
                ).order_by("created_at"),
            ),
            Prefetch(
                "cashflow_snapshots",
                queryset=CashFlowSnapshot.objects.select_related("cashflow").order_by(
                    "snapshot_date"
                ),
            ),
            Prefetch(
                "cashflow_comparisons",
                queryset=CashFlowComparison.objects.select_related(
                    "base_snapshot",
                    "compare_snapshot",
                    "base_snapshot__cashflow",
                    "compare_snapshot__cashflow",
                ).order_by("created_at"),
            ),
            Prefetch(
                "dividend_snapshots",
                queryset=DividendSnapshot.objects.order_by("-year", "-created_at"),
            ),
            Prefetch(
                "dividend_comparisons",
                queryset=DividendComparison.objects.select_related(
                    "base_snapshot",
                    "compare_snapshot",
                ).order_by("created_at"),
            ),
        ),
        slug=slug,
    )

    if not request.user.is_staff and request.user != post.author:
        raise PermissionDenied

    breadcrumbs: list[dict[str, str | None]] = [
        {
            "label": "Blog",
            "url": reverse("blog:post_list"),
        },
        {"label": "Önizleme", "url": None},
        {
            "label": post.title,
            "url": None,
        },
    ]

    comment_context = _build_comment_context(request, post)
    has_social_account = comment_context["has_social_account"]

    reaction_context = _build_reaction_context(request, post)
    can_react = has_social_account

    return render(
        request,
        "blog/post_detail.html",
        {
            "post": post,
            "post_tag_items": build_tag_items(post.tags.all()),
            "active_nav": "blog",
            "active_category_slug": post.category.slug if post.category else "",
            "active_tag_slug": "",
            "active_archive_key": (
                f"{post.published_at.year:04d}-{post.published_at.month:02d}"
                if post.published_at
                else ""
            ),
            "breadcrumbs": breadcrumbs,
            "is_preview": True,
            "comment_form": comment_context["comment_form"],
            "can_comment": has_social_account,
            "requires_social_auth": not has_social_account,
            "comment_page_obj": comment_context["comment_page_obj"],
            "comment_total": comment_context["comment_total"],
            "can_react": can_react,
            **reaction_context,
        },
    )


@require_POST
@login_required
def post_reaction(request, slug: str):
    post = get_object_or_404(
        BlogPost.objects.filter(status=BlogPost.Status.PUBLISHED),
        slug=slug,
    )

    has_social_account = SocialAccount.objects.filter(user=request.user).exists()
    if not has_social_account:
        return JsonResponse(
            {"detail": "Sosyal hesap gereklidir."},
            status=403,
        )

    reaction = (request.POST.get("reaction") or "").strip()
    valid_reactions = {choice.value for choice in BlogPostReaction.Reaction}
    if reaction and reaction not in valid_reactions:
        return JsonResponse({"detail": "Geçersiz tepki."}, status=400)

    existing = BlogPostReaction.objects.filter(post=post, user=request.user).first()
    selected = ""

    if reaction:
        if existing:
            if existing.reaction == reaction:
                existing.delete()
            else:
                existing.reaction = reaction
                existing.save(update_fields=["reaction", "updated_at"])
                selected = reaction
        else:
            BlogPostReaction.objects.create(
                post=post,
                user=request.user,
                reaction=reaction,
            )
            selected = reaction
    else:
        if existing:
            existing.delete()

    counts = (
        BlogPostReaction.objects.filter(post=post)
        .values("reaction")
        .annotate(total=Count("id"))
    )
    counts_payload = {item["reaction"]: item["total"] for item in counts}

    return JsonResponse({"selected": selected, "counts": counts_payload})


def archive_detail(request, year: int, month: int):
    archive_month = date(year, month, 1)
    archive_month = date_format(archive_month, "F Y")
    qs = (
        BlogPost.objects.filter(
            status=BlogPost.Status.PUBLISHED,
            published_at__year=year,
            published_at__month=month,
        )
        .select_related("author", "category")
        .prefetch_related("tags")
        .order_by("-published_at", "-created_at")
    )

    paginator = Paginator(qs, POST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    breadcrumbs = [
        {
            "label": "Blog",
            "url": reverse("blog:post_list"),
        },
        {
            "label": archive_month,
            "url": None,
        },
    ]

    return render(
        request,
        "blog/archive_detail.html",
        {
            "page_obj": page_obj,
            "archive_month": archive_month,
            "active_nav": "blog",
            "active_category_slug": "",
            "active_tag_slug": "",
            "active_archive_key": f"{year:04d}-{month:02d}",
            "breadcrumbs": breadcrumbs,
        },
    )


def category_detail(request, slug: str):
    category = get_object_or_404(Category, slug=slug)

    qs = (
        BlogPost.objects.filter(category=category, status=BlogPost.Status.PUBLISHED)
        .select_related("author", "category")
        .prefetch_related("tags")
        .order_by("-published_at", "-created_at")
    )

    paginator = Paginator(qs, POST_PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    breadcrumbs = [
        {
            "label": "Blog",
            "url": reverse("blog:post_list"),
        },
        {
            "label": category.name,
            "url": None,
        },
    ]

    return render(
        request,
        "blog/category_detail.html",
        {
            "category": category,
            "page_obj": page_obj,
            "active_category_slug": category.slug,
            "active_tag_slug": "",
            "active_nav": "blog",
            "active_archive_key": "",
            "breadcrumbs": breadcrumbs,
        },
    )


def tag_detail(request, slug: str):
    tag = get_object_or_404(Tag, slug=slug)

    qs = (
        BlogPost.objects.filter(
            tags=tag,
            status=BlogPost.Status.PUBLISHED,
        )
        .select_related("author", "category")
        .prefetch_related("tags")
        .order_by("-published_at", "-created_at")
    )

    paginator = Paginator(qs, POST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    breadcrumbs = [
        {
            "label": "Blog",
            "url": reverse("blog:post_list"),
        },
        {
            "label": f"#{tag.name}",
            "url": None,
        },
    ]

    return render(
        request,
        "blog/tag_detail.html",
        {
            "tag": tag,
            "page_obj": page_obj,
            "active_nav": "blog",
            "active_category_slug": "",
            "active_tag_slug": tag.slug,
            "active_archive_key": "",
            "breadcrumbs": breadcrumbs,
        },
    )
