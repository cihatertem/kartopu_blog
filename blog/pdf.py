import io
import os
import re
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import QuerySet
from django.utils.html import escape, strip_tags
from PIL import Image as PILImage
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.fonts import addMapping
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
from blog.templatetags.blog_extras import (
    _get_cashflow_comparisons,
    _get_cashflow_snapshots,
    _get_dividend_comparisons,
    _get_dividend_snapshots,
    _get_item_by_identifier,
    _get_portfolio_comparisons,
    _get_portfolio_snapshots,
    _get_salary_savings_snapshots,
)

# Custom TTF Font Registration for Full Turkish Character Support
FONT_NAME = "Helvetica"
FONT_NAME_BOLD = "Helvetica-Bold"
FONT_NAME_ITALIC = "Helvetica-Oblique"
FONT_NAME_BOLD_ITALIC = "Helvetica-BoldOblique"


def _setup_fonts() -> tuple[str, str, str, str]:
    font_dir = os.path.join(settings.BASE_DIR, "static", "fonts")

    normal_candidates = [
        os.path.join(font_dir, "DejaVuSans.ttf"),
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        os.path.join(font_dir, "DejaVuSans-Bold.ttf"),
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    italic_candidates = [
        os.path.join(font_dir, "DejaVuSans-Oblique.ttf"),
        "/usr/share/fonts/TTF/DejaVuSans-Oblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
    ]
    bold_italic_candidates = [
        os.path.join(font_dir, "DejaVuSans-BoldOblique.ttf"),
        "/usr/share/fonts/TTF/DejaVuSans-BoldOblique.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
    ]

    normal_path = next((p for p in normal_candidates if os.path.exists(p)), None)
    bold_path = next((p for p in bold_candidates if os.path.exists(p)), None)
    italic_path = next((p for p in italic_candidates if os.path.exists(p)), None)
    bold_italic_path = next(
        (p for p in bold_italic_candidates if os.path.exists(p)), None
    )

    if normal_path and bold_path:
        try:
            pdfmetrics.registerFont(TTFont("DejaVuSans", normal_path))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", bold_path))

            reg_italic = "DejaVuSans-Bold"
            reg_bold_italic = "DejaVuSans-Bold"

            if italic_path:
                pdfmetrics.registerFont(TTFont("DejaVuSans-Oblique", italic_path))
                reg_italic = "DejaVuSans-Oblique"

            if bold_italic_path:
                pdfmetrics.registerFont(
                    TTFont("DejaVuSans-BoldOblique", bold_italic_path)
                )
                reg_bold_italic = "DejaVuSans-BoldOblique"
            elif italic_path:
                reg_bold_italic = "DejaVuSans-Oblique"

            addMapping("DejaVuSans", 0, 0, "DejaVuSans")
            addMapping("DejaVuSans", 1, 0, "DejaVuSans-Bold")
            addMapping("DejaVuSans", 0, 1, reg_italic)
            addMapping("DejaVuSans", 1, 1, reg_bold_italic)

            return "DejaVuSans", "DejaVuSans-Bold", reg_italic, reg_bold_italic
        except Exception:
            pass

    return FONT_NAME, FONT_NAME_BOLD, FONT_NAME_ITALIC, FONT_NAME_BOLD_ITALIC


FONT_REG, FONT_BOLD, FONT_ITAL, FONT_BOLD_ITAL = _setup_fonts()


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
        "ChartHeader": ParagraphStyle(
            "ChartHeader",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=10.5,
            leading=14,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=8,
            spaceAfter=4,
        ),
        "TableHead": ParagraphStyle(
            "TableHead",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=colors.white,
            alignment=0,
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=base_styles["Normal"],
            fontName=FONT_REG,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#2D3748"),
        ),
        "TableCellBold": ParagraphStyle(
            "TableCellBold",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1A202C"),
        ),
        "DisclaimerTitle": ParagraphStyle(
            "DisclaimerTitle",
            parent=base_styles["Normal"],
            fontName=FONT_BOLD,
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#C53030"),
            spaceAfter=3,
        ),
        "DisclaimerText": ParagraphStyle(
            "DisclaimerText",
            parent=base_styles["Normal"],
            fontName=FONT_REG,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#742A2A"),
        ),
    }
    return styles


