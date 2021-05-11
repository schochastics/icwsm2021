# pylint: disable=global-statement,redefined-outer-name
import argparse
import csv
import glob
import json
import os

import yaml
from flask import Flask, jsonify, redirect, render_template, send_from_directory
from flask_frozen import Freezer
from flaskext.markdown import Markdown

# for auth
from authlib.integrations.flask_client import OAuth
from six.moves.urllib.parse import urlencode
from flask import url_for, session
from dotenv import load_dotenv, find_dotenv
from functools import wraps
import json
from os import environ as env
from werkzeug.exceptions import HTTPException

import constants

site_data = {}
by_uid = {}

def main(site_data_path):
    global site_data, extra_files
    extra_files = ["README.md"]
    # Load all for your sitedata one time.
    for f in glob.glob(site_data_path + "/*"):
        extra_files.append(f)
        name, typ = f.split("/")[-1].split(".")
        if typ == "json":
            site_data[name] = json.load(open(f))
        elif typ in {"csv", "tsv"}:
            site_data[name] = list(csv.DictReader(open(f)))
        elif typ == "yml":
            site_data[name] = yaml.load(open(f).read(), Loader=yaml.SafeLoader)

    for typ in ["papers", "speakers", "workshops","tutorials","panels"]:
        by_uid[typ] = {}
        for p in site_data[typ]:
            by_uid[typ][p["UID"]] = p

    print("Data Successfully Loaded")
    return extra_files


# ------------- SERVER CODE -------------------->

app = Flask(__name__)
app.config.from_object(__name__)
freezer = Freezer(app)
markdown = Markdown(app)

# --------------------init auth0
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

AUTH0_CALLBACK_URL = env.get(constants.AUTH0_CALLBACK_URL)
AUTH0_CLIENT_ID = env.get(constants.AUTH0_CLIENT_ID)
AUTH0_CLIENT_SECRET = env.get(constants.AUTH0_CLIENT_SECRET)
AUTH0_DOMAIN = env.get(constants.AUTH0_DOMAIN)
AUTH0_BASE_URL = 'https://' + AUTH0_DOMAIN
AUTH0_AUDIENCE = env.get(constants.AUTH0_AUDIENCE)

app.secret_key = constants.SECRET_KEY

oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=AUTH0_CLIENT_ID,
    client_secret=AUTH0_CLIENT_SECRET,
    api_base_url=AUTH0_BASE_URL,
    access_token_url=AUTH0_BASE_URL + '/oauth/token',
    authorize_url=AUTH0_BASE_URL + '/authorize',
    client_kwargs={
        'scope': 'openid profile email',
    },
)


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if constants.PROFILE_KEY not in session:
            return redirect('/login')
        return f(*args, **kwargs)

    return decorated

# MAIN PAGES

def _data():
    data = {}
    data["config"] = site_data["config"]
    return data


@app.route("/")
def index():
    return redirect("/index.html")
    # return redirect("/home.html")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(site_data_path, "favicon.ico")


# TOP LEVEL PAGES

# @app.route('/')
# def home():
#     return render_template('home.html')

@app.route("/index.html")
#@requires_auth
def home():
    data = _data()
    data["readme"] = open("README.md").read()
    data["committee"] = site_data["committee"]["committee"]
    return render_template("index.html", **data)
    # return render_template('home.html')


@app.route("/help.html")
def about():
    data = _data()
    data["FAQ"] = site_data["faq"]["FAQ"]
    return render_template("help.html", **data)


@app.route("/papers.html")
def papers():
    data = _data()
    data["papers"] = site_data["papers"]
    return render_template("papers.html", **data)


@app.route("/paper_vis.html")
#@requires_auth
def paper_vis():
    data = _data()
    return render_template("papers_vis.html", **data)


