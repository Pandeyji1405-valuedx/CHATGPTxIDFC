import io
import pytest

def test_speech_synthesize_endpoint(client, auth_headers_user1):
    res = client.post("/api/speech/synthesize", json={
        "text": "According to RBI guidelines, NEFT operates 24x7 across 48 batches."
    }, headers=auth_headers_user1)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"

def test_speech_transcribe_endpoint(client, auth_headers_user1):
    fake_audio = io.BytesIO(b"RIFF....WAVEfmt ....data....")
    res = client.post(
        "/api/speech/transcribe",
        files={"file": ("audio_sample.wav", fake_audio, "audio/wav")},
        headers=auth_headers_user1
    )
    assert res.status_code == 200
    data = res.json()
    assert "transcript" in data
    assert data["status"] == "ready_for_review"
