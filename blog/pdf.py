import io
import os
import re
from typing import Any

from django.db.models import QuerySet
from django.utils.html import strip_tags
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from blog.models import BlogPost, BlogPostImage
from blog.services import (
    detect_content_markers,
    get_content_prefetches_for_markers,
)

# Custom TTF Font Registration for Full Turkish Character Support
FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
FONT_NAME_ITALIC = "Helvetica-Oblique"


def _setup_fonts() -> tuple[str, str, str]:
    normal_candidates = [
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    italic_candidates = [
        "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ]

    normal_path = next((p for p in normal_candidates if os.path.exists(p)), None)
    bold_path = next((p for p in bold_candidates if os.path.exists(p)), None)
    italic_path = next((p for p in italic_candidates if os.path.exists(p)), None)

    if normal_path and bold_path:
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", normal_path))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))
            if italic_path:
                pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", italic_path))
                return "DejaVuSans", "DejaVuSans-Bold", "DejaVuSans-Oblique"
            return "DejaVuSans", "DejaVuSans-Bold", "DejaVuSans"
        except Exception:
            pass

    return FONT_NAME, FONT_NAME_BOLD, FONT_NAME_ITALIC


FONT_REG, FONT_BOLD, FONT_ITAL = _setup_fonts()


def _get_styles():
    base_styles = getSampleStyleSheet()
    styles = {
        "DocTitle": ParagraphStyle(
            "DocTitle",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1A202C"),
            alignment=1,  # Center
            spaceAfter=15,
        ),
        "PostTitle": ParagraphStyle(
            "PostTitle",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=16,
            leading=20,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "Meta": ParagraphStyle(
            "Meta",
            parent=base_styles["Normal"],
            fontName=FONT_REG,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#718096"),
            spaceAfter=4,
        ),
        "Tags": ParagraphStyle(
            "Tags",
            parent=base_styles["Normal"],
            fontName=FONT_ITAL,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#319795"),
            spaceAfter=10,
        ),
        "Excerpt": ParagraphStyle(
            "Excerpt",
            parent=base_styles["Normal"],
            fontName=FONT_ITAL,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#4A5568"),
            backColor=colors.HexColor("#EDF2F7"),
            borderColor=colors.HexColor("#CBD5E0"),
            borderWidth=1,
            borderPadding=6,
            spaceAfter=10,
        ),
        "H1": ParagraphStyle(
            "PostH1",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=10,
            spaceAfter=4,
        ),
        "H2": ParagraphStyle(
            "PostH2",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=8,
            spaceAfter=3,
        ),
        "Body": ParagraphStyle(
            "PostBody",
            parent=base_styles["Normal"],
            fontName=FONT_REG,
            fontSize=9.5,
            leading=13.5,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=6,
        ),
        "TableHead": ParagraphStyle(
            "TableHead",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
            alignment=1,
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=base_styles["Normal"],
            fontName=FONT_REG,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#2D3748"),
        ),
    }
    return styles


def _load_reportlab_image(image_field, max_width=450, max_height=250) -> RLImage | None:
    if not image_field:
        return None
    try:
        if hasattr(image_field, "path") and os.path.exists(image_field.path):
            img_src = image_field.path
        else:
            img_src = io.BytesIO(image_field.read())

        with PILImage.open(img_src) as pil_img:
            orig_w, orig_h = pil_img.size
            if orig_w == 0 or orig_h == 0:
                return None

            # Calculate proportional scale
            ratio = min(max_width / float(orig_w), max_height / float(orig_h), 1.0)
            target_w = orig_w * ratio
            target_h = orig_h * ratio

            # Convert to RGB buffer if necessary
            buf = io.BytesIO()
            rgb_img = pil_img.convert("RGB")
            rgb_img.save(buf, format="JPEG", quality=85)
            buf.seek(0)

            return RLImage(buf, width=target_w, height=target_h)
    except Exception:
        return None


def _format_currency_val(val: Any) -> str:
    if val is None:
        return "—"
    try:
        num = float(val)
        return f"{num:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
    except (ValueError, TypeError):
        return str(val)


def _render_snapshot_summary_table(snapshots, title_prefix: str, styles) -> Table | None:
    if not snapshots:
        return None

    data = [
        [
            Paragraph(title_prefix, styles["TableHead"]),
            Paragraph("Tarih", styles["TableHead"]),
            Paragraph("Toplam Değer", styles["TableHead"]),
            Paragraph("Getiri (%)", styles["TableHead"]),
        ]
    ]

    for s in snapshots:
        name = getattr(
            getattr(s, "portfolio", None) or getattr(s, "cashflow", None),
            "name",
            title_prefix,
        )
        date_str = str(getattr(s, "snapshot_date", "—"))
        total_val = getattr(s, "total_value", None) or getattr(s, "total_amount", None)
        return_pct = getattr(s, "total_return_pct", None) or getattr(
            s, "savings_rate", None
        )

        data.append(
            [
                Paragraph(str(name), styles["TableCell"]),
                Paragraph(date_str, styles["TableCell"]),
                Paragraph(_format_currency_val(total_val), styles["TableCell"]),
                Paragraph(
                    f"%{float(return_pct):.2f}" if return_pct is not None else "—",
                    styles["TableCell"],
                ),
            ]
        )

    table = Table(data, colWidths=[150, 90, 110, 100])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.HexColor("#F7FAFC"), colors.white],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
            ]
        )
    )
    return table


