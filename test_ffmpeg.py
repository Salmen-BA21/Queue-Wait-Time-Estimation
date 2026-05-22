import subprocess
import time

cmd = [
    'ffmpeg',
    '-hide_banner',
    '-loglevel', 'error',
    '-nostdin',
    '-f', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-s', '640x480',
    '-r', '15',
    '-i', '-',
    '-an',
    '-c:v', 'libx264',
    '-preset', 'veryfast',
    '-tune', 'zerolatency',
    '-pix_fmt', 'yuv420p',
    '-f', 'rtsp',
    '-rtsp_transport', 'tcp',
    'rtsp://127.0.0.1:8554/ann-test'
]

print('Command:', ' '.join(cmd))
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print('Process started, PID:', proc.pid)
time.sleep(0.5)
poll_result = proc.poll()
print('Poll result:', poll_result)
if poll_result is not None:
    stderr_output = proc.stderr.read().decode()
    print('STDERR:', stderr_output)
else:
    print('Process is still running')
proc.terminate()
proc.wait()
