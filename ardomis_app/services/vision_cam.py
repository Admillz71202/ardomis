import os, time, subprocess

def capture_image() -> str:
    out = f"/tmp/ardomis_{int(time.time())}.jpg"
    cmd = ["rpicam-still", "-n", "-t", "300", "-o", out, "--width", "1280", "--height", "720"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.exists(out):
        raise RuntimeError("Camera capture failed: file not created.")
    return out
