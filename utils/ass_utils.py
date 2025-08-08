"""
Advanced SubStation Alpha (ASS) subtitle utilities
Copyright (c) 2025 SparkAudio
Licensed under the Apache License, Version 2.0

This module generates ASS format subtitles with word-level timing
for use with ffmpeg and video players.
"""

import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


class ASSGenerator:
    """
    Generates Advanced SubStation Alpha (ASS) subtitles with word-level timing.
    """

    def __init__(self):
        """Initialize ASS generator with default styling."""
        self.default_style = {
            "fontname": "Arial",
            "fontsize": 24,
            "primary_colour": "&H00FFFFFF",  # White
            "secondary_colour": "&H000000FF",  # Blue
            "outline_colour": "&H00000000",  # Black
            "back_colour": "&H80000000",  # Semi-transparent black
            "bold": 0,
            "italic": 0,
            "underline": 0,
            "strikeout": 0,
            "scale_x": 100,
            "scale_y": 100,
            "spacing": 0,
            "angle": 0,
            "border_style": 1,
            "outline": 2,
            "shadow": 2,
            "alignment": 2,  # Bottom center
            "margin_l": 10,
            "margin_r": 10,
            "margin_v": 10,
            "encoding": 1,
        }

        # Karaoke highlighting style
        self.karaoke_style = self.default_style.copy()
        self.karaoke_style.update(
            {
                "fontname": "Arial",
                "fontsize": 26,
                "primary_colour": "&H0000FFFF",  # Yellow
                "secondary_colour": "&H00FFFFFF",  # White
                "bold": 1,
                "outline": 3,
                "shadow": 0,
            }
        )

    def _format_time(self, seconds: float) -> str:
        """
        Convert seconds to ASS time format (H:MM:SS.CC).

        Args:
            seconds: Time in seconds

        Returns:
            str: ASS formatted time string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        centiseconds = int((seconds % 1) * 100)

        return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"

    def _escape_ass_text(self, text: str) -> str:
        """
        Escape special characters for ASS format.

        Args:
            text: Input text

        Returns:
            str: Escaped text
        """
        # Replace curly braces and backslashes
        text = text.replace("\\", "\\\\")
        text = text.replace("{", "\\{")
        text = text.replace("}", "\\}")

        # Convert newlines to ASS line breaks
        text = text.replace("\n", "\\N")
        text = text.replace("\r", "")

        return text

    def _create_ass_header(self, title: str = "SparkTTS Generated Subtitles") -> str:
        """
        Create ASS file header with script info and styles.

        Args:
            title: Title for the subtitle file

        Returns:
            str: ASS header content
        """
        header = f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayDepth: 0
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""

        # Add default style
        style_line = (
            f"Style: Default,{self.default_style['fontname']},{self.default_style['fontsize']},"
            f"{self.default_style['primary_colour']},{self.default_style['secondary_colour']},"
            f"{self.default_style['outline_colour']},{self.default_style['back_colour']},"
            f"{self.default_style['bold']},{self.default_style['italic']},"
            f"{self.default_style['underline']},{self.default_style['strikeout']},"
            f"{self.default_style['scale_x']},{self.default_style['scale_y']},"
            f"{self.default_style['spacing']},{self.default_style['angle']},"
            f"{self.default_style['border_style']},{self.default_style['outline']},"
            f"{self.default_style['shadow']},{self.default_style['alignment']},"
            f"{self.default_style['margin_l']},{self.default_style['margin_r']},"
            f"{self.default_style['margin_v']},{self.default_style['encoding']}"
        )

        # Add karaoke style
        karaoke_style_line = (
            f"Style: Karaoke,{self.karaoke_style['fontname']},{self.karaoke_style['fontsize']},"
            f"{self.karaoke_style['primary_colour']},{self.karaoke_style['secondary_colour']},"
            f"{self.karaoke_style['outline_colour']},{self.karaoke_style['back_colour']},"
            f"{self.karaoke_style['bold']},{self.karaoke_style['italic']},"
            f"{self.karaoke_style['underline']},{self.karaoke_style['strikeout']},"
            f"{self.karaoke_style['scale_x']},{self.karaoke_style['scale_y']},"
            f"{self.karaoke_style['spacing']},{self.karaoke_style['angle']},"
            f"{self.karaoke_style['border_style']},{self.karaoke_style['outline']},"
            f"{self.karaoke_style['shadow']},{self.karaoke_style['alignment']},"
            f"{self.karaoke_style['margin_l']},{self.karaoke_style['margin_r']},"
            f"{self.karaoke_style['margin_v']},{self.karaoke_style['encoding']}"
        )

        header += style_line + "\n" + karaoke_style_line + "\n\n"

        # Events section header
        header += """[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text

"""

        return header

    def _group_words_into_lines(
        self,
        word_timings: List[Dict[str, Any]],
        max_line_length: int = 50,
        max_line_duration: float = 5.0,
    ) -> List[List[Dict[str, Any]]]:
        """
        Group words into subtitle lines based on timing and length.

        Args:
            word_timings: List of word timing dictionaries
            max_line_length: Maximum characters per line
            max_line_duration: Maximum duration per line in seconds

        Returns:
            List[List[Dict]]: Grouped words for each line
        """
        if not word_timings:
            return []

        lines = []
        current_line = []
        current_length = 0
        line_start_time = word_timings[0]["start"]

        for word_info in word_timings:
            word = word_info["word"].strip()
            word_length = len(word) + 1  # Include space
            word_duration = word_info["end"] - line_start_time

            # Check if we should start a new line
            should_break = (
                (current_length + word_length > max_line_length)
                or (word_duration > max_line_duration)
                or (word.endswith(".") or word.endswith("!") or word.endswith("?"))
            )

            if current_line and should_break:
                # Finish current line
                lines.append(current_line)
                current_line = [word_info]
                current_length = word_length
                line_start_time = word_info["start"]
            else:
                # Add to current line
                current_line.append(word_info)
                current_length += word_length

        # Add the last line
        if current_line:
            lines.append(current_line)

        logger.info(
            f"Grouped {len(word_timings)} words into {len(lines)} subtitle lines"
        )
        return lines

    def _create_karaoke_effect(
        self, words: List[Dict[str, Any]]
    ) -> Tuple[str, float, float]:
        """
        Create karaoke effect text with timing tags.

        Args:
            words: List of word timing dictionaries for this line

        Returns:
            Tuple[str, float, float]: (karaoke_text, start_time, end_time)
        """
        if not words:
            return "", 0.0, 0.0

        start_time = words[0]["start"]
        end_time = words[-1]["end"]

        # Build karaoke text with \\k tags
        karaoke_text = ""

        for i, word_info in enumerate(words):
            word = word_info["word"].strip()
            word_start = word_info["start"]
            word_end = word_info["end"]

            # Calculate duration in centiseconds
            duration_cs = int((word_end - word_start) * 100)

            # Add karaoke timing tag
            karaoke_text += f"{{\\k{duration_cs}}}{self._escape_ass_text(word)}"

            # Add space between words (except for the last word)
            if i < len(words) - 1:
                karaoke_text += " "

        return karaoke_text, start_time, end_time

    def generate(
        self,
        text: str,
        word_timings: List[Dict[str, Any]],
        title: str = "SparkTTS Generated Subtitles",
        include_karaoke: bool = True,
        max_line_length: int = 50,
        max_line_duration: float = 5.0,
    ) -> str:
        """
        Generate ASS subtitle file content.

        Args:
            text: Full text content
            word_timings: Word-level timing information from WhisperX
            title: Title for the subtitle file
            include_karaoke: Whether to include karaoke-style word highlighting
            max_line_length: Maximum characters per line
            max_line_duration: Maximum duration per line in seconds

        Returns:
            str: Complete ASS file content
        """
        try:
            logger.info("Generating ASS subtitles...")

            # Start with header
            ass_content = self._create_ass_header(title)

            if not word_timings:
                logger.warning("No word timings provided, creating simple subtitle")
                # Create a simple subtitle for the entire text
                escaped_text = self._escape_ass_text(text)
                line = f"Dialogue: 0,0:00:00.00,0:00:05.00,Default,,0,0,0,,{escaped_text}\n"
                ass_content += line
                return ass_content

            # Group words into subtitle lines
            word_lines = self._group_words_into_lines(
                word_timings, max_line_length, max_line_duration
            )

            # Generate subtitle lines
            for line_words in word_lines:
                if not line_words:
                    continue

                # Create regular subtitle line
                start_time = self._format_time(line_words[0]["start"])
                end_time = self._format_time(line_words[-1]["end"])

                # Build line text
                line_text = " ".join([word["word"].strip() for word in line_words])
                escaped_text = self._escape_ass_text(line_text)

                # Add regular dialogue line
                dialogue_line = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{escaped_text}\n"
                ass_content += dialogue_line

                # Add karaoke line if requested
                if include_karaoke:
                    karaoke_text, k_start, k_end = self._create_karaoke_effect(
                        line_words
                    )
                    k_start_time = self._format_time(k_start)
                    k_end_time = self._format_time(k_end)

                    karaoke_line = f"Dialogue: 1,{k_start_time},{k_end_time},Karaoke,,0,0,0,,{karaoke_text}\n"
                    ass_content += karaoke_line

            logger.info(f"Generated ASS subtitles with {len(word_lines)} lines")
            return ass_content

        except Exception as e:
            logger.error(f"Failed to generate ASS subtitles: {str(e)}")
            raise

    def generate_simple(
        self,
        text: str,
        duration: float = None,
        title: str = "SparkTTS Generated Subtitles",
    ) -> str:
        """
        Generate simple ASS subtitles without word-level timing.

        Args:
            text: Text content
            duration: Duration in seconds (defaults to 5 seconds)
            title: Title for the subtitle file

        Returns:
            str: Complete ASS file content
        """
        if duration is None:
            # Estimate duration based on text length (rough estimate)
            duration = max(3.0, len(text) * 0.1)

        try:
            logger.info("Generating simple ASS subtitles...")

            # Start with header
            ass_content = self._create_ass_header(title)

            # Split text into lines if it's too long
            max_line_length = 50
            words = text.split()
            lines = []
            current_line = []
            current_length = 0

            for word in words:
                if current_length + len(word) + 1 > max_line_length and current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)
                else:
                    current_line.append(word)
                    current_length += len(word) + 1

            if current_line:
                lines.append(" ".join(current_line))

            # Calculate timing for each line
            line_duration = duration / len(lines) if lines else duration

            for i, line_text in enumerate(lines):
                start_time = self._format_time(i * line_duration)
                end_time = self._format_time((i + 1) * line_duration)

                escaped_text = self._escape_ass_text(line_text)
                dialogue_line = f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{escaped_text}\n"
                ass_content += dialogue_line

            logger.info(f"Generated simple ASS subtitles with {len(lines)} lines")
            return ass_content

        except Exception as e:
            logger.error(f"Failed to generate simple ASS subtitles: {str(e)}")
            raise

    def validate_ass_content(self, ass_content: str) -> Dict[str, Any]:
        """
        Validate ASS content and return statistics.

        Args:
            ass_content: ASS file content

        Returns:
            Dict: Validation results and statistics
        """
        try:
            lines = ass_content.split("\n")

            # Count sections
            sections = {"script_info": False, "styles": False, "events": False}

            dialogue_count = 0
            total_duration = 0.0

            for line in lines:
                line = line.strip()

                if line.startswith("[Script Info]"):
                    sections["script_info"] = True
                elif line.startswith("[V4+ Styles]"):
                    sections["styles"] = True
                elif line.startswith("[Events]"):
                    sections["events"] = True
                elif line.startswith("Dialogue:"):
                    dialogue_count += 1

                    # Extract timing information
                    try:
                        parts = line.split(",")
                        if len(parts) >= 3:
                            start_str = parts[1]
                            end_str = parts[2]

                            # Convert to seconds for duration calculation
                            start_seconds = self._parse_ass_time(start_str)
                            end_seconds = self._parse_ass_time(end_str)
                            total_duration = max(total_duration, end_seconds)
                    except (ValueError, IndexError):
                        pass

            # Validation results
            is_valid = all(sections.values()) and dialogue_count > 0

            results = {
                "is_valid": is_valid,
                "sections_present": sections,
                "dialogue_lines": dialogue_count,
                "total_duration_seconds": total_duration,
                "total_duration_formatted": self._format_time(total_duration),
                "file_size_bytes": len(ass_content.encode("utf-8")),
            }

            logger.info(
                f"ASS validation: {dialogue_count} lines, {total_duration:.2f}s duration, valid={is_valid}"
            )
            return results

        except Exception as e:
            logger.error(f"ASS validation failed: {str(e)}")
            return {"is_valid": False, "error": str(e)}

    def _parse_ass_time(self, time_str: str) -> float:
        """
        Parse ASS time format to seconds.

        Args:
            time_str: ASS time string (H:MM:SS.CC)

        Returns:
            float: Time in seconds
        """
        try:
            # Format: H:MM:SS.CC
            parts = time_str.split(":")
            hours = int(parts[0])
            minutes = int(parts[1])

            seconds_parts = parts[2].split(".")
            seconds = int(seconds_parts[0])
            centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

            total_seconds = hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0
            return total_seconds

        except (ValueError, IndexError):
            return 0.0


# Convenience functions
def generate_ass_subtitles(
    text: str,
    word_timings: List[Dict[str, Any]] = None,
    title: str = "SparkTTS Generated Subtitles",
    include_karaoke: bool = True,
) -> str:
    """
    Generate ASS subtitles from text and optional word timings.

    Args:
        text: Full text content
        word_timings: Optional word-level timing information
        title: Title for the subtitle file
        include_karaoke: Whether to include karaoke-style highlighting

    Returns:
        str: Complete ASS file content
    """
    generator = ASSGenerator()

    if word_timings:
        return generator.generate(text, word_timings, title, include_karaoke)
    else:
        return generator.generate_simple(text, title=title)


def validate_ass_file(ass_content: str) -> Dict[str, Any]:
    """
    Validate ASS file content.

    Args:
        ass_content: ASS file content

    Returns:
        Dict: Validation results
    """
    generator = ASSGenerator()
    return generator.validate_ass_content(ass_content)
