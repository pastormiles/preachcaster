"""
RSS Feed Generator
Creates podcast-compatible RSS feeds for sermon distribution.

Generates RSS 2.0 feeds with iTunes/Apple Podcasts extensions.
Compatible with: Apple Podcasts, Spotify, Google Podcasts, Overcast, etc.
"""

import logging
from datetime import datetime
from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from app.models import Church, PodcastSettings, Sermon, SermonStatus

logger = logging.getLogger(__name__)

# iTunes namespace
ITUNES_NS = "http://www.itunes.com/dtds/podcast-1.0.dtd"

# Podcast categories for iTunes
ITUNES_CATEGORIES = {
    "Religion & Spirituality": [
        "Christianity",
        "Buddhism",
        "Hinduism",
        "Islam",
        "Judaism",
        "Religion",
        "Spirituality"
    ],
    "Society & Culture": [
        "Philosophy",
        "Personal Journals",
        "Places & Travel",
        "Relationships"
    ],
    "Education": [
        "Self Improvement",
        "Courses",
        "How To",
        "Language Learning"
    ]
}


def format_rfc2822_date(dt: Optional[datetime]) -> str:
    """Format datetime as RFC 2822 for RSS pubDate."""
    if dt is None:
        dt = datetime.utcnow()
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def format_duration(seconds: Optional[int]) -> str:
    """Format duration for iTunes (HH:MM:SS)."""
    if not seconds:
        return "00:00:00"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def escape_xml(text: str) -> str:
    """Escape special characters for XML."""
    if text is None:
        return ""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def generate_rss_feed(
    church: Church,
    podcast_settings: PodcastSettings,
    sermons: list[Sermon],
    base_url: str = "https://preachcaster.com"
) -> str:
    """
    Generate a podcast RSS feed for a church.

    Args:
        church: Church model instance
        podcast_settings: PodcastSettings model instance
        sermons: List of published Sermon instances
        base_url: Base URL for the PreachCaster site

    Returns:
        XML string of the RSS feed
    """
    # Create root RSS element
    rss = Element("rss")
    rss.set("version", "2.0")
    rss.set("xmlns:itunes", ITUNES_NS)
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")

    # Required channel elements
    SubElement(channel, "title").text = podcast_settings.title or f"{church.name} Sermons"
    SubElement(channel, "link").text = podcast_settings.website_url or f"{base_url}/{church.slug}"
    SubElement(channel, "description").text = (
        podcast_settings.description or
        f"Sermons and teachings from {church.name}"
    )
    SubElement(channel, "language").text = podcast_settings.language or "en-us"

    # Atom self-link (required by some validators)
    feed_url = f"{base_url}/feed/{church.slug}.xml"
    atom_link = SubElement(channel, "{http://www.w3.org/2005/Atom}link")
    atom_link.set("href", feed_url)
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    # Last build date
    SubElement(channel, "lastBuildDate").text = format_rfc2822_date(datetime.utcnow())

    # iTunes-specific channel elements
    itunes_author = SubElement(channel, "{%s}author" % ITUNES_NS)
    itunes_author.text = podcast_settings.author or church.name

    itunes_summary = SubElement(channel, "{%s}summary" % ITUNES_NS)
    itunes_summary.text = (
        podcast_settings.description or
        f"Sermons and teachings from {church.name}"
    )

    # iTunes owner
    itunes_owner = SubElement(channel, "{%s}owner" % ITUNES_NS)
    SubElement(itunes_owner, "{%s}name" % ITUNES_NS).text = podcast_settings.author or church.name
    SubElement(itunes_owner, "{%s}email" % ITUNES_NS).text = (
        podcast_settings.email or "podcast@preachcaster.com"
    )

    # iTunes image (artwork)
    if podcast_settings.artwork_url:
        itunes_image = SubElement(channel, "{%s}image" % ITUNES_NS)
        itunes_image.set("href", podcast_settings.artwork_url)

        # Also add standard RSS image
        image = SubElement(channel, "image")
        SubElement(image, "url").text = podcast_settings.artwork_url
        SubElement(image, "title").text = podcast_settings.title or church.name
        SubElement(image, "link").text = podcast_settings.website_url or f"{base_url}/{church.slug}"

    # iTunes category
    category = podcast_settings.category or "Religion & Spirituality"
    subcategory = podcast_settings.subcategory or "Christianity"

    itunes_category = SubElement(channel, "{%s}category" % ITUNES_NS)
    itunes_category.set("text", category)
    if subcategory:
        itunes_subcat = SubElement(itunes_category, "{%s}category" % ITUNES_NS)
        itunes_subcat.set("text", subcategory)

    # iTunes explicit (clean content)
    SubElement(channel, "{%s}explicit" % ITUNES_NS).text = "false"

    # iTunes type (episodic for sermons)
    SubElement(channel, "{%s}type" % ITUNES_NS).text = "episodic"

    # Add episodes (items)
    for sermon in sermons:
        if sermon.status != SermonStatus.PUBLISHED.value:
            continue
        if not sermon.audio_url:
            continue

        item = SubElement(channel, "item")

        # Basic item info
        SubElement(item, "title").text = sermon.title

        # Link to sermon page
        sermon_url = f"{base_url}/{church.slug}/sermons/{sermon.slug}"
        SubElement(item, "link").text = sermon_url

        # Description with HTML content
        description = sermon.summary or sermon.description or ""
        SubElement(item, "description").text = description

        # Content:encoded for full HTML
        if sermon.summary:
            content_html = f"<p>{escape_xml(sermon.summary)}</p>"
            if sermon.big_idea:
                content_html += f"<p><strong>The Big Idea:</strong> {escape_xml(sermon.big_idea)}</p>"
            content_encoded = SubElement(item, "{http://purl.org/rss/1.0/modules/content/}encoded")
            content_encoded.text = content_html

        # Enclosure (audio file) - REQUIRED for podcasts
        enclosure = SubElement(item, "enclosure")
        enclosure.set("url", sermon.audio_url)
        enclosure.set("type", "audio/mpeg")
        # File size in bytes (estimate if not available)
        file_size = str(sermon.duration_seconds * 16000) if sermon.duration_seconds else "0"
        enclosure.set("length", file_size)

        # GUID (unique identifier)
        guid = SubElement(item, "guid")
        guid.set("isPermaLink", "false")
        guid.text = f"preachcaster-{church.id}-{sermon.youtube_video_id}"

        # Publication date
        pub_date = sermon.sermon_date or sermon.published_at or sermon.created_at
        SubElement(item, "pubDate").text = format_rfc2822_date(pub_date)

        # iTunes episode info
        SubElement(item, "{%s}title" % ITUNES_NS).text = sermon.title
        SubElement(item, "{%s}summary" % ITUNES_NS).text = description[:4000]  # iTunes limit

        if sermon.duration_seconds:
            SubElement(item, "{%s}duration" % ITUNES_NS).text = format_duration(sermon.duration_seconds)

        SubElement(item, "{%s}explicit" % ITUNES_NS).text = "false"
        SubElement(item, "{%s}episodeType" % ITUNES_NS).text = "full"

        # iTunes image for episode (if different from channel)
        # Could use video thumbnail here

    # Convert to string with pretty printing
    xml_string = tostring(rss, encoding="unicode")

    # Parse and pretty print
    dom = minidom.parseString(xml_string)
    pretty_xml = dom.toprettyxml(indent="  ")

    # Remove extra declaration line
    lines = pretty_xml.split('\n')
    if lines[0].startswith('<?xml'):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'

    return '\n'.join(lines)


def validate_feed(xml_string: str) -> tuple[bool, list[str]]:
    """
    Validate RSS feed for common issues.

    Args:
        xml_string: RSS feed XML string

    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    issues = []

    # Check for required elements
    required_checks = [
        ("<title>", "Missing channel title"),
        ("<description>", "Missing channel description"),
        ("<enclosure", "No audio enclosures found"),
        ("itunes:image", "Missing iTunes artwork"),
        ("itunes:category", "Missing iTunes category"),
    ]

    for check, message in required_checks:
        if check not in xml_string:
            issues.append(message)

    # Check for common issues
    if "http://" in xml_string and "https://" not in xml_string:
        issues.append("Warning: Using HTTP instead of HTTPS for URLs")

    return len(issues) == 0, issues
