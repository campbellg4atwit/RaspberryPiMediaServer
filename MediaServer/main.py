import ffmpeg, os
from flask import Flask, jsonify, redirect, url_for, request, session, flash, render_template
from werkzeug.utils import secure_filename

# This is to get the directory that the program
# is currently running in.
dir_path = os.path.dirname(os.path.realpath(__file__))
vid_path = dir_path + "static/videos/"

app = Flask(__name__)
app.secret_key = "S-E-C-R-E-T-K-E-Y"
app.config['UPLOAD_FOLDER'] = vid_path
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

## Function that returns a list of all of the video titles downloaded
def get_videos():
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
      if "compressed_" in file:
        videos.append(str(file))

  return videos

## Function that returns a list of all of the video titles downloaded using key words as a filter
def search_videos(search):
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
        if "compressed_" in file:
          if search in file:
            videos.append(str(file))

  return videos

## Function that downloads a file given
def download_video(fileItem):
  if fileItem.filename:
    fn = secure_filename(fileItem.filename)
    fn = os.path.join(app.config['UPLOAD_FOLDER'], fn)
    fileItem.save()
    compress_video(vid_path + fn, vid_path + "compressed_" + fn, 50 * 1000)

## Function that compresses the downloaded video
def compress_video(video_full_path, output_file_name, target_size):
    min_audio_bitrate = 32000 #4Kbits/s
    max_audio_bitrate = 256000 #32Kbits/s

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


## Page that plays the video
@app.route('/play', methods=['GET','POST'])
def play():
  return render_template('watch.html', videoTitle=session.get("videoTitle"))

## Page When sending videos to media server
@app.route('/video_send')
def send_page():
  return render_template('upload.html')

## Page When sending videos to media server
@app.route('/video_send', methods=['POST'])
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
      flash('Video successfully uploaded')
      return render_template('upload.html', filename=file.filename)

## Page to feed into video element to show the mp4 file
@app.route('/display/<filename>')
def display_video(filename):
	return redirect(url_for('static', filename=vid_path + filename), code=301)

## Buffer page that dictates which video you picked from /browse
@app.route('/video_pick', methods=['GET', 'POST'])
def choose():
    if request.method == 'POST':
      session["videoTitle"] = request.form["video"]
      return redirect(url_for('play'))

## Page where you can view a list of videos and choose which one you want to watch
@app.route('/browse', methods=['GET', 'POST'])
def browse():
    videos = get_videos()
    videos.sort()
    return render_template('browse.html', videos=videos)

## Default page that redirects to general browsing of videos
@app.route('/')
def home():
    return redirect(url_for('browse'))

if __name__ == "__main__":
  app.run(threaded=True, debug=True)