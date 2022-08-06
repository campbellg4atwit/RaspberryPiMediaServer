import ffmpeg, os, re
from flask import Flask, redirect, url_for, request, session, flash, render_template, make_response, Response
from werkzeug.utils import secure_filename

# This is to get the directory that the program
# is currently running in.
dir_path = os.path.dirname(os.path.realpath(__file__))
vid_path = dir_path + "/static/videos/"

app = Flask(__name__)
app.secret_key = "S-E-C-R-E-T-K-E-Y"
app.config['UPLOAD_FOLDER'] = vid_path
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

## Function that returns a list of all of the video titles downloaded
def get_videos():
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
    # Comment out this if statement to see original files and compressed videos
      if "compressed_" in file:
        videos.append(str(file))

  return videos

## Function that returns a list of all of the video titles downloaded using key words as a filter
## Search functionality but not actually built into web application
def search_videos(search):
  videos = []
  for root, dirs, files in os.walk(vid_path):
    for file in files:
        if "compressed_" in file:
          if search in file:
            videos.append(str(file))

  return videos


## Function that returns a chunk of requested video
def get_chunk(byte1, byte2, filename):
    #Finds Video Selected
    full_path = vid_path + filename
    file_size = os.stat(full_path).st_size
    start = 0
    
    # Gets requested chunk length
    if byte1 < file_size:
        start = byte1
    if byte2:
        length = byte2 + 1 - byte1
    else:
        length = file_size - start

    # Opens and returns requested chunk
    with open(full_path, 'rb') as f:
        f.seek(start)
        chunk = f.read(length)
    return chunk, start, length, file_size

## Function that compresses the downloaded video
def compress_video(og_vid_path, output_file_name, target_size):
    #Minimum and maximum bit rates an mp3 file usually expects.
    min_audio_bitrate = 32000 #4Kbits/s
    max_audio_bitrate = 256000 #32Kbits/s

    probe = ffmpeg.probe(og_vid_path)
    # Video duration, in s.
    duration = float(probe['format']['duration'])
    # Audio bitrate, in bps.
    audio_bitrate = float(next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)['bit_rate'])
    # Target total bitrate, in bps. Required Bits / (GB*Seconds)
    target_total_bitrate = (target_size * 1024 * 8) / (1.073741824 * duration)

    # Target audio bitrate, in bps
    # Fits current bitrate into min and max audio bitrate selected. (high end mp3 audio)
    if 10 * audio_bitrate > target_total_bitrate:
        audio_bitrate = target_total_bitrate / 10
        if audio_bitrate < min_audio_bitrate < target_total_bitrate:
            audio_bitrate = min_audio_bitrate
        elif audio_bitrate > max_audio_bitrate:
            audio_bitrate = max_audio_bitrate
    # Target video bitrate, in bps.
    video_bitrate = target_total_bitrate - audio_bitrate

    i = ffmpeg.input(og_vid_path)
    ffmpeg.output(i, os.devnull,
                  **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 1, 'f': 'mp4'}
                  ).overwrite_output().run()
    ffmpeg.output(i, output_file_name,
                  **{'c:v': 'libx264', 'b:v': video_bitrate, 'pass': 2, 'c:a': 'aac', 'b:a': audio_bitrate}
                  ).overwrite_output().run()


#===============================================================  FLASK WEBPAGES ======================================================================================================

## Page that plays the video
@app.route('/play', methods=['GET','POST'])
def play():
  return render_template('watch.html', videoTitle=session.get("videoTitle"))

## Page when sending videos to media server.
@app.route('/video_send')
def send_page():
  return render_template('upload.html')

## Dropzone function for uploading videos to media server
@app.route('/video_send', methods=['POST'])
def send():
    file = request.files['file']

    #Decides on path to save video
    save_path = vid_path + secure_filename(file.filename)
    current_chunk = int(request.form['dzchunkindex'])

    # If the file already exists it's ok if we are appending to it,
    # but not if it's new file that would overwrite the existing one
    if os.path.exists(save_path) and current_chunk == 0:
        # 400 and 500s will tell dropzone that an error occurred and show an error
        return make_response(('File already exists', 400))

    # Tries to create and write file, taking information from inputed file
    try:
        with open(save_path, 'ab') as f:
            f.seek(int(request.form['dzchunkbyteoffset']))
            f.write(file.stream.read())
    except OSError:
        flash('Could not write to file')
        return make_response(("Not sure why,"
                              " but we couldn't write the file to disk", 500))

    # Gets how many chunks Dropzone decided to split file into
    total_chunks = int(request.form['dztotalchunkcount'])

    # Downloads and writes file one chunk at a time
    if current_chunk + 1 == total_chunks:
        # This was the last chunk, the file should be complete and the size we expect
        if os.path.getsize(save_path) != int(request.form['dztotalfilesize']):
            flash(f"File {file.filename} was completed, "
                      f"but has a size mismatch."
                      f"Was {os.path.getsize(save_path)} but we"
                      f" expected {request.form['dztotalfilesize']} ")
            return make_response(('Size mismatch', 500))
        else:
            # Compresses video once download is finished
            try:
              compress_video(vid_path + file.filename, vid_path + "compressed_" + file.filename, 50 * 1000)
            finally:
              flash(f'File {file.filename} has been uploaded successfully')
    else:
        flash(f'Chunk {current_chunk + 1} of {total_chunks} '
                  f'for file {file.filename} complete')

    return make_response(("Chunk upload successful", 200))

# Function to display and load video in html, loading and processing in chunks.
@app.route('/video/<filename>')
def display_video(filename):
    # Gets range header from the video to tell how far in the video the user is
    range_header = request.headers.get('Range', None)
    byte1, byte2 = 0, None

    # Makes sure to select chunks that the header is in and after to load.
    if range_header:
        match = re.search(r'(\d+)-(\d*)', range_header)
        groups = match.groups()

        if groups[0]:
            byte1 = int(groups[0])
        if groups[1]:
            byte2 = int(groups[1])
    
    # Loads and sends chunks of loaded video to user.
    chunk, start, length, file_size = get_chunk(byte1, byte2, filename)
    resp = Response(chunk, 206, mimetype='video/mp4',
                      content_type='video/mp4', direct_passthrough=True)
    resp.headers.add('Content-Range', 'bytes {0}-{1}/{2}'.format(start, start + length - 1, file_size))
    return resp

## Buffer page that dictates which video you picked from /browse
@app.route('/video_pick', methods=['GET', 'POST'])
def choose():
    if request.method == 'POST':
      title = request.form["id"]
      session["videoTitle"] = str(title)
      return redirect(url_for('play'))

## Page where you can view a list of videos and choose which one you want to watch
@app.route('/browse', methods=['GET', 'POST'])
def browse():
    session.clear()
    videos = get_videos()
    videos.sort()
    return render_template('browse.html', videos=videos)

## Default page that redirects to general browsing of videos
@app.route('/')
def home():
    return redirect(url_for('browse'))

if __name__ == "__main__":
  app.run(threaded=True, debug=True)