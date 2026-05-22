import sys
sys.path.insert(0, 'backend')

from src.api.runtime import configure_mediamtx_annotated_path

# Test configuring a path
path_name = "ann-test-config"
print(f"Configuring MediaMTX path: {path_name}")

try:
    configure_mediamtx_annotated_path(path_name)
    print("✓ Path configured successfully")
except Exception as e:
    print(f"✗ Error: {e}")

# Now test if FFmpeg can publish to it
print("\nTesting FFmpeg publish...")
import subprocess
import time
import numpy as np

frame = np.zeros((360, 634, 3), dtype=np.uint8)
frame[:, :, 1] = 255  # Green frame

cmd = [
    'ffmpeg',
    '-hide_banner',
    '-loglevel', 'error',
    '-nostdin',
    '-f', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-s', '634x360',
    '-r', '15',
    '-i', '-',
    '-an',
    '-c:v', 'libx264',
    '-preset', 'veryfast',
    '-tune', 'zerolatency',
    '-pix_fmt', 'yuv420p',
    '-f', 'rtsp',
    '-rtsp_transport', 'tcp',
    f'rtsp://127.0.0.1:8554/{path_name}'
]

proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print(f'FFmpeg started, PID: {proc.pid}')

time.sleep(0.5)
poll_result = proc.poll()

if poll_result is not None:
    print(f'✗ FFmpeg exited immediately with code {poll_result}')
    stderr = proc.stderr.read().decode()
    if stderr:
        print(f'STDERR: {stderr[:500]}')
else:
    print('✓ FFmpeg is running')
    try:
        # Send a few frames
        for i in range(5):
            proc.stdin.write(frame.tobytes())
            proc.stdin.flush()
        print('✓ Sent 5 frames successfully')
    except Exception as e:
        print(f'✗ Error sending frames: {e}')
    finally:
        proc.terminate()
        proc.wait(timeout=2)
        print(f'FFmpeg terminated with code {proc.returncode}')
