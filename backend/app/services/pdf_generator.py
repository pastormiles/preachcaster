"""
PDF Discussion Guide Generator
Creates beautifully formatted PDF discussion guides for small groups.

Adapted from CWI script 08_generate_discussion_guide_v1.py for SaaS architecture.
"""

import io
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf import FPDF
from google.cloud import storage

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# PDF Settings
PAGE_WIDTH = 210  # A4 width in mm
PAGE_HEIGHT = 297  # A4 height in mm
MARGIN_LEFT = 15
MARGIN_RIGHT = 15
MARGIN_TOP = 15
MARGIN_BOTTOM = 15

# Font sizes
FONT_SIZE_TITLE = 18
FONT_SIZE_SECTION = 12
FONT_SIZE_BODY = 10
FONT_SIZE_SMALL = 9


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class DiscussionGuidePDF(FPDF):
    """Custom PDF class for discussion guides with church branding."""

    def __init__(
        self,
        church_name: str = "Church",
        primary_color: str = "#ea580c",  # Orange-600
        secondary_color: str = "#c2410c",  # Orange-700
    ):
        super().__init__()
        self.church_name = church_name
        self.primary_color = hex_to_rgb(primary_color)
        self.secondary_color = hex_to_rgb(secondary_color)

        # Set margins
        self.set_margins(MARGIN_LEFT, MARGIN_TOP, MARGIN_RIGHT)
        self.set_auto_page_break(True, MARGIN_BOTTOM)

        # Add page
        self.add_page()

    def add_header(
        self,
        sermon_title: str,
        date: Optional[str] = None,
        speaker: Optional[str] = None
    ):
        """Add document header with church branding."""
        # Church name
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*self.primary_color)
        self.cell(0, 6, self.church_name, ln=True)

        # Subtitle
        self.set_font("Helvetica", "", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, "Small Group Discussion Guide", ln=True)

        # Divider line
        self.ln(3)
        self.set_draw_color(*self.primary_color)
        self.set_line_width(0.5)
        self.line(MARGIN_LEFT, self.get_y(), PAGE_WIDTH - MARGIN_RIGHT, self.get_y())
        self.ln(5)

        # Sermon title
        self.set_font("Helvetica", "B", FONT_SIZE_TITLE)
        self.set_text_color(*self.primary_color)
        self.multi_cell(0, 8, sermon_title)

        # Date and speaker
        if date or speaker:
            self.set_font("Helvetica", "", FONT_SIZE_SMALL)
            self.set_text_color(100, 100, 100)
            info_parts = []
            if date:
                info_parts.append(date)
            if speaker:
                info_parts.append(speaker)
            self.cell(0, 5, "  |  ".join(info_parts), ln=True)

        self.ln(5)

    def add_section(self, title: str, content, is_list: bool = False):
        """Add a section with title and content."""
        # Check if we need a new page
        if self.get_y() > PAGE_HEIGHT - 50:
            self.add_page()

        # Section title
        self.set_font("Helvetica", "B", FONT_SIZE_SECTION)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 7, title.upper(), ln=True)

        # Content
        self.set_font("Helvetica", "", FONT_SIZE_BODY)
        self.set_text_color(40, 40, 40)

        if is_list and isinstance(content, list):
            for i, item in enumerate(content, 1):
                self.set_x(MARGIN_LEFT + 3)
                self.set_font("Helvetica", "B", FONT_SIZE_BODY)
                self.cell(8, 6, f"{i}.")
                self.set_font("Helvetica", "", FONT_SIZE_BODY)
                available_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT - 11
                self.multi_cell(available_width, 6, str(item))
                self.ln(1)
        else:
            self.multi_cell(0, 6, str(content))

        self.ln(4)

    def add_scripture_box(self, reference: str, text: str):
        """Add a highlighted scripture box."""
        if self.get_y() > PAGE_HEIGHT - 60:
            self.add_page()

        # Section title
        self.set_font("Helvetica", "B", FONT_SIZE_SECTION)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 7, "SCRIPTURE FOCUS", ln=True)

        # Box background
        self.set_fill_color(255, 247, 237)  # Orange-50

        # Reference
        self.set_font("Helvetica", "B", FONT_SIZE_BODY)
        self.set_text_color(*self.primary_color)
        self.set_x(MARGIN_LEFT + 3)
        ref_cell_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT - 6
        self.multi_cell(ref_cell_width, 6, reference, fill=True)

        # Text
        if text:
            self.set_font("Helvetica", "I", FONT_SIZE_BODY)
            self.set_text_color(60, 60, 60)
            self.set_x(MARGIN_LEFT + 3)
            self.multi_cell(ref_cell_width, 6, f'"{text}"', fill=True)

        self.ln(6)

    def add_big_idea_box(self, big_idea: str):
        """Add a highlighted big idea box."""
        if self.get_y() > PAGE_HEIGHT - 50:
            self.add_page()

        # Section title
        self.set_font("Helvetica", "B", FONT_SIZE_SECTION)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 7, "THE BIG IDEA", ln=True)

        # Box with primary color background
        self.set_fill_color(*self.primary_color)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)

        box_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
        self.multi_cell(box_width, 8, big_idea, fill=True, align='C')

        self.ln(6)

    def add_bullet_section(self, title: str, items: list[str]):
        """Add a section with bullet points."""
        if self.get_y() > PAGE_HEIGHT - 50:
            self.add_page()

        # Section title
        self.set_font("Helvetica", "B", FONT_SIZE_SECTION)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 7, title.upper(), ln=True)

        # Bullet items
        self.set_font("Helvetica", "", FONT_SIZE_BODY)
        self.set_text_color(40, 40, 40)

        for item in items:
            self.set_x(MARGIN_LEFT + 3)
            self.cell(5, 6, "-")
            available_width = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT - 8
            self.multi_cell(available_width, 6, str(item))

        self.ln(4)

    def add_going_deeper(self, scriptures: list[dict]):
        """Add going deeper section with scripture references."""
        if not scriptures:
            return

        if self.get_y() > PAGE_HEIGHT - 30:
            self.add_page()

        # Section title
        self.set_font("Helvetica", "B", FONT_SIZE_SECTION)
        self.set_text_color(*self.secondary_color)
        self.cell(0, 7, "GOING DEEPER", ln=True)

        # Scripture references
        self.set_font("Helvetica", "", FONT_SIZE_SMALL)
        self.set_text_color(80, 80, 80)

        refs = [s.get("reference", "") for s in scriptures if s.get("reference")]
        self.cell(0, 5, "  |  ".join(refs), ln=True)

        self.ln(4)


