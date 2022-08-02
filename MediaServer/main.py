import socket, ffmpeg, os, pickle, struct
from ffmpeg_videostream import VideoStream

# This is to get the directory that the program
# is currently running in.
dir_path = os.path.dirname(os.path.realpath(__file__))
vid_path = dir_path + "/Videos/"


server_socket = socket.socket(socket.AF_INET,socket.SOCK_STREAM)

host_name  = socket.gethostname()
host_ip = socket.gethostbyname(host_name)
port = 9999
socket_address = (host_ip,port)
server_socket.bind(socket_address)


def get_videos():
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
      if "compressed_" in file:
        videos.append(root+'/'+str(file))

  return videos

def search_videos(search):
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
        if "compressed_" in file:
          if search in file:
            videos.append(root+'/'+str(file))

  return videos

def streamVideo(video_name):
    client_socket,addr = server_socket.accept()
    video = VideoStream(vid_path + video_name)
    video.open_stream()
    while True:
      eof, frame = video.read()
      a = pickle.dumps(frame)
      message = struct.pack("Q",len(a))+a
      client_socket.sendall(message)
      if eof:
        client_socket.close()
        break

def download_video(fileItem):
  if fileItem.filename:
    fn = os.path.basename(fileItem.filename)
    with open(vid_path + fn, 'wb') as code:
      code.write(fileItem.file.read())
    compress_video(vid_path + fn, vid_path + "compressed_" + fn, 50 * 1000)

def compress_video(video_full_path, output_file_name, target_size):
    # Reference: https://en.wikipedia.org/wiki/Bit_rate#Encoding_bit_rate
    min_audio_bitrate = 32000
    max_audio_bitrate = 256000

    probe = ffmpeg.probe(video_full_path)
    # Video duration, in s.
    duration = float(probe['format']['duration'])
    # Audio bitrate, in bps.
    audio_bitrate = float(next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)['bit_rate'])
    # Target total bitrate, in bps.
    target_total_bitrate = (target_size * 1024 * 8) / (1.073741824 * duration)

    # Target audio bitrate, in bps
    if 10 * audio_bitrate > target_total_bitrate:
        audio_bitrate = target_total_bitrate / 10
        if audio_bitrate < min_audio_bitrate < target_total_bitrate:
            audio_bitrate = min_audio_bitrate
        elif audio_bitrate > max_audio_bitrate:
            audio_bitrate = max_audio_bitrate
    # Target video bitrate, in bps.
    video_bitrate = target_total_bitrate - audio_bitrate

    i = ffmpeg.input(video_full_path)
    ffmpeg.output(i, os.devnull,
                  **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 1, 'f': 'mp4'}
                  ).overwrite_output().run()
    ffmpeg.output(i, output_file_name,
                  **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 2, 'c:a': 'aac', 'b:a': audio_bitrate}
                  ).overwrite_output().run()


if __name__ == "__main__":
  server_socket.listen(1)
  print("LISTENING AT:", socket_address)
  while True:
    pass