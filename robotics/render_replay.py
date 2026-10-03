"""Render a RECORDED REPLAY (mp4) from a saved trajectory (PLAN: T23). Not a live simulation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import imageio.v2 as imageio
import mujoco
import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
CAPTION = "RECORDED REPLAY - workflow simulation only; not wet-lab validated"


def render(trajectory: Path, out: Path, fps: int = 30, size=(480, 640)) -> Path:
    pts = json.loads(Path(trajectory).read_text())["points"]
    if not pts:
        raise ValueError("empty trajectory: nothing to replay (run was rejected before motion)")
    model = mujoco.MjModel.from_xml_path(str(HERE / "scene.xml"))
    data = mujoco.MjData(model)
    cam = mujoco.MjvCamera()
    cam.lookat[:] = [0.15, 0.1, 0.02]
    cam.distance, cam.azimuth, cam.elevation = 0.55, 90, -55
    frames = []
    with mujoco.Renderer(model, *size) as r:
        for p in pts[:: max(1, len(pts) // 300)]:
            data.qpos[:3] = [c / 1000 for c in p]
            mujoco.mj_forward(model, data)
            r.update_scene(data, cam)
            img = Image.fromarray(r.render())
            ImageDraw.Draw(img).text((8, 8), CAPTION, fill=(255, 255, 255))
            frames.append(img)
    out = Path(out)
    imageio.mimsave(out, [np.asarray(f) for f in frames], fps=fps)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trajectory")
    ap.add_argument("out")
    a = ap.parse_args()
    print(render(Path(a.trajectory), Path(a.out)))
