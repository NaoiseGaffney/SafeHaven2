import os
from flask import Flask
import gunicorn
import datetime
from datetime import timedelta
from flask_mongoengine import (
    MongoEngine,
    MongoEngineSession,
    MongoEngineSessionInterface,
)
from flask_user import (
    login_required,
    UserManager,
    UserMixin,
    current_user,
    roles_required,
)
from flask_login import logout_user
from flask import (
    Flask,
    render_template_string,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    session,
)
from mongoengine.fields import ReferenceField
from flask_wtf.csrf import CSRFProtect, CSRFError

from config import ConfigClass

from dotenv import load_dotenv
from pathlib import Path

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

if os.environ.get("FDT") == "ON":
    from flask_debugtoolbar import DebugToolbarExtension

# --- // Application Factory Setup (based on the Flask-User example for MongoDB)
# https://flask-user.readthedocs.io/en/latest/mongodb_app.html
# Setup Flask and load app.config
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.from_object(__name__ + ".ConfigClass")
csrf = CSRFProtect(app)
csrf.init_app(app)

if os.environ.get("FDT") == "ON":
    app.debug = True

# Setup Flask-MongoEngine --> MongoEngine --> PyMongo --> MongoDB
db = MongoEngine(app)

# Use Flask Sessions with Mongoengine
app.session_interface = MongoEngineSessionInterface(db)

# Initiate the Flask Debug Toolbar Extension
if os.environ.get("FDT") == "ON":
    toolbar = DebugToolbarExtension(app)

# --- // Classes -> MongoDB Collections: User, Place.
# Flask-User User Class (Collection) extended with email_confirmed_at
# Added username indexing and background-indexing for performance


class User(db.Document, UserMixin):
    # Active set to True to allow login of user
    active = db.BooleanField(default=True)

    # User authentication information
    username = db.StringField(default="")
    password = db.StringField()

    # User information
    first_name = db.StringField(default="")
    last_name = db.StringField(default="")
    email = db.StringField(default="")
    email_confirmed_at = db.DateTimeField()
    # Required for the e-mail confirmation, and subsequent login.

    # Relationships  (Roles: user or user and Admin)
    roles = db.ListField(db.StringField(), default=["user"])

    meta = {
        "auto_create_index": True,
        "index_background": True,
        "indexes": ["username"],
    }


# Venue Class (Collection) containing the fields related to the venues that users can view, create, and update.
# Delete own venue creation?
class Venue(db.Document):
    name = db.StringField(default="")
    type = db.StringField(choices=["Bar or Pub", "Restaurant", "Club", "Theater", "Health", "Gym", "Hotel", "Other"])
    address = db.StringField(default="")
    post_code = db.StringField(default="")
    city = db.StringField(default="")
    country = db.StringField(default="")

    # Key Identifiers (Ed's list)
    pinkwashing = db.BooleanField(default=False)
    identity = db.BooleanField(default=False)
    inclusive = db.BooleanField(default=False)

    # Relationships  (Tags: default and/or user created?) (User created the Venue)
    tags_LGBTQ = db.BooleanField(default=False)
    tags_Trans = db.BooleanField(default=False)
    tags_Youth = db.BooleanField(default=False)
    tags_Shelter = db.BooleanField(default=False)
    user = db.StringField(default="")

    meta = {
        "auto_create_index": True,
        "index_background": True,
        "indexes": ["name", "city", "country"],
    }


# Setup Flask-User and specify the User data-model
user_manager = UserManager(app, db, User)


# --- // Safe Havens Main Routes (Endpoints): CRUD.
@app.route("/")
@app.route("/index")
@app.route("/index.htm")
@app.route("/index.html")
def home_page():
    """
    Landing/Home Page, accessible before sign in/login. If logged in, user is redirected to the Member's Page.
    At first access/touch the user 'admin' is created using environment variables for the password and email address.
    The admin user creation is here as it will be created twice on Heroku if placed in the main code.
    """
    if current_user.is_authenticated:
        return redirect(url_for("main_page"))

    # Create admin user as first/default user, if admin does not exist.
    # Password and e-mail are set using environment variables.
    if not User.objects.filter(User.username == "admin"):
        try:
            user = User(
                username="admin",
                first_name="Administrator",
                last_name="Administrator",
                email=os.environ.get("MAIL_DEFAULT_SENDER"),
                email_confirmed_at=datetime.datetime.utcnow(),
                password=user_manager.hash_password(os.environ.get("ADMIN_PASSWORD")),
            )
            user.roles.append("Admin")
            user.save()

            flash("'admin' account created.", "success")
            app.logger.info(
                "'admin' account is created at startup if the user doesn't exist: [SUCCESS] - (index.html)."
            )
        except Exception:
            flash("'admin' account not created.", "danger")
            app.logger.critical(
                "'admin' account is created at startup if the user doesn't exist: [FAILURE] - (index.html)."
            )
    return render_template("home.html")


@app.route("/main")
def main_page():
    """
    The "R" in CRUD, a list of all venues.
    """
    venues_list = Venue.objects()
    return render_template("main.html", venues_list=venues_list)


@app.route("/add_venue")
@login_required
@app.errorhandler(CSRFError)
def add_venue():
    """
    Preparation for "C" in CRUD, add a venue. Present the form.
    """
    tags = {"LGBTQ+", "Trans", "Youth", "Shelter"}
    sorted_tags = sorted(tags)
    print(sorted_tags)

    types = {"Bar or Pub", "Restaurant", "Club", "Theater", "Health", "Gym", "Hotel", "Other"}
    sorted_types = sorted(types)
    print(sorted_types)

    venues = Venue.objects()
    print(venues.count())
    return render_template("add_venue.html", sorted_tags=sorted_tags, sorted_types=sorted_types, venues=venues)


@app.route("/save_venue", methods=["POST"])
@login_required
@app.errorhandler(CSRFError)
def save_venue():
    """
    The "C" in CRUD, save the filled in venue form.
    """
    venue = Venue(
        name=request.form.get("name"),
        type=request.form.get("type"),
        address=request.form.get("address"),
        post_code=request.form.get("post_code"),
        city=request.form.get("city"),
        country=request.form.get("country"),
        pinkwashing=request.form.get("pinkwashing"),
        identity=request.form.get("identity"),
        inclusive=request.form.get("inclusive"),
        tags_LGBTQ=request.form.get("tags_LGBTQ"),
        tags_Trans=request.form.get("tags_Trans"),
        tags_Youth=request.form.get("tags_Youth"),
        tags_Shelter=request.form.get("tags_Shelter"),
        user=current_user.username
    )

    try:
        venue.save()
        flash("The venue was saved!", "success")
    except Exception:
        flash("The venue was NOT saved!", "danger")
    return redirect(url_for("main_page"))


if __name__ == "__main__":
    if os.environ.get("APPDEBUG") == "ON":
        app.run(host=os.environ.get("IP"), port=os.environ.get("PORT"), debug=True)
    else:
        app.run(host=os.environ.get("IP"), port=os.environ.get("PORT"), debug=False)
