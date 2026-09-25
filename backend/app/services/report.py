import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.db.models import Voyage


def build_voyage_report_pdf(voyage: Voyage) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"Voyage {voyage.id} Report")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("SeaPath Voyage Report", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"Voyage #{voyage.id} — Strategy: {voyage.strategy}", styles["Heading2"]))
    story.append(Spacer(1, 12))

    data = [
        ["Metric", "Value"],
        ["Origin", f"{voyage.origin_lat:.3f}, {voyage.origin_lon:.3f}"],
        ["Destination", f"{voyage.dest_lat:.3f}, {voyage.dest_lon:.3f}"],
        ["Distance (nm)", f"{voyage.distance_nm:.1f}"],
        ["Duration (hr)", f"{voyage.duration_hr:.1f}"],
        ["Fuel used (tons)", f"{voyage.fuel_tons:.2f}"],
        ["CO2 emitted (tons)", f"{voyage.co2_tons:.2f}"],
        ["Created", voyage.created_at.strftime("%Y-%m-%d %H:%M UTC")],
    ]
    table = Table(data, colWidths=[180, 250])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#065A82")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE6EC")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F8FA")]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)

    doc.build(story)
    return buffer.getvalue()