def _format_currency_val(val: Any, currency_code: str | None = None) -> str:
    if val is None or val == "":
        return "—"
    try:
        num = float(val)
        formatted = f"{num:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")
        if currency_code:
            return f"{formatted} {currency_code}"
        return formatted
    except (ValueError, TypeError):
        return str(val)


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

            ratio = min(max_width / float(orig_w), max_height / float(orig_h), 1.0)
            target_w = orig_w * ratio
            target_h = orig_h * ratio

            buf = io.BytesIO()
            rgb_img = pil_img.convert("RGB")
            rgb_img.save(buf, format="JPEG", quality=85)
            buf.seek(0)

            return RLImage(buf, width=target_w, height=target_h)
    except Exception:
        return None


# --- VECTOR CHART GENERATOR HELPERS ---

COLOR_PALETTE = [
    colors.HexColor("#2B6CB0"),
    colors.HexColor("#319795"),
    colors.HexColor("#D69E2E"),
    colors.HexColor("#E53E3E"),
    colors.HexColor("#805AD5"),
    colors.HexColor("#DD6B20"),
    colors.HexColor("#3182CE"),
    colors.HexColor("#38A169"),
]


def _create_pie_chart_drawing(items_data: list[tuple[str, float, float]]) -> Drawing | None:
    """items_data: list of (label_str, total_val_float, pct_float)"""
    if not items_data:
        return None

    top_items = items_data[:7]
    values = [item[1] for item in top_items if item[1] > 0]
    if not values:
        return None

    drawing = Drawing(440, 150)
    pie = Pie()
    pie.x = 10
    pie.y = 10
    pie.width = 130
    pie.height = 130
    pie.data = values
    pie.sideLabels = 0
    pie.labels = [f"%{item[2]:.1f}" for item in top_items[: len(values)]]

    for i, color in enumerate(COLOR_PALETTE[: len(values)]):
        pie.slices[i].fillColor = color
        pie.slices[i].strokeColor = colors.white
        pie.slices[i].strokeWidth = 1

    legend = Legend()
    legend.x = 175
    legend.y = 135
    legend.dx = 8
    legend.dy = 8
    legend.fontName = FONT_REG
    legend.fontSize = 8
    legend.colorNamePairs = [
        (COLOR_PALETTE[i], f"{item[0][:20]} (%{item[2]:.1f})")
        for i, item in enumerate(top_items[: len(values)])
    ]

    drawing.add(pie)
    drawing.add(legend)
    return drawing


def _create_bar_chart_drawing(categories: list[str], values: list[float]) -> Drawing | None:
    if not categories or not values:
        return None

    cats = [str(c)[:15] for c in categories[:10]]
    vals = [float(v) for v in values[:10]]

    drawing = Drawing(440, 140)
    chart = VerticalBarChart()
    chart.x = 45
    chart.y = 20
    chart.height = 105
    chart.width = 375
    chart.data = [vals]
    chart.categoryAxis.categoryNames = cats
    chart.categoryAxis.labels.fontName = FONT_REG
    chart.categoryAxis.labels.fontSize = 7.5
    chart.valueAxis.labels.fontName = FONT_REG
    chart.valueAxis.labels.fontSize = 7.5
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = colors.HexColor("#2B6CB0")

    drawing.add(chart)
    return drawing


def _create_styled_table(data_matrix: list[list[Any]], col_widths=None) -> Table:
    table = Table(data_matrix, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
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


# --- MARKER PDF RENDERERS ---

def _render_legal_disclaimer_pdf(styles) -> list:
    content = [
        Paragraph("YASAL UYARI", styles["DisclaimerTitle"]),
        Paragraph(
            "Burada yer alan yatırım bilgi, yorum ve tavsiyeleri yatırım danışmanlığı kapsamında değildir. "
            "Yatırım danışmanlığı hizmeti, kişilerin risk ve getiri tercihleri dikkate alınarak kişiye özel "
            "sunulmaktadır. Burada yer alan ve hiçbir şekilde yönlendirici nitelikte olmayan içerik, yorum ve "
            "tavsiyeler ise genel niteliktedir. Bu tavsiyeler mali durumunuz ile risk ve getiri tercihlerinize "
            "uygun olmayabilir. Bu nedenle, sadece burada yer alan bilgilere dayanılarak yatırım kararı "
            "verilmesi beklentilerinize uygun sonuçlar doğurmayabilir.",
            styles["DisclaimerText"],
        ),
    ]
    container = Table([[content]], colWidths=[450])
    container.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF5F5")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FEB2B2")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [Spacer(1, 6), container, Spacer(1, 6)]


