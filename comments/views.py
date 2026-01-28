from allauth.socialaccount.models import SocialAccount
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from blog.models import BlogPost
from core.helpers import client_ip_key

from .forms import CommentForm
from .models import Comment

COMMENT_RATE_LIMIT = "10/m"
COMMENT_RATE_LIMIT_KEY = "ip"


@ratelimit(
    key=client_ip_key,
    rate=COMMENT_RATE_LIMIT,
    block=False,
    method=["POST"],
)
@login_required
@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(
        BlogPost,
        pk=post_id,
        status=BlogPost.Status.PUBLISHED,
    )

    if getattr(request, "limited", False):
        messages.error(
            request,
            "Çok fazla istek gönderdiniz. Lütfen bir dakika sonra tekrar deneyin.",
        )
        return redirect(post.get_absolute_url())

    form = CommentForm(request.POST)
    if not form.is_valid():
        if form.errors.get("body"):
            messages.error(
                request,
                form.errors.get("body", ""),  # pyright: ignore[reportArgumentType]
            )
        return redirect(post.get_absolute_url())

    social_account = SocialAccount.objects.filter(user=request.user).first()
    if social_account is None:
        messages.error(
            request,
            "Yorum yapabilmek için sosyal hesap ile giriş yapmalısınız.",
        )
        return redirect(post.get_absolute_url())

    status = Comment.Status.PENDING
    if form.cleaned_data.get("website"):
        status = Comment.Status.SPAM

    parent = None
    parent_id = form.cleaned_data.get("parent_id")
    if parent_id:
        parent = Comment.objects.filter(
            id=parent_id,
            post=post,
            status=Comment.Status.APPROVED,
        ).first()
        if parent is None:
            messages.error(
                request,
                "Yanıtlamak istediğiniz yorum bulunamadı.",
            )
            return redirect(post.get_absolute_url())

    comment = form.save(commit=False)
    comment.post = post
    comment.author = request.user
    comment.status = status
    comment.parent = parent
    comment.ip_address = request.META.get("REMOTE_ADDR")
    comment.user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
    comment.social_provider = social_account.provider
    comment.save()

    messages.success(
        request,
        "Yorumunuz alınmıştır ve moderasyon sonrası yayınlanacaktır.",
    )
    return redirect(post.get_absolute_url())
