from __future__ import annotations

import io
from datetime import date

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.infrastructure.db.models import TradeMode
from src.infrastructure.persistence.pnl_repository import PnlRepository


class PdfGenerator:
    """
    PDF generation service for reports using reportlab.
    Currently supports P&L reports with summary, daily table, and a trend chart.
    """

    def generate_pnl_report(
        self,
        db,
        user_id: int,
        trade_mode: TradeMode,
        start_date: date,
        end_date: date,
        include_unrealized: bool = True,
    ) -> bytes:
        """
        Generate a PDF report for P&L in the given date range.

        Returns PDF bytes.
        """
        # Fetch data
        repo = PnlRepository(db)
        records = repo.range(user_id=user_id, start=start_date, end=end_date)

        # Prepare aggregates
        total_realized = sum((r.realized_pnl or 0) for r in records)
        total_unrealized = sum((r.unrealized_pnl or 0) for r in records)
        total_fees = sum((r.fees or 0) for r in records)
        total_pnl = total_realized + (total_unrealized if include_unrealized else 0) - total_fees

        # Build document
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm)
        styles = getSampleStyleSheet()
        story: list = []

        # Title
        story.append(Paragraph("Profit & Loss Report", styles["Title"]))
        story.append(
            Paragraph(
                f"Mode: {trade_mode.value.capitalize()} • Range: {start_date.isoformat()} to {end_date.isoformat()}",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 0.5 * cm))

        # Summary
        summary_data = [
            ["Metric", "Amount"],
            ["Total Realized", f"{total_realized:.2f}"],
            ["Total Unrealized", f"{total_unrealized:.2f}"],
            ["Total Fees", f"{total_fees:.2f}"],
            [
                "Total P&L",
                (
                    f"{total_pnl:.2f}"
                    if include_unrealized
                    else f"{(total_realized - total_fees):.2f}"
                ),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[6 * cm, 6 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1e293b")),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 0.5 * cm))

        # Trend chart (daily total pnl)
        if records:
            drawing = Drawing(16 * cm, 6 * cm)
            chart = LinePlot()
            chart.x = 1 * cm
            chart.y = 1 * cm
            chart.height = 4 * cm
            chart.width = 14 * cm

            # Build series: (x, y) pairs with x as index (days)
            series = []
            for idx, r in enumerate(records):
                y_val = (
                    (r.realized_pnl or 0)
                    + ((r.unrealized_pnl or 0) if include_unrealized else 0)
                    - (r.fees or 0)
                )
                series.append((idx, float(y_val)))

            chart.data = [series]
            chart.lines[0].strokeColor = (
                colors.HexColor("#22c55e") if total_pnl >= 0 else colors.HexColor("#ef4444")
            )
            chart.strokeColor = colors.HexColor("#1e293b")
            chart.joinedLines = 1
            chart.xValueAxis.labels.angle = 0
            chart.xValueAxis.valueMin = 0
            chart.xValueAxis.valueMax = max(1, len(series) - 1)
            chart.yValueAxis.valueMin = min(0, min(y for _, y in series))
            chart.yValueAxis.valueMax = max(0, max(y for _, y in series))
            drawing.add(chart)
            story.append(Paragraph("Daily Total P&L Trend", styles["Heading3"]))
            story.append(drawing)
            story.append(Spacer(1, 0.5 * cm))

        # Daily table
        table_data: list[list[str]] = [["Date", "Realized", "Unrealized", "Fees", "Total"]]
        for r in records:
            total = (
                (r.realized_pnl or 0)
                + ((r.unrealized_pnl or 0) if include_unrealized else 0)
                - (r.fees or 0)
            )
            table_data.append(
                [
                    r.date.isoformat(),
                    f"{(r.realized_pnl or 0):.2f}",
                    f"{(r.unrealized_pnl or 0):.2f}",
                    f"{(r.fees or 0):.2f}",
                    f"{total:.2f}",
                ]
            )

        daily_table = Table(table_data, colWidths=[4 * cm, 3 * cm, 3 * cm, 3 * cm, 3 * cm])
        daily_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#1e293b")),
                ]
            )
        )
        story.append(Spacer(1, 0.25 * cm))
        story.append(daily_table)

        # Build document
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes
