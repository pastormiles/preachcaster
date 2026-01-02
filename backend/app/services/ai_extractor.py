"""
AI Content Extractor Service
Generates AI-powered content from sermon transcripts using OpenAI.

Adapted from CWI script 07_generate_ai_content_v1.py for SaaS architecture.

Generated Content:
- Summary (2-3 sentences for RSS feed)
- Big Idea (memorable one-liner)
- Primary Scripture reference
- Supporting Scripture references
- Topics/tags
- Discussion Guide (icebreaker, questions, application, prayer points)
"""

import json
import logging
from typing import Optional

from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Model pricing per 1M tokens (for cost tracking)
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}

DEFAULT_MODEL = "gpt-4o-mini"

# System prompt for sermon analysis
SYSTEM_PROMPT = """You are an expert at analyzing Christian sermon content. Your task is to extract key information and generate helpful content for church communications and small group discussions.

IMPORTANT GUIDELINES:
1. Be accurate with scripture references - verify book, chapter, and verse numbers are correct
2. Generate content that is theologically sound and practically applicable
3. Maintain the speaker's tone and intent in summaries
4. Create discussion questions that encourage genuine reflection, not just yes/no answers
5. Make application challenges specific and actionable

Always respond in valid JSON format with no markdown formatting or code blocks. Just raw JSON."""

# User prompt template
USER_PROMPT_TEMPLATE = """Analyze this sermon transcript and generate the following content:

1. SUMMARY: A 2-3 sentence summary suitable for a podcast description (third person)
2. BIG_IDEA: One memorable sentence capturing the main point (quotable format)
3. PRIMARY_SCRIPTURE: The main Bible passage referenced
   - Include "reference" (e.g., "Philippians 4:6-7")
   - Include "text" (the actual verse text, abbreviated if long)
4. SUPPORTING_SCRIPTURES: Up to 3 additional passages mentioned (array of objects with reference and text)
5. TOPICS: 3-5 single-word theme tags (lowercase, e.g., "grace", "prayer", "anxiety")
6. ICEBREAKER: A casual, non-threatening opening question for small group discussion
7. DISCUSSION_QUESTIONS: 5 thoughtful questions that reference specific sermon content
8. APPLICATION: A specific, actionable challenge for the week ahead
9. PRAYER_POINTS: 2-3 specific prayer focus items (array of strings)

SERMON TITLE: {title}

TRANSCRIPT:
{transcript_text}

Respond with valid JSON only, using this exact structure:
{{"summary": "...", "big_idea": "...", "primary_scripture": {{"reference": "...", "text": "..."}}, "supporting_scriptures": [{{"reference": "...", "text": "..."}}], "topics": ["...", "..."], "discussion_guide": {{"icebreaker": "...", "questions": ["...", "...", "...", "...", "..."], "application": "...", "prayer_points": ["...", "..."]}}}}"""


class AIExtractorError(Exception):
    """Exception raised when AI extraction fails."""
    pass


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.
    Rough estimate: ~4 characters per token for English text.
    """
    return len(text) // 4


def estimate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Calculate estimated API cost in USD."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def generate_ai_content(
    transcript_text: str,
    title: str,
    model: str = DEFAULT_MODEL,
    api_key: Optional[str] = None
) -> dict:
    """
    Generate AI content from sermon transcript.

    Args:
        transcript_text: Full transcript text
        title: Sermon title
        model: OpenAI model to use
        api_key: OpenAI API key (uses settings if not provided)

    Returns:
        dict with generated content:
            - summary
            - big_idea
            - primary_scripture
            - supporting_scriptures
            - topics
            - discussion_guide (icebreaker, questions, application, prayer_points)
            - tokens_used
            - estimated_cost_usd

    Raises:
        AIExtractorError: If generation fails
    """
    api_key = api_key or settings.openai_api_key
    if not api_key:
        raise AIExtractorError("OpenAI API key not configured")

    # Truncate very long transcripts (GPT-4 has ~128k context)
    max_chars = 100000  # ~25k tokens
    if len(transcript_text) > max_chars:
        logger.warning(f"Truncating transcript from {len(transcript_text)} to {max_chars} chars")
        transcript_text = transcript_text[:max_chars] + "\n\n[Transcript truncated...]"

    # Build the prompt
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        transcript_text=transcript_text
    )

    # Estimate input tokens for cost tracking
    full_prompt = SYSTEM_PROMPT + user_prompt
    estimated_input_tokens = estimate_tokens(full_prompt)

    logger.info(f"Generating AI content for '{title}' (~{estimated_input_tokens} input tokens)")

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        # Extract response content
        content = response.choices[0].message.content

        # Get usage stats
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens
        }

        # Parse JSON response
        try:
            ai_content = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Response content: {content[:500]}...")
            raise AIExtractorError(f"AI returned invalid JSON: {e}")

        # Calculate cost
        cost = estimate_cost(
            usage["prompt_tokens"],
            usage["completion_tokens"],
            model
        )

        # Add metadata
        ai_content["model"] = model
        ai_content["tokens_used"] = usage
        ai_content["estimated_cost_usd"] = cost

        logger.info(f"AI content generated: {usage['total_tokens']} tokens, ${cost:.4f}")

        return ai_content

    except Exception as e:
        if "AIExtractorError" in str(type(e)):
            raise
        raise AIExtractorError(f"OpenAI API error: {e}")


def extract_scripture_references(text: str) -> list[str]:
    """
    Extract Bible references from text using pattern matching.
    Fallback method when AI extraction fails.

    Args:
        text: Text to search for scripture references

    Returns:
        List of scripture reference strings
    """
    import re

    # Pattern for common Bible reference formats
    pattern = r'\b(\d?\s*[A-Z][a-z]+)\s+(\d+)(?::(\d+)(?:-(\d+))?)?\b'

    # Common Bible book names
    books = {
        "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
        "Joshua", "Judges", "Ruth", "Samuel", "Kings", "Chronicles",
        "Ezra", "Nehemiah", "Esther", "Job", "Psalm", "Psalms",
        "Proverbs", "Ecclesiastes", "Song", "Isaiah", "Jeremiah",
        "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
        "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah",
        "Haggai", "Zechariah", "Malachi",
        "Matthew", "Mark", "Luke", "John", "Acts", "Romans",
        "Corinthians", "Galatians", "Ephesians", "Philippians",
        "Colossians", "Thessalonians", "Timothy", "Titus", "Philemon",
        "Hebrews", "James", "Peter", "Jude", "Revelation"
    }

    references = []
    matches = re.findall(pattern, text)

    for match in matches:
        book = match[0].strip()
        if any(b.lower() in book.lower() for b in books):
            chapter = match[1]
            verse_start = match[2] if match[2] else ""
            verse_end = match[3] if match[3] else ""

            if verse_start and verse_end:
                ref = f"{book} {chapter}:{verse_start}-{verse_end}"
            elif verse_start:
                ref = f"{book} {chapter}:{verse_start}"
            else:
                ref = f"{book} {chapter}"

            references.append(ref)

    return list(set(references))  # Remove duplicates


def generate_simple_summary(text: str, max_sentences: int = 3) -> str:
    """
    Generate a simple extractive summary without AI.
    Fallback method when AI extraction fails or is not configured.

    Args:
        text: Full text to summarize
        max_sentences: Maximum sentences in summary

    Returns:
        Simple summary string
    """
    # Split into sentences
    import re
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

    if not sentences:
        return ""

    # Return first few sentences as summary
    summary_sentences = sentences[:max_sentences]
    return ". ".join(summary_sentences) + "."


def format_transcript(
    raw_transcript: str,
    api_key: Optional[str] = None
) -> str:
    """
    Use AI to format raw transcript into proper sentences and paragraphs.

    YouTube auto-transcripts are often a stream of text without punctuation.
    This function adds proper capitalization, punctuation, and paragraph breaks.

    Args:
        raw_transcript: Raw transcript text from YouTube
        api_key: OpenAI API key (uses settings if not provided)

    Returns:
        Properly formatted transcript text
    """
    api_key = api_key or settings.openai_api_key
    if not api_key:
        logger.warning("OpenAI not configured, returning raw transcript")
        return raw_transcript

    # For very short transcripts, don't bother
    if len(raw_transcript) < 500:
        return raw_transcript

    # Truncate if too long (process in chunks for very long transcripts)
    max_chars = 30000  # ~7500 tokens, leaving room for response
    if len(raw_transcript) > max_chars:
        # Process in chunks
        chunks = [raw_transcript[i:i+max_chars] for i in range(0, len(raw_transcript), max_chars)]
        formatted_chunks = []
        for chunk in chunks:
            formatted_chunks.append(_format_transcript_chunk(chunk, api_key))
        return "\n\n".join(formatted_chunks)

    return _format_transcript_chunk(raw_transcript, api_key)


def _format_transcript_chunk(text: str, api_key: str) -> str:
    """Format a single chunk of transcript text."""
    format_prompt = """Format this raw transcript into proper written English. Add:
1. Proper capitalization
2. Punctuation (periods, commas, question marks)
3. Paragraph breaks where topics change or natural pauses occur
4. Remove filler words like "um", "uh", "you know" if excessive

Keep the content exactly the same - just improve the formatting for readability.
Do NOT summarize or shorten the text. Return the full formatted transcript.

RAW TRANSCRIPT:
{text}

FORMATTED TRANSCRIPT:"""

    try:
        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cheap for formatting
            messages=[
                {"role": "user", "content": format_prompt.format(text=text)}
            ],
            temperature=0.3,  # Low temperature for consistent formatting
            max_tokens=8000
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"Transcript formatting failed: {e}")
        return text  # Return original if formatting fails


async def process_sermon_ai_content(
    transcript_text: str,
    title: str,
    video_id: str
) -> dict:
    """
    Full AI content processing for a sermon.

    Args:
        transcript_text: Full transcript text
        title: Sermon title
        video_id: YouTube video ID for reference

    Returns:
        dict with all generated AI content
    """
    if not settings.openai_api_key:
        logger.warning("OpenAI not configured, using fallback extraction")
        return {
            "video_id": video_id,
            "title": title,
            "summary": generate_simple_summary(transcript_text),
            "big_idea": None,
            "primary_scripture": None,
            "supporting_scriptures": extract_scripture_references(transcript_text),
            "topics": [],
            "discussion_guide": None,
            "ai_generated": False
        }

    content = generate_ai_content(transcript_text, title)
    content["video_id"] = video_id
    content["title"] = title
    content["ai_generated"] = True

    return content
