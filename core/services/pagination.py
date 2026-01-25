from django.core.paginator import Paginator


def get_page_obj(request, items, *, per_page: int, page_param: str = "page"):
    paginator = Paginator(items, per_page)
    return paginator.get_page(request.GET.get(page_param))