def _parse_content_to_flowables(post: BlogPost, styles) -> list:
    flowables = []
    content = post.content or ""
    lines = content.splitlines()

    image_pattern = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")
    marker_pattern = re.compile(
        r"\{\{\s*(?P<tag>[a-zA-Z0-9_]+)(?::(?P<arg>[^\s\}]+))?\s*\}\}"
    )

    post_images = list(post.images.all())
    used_images_set = set()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check for headings
        if stripped.startswith("# "):
            heading_text = stripped[2:].strip()
            flowables.append(Paragraph(heading_text, styles["H1"]))
            continue
        elif stripped.startswith("## "):
            heading_text = stripped[3:].strip()
            flowables.append(Paragraph(heading_text, styles["H1"]))
            continue
        elif stripped.startswith("### "):
            heading_text = stripped[4:].strip()
            flowables.append(Paragraph(heading_text, styles["H2"]))
            continue

        # Check for {{ image:N }}
        img_match = image_pattern.search(stripped)
        if img_match:
            idx = int(img_match.group(1)) - 1
            if 0 <= idx < len(post_images):
                blog_img = post_images[idx]
                used_images_set.add(blog_img.pk)
                rl_img = _load_reportlab_image(blog_img.image)
                if rl_img:
                    flowables.append(Spacer(1, 4))
                    flowables.append(rl_img)
                    if blog_img.caption:
                        flowables.append(
                            Paragraph(f"<i>{blog_img.caption}</i>", styles["Meta"])
                        )
                    flowables.append(Spacer(1, 4))
            continue

        # Check for financial chart/summary markers
        marker_match = marker_pattern.search(stripped)
        if marker_match:
            tag = marker_match.group("tag")
            if "portfolio" in tag:
                snapshots = list(
                    getattr(post, "portfolio_snapshots", None).all()
                    if hasattr(post, "portfolio_snapshots")
                    else []
                )
                tbl = _render_snapshot_summary_table(snapshots, "Portföy Özeti", styles)
                if tbl:
                    flowables.append(Spacer(1, 6))
                    flowables.append(tbl)
                    flowables.append(Spacer(1, 6))
            elif "cashflow" in tag:
                snapshots = list(
                    getattr(post, "cashflow_snapshots", None).all()
                    if hasattr(post, "cashflow_snapshots")
                    else []
                )
                tbl = _render_snapshot_summary_table(
                    snapshots, "Nakit Akışı Özeti", styles
                )
                if tbl:
                    flowables.append(Spacer(1, 6))
                    flowables.append(tbl)
                    flowables.append(Spacer(1, 6))
            elif "dividend" in tag:
                snapshots = list(
                    getattr(post, "dividend_snapshots", None).all()
                    if hasattr(post, "dividend_snapshots")
                    else []
                )
                tbl = _render_snapshot_summary_table(snapshots, "Temettü Özeti", styles)
                if tbl:
                    flowables.append(Spacer(1, 6))
                    flowables.append(tbl)
                    flowables.append(Spacer(1, 6))
            elif "savings" in tag:
                snapshots = list(
                    getattr(post, "salary_savings_snapshots", None).all()
                    if hasattr(post, "salary_savings_snapshots")
                    else []
                )
                tbl = _render_snapshot_summary_table(
                    snapshots, "Tasarruf Özeti", styles
                )
                if tbl:
                    flowables.append(Spacer(1, 6))
                    flowables.append(tbl)
                    flowables.append(Spacer(1, 6))
            continue

        # Normal text line
        cleaned_text = (
            stripped.replace("**", "<b>", 1).replace("**", "</b>", 1)
            if stripped.count("**") >= 2
            else stripped
        )
        flowables.append(Paragraph(cleaned_text, styles["Body"]))

    # Render any unused inline images at the bottom of the post content
    for blog_img in post_images:
        if blog_img.pk not in used_images_set:
            rl_img = _load_reportlab_image(blog_img.image)
            if rl_img:
                flowables.append(Spacer(1, 6))
                flowables.append(rl_img)
                if blog_img.caption:
                    flowables.append(
                        Paragraph(f"<i>{blog_img.caption}</i>", styles["Meta"])
                    )
                flowables.append(Spacer(1, 4))

    return flowables