def generate_discussion_guide_pdf(
    ai_content: dict,
    church_name: str,
    sermon_title: str,
    sermon_date: Optional[str] = None,
    speaker: Optional[str] = None,
    primary_color: str = "#ea580c",
    secondary_color: str = "#c2410c"
) -> bytes:
    """
    Generate a discussion guide PDF from AI content.

    Args:
        ai_content: AI-generated content dict
        church_name: Church name for branding
        sermon_title: Title of the sermon
        sermon_date: Date of the sermon (optional)
        speaker: Speaker name (optional)
        primary_color: Primary brand color (hex)
        secondary_color: Secondary brand color (hex)

    Returns:
        PDF file as bytes
    """
    pdf = DiscussionGuidePDF(
        church_name=church_name,
        primary_color=primary_color,
        secondary_color=secondary_color
    )

    # Header
    pdf.add_header(sermon_title, date=sermon_date, speaker=speaker)

    # Scripture Focus
    primary_scripture = ai_content.get("primary_scripture", {})
    if primary_scripture:
        pdf.add_scripture_box(
            primary_scripture.get("reference", "Scripture Reference"),
            primary_scripture.get("text", "")
        )

    # Big Idea
    big_idea = ai_content.get("big_idea", "")
    if big_idea:
        pdf.add_big_idea_box(big_idea)

    # Discussion Guide Content
    discussion_guide = ai_content.get("discussion_guide", {})

    # Icebreaker
    icebreaker = discussion_guide.get("icebreaker", "")
    if icebreaker:
        pdf.add_section("Icebreaker", icebreaker)

    # Discussion Questions
    questions = discussion_guide.get("questions", [])
    if questions:
        pdf.add_section("Discussion Questions", questions, is_list=True)

    # This Week's Challenge
    application = discussion_guide.get("application", "")
    if application:
        pdf.add_section("This Week's Challenge", application)

    # Prayer Focus
    prayer_points = discussion_guide.get("prayer_points", [])
    if prayer_points:
        pdf.add_bullet_section("Prayer Focus", prayer_points)

    # Going Deeper
    supporting_scriptures = ai_content.get("supporting_scriptures", [])
    if supporting_scriptures:
        pdf.add_going_deeper(supporting_scriptures)

    # Footer with branding
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, f"Generated by PreachCaster for {church_name}", align='C')

    # Return PDF as bytes
    return pdf.output()


def upload_pdf_to_gcs(
    pdf_bytes: bytes,
    church_slug: str,
    video_id: str
) -> str:
    """
    Upload discussion guide PDF to Google Cloud Storage.

    Args:
        pdf_bytes: PDF file content as bytes
        church_slug: Church slug for organization
        video_id: YouTube video ID

    Returns:
        Public URL of uploaded file
    """
    if not settings.gcs_bucket_name:
        raise Exception("GCS bucket not configured")

    try:
        client = storage.Client(project=settings.gcs_project_id)
        bucket = client.bucket(settings.gcs_bucket_name)

        # Organize by church: guides/{church_slug}/{video_id}_discussion_guide.pdf
        blob_name = f"guides/{church_slug}/{video_id}_discussion_guide.pdf"
        blob = bucket.blob(blob_name)

        # Upload
        blob.upload_from_string(
            pdf_bytes,
            content_type="application/pdf"
        )

        # Make publicly accessible
        blob.make_public()

        logger.info(f"Uploaded PDF to GCS: {blob.public_url}")
        return blob.public_url

    except Exception as e:
        raise Exception(f"GCS upload failed: {e}")


async def create_discussion_guide(
    ai_content: dict,
    church_name: str,
    church_slug: str,
    sermon_title: str,
    video_id: str,
    sermon_date: Optional[str] = None,
    speaker: Optional[str] = None
) -> dict:
    """
    Full discussion guide creation pipeline.

    1. Generate PDF from AI content
    2. Upload to cloud storage
    3. Return URL

    Args:
        ai_content: AI-generated content
        church_name: Church name for branding
        church_slug: Church slug for storage
        sermon_title: Sermon title
        video_id: YouTube video ID
        sermon_date: Optional date
        speaker: Optional speaker name

    Returns:
        dict with pdf_url
    """
    # Generate PDF
    pdf_bytes = generate_discussion_guide_pdf(
        ai_content=ai_content,
        church_name=church_name,
        sermon_title=sermon_title,
        sermon_date=sermon_date,
        speaker=speaker
    )

    # Upload to cloud storage
    pdf_url = upload_pdf_to_gcs(pdf_bytes, church_slug, video_id)

    return {
        "pdf_url": pdf_url,
        "video_id": video_id
    }
