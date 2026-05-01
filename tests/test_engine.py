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