def generate_published_posts_pdf(queryset: QuerySet[BlogPost]) -> bytes:
    """Generates a PDF document containing only published blog posts, complete with

    titles, subheadings, tags, photos (cover & inline), and financial summary tables.

    Returns the raw PDF byte stream.
    """
    # CRITICAL: Filter ONLY published posts
    published_posts = queryset.filter(status=BlogPost.Status.PUBLISHED).select_related(
        "author", "category"
    ).prefetch_related("tags", "images")

    # Prefetch all data markers present in post bodies efficiently
    all_markers = set()
    for post in published_posts:
        all_markers.update(detect_content_markers(post.content))
    if all_markers:
        prefetches = get_content_prefetches_for_markers(all_markers)
        published_posts = published_posts.prefetch_related(*prefetches)

    published_posts = published_posts.order_by("-published_at", "-created_at")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = _get_styles()
    story = []

    # Main Document Header
    story.append(
        Paragraph("Kartopu Blog - Yayınlanmış Yazılar Raporu", styles["DocTitle"])
    )
    story.append(
        HRFlowable(
            width="100%",
            thickness=1.5,
            color=colors.HexColor("#2B6CB0"),
            spaceAfter=15,
        )
    )

    posts_list = list(published_posts)
    num_posts = len(posts_list)

    for idx, post in enumerate(posts_list):
        # 1. Post Title (Main Header)
        story.append(Paragraph(post.title, styles["PostTitle"]))

        # 2. Metadata (Subheadings / info)
        category_name = post.category.name if post.category else "Genel"
        published_date_str = (
            post.published_at.strftime("%d.%m.%Y %H:%M")
            if post.published_at
            else "—"
        )
        author_name = post.author.get_full_name() or post.author.username
        meta_str = f"<b>Kategori:</b> {category_name} | <b>Yazar:</b> {author_name} | <b>Tarih:</b> {published_date_str}"
        story.append(Paragraph(meta_str, styles["Meta"]))

        # 3. Tags
        tags_list = list(post.tags.all())
        if tags_list:
            tag_names = ", ".join([f"#{t.name}" for t in tags_list])
            story.append(Paragraph(f"<b>Etiketler:</b> {tag_names}", styles["Tags"]))

        # 4. Cover Photo
        if post.cover_image:
            cover_rl_img = _load_reportlab_image(
                post.cover_image, max_width=480, max_height=260
            )
            if cover_rl_img:
                story.append(Spacer(1, 4))
                story.append(cover_rl_img)
                story.append(Spacer(1, 6))

        # 5. Excerpt
        if post.excerpt:
            story.append(Paragraph(strip_tags(post.excerpt), styles["Excerpt"]))

        # 6. Post Content (Subheadings, paragraphs, inline images, chart tables)
        content_flowables = _parse_content_to_flowables(post, styles)
        story.extend(content_flowables)

        # Separator between posts
        if idx < num_posts - 1:
            story.append(Spacer(1, 15))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.5,
                    color=colors.HexColor("#CBD5E0"),
                    spaceAfter=15,
                )
            )

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
