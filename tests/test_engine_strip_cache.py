"""Assistant-text post-processing — cache paths stripped."""

from __future__ import annotations

from alpi.engine import _strip_cache_noise


def test_strips_tts_path_line() -> None:
    text = (
        "Hecho. \"hola\" en audio.\n"
        "Archivo: /Users/javi/.alpi/cache/tts/f13a84f27d75c79f.mp3.\n"
        "Explicación: es un saludo."
    )
    out = _strip_cache_noise(text)
    assert "Archivo:" not in out
    assert "cache/tts" not in out
    assert "Hecho" in out
    assert "Explicación" in out


def test_strips_profiled_path() -> None:
    text = "played at /Users/x/.alpi/profiles/alf/cache/tts/abc.mp3 now"
    assert _strip_cache_noise(text) == ""


def test_strips_stt_path() -> None:
    text = "transcription at /Users/x/.alpi/cache/stt/clip.wav done"
    assert _strip_cache_noise(text) == ""


def test_leaves_unrelated_text_alone() -> None:
    text = "The answer is 42 and there's no noise here."
    assert _strip_cache_noise(text) == text


def test_strips_only_offending_lines_in_multiline() -> None:
    text = (
        "Line one.\n"
        "/Users/javi/.alpi/cache/tts/xx.mp3\n"
        "Line three.\n"
        "Also /Users/javi/.alpi/cache/tts/yy.ogg inline\n"
        "Final line."
    )
    out = _strip_cache_noise(text)
    assert "Line one." in out
    assert "Line three." in out
    assert "Final line." in out
    assert "cache/tts" not in out
