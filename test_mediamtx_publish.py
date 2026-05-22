import subprocess
import time
import numpy as np

# Create a test frame (640x480 BGR)
frame = np.zeros((360, 634, 3), dtype=np.uint8)
frame[:, :, 2] = 255  # Red frame

cmd = [
    'ffmpeg',
    '-hide_banner',
    '-loglevel', 'info',  # Changed to info to see errors
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
    'rtsp://127.0.0.1:8554/ann-test-manual'
]

print('Starting FFmpeg...')
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print(f'Process started, PID: {proc.pid}')

# Wait a bit for FFmpeg to initialize
time.sleep(0.5)

# Check if process is still running
poll_result = proc.poll()
print(f'Poll result after 0.5s: {poll_result}')

if poll_result is not None:
    print('Process exited!')
    stderr_output = proc.stderr.read().decode()
    print('STDERR:', stderr_output)
else:
    print('Process is running, sending frames...')
    try:
        # Send 30 frames (2 seconds at 15 FPS)
        for i in range(30):
            proc.stdin.write(frame.tobytes())
            proc.stdin.flush()
            time.sleep(1/15)
            if i % 10 == 0:
                print(f'Sent {i} frames')
        
        print('Finished sending frames')
        proc.stdin.close()
        proc.wait(timeout=2)
        print(f'Process exited with code: {proc.returncode}')
    except Exception as e:
        print(f'Error: {e}')
        stderr_output = proc.stderr.read().decode()
        print('STDERR:', stderr_output)
        proc.terminate()