def _render_portfolio_summary_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []
    curr = getattr(snapshot.portfolio, "currency", "")
    total_val = _format_currency_val(snapshot.total_value, curr)
    total_cost = _format_currency_val(snapshot.total_cost, curr)
    ret_pct = f"%{float(snapshot.total_return_pct * 100):.2f}" if snapshot.total_return_pct is not None else "—"

    rows = [
        [
            Paragraph("Portföy Özeti", styles["TableHead"]),
            Paragraph("Değer", styles["TableHead"]),
        ],
        [Paragraph("Portföy Adı", styles["TableCellBold"]), Paragraph(escape(str(snapshot.portfolio.name)), styles["TableCell"])],
        [Paragraph("Tarih", styles["TableCellBold"]), Paragraph(str(snapshot.snapshot_date), styles["TableCell"])],
        [Paragraph("Toplam Değer", styles["TableCellBold"]), Paragraph(total_val, styles["TableCell"])],
        [Paragraph("Toplam Maliyet", styles["TableCellBold"]), Paragraph(total_cost, styles["TableCell"])],
        [Paragraph("Toplam Getiri (%)", styles["TableCellBold"]), Paragraph(ret_pct, styles["TableCell"])],
    ]

    if getattr(snapshot, "target_value", None):
        rows.append([Paragraph("Hedef Değer", styles["TableCellBold"]), Paragraph(_format_currency_val(snapshot.target_value, curr), styles["TableCell"])])
    if getattr(snapshot, "target_ratio_pct", None):
        rows.append([Paragraph("Hedef Gerçekleşme (%)", styles["TableCellBold"]), Paragraph(f"%{float(snapshot.target_ratio_pct):.2f}", styles["TableCell"])])

    tbl = _create_styled_table(rows, col_widths=[180, 270])
    return [Spacer(1, 4), Paragraph("Portföy Özeti", styles["ChartHeader"]), tbl, Spacer(1, 6)]


def _render_portfolio_charts_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    items = list(snapshot.items.all())
    valid_items = [i for i in items if i.total_value and i.total_value > 0]

    flowables = [Spacer(1, 4), Paragraph("Varlık Dağılımı & Detayı", styles["ChartHeader"])]

    if valid_items:
        tot_val = sum(float(i.total_value) for i in valid_items)
        pie_data = []
        for i in valid_items:
            pct = (float(i.total_value) / tot_val * 100) if tot_val > 0 else 0
            symbol = getattr(i.asset, "symbol", "") or getattr(i.asset, "name", "Varlık")
            pie_data.append((symbol, float(i.total_value), pct))

        pie_data.sort(key=lambda x: x[1], reverse=True)
        pie_drawing = _create_pie_chart_drawing(pie_data)
        if pie_drawing:
            flowables.append(pie_drawing)
            flowables.append(Spacer(1, 6))

    # Asset Table
    rows = [
        [
            Paragraph("Varlık", styles["TableHead"]),
            Paragraph("Miktar", styles["TableHead"]),
            Paragraph("Maliyet", styles["TableHead"]),
            Paragraph("Birim Fiyat", styles["TableHead"]),
            Paragraph("Toplam Değer", styles["TableHead"]),
            Paragraph("Oran (%)", styles["TableHead"]),
        ]
    ]

    curr = getattr(snapshot.portfolio, "currency", "")
    tot_val = sum(float(i.total_value or 0) for i in items)

    for i in items:
        symbol = getattr(i.asset, "symbol", "") or getattr(i.asset, "name", "Varlık")
        qty = str(i.quantity or "—")
        cost = _format_currency_val(i.cost_basis, curr)
        price = _format_currency_val(i.unit_price, curr)
        val = _format_currency_val(i.total_value, curr)
        pct = f"%{(float(i.total_value or 0) / tot_val * 100):.2f}" if tot_val > 0 else "—"

        rows.append([
            Paragraph(escape(symbol), styles["TableCellBold"]),
            Paragraph(qty, styles["TableCell"]),
            Paragraph(cost, styles["TableCell"]),
            Paragraph(price, styles["TableCell"]),
            Paragraph(val, styles["TableCell"]),
            Paragraph(pct, styles["TableCell"]),
        ])

    tbl = _create_styled_table(rows, col_widths=[90, 60, 80, 70, 90, 60])
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))
    return flowables


