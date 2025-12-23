import subprocess
import time
import sys

def stream_fake_camera(rtsp_url="rtsp://localhost:8554/test_cam"):
    """
    Simulates a camera by streaming a test pattern to the MediaMTX server via RTSP.
    Requires ffmpeg to be installed and in the system PATH.
    """
    print(f"Starting fake camera stream to {rtsp_url}...")
    
    # FFmpeg command to generate a test pattern and stream it via RTSP (TCP)
    # -re: Read input at native frame rate
    # -f lavfi -i testsrc=size=1920x1080:rate=15: Generate 1080p 15fps video
    # -c:v libx264: Encode as H.264
    # -preset ultrafast: Low CPU usage
    # -tune zerolatency: Low latency
    # -f rtsp: Output format
    command = [
        "ffmpeg",
        "-re",
        "-f", "lavfi",
        "-i", "testsrc=size=1920x1080:rate=15",
        "-f", "lavfi",
        "-i", "sine=frequency=1000:duration=60", # Add dummy audio
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-f", "rtsp",
        "-rtsp_transport", "tcp",
        rtsp_url
    ]

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Stream started. Press Ctrl+C to stop.")
        
        # Keep the script running
        while True:
            time.sleep(1)
            if process.poll() is not None:
                print("FFmpeg process exited unexpectedly.")
                stdout, stderr = process.communicate()
                print(stderr.decode())
                break
                
    except KeyboardInterrupt:
        print("\nStopping stream...")
        process.terminate()
    except FileNotFoundError:
        print("Error: FFmpeg not found. Please install FFmpeg and add it to your PATH.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "rtsp://localhost:8554/test_cam"
    stream_fake_camera(url)