@app.route("/calendar.html")
def schedule():
    data = _data()
    data["day1"] = {
        "speakers": [s for s in site_data["speakers"]
                if s["day"] == "Tuesday"],
        "highlighted": [
            format_paper(by_uid["papers"][h["UID"]]) for h in site_data["highlighted"] if h["session"]=="S0"
        ],
    }
    data["day2"] = {
        "speakers": [s for s in site_data["speakers"]
                if s["day"] == "Wednesday"],
        "highlighted": [
            format_paper(by_uid["papers"][h["UID"]]) for h in site_data["highlighted"] if h["session"]=="S1"
        ],
    }
    data["day3"] = {
        "speakers": [s for s in site_data["speakers"]
                if s["day"] == "Wednesday"],
        "highlighted": [
            format_paper(by_uid["papers"][h["UID"]]) for h in site_data["highlighted"] if h["session"]=="S2"
        ],
    }
    return render_template("schedule.html", **data)


@app.route("/workshops.html")
def workshops():
    data = _data()
    data["workshops"] = [
        format_workshop(workshop) for workshop in site_data["workshops"]
    ]
    return render_template("workshops.html", **data)

@app.route("/tutorials.html")
def tutorials():
    data = _data()
    data["tutorials"] = [
        format_tutorial(tutorial) for tutorial in site_data["tutorials"]
    ]
    return render_template("tutorials.html", **data)

@app.route("/panels.html")
def panels():
    data = _data()
    data["panels"] = [
        format_panel(panels) for panels in site_data["panels"]
    ]
    return render_template("panels.html", **data)

@app.route("/speakers.html")
def speakers():
    data = _data()
    data["speakers"] = [
        format_speaker(speakers) for speakers in site_data["speakers"]
    ]
    return render_template("speakers.html", **data)

def extract_list_field(v, key):
    value = v.get(key, "")
    if isinstance(value, list):
        return value
    else:
        return value.split("|")

def format_paper(v):
    list_keys = ["authors", "keywords","session"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "UID": v["UID"],
        "title": v["title"],
        "forum": v["UID"],
        "authors": list_fields["authors"],
        "keywords": list_fields["keywords"],
        "abstract": v["abstract"],
        "track":v["track"],
        "sessions": list_fields["session"],
        "slack": v["slack"],
        "date":v["date"],
        "time": v["time"],
        "topic": v["topic"]
        # "TLDR": v["abstract"]
        # "recs": [],
        # links to external content per poster
        #"pdf_url": v.get("pdf_url", ""),  # render poster from this PDF
        #"code_link": "",  # link to code
        #"link": ""  # link to paper
    }


def format_workshop(v):
    list_keys = ["authors"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "id": v["UID"],
        "title": v["title"],
        "longtitle": v["longtitle"],
        "organizers": list_fields["authors"],
        "abstract": v["abstract"],
        "length": v["length"],
        "link": v["link"],
        "logo": v["logo"]
    }

def format_tutorial(v):
    list_keys = ["authors"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "id": v["UID"],
        "title": v["title"],
        "organizers": list_fields["authors"],
        "abstract": v["abstract"],
        "link": v["link"],
        "logo": v["logo"]
    }

def format_panel(v):
    list_keys = ["authors","images"]
    list_fields = {}
    for key in list_keys:
        list_fields[key] = extract_list_field(v, key)

    return {
        "id": v["UID"],
        "title": v["title"],
        "organizers": list_fields["authors"],
        "images": list_fields["images"],
        "moderator": v["moderator"],
        "modimg": v["modimg"],
        "link": v["link"],
        "abstract": v["abstract"],
        "short": v["short"],
        "date":v["date"],
        "time": v["time"]
    }

def format_speaker(v):
    return {
        "UID": v["UID"],
        "day": v["day"],
        "date1": v["date1"],
        "date2": v["date2"],
        "time1": v["time1"],
        "time2": v["time2"],
        "image": v["image"],
        "title": v["title"],
        "institution": v["institution"],
        "speaker": v["speaker"],
        "abstract": v["abstract"],
        "bio": v["bio"],
        "session": v["session"]
    }

# ITEM PAGES


@app.route("/poster_<poster>.html")
#@requires_auth
def poster(poster):
    uid = poster
    v = by_uid["papers"][uid]
    data = _data()
    data["paper"] = format_paper(v)
    return render_template("poster.html", **data)


