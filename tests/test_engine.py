from tts.engine import DEFAULT_VOICE_ID, VOICES, TTSEngine


def test_default_voice_in_registry():
    assert DEFAULT_VOICE_ID in VOICES


def test_at_least_three_languages():
    languages = {vid.split("_", 1)[0] for vid in VOICES}
    assert len(languages) >= 3


def test_voice_id_format():
    for voice_id in VOICES:
        parts = voice_id.split("-")
        assert len(parts) >= 3, f"unexpected voice id format: {voice_id}"
        lang_region = parts[0]
        assert "_" in lang_region


def test_all_voices_have_human_names():
    for voice_id, name in VOICES.items():
        assert name, f"empty display name for {voice_id}"
        assert len(name) > 3


def test_engine_constructs_without_models():
    engine = TTSEngine()
    assert isinstance(engine.available_voices(), list)


def test_engine_unknown_voice_raises():
    import pytest

    engine = TTSEngine()
    with pytest.raises(FileNotFoundError):
        engine.synthesize_to_wav_bytes("hi", voice_id="nonexistent_voice")


def test_advertised_counts_match_reality():
    """The README and the page header both quote these numbers; they claimed
    seven languages while the registry held eight."""
    import pathlib

    from tts.normalize import language_for_voice

    languages = {language_for_voice(vid) for vid in VOICES}
    claim = f"{len(VOICES)} voices, {len(languages)} languages"
    readme = pathlib.Path("README.md").read_text(encoding="utf-8")
    assert claim in readme, f"README does not say {claim!r}"

    page = pathlib.Path("templates/index.html").read_text(encoding="utf-8")
    tagline = f"{len(VOICES)} neural voices &middot; {len(languages)} languages"
    assert tagline in page, f"page header does not say {tagline!r}"


def test_every_voice_has_a_download_entry():
    """A voice in the registry with no download entry can never be installed,
    and would surface as a 503 the operator cannot fix."""
    from download_model import VOICES as DOWNLOADS

    downloadable = {voice_id for voice_id, _path in DOWNLOADS}
    missing = set(VOICES) - downloadable
    assert not missing, f"no download entry for: {sorted(missing)}"


def test_download_paths_match_voice_ids():
    """The remote path and the file name are derived separately; a mismatch is
    how the Russian voice 404'd on every download."""
    from download_model import VOICES as DOWNLOADS

    for voice_id, path in DOWNLOADS:
        locale, speaker, quality = (
            voice_id.split("-")[0],
            voice_id.split("-")[1],
            voice_id.split("-")[-1],
        )
        expected = f"{locale.split('_')[0]}/{locale}/{speaker}/{quality}"
        assert path == expected, f"{voice_id}: path {path!r} should be {expected!r}"