def _render_portfolio_irr_charts_pdf(snapshot, styles) -> list:
    if not snapshot or not hasattr(snapshot, "portfolio"):
        return []

    irr_history = snapshot.portfolio.get_irr_history(until_date=snapshot.snapshot_date)
    if not irr_history:
        return []

    flowables = [Spacer(1, 4), Paragraph("Portföy İç Verim Oranı (IRR) Gelişimi", styles["ChartHeader"])]

    dates = [str(item["date"]) for item in irr_history]
    irrs = [float(item["irr"]) for item in irr_history]

    chart_drawing = _create_bar_chart_drawing(dates, irrs)
    if chart_drawing:
        flowables.append(chart_drawing)
        flowables.append(Spacer(1, 6))

    rows = [
        [
            Paragraph("Tarih", styles["TableHead"]),
            Paragraph("İç Verim Oranı (IRR %)", styles["TableHead"]),
        ]
    ]
    for d_str, irr_val in zip(dates, irrs):
        rows.append([
            Paragraph(d_str, styles["TableCellBold"]),
            Paragraph(f"%{irr_val:.2f}", styles["TableCell"]),
        ])

    tbl = _create_styled_table(rows, col_widths=[200, 250])
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))
    return flowables


def _render_portfolio_category_summary_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    items = list(snapshot.items.all())
    category_totals: dict[str, float] = {}

    for item in items:
        cat_name = str(getattr(item.asset, "get_category_display", lambda: "Diğer")() or "Diğer")
        val = float(item.total_value or 0)
        category_totals[cat_name] = category_totals.get(cat_name, 0.0) + val

    flowables = [Spacer(1, 4), Paragraph("Kategori Dağılım Özeti", styles["ChartHeader"])]
    tot_val = sum(category_totals.values())

    if tot_val > 0:
        pie_data = [(cat, val, (val / tot_val * 100)) for cat, val in category_totals.items() if val > 0]
        pie_data.sort(key=lambda x: x[1], reverse=True)
        pie_drawing = _create_pie_chart_drawing(pie_data)
        if pie_drawing:
            flowables.append(pie_drawing)
            flowables.append(Spacer(1, 6))

    rows = [
        [
            Paragraph("Kategori", styles["TableHead"]),
            Paragraph("Toplam Değer", styles["TableHead"]),
            Paragraph("Oran (%)", styles["TableHead"]),
        ]
    ]

    curr = getattr(snapshot.portfolio, "currency", "")
    for cat, val in category_totals.items():
        pct = f"%{(val / tot_val * 100):.2f}" if tot_val > 0 else "—"
        rows.append([
            Paragraph(escape(cat), styles["TableCellBold"]),
            Paragraph(_format_currency_val(val, curr), styles["TableCell"]),
            Paragraph(pct, styles["TableCell"]),
        ])

    tbl = _create_styled_table(rows, col_widths=[180, 160, 110])
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))
    return flowables


def _render_portfolio_comparison_summary_pdf(comparison, styles) -> list:
    if not comparison:
        return []

    base_s = comparison.base_snapshot
    comp_s = comparison.compare_snapshot

    curr = getattr(base_s.portfolio, "currency", "")
    base_val = float(base_s.total_value or 0)
    comp_val = float(comp_s.total_value or 0)
    diff = comp_val - base_val
    pct_change = ((diff / base_val) * 100) if base_val > 0 else 0

    rows = [
        [
            Paragraph("Dönem", styles["TableHead"]),
            Paragraph("Tarih", styles["TableHead"]),
            Paragraph("Toplam Değer", styles["TableHead"]),
        ],
        [Paragraph("Baz Dönem", styles["TableCellBold"]), Paragraph(str(base_s.snapshot_date), styles["TableCell"]), Paragraph(_format_currency_val(base_val, curr), styles["TableCell"])],
        [Paragraph("Karşılaştırılan Dönem", styles["TableCellBold"]), Paragraph(str(comp_s.snapshot_date), styles["TableCell"]), Paragraph(_format_currency_val(comp_val, curr), styles["TableCell"])],
        [Paragraph("Değişim / Fark", styles["TableCellBold"]), Paragraph(f"%{pct_change:.2f}", styles["TableCellBold"]), Paragraph(_format_currency_val(diff, curr), styles["TableCellBold"])],
    ]

    tbl = _create_styled_table(rows, col_widths=[140, 140, 170])
    return [Spacer(1, 4), Paragraph("Portföy Karşılaştırma Özeti", styles["ChartHeader"]), tbl, Spacer(1, 6)]


