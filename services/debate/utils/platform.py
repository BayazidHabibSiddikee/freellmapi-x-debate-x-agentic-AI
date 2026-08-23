import subprocess

def open_camera():
    pass

def kill_camera():
    pass

def screenshot():
    path = "/tmp/marin_screenshot.png"
    subprocess.run(["scrot", "-s", path], capture_output=True)
    from PIL import Image
    return Image.open(path)