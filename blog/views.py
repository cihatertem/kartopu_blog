from django.db.models import F
from django.shortcuts import HttpResponse, get_object_or_404, render

from .models import BlogPost


# Create your views here.
def blog_view(request):
    return HttpResponse(b"Blog Page")


def post_detail(request, slug):
    post = get_object_or_404(
        BlogPost,
        slug=slug,
        # status=BlogPost.Status.PUBLISHED,
    )

    # View count (session bazlı)
    session_key = f"viewed_post_{post.pk}"
    if not request.session.get(session_key):
        BlogPost.objects.filter(pk=post.pk).update(view_count=F("view_count") + 1)
        request.session[session_key] = True

    context = {
        "post": post,
    }
    return render(request, "blog/post_detail.html", context)