def _render_portfolio_comparison_charts_pdf(comparison, styles) -> list:
    if not comparison:
        return []

    base_s = comparison.base_snapshot
    comp_s = comparison.compare_snapshot

    categories = [str(base_s.snapshot_date), str(comp_s.snapshot_date)]
    values = [float(base_s.total_value or 0), float(comp_s.total_value or 0)]

    chart_drawing = _create_bar_chart_drawing(categories, values)
    flowables = [Spacer(1, 4), Paragraph("Portföy Karşılaştırma Grafiği", styles["ChartHeader"])]
    if chart_drawing:
        flowables.append(chart_drawing)
        flowables.append(Spacer(1, 6))

    return flowables


def _render_cashflow_summary_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    curr = getattr(snapshot.cashflow, "currency", "")
    tot_amount = _format_currency_val(snapshot.total_amount, curr)

    rows = [
        [
            Paragraph("Nakit Akışı Özeti", styles["TableHead"]),
            Paragraph("Değer", styles["TableHead"]),
        ],
        [Paragraph("Nakit Akışı Adı", styles["TableCellBold"]), Paragraph(escape(str(snapshot.cashflow.name)), styles["TableCell"])],
        [Paragraph("Tarih", styles["TableCellBold"]), Paragraph(str(snapshot.snapshot_date), styles["TableCell"])],
        [Paragraph("Net Tutar", styles["TableCellBold"]), Paragraph(tot_amount, styles["TableCellBold"])],
    ]

    tbl = _create_styled_table(rows, col_widths=[180, 270])
    return [Spacer(1, 4), Paragraph("Nakit Akışı Özeti", styles["ChartHeader"]), tbl, Spacer(1, 6)]


def _render_cashflow_charts_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    items = list(snapshot.items.all())
    flowables = [Spacer(1, 4), Paragraph("Nakit Akışı Dağılımı", styles["ChartHeader"])]

    if items:
        tot_val = sum(float(i.amount or 0) for i in items if i.amount and i.amount > 0)
        pie_data = []
        for i in items:
            val = float(i.amount or 0)
            if val > 0:
                pct = (val / tot_val * 100) if tot_val > 0 else 0
                cat_name = str(getattr(i, "category", "Kategori") or "Kategori")
                pie_data.append((cat_name, val, pct))

        pie_drawing = _create_pie_chart_drawing(pie_data)
        if pie_drawing:
            flowables.append(pie_drawing)
            flowables.append(Spacer(1, 6))

    rows = [
        [
            Paragraph("Kategori / Açıklama", styles["TableHead"]),
            Paragraph("Tutar", styles["TableHead"]),
        ]
    ]

    curr = getattr(snapshot.cashflow, "currency", "")
    for i in items:
        cat_name = str(getattr(i, "category", "Kategori") or "Kategori")
        amt = _format_currency_val(i.amount, curr)
        rows.append([
            Paragraph(escape(cat_name), styles["TableCellBold"]),
            Paragraph(amt, styles["TableCell"]),
        ])

    tbl = _create_styled_table(rows, col_widths=[250, 200])
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))
    return flowables


def _render_cashflow_comparison_summary_pdf(comparison, styles) -> list:
    if not comparison:
        return []

    base_s = comparison.base_snapshot
    comp_s = comparison.compare_snapshot

    curr = getattr(base_s.cashflow, "currency", "")
    base_val = float(base_s.total_amount or 0)
    comp_val = float(comp_s.total_amount or 0)
    diff = comp_val - base_val

    rows = [
        [
            Paragraph("Dönem", styles["TableHead"]),
            Paragraph("Tarih", styles["TableHead"]),
            Paragraph("Net Akış Tutarı", styles["TableHead"]),
        ],
        [Paragraph("Baz Dönem", styles["TableCellBold"]), Paragraph(str(base_s.snapshot_date), styles["TableCell"]), Paragraph(_format_currency_val(base_val, curr), styles["TableCell"])],
        [Paragraph("Karşılaştırılan Dönem", styles["TableCellBold"]), Paragraph(str(comp_s.snapshot_date), styles["TableCell"]), Paragraph(_format_currency_val(comp_val, curr), styles["TableCell"])],
        [Paragraph("Fark", styles["TableCellBold"]), Paragraph("—", styles["TableCell"]), Paragraph(_format_currency_val(diff, curr), styles["TableCellBold"])],
    ]

    tbl = _create_styled_table(rows, col_widths=[140, 140, 170])
    return [Spacer(1, 4), Paragraph("Nakit Akışı Karşılaştırma Özeti", styles["ChartHeader"]), tbl, Spacer(1, 6)]


