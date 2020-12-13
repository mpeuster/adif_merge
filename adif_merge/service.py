import os
import argparse
import logging
import uuid
import time
import shutil
from flask import Flask, render_template, request, session
from werkzeug.utils import secure_filename
from apscheduler.schedulers.background import BackgroundScheduler
from adif_merge import setup_logging, process_adifs, parse_args


UPLOAD_FOLDER = os.getenv("AMS_UPLOAD_FOLDER", default="adif_merge/static")
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
    for i, f in enumerate(["file1", "file2"]):
        file = request.files[f]
        if file.filename == "":
            return "bad input, no files selected", 400
        if file and allowed_file(file.filename):
            filename = "{:02d}__{}".format(i, secure_filename(file.filename))
            fp = os.path.join(session_path, filename)
            try:
                file.save(fp)
                file_paths.append(fp)
                logging.debug ("Uploaded: {}".format(fp))
            except OSError:
                logging.error ("Could not write: {}".format(fp))
                return "Could not store: {}".format(filename), 501

    # check options
    try:
        opt_time_window = int(request.form.get("time_window", 115))
        opt_wsjtx_log = bool(request.form.get("option_wsjtx_log", False))
        opt_problems = bool(request.form.get("option_problems", False))
        opt_minimal = bool(request.form.get("option_minimal", False))
    except:
        return "bad inputs", 400

    # gen. args & call merge
    arg_list = list()
    if opt_minimal:
        arg_list.append("--minimal")
    if opt_problems:
        arg_list.append("--problems")
        arg_list.append("{}".format(os.path.join(session_path, "problems.json")))
    if opt_wsjtx_log:
        arg_list.append("--wsjtx-log")
        arg_list.append("{}".format(os.path.join(session_path, "wsjtx.log")))
    arg_list.append("--merge-window")
    arg_list.append("{}".format(opt_time_window))
    arg_list.append("--output")
    arg_list.append("{}".format(os.path.join(session_path, "merged.adi")))
    arg_list.extend(file_paths)
    logging.debug("Arg list: {}".format(arg_list))
    args = parse_args(arg_list)

    # to the work ...
    logging.debug("Triggering adif_merge with: {}".format(vars(args)))
    process_adifs(args)
    logging.debug("Done! Output: {}".format(args.output))

    # generate result
    return render_template(
        "result.html",
        title=os.getenv("AMS_TITLE", default="ADIF Merge Service"),
        sid = session["sid"],
        output_file_name = os.path.basename(args.output),
        problems_file_name = os.path.basename(args.problems) if args.problems and os.path.exists(args.problems) else "",
        wsjtx_log_file_name = os.path.basename(args.wsjtx_log) if args.wsjtx_log else "",
        )


def cleanup():
    for f in os.listdir(UPLOAD_FOLDER):
        path = os.path.join(UPLOAD_FOLDER, f)
        if os.path.isdir(path):
            if (time.time() - os.stat(path).st_mtime) > 3600:
                logging.info("Cleanup: Removing {}".format(path))
                shutil.rmtree(path)


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
    # TODO: create cleanup job
    scheduler = BackgroundScheduler()
    scheduler.add_job(cleanup, 'interval', minutes=120)
    scheduler.start()
    # start the server
    app.run(host=args.addr, port=args.port, debug=args.debug)