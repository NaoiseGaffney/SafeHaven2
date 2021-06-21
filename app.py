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
import json
from json.decoder import JSONDecodeError
from jsonschema import validate, ValidationError

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

# --- // Classes -> MongoDB Collections: User, Venue, Review
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
class Venue(db.Document):
    name = db.StringField(default="")
    venue_type = db.StringField(choices=["Bar or Pub", "Restaurant", "Club", "Theatre", "Health", "Gym", "Hotel", "Other", "Church", "Group", "Wedding Venue", "Neighbourhood", "Market", "Cabaret", "Café", "Museum"])
    address = db.StringField(default="")
    post_code = db.StringField(default="")
    city = db.StringField(default="")
    country = db.StringField(default="")
    url = db.StringField(default="")
    lat = db.StringField(default="")
    lon = db.StringField(default="")
    user = db.StringField(default="admin")

    meta = {
        "auto_create_index": True,
        "index_background": True,
        "indexes": ["name", "city", "country"],
        "ordering": ["name"],
    }


class Review(db.Document):
    text_field = db.StringField(default="", maxlength=2000)
    user = db.StringField(default="")
    venue_id = db.ObjectIdField(Venue)

    # LGBTQ+ Toggles/Switches/Tickboxes
    rainbow_flag = db.BooleanField(default=False)
    welcoming = db.BooleanField(default=False)
    program_focus = db.BooleanField(default=False)

    # Relationships (Tags: default)
    tags_LGBTQ = db.BooleanField(default=False)
    tags_Trans = db.BooleanField(default=False)
    tags_Youth = db.BooleanField(default=False)
    tags_Shelter = db.BooleanField(default=False)

    meta = {
        "auto_create_index": True,
        "index_background": True,
        "indexes": ["venue_id"],
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
    Landing/Home Page, accessible before sign in/login. If logged in, user is redirected to the Main Page.
    At first access/touch the user 'admin' is created using environment variables for the password and email address.
    The admin user creation is here as it will be created twice on Heroku if placed in the main code.
    """

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


# --- // CRUD for Venue
@app.route("/main")
@app.route("/main/<int:page>")
def main_page(page=1):
    """
    The "R" in CRUD, a list of all venues.
    """
    venues_list = Venue.objects()
    review_list = Review.objects()
    venues_list_pagination = venues_list.paginate(page=page, per_page=4)
    return render_template("main.html", review_list=review_list, venues_list_pagination=venues_list_pagination, page_prev=(page - 1), page_next=(page + 1))


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

    types = {"Bar or Pub", "Restaurant", "Club", "Theatre", "Health", "Gym", "Hotel", "Other", "Church", "Group", "Wedding Venue", "Neighbourhood", "Market", "Cabaret", "Café", "Museum"}
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
        venue_type=request.form.get("venue_type"),
        address=request.form.get("address"),
        post_code=request.form.get("post_code"),
        city=request.form.get("city"),
        country=request.form.get("country"),
        url=request.form.get("url"),
        user=current_user.username
    )

    try:
        venue.save()
        flash("The venue was saved!", "success")
    except Exception:
        flash("The venue was NOT saved!", "danger")
    return redirect(url_for("main_page"))


@app.route("/edit_venue/<id>", methods=["POST", "GET"])
@login_required
@roles_required("Admin")
@app.errorhandler(CSRFError)
def edit_venue(id):
    venue = Venue.objects.get(id=id)
    types = {"Bar or Pub", "Restaurant", "Club", "Theatre", "Health", "Gym", "Hotel", "Other", "Church", "Group", "Wedding Venue", "Neighbourhood", "Market", "Cabaret", "Café", "Museum"}
    sorted_types = sorted(types)

    return render_template("edit_venue.html", venue=venue, sorted_types=sorted_types)


@app.route("/update_venue/<id>", methods=["POST", "GET"])
@login_required
@roles_required("Admin")
@app.errorhandler(CSRFError)
def update_venue(id):
    """
    The "U" in CRUD, update the venue form.
    """
    venue = Venue.objects.get(id=id)
    venue_form = {
        "name": request.form.get("name"),
        "venue_type": request.form.get("venue_type"),
        "address": request.form.get("address"),
        "post_code": request.form.get("post_code"),
        "city": request.form.get("city"),
        "country": request.form.get("country"),
        "url": request.form.get("url"),
        "user": venue.user
    }

    try:
        venue.update(**venue_form)
        flash("The venue was updated!", "success")
    except Exception:
        flash("The venue was NOT updated!", "danger")
    return redirect(url_for("main_page"))


@app.route("/delete_venue/<id>", methods=["POST", "GET"])
@login_required
@roles_required("Admin")
@app.errorhandler(CSRFError)
def delete_venue(id):
    """
    The "D" in CRUD, delete the venue and associated reviews based on user.
    """
    venue = Venue.objects.get(id=id)
    reviews = Review.objects(user=venue.user)

    try:
        venue.delete()
        reviews.delete()
        flash("The venue was deleted!", "success")
    except Exception:
        flash("The venue was NOT deleted!", "danger")
    return redirect(url_for("main_page"))


# --- // CRUD for Review
@app.route("/add_review/<id>")
@login_required
@app.errorhandler(CSRFError)
def add_review(id):
    print(id)
    return render_template("add_review.html", id=id)


@app.route("/save_review/<id>", methods=["POST"])
@login_required
@app.errorhandler(CSRFError)
def save_review(id):
    """
    The "C" in CRUD, save the filled in venue review form.
    """
    review = Review(
        text_field=request.form.get("text_field"),
        venue_id=id,
        rainbow_flag=request.form.get("rainbow_flag"),
        welcoming=request.form.get("welcoming"),
        program_focus=request.form.get("program_focus"),
        tags_LGBTQ=request.form.get("tags_LGBTQ"),
        tags_Trans=request.form.get("tags_Trans"),
        tags_Youth=request.form.get("tags_Youth"),
        tags_Shelter=request.form.get("tags_Shelter"),
        user=current_user.username
    )

    try:
        review.save()
        flash("The review was saved!", "success")
    except Exception:
        flash("The review was NOT saved!", "danger")
    return redirect(url_for("main_page"))


@app.route("/delete_review/<id>", methods=["POST"])
@login_required
@roles_required("Admin")
@app.errorhandler(CSRFError)
def delete_review(id):
    """
    The "D" in CRUD, delete an offensive review by Admin.
    """
    review = Review.objects.get(id)

    try:
        review.delete()
        flash("The review was deleted!", "success")
    except Exception:
        flash("The review was NOT deleted!", "danger")
    return redirect(url_for("main_page"))


# --- // Load JSON file of Venues
@app.route("/load_venues")
@roles_required("Admin")
def load_venues():
    """
    Create the venues Collection if it does not exist. First validation: Venue Collection exists. Second validation: FileNotFound ('venues.json').
    Third validation: JSONDecodeError (valid JSON format). Fourth validation: correct JSON Schema = Venue Class.
    """
    try:
        with open("venues.json", "r", encoding="utf-8") as f:
            venues_dict = json.load(f)
    except FileNotFoundError:
        flash("'venues.json' can't be found.", "danger")
    except json.decoder.JSONDecodeError:
        flash("'venues.json' isn't a proper JSON file.", "danger")
        return redirect(url_for("main_page"))

    venues_schema = {
        "type": "object",
        "properties": {
                "name": {"type": "string"},
                "venue_type": {"type": "string"},
                "address": {"type": "string"},
                "post_code": {"type": "string"},
                "city": {"type": "string"},
                "country": {"type": "string"},
                "lat": {"type": "string"},
                "lon": {"type": "string"},
        },
    }

    try:
        for venue in venues_dict:
            validate(instance=venue, schema=venues_schema)
    except ValidationError:
        venues_title = venue["name"]
        flash("'venues.json' has JSON Schema errors.", "danger")
        return redirect(url_for("admin_dashboard"))

    try:
        venue_instances = [Venue(**data) for data in venues_dict]
        Venue.objects.insert(venue_instances, load_bulk=False)
        flash("Venues Collection created.", "success")
    except Exception:
        flash(f"Venues Collection NOT created.", "danger")
    finally:
        return redirect(url_for("main_page") or url_for("home_page"))


# --- // Error Handlers for 400 CSRF Error (Bad Request), 404 Page Not Found, 405 Method Not Allowed, and 500 Internal Server Error.
@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    excuse = "Apologies, the Safe Havens Security Detail have omitted to secure this page! We're calling them back from their lunch-break to fix this. Please click on [ Home ] to go to the Home Page, or click on [ Sign Out ] below."
    return render_template("oops.html", error=error.description, excuse=excuse, error_type="Client: 400 - Bad Request")


@app.errorhandler(404)
def not_found(error):
    excuse = "Apologies, our Staff are lost in the Safe Havens! Please click on [ Home ] to go to the Home Page, or click on [ Sign Out ] below."
    return render_template("oops.html", error=error, excuse=excuse, error_type="Client: 404 - Page Not Found")


@app.errorhandler(405)
def not_found(error):
    excuse = "Apologies, our Staff won't allow you to do this! Please click on [ Home ] to go to the Home Page, or click on [ Sign Out ] below."
    return render_template("oops.html", error=error, excuse=excuse, error_type="Client: 405 - Method Not Allowed")


@app.errorhandler(500)
def internal_error(error):
    excuse = "Apologies, something serious occurred and the Staff are working on resolving the issue! This section is cordoned off for now. Please click on [ Home ] to go to the Home Page, or click on [ Sign Out ] below."
    return render_template("oops.html", error=error, excuse=excuse, error_type="Server: 500 - Internal Server Error")


if __name__ == "__main__":
    if os.environ.get("APPDEBUG") == "ON":
        app.run(host=os.environ.get("IP"), port=os.environ.get("PORT"), debug=True)
    else:
        app.run(host=os.environ.get("IP"), port=os.environ.get("PORT"), debug=False)