def _render_cashflow_comparison_charts_pdf(comparison, styles) -> list:
    if not comparison:
        return []

    base_s = comparison.base_snapshot
    comp_s = comparison.compare_snapshot

    categories = [str(base_s.snapshot_date), str(comp_s.snapshot_date)]
    values = [float(base_s.total_amount or 0), float(comp_s.total_amount or 0)]

    chart_drawing = _create_bar_chart_drawing(categories, values)
    flowables = [Spacer(1, 4), Paragraph("Nakit Akışı Karşılaştırma Grafiği", styles["ChartHeader"])]
    if chart_drawing:
        flowables.append(chart_drawing)
        flowables.append(Spacer(1, 6))

    return flowables


def _render_savings_rate_summary_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    curr = getattr(snapshot, "currency", "")
    rate_pct = (
        f"%{float(snapshot.savings_rate * 100):.2f}"
        if snapshot.savings_rate is not None
        else "—"
    )
    income_val = getattr(snapshot, "total_salary", getattr(snapshot, "income", None))
    savings_val = getattr(
        snapshot, "total_savings", getattr(snapshot, "savings", None)
    )

    rows = [
        [
            Paragraph("Maaş / Tasarruf Özeti", styles["TableHead"]),
            Paragraph("Değer", styles["TableHead"]),
        ],
        [
            Paragraph("Tarih", styles["TableCellBold"]),
            Paragraph(str(snapshot.snapshot_date), styles["TableCell"]),
        ],
        [
            Paragraph("Maaş / Gelir Tutarı", styles["TableCellBold"]),
            Paragraph(_format_currency_val(income_val, curr), styles["TableCell"]),
        ],
        [
            Paragraph("Tasarruf Tutarı", styles["TableCellBold"]),
            Paragraph(_format_currency_val(savings_val, curr), styles["TableCell"]),
        ],
        [
            Paragraph("Tasarruf Oranı (%)", styles["TableCellBold"]),
            Paragraph(rate_pct, styles["TableCellBold"]),
        ],
    ]

    tbl = _create_styled_table(rows, col_widths=[180, 270])
    return [
        Spacer(1, 4),
        Paragraph("Tasarruf Oranı Özeti", styles["ChartHeader"]),
        tbl,
        Spacer(1, 6),
    ]


def _render_savings_rate_charts_pdf(snapshot, styles) -> list:
    if not snapshot or not hasattr(snapshot, "flow"):
        return []

    history = list(snapshot.flow.snapshots.order_by("snapshot_date"))
    if not history:
        return []

    flowables = [
        Spacer(1, 4),
        Paragraph("Tasarruf Oranı Gelişim Grafiği", styles["ChartHeader"]),
    ]

    dates = [str(s.snapshot_date) for s in history]
    rates = [float((s.savings_rate or 0) * 100) for s in history]

    chart_drawing = _create_bar_chart_drawing(dates, rates)
    if chart_drawing:
        flowables.append(chart_drawing)
        flowables.append(Spacer(1, 6))

    rows = [
        [
            Paragraph("Tarih", styles["TableHead"]),
            Paragraph("Tasarruf Oranı (%)", styles["TableHead"]),
        ]
    ]
    for d_str, r_val in zip(dates, rates):
        rows.append(
            [
                Paragraph(d_str, styles["TableCellBold"]),
                Paragraph(f"%{r_val:.2f}", styles["TableCell"]),
            ]
        )

    tbl = _create_styled_table(rows, col_widths=[200, 250])
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))
    return flowables


