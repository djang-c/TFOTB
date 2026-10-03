# Decisions
- **Simulator: MuJoCo 3.14.0** (default per PLAN). Open question "existing ROS 2 stack?" unanswered -> no Gazebo. Revisit only if a ROS 2 stack exists.
- **Motion checking is kinematic**: straight-line segments sampled at 1 mm, MuJoCo contact queries + joint-limit tests. No dynamics, no liquids.
- **Failure policy**: first failure stops the run and is reported; nothing is clipped.
- **Environment**: Python 3.12 venv, `requirements.lock` pinned. mp4 replay uses MuJoCo renderer (GLFW on macOS) + imageio-ffmpeg.
- **Scene/spec coupling**: spec coordinates (mm) are authored to match `scene.xml`; the scene hash is recorded per run.