@app.route("/speaker_<speaker>.html")
#@requires_auth
def speaker(speaker):
    uid = speaker
    v = by_uid["speakers"][uid]
    data = _data()
    data["speaker"] = v
    return render_template("speaker.html", **data)


@app.route("/workshop_<workshop>.html")
def workshop(workshop):
    uid = workshop
    v = by_uid["workshops"][uid]
    data = _data()
    data["workshop"] = format_workshop(v)
    return render_template("workshop.html", **data)

@app.route("/tutorial_<tutorial>.html")
def tutorial(tutorial):
    uid = tutorial
    v = by_uid["tutorials"][uid]
    data = _data()
    data["tutorial"] = format_tutorial(v)
    return render_template("tutorial.html", **data)

@app.route("/panel_<panel>.html")
#@requires_auth
def panel(panel):
    uid = panel
    v = by_uid["panels"][uid]
    data = _data()
    data["panel"] = format_panel(v)
    return render_template("panel.html", **data)

# FRONT END SERVING


@app.route("/papers.json")
def paper_json():
    json = []
    for v in site_data["papers"]:
        json.append(format_paper(v))
    return jsonify(json)


@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory("static", path)


@app.route("/serve_<path>.json")
def serve(path):
    return jsonify(site_data[path])


# --------------- DRIVER CODE -------------------------->
# Code to turn it all static


@freezer.register_generator
def generator():
    for paper in site_data["papers"]:
        yield "poster", {"poster": str(paper["UID"])}
    for speaker in site_data["speakers"]:
        yield "speaker", {"speaker": str(speaker["UID"])}
    for workshop in site_data["workshops"]:
        yield "workshop", {"workshop": str(workshop["UID"])}
    for tutorial in site_data["tutorials"]:
        yield "tutorial", {"tutorial": str(tutorial["UID"])}
    for panel in site_data["panels"]:
        yield "panel", {"panel": str(panel["UID"])}

    for key in site_data:
        yield "serve", {"path": key}


def parse_arguments():
    parser = argparse.ArgumentParser(description="MiniConf Portal Command Line")

    parser.add_argument(
        "--build",
        action="store_true",
        default=False,
        help="Convert the site to static assets",
    )

    parser.add_argument(
        "-b",
        action="store_true",
        default=False,
        dest="build",
        help="Convert the site to static assets",
    )

    parser.add_argument("path", help="Pass the JSON data path and run the server")

    args = parser.parse_args()
    return args


#---------------------------------auth0 pages----------------------------------------------#
# Controllers API
# @app.route('/')
# def home():
#     return render_template('home.html')


@app.route('/callback')
def callback_handling():
    auth0.authorize_access_token()
    resp = auth0.get('userinfo')
    userinfo = resp.json()

    session[constants.JWT_PAYLOAD] = userinfo
    session[constants.PROFILE_KEY] = {
        'user_id': userinfo['sub'],
        'name': userinfo['name'],
        'picture': userinfo['picture']
    }
    return redirect('/') #redirect to home auth0


@app.route('/login')
def login():
    return auth0.authorize_redirect(redirect_uri=AUTH0_CALLBACK_URL, audience=AUTH0_AUDIENCE)


@app.route('/logout')
def logout():
    session.clear()
    params = {'returnTo': url_for('home', _external=True), 'client_id': AUTH0_CLIENT_ID}
    return redirect("https://www.icwsm.org")


@app.route('/dashboard')
#@requires_auth
def dashboard():
    return render_template('dashboard.html',
                           userinfo=session[constants.PROFILE_KEY],
                           userinfo_pretty=json.dumps(session[constants.JWT_PAYLOAD], indent=4))
                           
#-------------------------------end try auth0 ---------------------------------------------------------

if __name__ == "__main__":
    args = parse_arguments()

    site_data_path = args.path
    extra_files = main(site_data_path)

    if args.build:
        freezer.freeze()
    else:
        debug_val = False
        if os.getenv("FLASK_DEBUG") == "True":
            debug_val = True

        app.run(port=5000,host='0.0.0.0', debug=debug_val, extra_files=extra_files)
