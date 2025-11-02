from app.core.project import Project, ClipDescriptor


def test_project_add_remove(tmp_path):
    p = Project(name="Test")
    c1 = ClipDescriptor(path="/video/a.mp4", in_point=1.0, out_point=2.5)
    c2 = ClipDescriptor(path="/video/b.mp4")
    p.add_clip(c1)
    p.add_clip(c2)
    assert len(p.clips) == 2
    removed = p.remove_clip(0)
    assert removed.path == c1.path
    assert len(p.clips) == 1


def test_project_serialization(tmp_path):
    p = Project(
        name="Serialize",
        clips=[ClipDescriptor(path="/x.mp4", in_point=0.5, out_point=3.0)],
    )
    out_file = tmp_path / "proj.json"
    p.save(out_file)
    loaded = Project.load(out_file)
    assert loaded.name == p.name
    assert len(loaded.clips) == 1
    assert loaded.clips[0].in_point == 0.5
    # structure stability
    d = loaded.to_dict()
    assert "clips" in d and isinstance(d["clips"], list)