def _render_dividend_summary_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    curr = getattr(snapshot, "currency", "")
    tot_amt = _format_currency_val(snapshot.total_amount, curr)

    flowables = [Spacer(1, 4), Paragraph("Temettü Özeti", styles["ChartHeader"])]

    summary_rows = [
        [
            Paragraph("Temettü Yılı", styles["TableHead"]),
            Paragraph("Toplam Temettü Tutarı", styles["TableHead"]),
        ],
        [
            Paragraph(str(snapshot.year), styles["TableCellBold"]),
            Paragraph(tot_amt, styles["TableCellBold"]),
        ],
    ]
    flowables.append(_create_styled_table(summary_rows, col_widths=[180, 270]))

    payment_items = list(snapshot.payment_items.all())
    if payment_items:
        flowables.append(Spacer(1, 6))
        flowables.append(Paragraph("Temettü Ödeme Dökümü", styles["H2"]))

        p_rows = [
            [
                Paragraph("Hisse / Varlık", styles["TableHead"]),
                Paragraph("Ödeme Tarihi", styles["TableHead"]),
                Paragraph("Ödenen Tutar", styles["TableHead"]),
            ]
        ]
        for p in payment_items:
            symbol = (
                getattr(p.asset, "symbol", "")
                or getattr(p.asset, "name", "Hisse")
            )
            d_str = str(p.payment_date or "—")
            amt_val = getattr(p, "total_net_amount", getattr(p, "amount", 0))
            amt = _format_currency_val(amt_val, curr)
            p_rows.append(
                [
                    Paragraph(escape(symbol), styles["TableCellBold"]),
                    Paragraph(d_str, styles["TableCell"]),
                    Paragraph(amt, styles["TableCell"]),
                ]
            )

        flowables.append(_create_styled_table(p_rows, col_widths=[150, 150, 150]))

    flowables.append(Spacer(1, 6))
    return flowables


def _render_dividend_charts_pdf(snapshot, styles) -> list:
    if not snapshot:
        return []

    asset_items = list(snapshot.asset_items.all())
    flowables = [Spacer(1, 4), Paragraph("Temettü Dağılım Grafiği & Detayı", styles["ChartHeader"])]

    if asset_items:
        tot_val = sum(float(i.total_amount or 0) for i in asset_items if i.total_amount and i.total_amount > 0)
        pie_data = []
        for i in asset_items:
            val = float(i.total_amount or 0)
            if val > 0:
                pct = (val / tot_val * 100) if tot_val > 0 else 0
                symbol = getattr(i.asset, "symbol", "") or getattr(i.asset, "name", "Hisse")
                pie_data.append((symbol, val, pct))

        pie_drawing = _create_pie_chart_drawing(pie_data)
        if pie_drawing:
            flowables.append(pie_drawing)
            flowables.append(Spacer(1, 6))

    rows = [
        [
            Paragraph("Hisse / Varlık", styles["TableHead"]),
            Paragraph("Toplam Temettü", styles["TableHead"]),
            Paragraph("Oran (%)", styles["TableHead"]),
        ]
    ]

    curr = getattr(snapshot, "currency", "")
    tot_val = sum(float(i.total_amount or 0) for i in asset_items)
    for i in asset_items:
        symbol = getattr(i.asset, "symbol", "") or getattr(i.asset, "name", "Hisse")
        val_str = _format_currency_val(i.total_amount, curr)
        pct_str = f"%{(float(i.total_amount or 0) / tot_val * 100):.2f}" if tot_val > 0 else "—"

        rows.append([
            Paragraph(escape(symbol), styles["TableCellBold"]),
            Paragraph(val_str, styles["TableCell"]),
            Paragraph(pct_str, styles["TableCell"]),
        ])

    tbl = _create_styled_table(rows, col_widths=[180, 160, 110])
    flowables.append(tbl)
    flowables.append(Spacer(1, 6))
    return flowables


