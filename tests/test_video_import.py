import os
from moviepy import VideoFileClip, ColorClip


def create_temp_clip(path: str):
    clip = ColorClip(size=(64, 64), color=(255, 0, 0), duration=1.0)
    # moviepy 2.x signature simplified; remove verbose/logger
    clip.write_videofile(path, fps=24)
    clip.close()


def test_import_first_frame(tmp_path="/tmp/clipdozer_test"):
    os.makedirs(tmp_path, exist_ok=True)
    video_path = os.path.join(tmp_path, "red.mp4")
    create_temp_clip(video_path)
    clip = VideoFileClip(video_path)
    frame = clip.get_frame(0)
    assert frame.shape[0] == 64 and frame.shape[1] == 64
    clip.close()


if __name__ == "__main__":
    test_import_first_frame()
    print("test_import_first_frame passed")
