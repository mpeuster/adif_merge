import os
import argparse
import logging
import uuid
from flask import Flask, render_template, request, session
from werkzeug.utils import secure_filename
from adif_merge import setup_logging
from adif_merge import process_adifs


UPLOAD_FOLDER = os.getenv("AMS_UPLOAD_FOLDER", default="/tmp/adif_merge")
ALLOWED_EXTENSIONS = {"ADI", "adi", "ADIF", "adif"}


app = Flask(__name__)
app.secret_key = os.getenv("AMS_SECRET_KEY", default=b"abcdefghijklmn")
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


def allowed_file(filename):
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS       

@app.route("/")
def form():
    session["sid"] = uuid.uuid4().hex
    logging.info("New session: {}".format(session["sid"]))
    return render_template("form.html", title=os.getenv("AMS_TITLE", default="ADIF Merge Service"))

@app.route("/merge", methods=["POST"])
def merge():
    if 'file1' not in request.files or 'file2' not in request.files:
        return "bad input", 400

    # lets have one folder per session:
    session_path = os.path.join(app.config['UPLOAD_FOLDER'], session["sid"])
    if not os.path.exists(session_path):
        try:
            os.mkdir(session_path)
        except OSError:
            logging.error ("Session folder could not be created: {}".format(session_path))

    # upload and store inputs
    file_paths = list()
    for f in ["file1", "file2"]:
        file = request.files[f]
        if file.filename == "":
            return "bad input, no files selected", 400
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            fp = os.path.join(session_path, filename)
            try:
                file.save(fp)
                file_paths.append(fp)
                logging.debug ("Uploaded: {}".format(fp))
            except OSError:
                logging.error ("Could not write: {}".format(fp))
                return "Could not store: {}".format(filename), 501

    # TODO: check options

    # TODO: call merge

    # TODO: generate result

    return "Done: {}".format(session["sid"])


def main():
    parser = argparse.ArgumentParser(
        description="adif_merge.py server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--port', type=int,
                        help="Port to listen", default=8081)
    parser.add_argument('--addr', type=str,
                        help="Host addr. to listen on", default="0.0.0.0")
    parser.add_argument('--log-level', type=str, default="info",
                        help="Log level for debugging")
    parser.add_argument('--debug', action="store_true",
                        help="Run server in dubgging mode")
    args = parser.parse_args()

    setup_logging(args)
    logging.info("adif_merge.py server starting ...")
    if not os.path.exists(UPLOAD_FOLDER):
        try:
            os.mkdir(UPLOAD_FOLDER)
        except OSError:
            logging.error ("Upload folder could not be created: {}".format(UPLOAD_FOLDER))
    app.run(host=args.addr, port=args.port, debug=args.debug)