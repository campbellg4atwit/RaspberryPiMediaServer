import ffmpeg, os, pickle, struct, cv2, pyaudio
from flask import Flask, jsonify, redirect, url_for, request, session, Blueprint, flash
import re

# This is to get the directory that the program
# is currently running in.
dir_path = os.path.dirname(os.path.realpath(__file__))
vid_path = dir_path + "/Videos/"

app = Flask(__name__)

def get_videos():
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
      if "compressed_" in file:
        videos.append(str(file))

  return videos

def search_videos(search):
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
        if "compressed_" in file:
          if search in file:
            videos.append(str(file))

  return videos

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


@app.route('/play', methods=['GET','POST'])
def play():
  
  return jsonify(videoTitle=session.get("videoTitle"))

@app.route('video_send', methods=['GET', 'POST'])
def send():
    if 'file' not in request.files:
      flash('No file part')
      return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
      flash('No image selected for uploading')
      return redirect(request.url)
    else:
      download_video(file)
      #print('upload_video filename: ' + filename)
      flash('Video successfully uploaded and displayed below')
      return jsonify(filename=file.filename)

@app.route('/display/<filename>')
def display_video(filename):
	#print('display_video filename: ' + filename)
	return redirect(url_for('static', filename=vid_path + filename), code=301)

@app.route('/video_pick', methods=['GET', 'POST'])
def choose():
    if request.method == 'POST':
      session["videoTitle"] = request.form["video"]
      return redirect(url_for('play'))

@app.route('/browse', methods=['GET', 'POST'])
def browse():
    return jsonify(videos=get_videos())      

@app.route('/')
def home():
    return redirect(url_for('browse'))

if __name__ == "__main__":
  app.run(threaded=True, debug=True)