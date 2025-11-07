# ------------------------------------------------------------
# report_pdf.py  (FINAL STABLE VERSION - NO ERRORS)
# ------------------------------------------------------------

import io
import os
import tempfile
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch


# Convert Plotly figure → PNG → temporary file path → ReportLab Image
def fig_to_temp_png(fig):
    if fig is None:
        return None

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    fig.write_image(temp.name, format="png")
    temp.close()
    return temp.name


def add_heading(text, stylesheet, story):
    story.append(Paragraph(f"<b>{text}</b>", stylesheet["Heading2"]))
    story.append(Spacer(1, 12))


def add_paragraph(text, stylesheet, story):
    story.append(Paragraph(text, stylesheet["BodyText"]))
    story.append(Spacer(1, 12))


def add_key_value(label, value, stylesheet, story):
    story.append(Paragraph(f"<b>{label}:</b> {value}", stylesheet["BodyText"]))
    story.append(Spacer(1, 6))


# ==============================================================
# ✅ MAIN FUNCTION - GENERATE EXECUTIVE PDF
# ==============================================================
def generate_executive_report(
    reco_df: pd.DataFrame,
    anomaly_fig=None,
    category_fig=None
):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    stylesheet = getSampleStyleSheet()
    story = []

    # -----------------------------
    # Title
    # -----------------------------
    story.append(
        Paragraph("<b>Smart Financial Reconciliation – Executive Summary Report</b>",
                  stylesheet["Title"])
    )
    story.append(Spacer(1, 20))

    # -----------------------------
    # KPI Summary
    # -----------------------------
    add_heading("📌 Reconciliation Summary", stylesheet, story)

    total = len(reco_df)
    matched = reco_df["match"].sum()
    mismatched = total - matched
    anomalies = reco_df["iso_is_anomaly"].sum()

    add_key_value("Total Transactions", total, stylesheet, story)
    add_key_value("Matched", matched, stylesheet, story)
    add_key_value("Mismatched", mismatched, stylesheet, story)
    add_key_value("Anomalies (ML)", anomalies, stylesheet, story)

    # -----------------------------
    # Anomaly Chart
    # -----------------------------
    if anomaly_fig is not None:
        anomaly_path = fig_to_temp_png(anomaly_fig)
        add_heading("🚩 ML Anomaly Insights", stylesheet, story)
        story.append(Image(anomaly_path, width=5 * inch, height=3 * inch))
        story.append(Spacer(1, 20))

    # -----------------------------
    # Category Chart
    # -----------------------------
    if category_fig is not None:
        category_path = fig_to_temp_png(category_fig)
        add_heading("🏷️ NLP Categorization Overview", stylesheet, story)
        story.append(Image(category_path, width=5 * inch, height=3 * inch))
        story.append(Spacer(1, 20))

    # -----------------------------
    # Recommendations
    # -----------------------------
    add_heading("🧠 Top Recommendation Samples", stylesheet, story)

    if "recommendation" in reco_df.columns:
        sample = reco_df.head(10)
        for _, row in sample.iterrows():
            story.append(Paragraph(
                f"<b>{row['ref']}</b> — {row['root_cause']} — {row['anomaly_reason']}<br/>{row['recommendation']}",
                stylesheet["BodyText"]
            ))
            story.append(Spacer(1, 12))
    else:
        add_paragraph("No recommendations present.", stylesheet, story)

    # -----------------------------
    # Final Notes
    # -----------------------------
    add_heading("✅ Report Generated Successfully", stylesheet, story)
    add_paragraph("This executive report summarizes key reconciliation insights.",
                  stylesheet, story)

    # Build PDF
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    # cleanup temp files
    try:
        if anomaly_fig is not None:
            os.remove(anomaly_path)
        if category_fig is not None:
            os.remove(category_path)
    except:
        pass

    return pdf
