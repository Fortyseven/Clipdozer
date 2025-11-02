from moviepy import VideoFileClip, ColorClip


def create_temp_clip(path: str):
    clip = ColorClip(size=(64, 64), color=(255, 0, 0), duration=1.0)
    clip.write_videofile(path, fps=24)
    clip.close()


def test_import_first_frame(tmp_path):
    video_path = tmp_path / "red.mp4"
    create_temp_clip(str(video_path))
    clip = VideoFileClip(str(video_path))
    frame = clip.get_frame(0)
    assert frame.shape[0] == 64 and frame.shape[1] == 64
    clip.close()