def _render_dividend_comparison_pdf(comparison, styles) -> list:
    if not comparison:
        return []

    base_s = comparison.base_snapshot
    comp_s = comparison.compare_snapshot

    curr = getattr(base_s, "currency", "")
    base_val = float(base_s.total_amount or 0)
    comp_val = float(comp_s.total_amount or 0)
    diff = comp_val - base_val

    rows = [
        [
            Paragraph("Yıl", styles["TableHead"]),
            Paragraph("Toplam Temettü", styles["TableHead"]),
        ],
        [Paragraph(str(base_s.year), styles["TableCellBold"]), Paragraph(_format_currency_val(base_val, curr), styles["TableCell"])],
        [Paragraph(str(comp_s.year), styles["TableCellBold"]), Paragraph(_format_currency_val(comp_val, curr), styles["TableCell"])],
        [Paragraph("Değişim / Fark", styles["TableCellBold"]), Paragraph(_format_currency_val(diff, curr), styles["TableCellBold"])],
    ]

    tbl = _create_styled_table(rows, col_widths=[200, 250])
    return [Spacer(1, 4), Paragraph("Temettü Karşılaştırma Özeti", styles["ChartHeader"]), tbl, Spacer(1, 6)]


MARKER_PDF_MAP = {
    "portfolio_summary": (_get_portfolio_snapshots, _render_portfolio_summary_pdf),
    "portfolio_charts": (_get_portfolio_snapshots, _render_portfolio_charts_pdf),
    "portfolio_irr_charts": (_get_portfolio_snapshots, _render_portfolio_irr_charts_pdf),
    "portfolio_category_summary": (_get_portfolio_snapshots, _render_portfolio_category_summary_pdf),
    "portfolio_comparison_summary": (_get_portfolio_comparisons, _render_portfolio_comparison_summary_pdf),
    "portfolio_comparison_charts": (_get_portfolio_comparisons, _render_portfolio_comparison_charts_pdf),
    "cashflow_summary": (_get_cashflow_snapshots, _render_cashflow_summary_pdf),
    "cashflow_charts": (_get_cashflow_snapshots, _render_cashflow_charts_pdf),
    "cashflow_comparison_summary": (_get_cashflow_comparisons, _render_cashflow_comparison_summary_pdf),
    "cashflow_comparison_charts": (_get_cashflow_comparisons, _render_cashflow_comparison_charts_pdf),
    "savings_rate_summary": (_get_salary_savings_snapshots, _render_savings_rate_summary_pdf),
    "savings_rate_charts": (_get_salary_savings_snapshots, _render_savings_rate_charts_pdf),
    "dividend_summary": (_get_dividend_snapshots, _render_dividend_summary_pdf),
    "dividend_charts": (_get_dividend_snapshots, _render_dividend_charts_pdf),
    "dividend_comparison": (_get_dividend_comparisons, _render_dividend_comparison_pdf),
}


def _parse_content_to_flowables(post: BlogPost, styles) -> list:
    flowables = []
    content = post.content or ""

    image_pattern = re.compile(r"\{\{\s*image:(\d+)\s*\}\}")
    marker_pattern = re.compile(
        r"\{\{\s*(?P<tag>[a-zA-Z0-9_]+)(?::(?P<arg>[^\s\}]+))?\s*\}\}"
    )

    post_images = list(post.images.all())
    used_images_set = set()

    lines = content.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check headings
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

        # Check {{ image:N }}
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

        # Check markers {{ tag:arg }}
        marker_match = marker_pattern.search(stripped)
        if marker_match:
            tag = marker_match.group("tag")
            arg = marker_match.group("arg")

            if tag == "legal_disclaimer":
                flowables.extend(_render_legal_disclaimer_pdf(styles))
                continue
            elif tag in MARKER_PDF_MAP:
                getter, render_func = MARKER_PDF_MAP[tag]
                items = getter(post)
                item = _get_item_by_identifier(items, arg)
                rendered_flowables = render_func(item, styles)
                if rendered_flowables:
                    flowables.extend(rendered_flowables)
                continue

        # Normal text line
        cleaned_text = (
            stripped.replace("**", "<b>", 1).replace("**", "</b>", 1)
            if stripped.count("**") >= 2
            else stripped
        )
        flowables.append(Paragraph(cleaned_text, styles["Body"]))

    # Render any unused inline images at bottom of post
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

    titles, subheadings, tags, photos (cover & inline), vector charts, data tables,

    and financial summary markers.

    Returns the raw PDF byte stream.
    """
    published_posts = queryset.filter(status=BlogPost.Status.PUBLISHED).select_related(
        "author", "category"
    ).prefetch_related("tags", "images")

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
        # 1. Post Title
        story.append(Paragraph(post.title, styles["PostTitle"]))

        # 2. Metadata
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

        # 6. Post Content (Subheadings, paragraphs, inline images, vector charts & tables)
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
