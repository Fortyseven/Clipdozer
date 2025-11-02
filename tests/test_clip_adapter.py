from app.media.clip_adapter import ClipAdapter
from moviepy import ColorClip


def test_clip_adapter_basic(tmp_path):
    video_path = tmp_path / "color.mp4"
    clip = ColorClip(size=(32, 32), color=(0, 255, 0), duration=0.5)
    clip.write_videofile(str(video_path), fps=24)
    clip.close()
    adapter = ClipAdapter.from_path(str(video_path))
    assert adapter.duration == 0.5
    frame = adapter.get_frame(0.1)
    assert frame.shape[0] == 32 and frame.shape[1] == 32
    audio = adapter.audio_array()
    assert audio is None  # ColorClip has no audio
    adapter.clip.close()
