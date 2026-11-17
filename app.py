import os

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash


# --------------------------------------------------
# APPLICATION CONFIGURATION
# --------------------------------------------------

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "change-this-development-key",
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://lifelink:lifelink_dev_password@localhost:5432/lifelink",
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# --------------------------------------------------
# BLOOD GROUP COMPATIBILITY
# --------------------------------------------------

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]

# Keys are recipient blood groups; values are compatible donor groups.
COMPATIBLE_DONORS = {
    "A+": ["A+", "A-", "O+", "O-"],
    "A-": ["A-", "O-"],
    "B+": ["B+", "B-", "O+", "O-"],
    "B-": ["B-", "O-"],
    "AB+": BLOOD_GROUPS,
    "AB-": ["AB-", "A-", "B-", "O-"],
    "O+": ["O+", "O-"],
    "O-": ["O-"],
}


# --------------------------------------------------
# DATABASE MODELS
# --------------------------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="donor")

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
    )

    donor_profile = db.relationship(
        "DonorProfile",
        backref="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class DonorProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    blood_group = db.Column(db.String(3), nullable=False)
    city = db.Column(db.String(100), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)

    is_available = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )

    consent_to_contact = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
    )


class BloodRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    requester_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    patient_name = db.Column(db.String(120), nullable=False)
    blood_group = db.Column(db.String(3), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    hospital_name = db.Column(db.String(150), nullable=False)
    units_required = db.Column(db.Integer, nullable=False)

    urgency = db.Column(
        db.String(20),
        nullable=False,
        default="Normal",
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Pending",
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
    )


class DonorResponse(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    donor_id = db.Column(
        db.Integer,
        db.ForeignKey("donor_profile.id"),
        nullable=False,
    )

    blood_request_id = db.Column(
        db.Integer,
        db.ForeignKey("blood_request.id"),
        nullable=False,
    )

    response = db.Column(
        db.String(20),
        nullable=False,
    )

    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "donor_id",
            "blood_request_id",
            name="unique_donor_request_response",
        ),
    )


# --------------------------------------------------
# LOGIN MANAGEMENT
# --------------------------------------------------

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def index():
    three_days_ago = datetime.utcnow() - timedelta(days=3)

    # Recent active blood requests
    recent_requests = (
        BloodRequest.query
        .filter(
            BloodRequest.created_at >= three_days_ago,
            BloodRequest.status.in_(
                ("Pending", "Matching", "Accepted", "In Progress")
            ),
        )
        .order_by(BloodRequest.created_at.desc())
        .all()
    )
    successful_matches = (
        db.session.query(BloodRequest, DonorProfile, User)
        .join(
            DonorResponse,
            DonorResponse.blood_request_id == BloodRequest.id,
        )
        .join(
            DonorProfile,
            DonorProfile.id == DonorResponse.donor_id,
        )
        .join(
            User,
            User.id == DonorProfile.user_id,
        )
        .filter(
            DonorResponse.response == "Accepted",
            BloodRequest.status.in_(
                ("Accepted", "In Progress", "Completed")
            ),
            BloodRequest.created_at >= three_days_ago,
        )
        .order_by(BloodRequest.created_at.desc())
        .all()
    )

    successful_donations = (
        db.session.query(BloodRequest, DonorProfile, User)
        .join(
            DonorResponse,
            DonorResponse.blood_request_id == BloodRequest.id,
        )
        .join(
            DonorProfile,
            DonorProfile.id == DonorResponse.donor_id,
        )
        .join(
            User,
            User.id == DonorProfile.user_id,
        )
        .filter(
            BloodRequest.status == "Completed",
            DonorResponse.response == "Accepted",
        )
        .order_by(BloodRequest.created_at.desc())
        .all()
    )

    # All registered donors
    community_donors = (
        db.session.query(DonorProfile, User)
        .join(User, User.id == DonorProfile.user_id)
        .order_by(DonorProfile.created_at.desc())
        .all()
    )

    return render_template(
        "index.html",
        blood_groups=BLOOD_GROUPS,
        recent_requests=recent_requests,
        successful_donations=successful_donations,
        successful_matches=successful_matches,
        community_donors=community_donors,
    )

# --------------------------------------------------
# USER REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "donor")

        if role not in ("donor", "requester"):
            role = "donor"

        if not full_name or not email or len(password) < 8:
            flash(
                "Enter your name and email, and use a password of at least 8 characters.",
                "error",
            )
            return render_template(
                "register.html",
                blood_groups=BLOOD_GROUPS,
            )

        existing_user = db.session.scalar(
            db.select(User).where(func.lower(User.email) == email)
        )

        if existing_user:
            flash("An account with that email already exists.", "error")
            return render_template(
                "register.html",
                blood_groups=BLOOD_GROUPS,
            )

        user = User(
            full_name=full_name,
            email=email,
            role=role,
        )
        user.set_password(password)

        db.session.add(user)
        db.session.flush()

        if role == "donor":
            blood_group = request.form.get("blood_group", "")
            city = request.form.get("city", "").strip()
            phone = request.form.get("phone", "").strip()
            consent = request.form.get("consent_to_contact") == "on"

            if (
                blood_group not in BLOOD_GROUPS
                or not city
                or not phone
                or not consent
            ):
                db.session.rollback()
                flash(
                    "Donor registration requires a valid blood group, city, phone number and contact consent.",
                    "error",
                )
                return render_template(
                    "register.html",
                    blood_groups=BLOOD_GROUPS,
                )

            donor = DonorProfile(
                user_id=user.id,
                blood_group=blood_group,
                city=city,
                phone=phone,
                consent_to_contact=consent,
            )
            db.session.add(donor)

        db.session.commit()
        login_user(user)
        flash("Your account has been created.", "success")
        return redirect(url_for("index"))

    return render_template(
        "register.html",
        blood_groups=BLOOD_GROUPS,
    )


# --------------------------------------------------
# USER LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = db.session.scalar(
            db.select(User).where(func.lower(User.email) == email)
        )

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("index"))

        flash("Email or password is incorrect.", "error")

    return render_template("login.html")


# --------------------------------------------------
# USER LOGOUT
# --------------------------------------------------

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# --------------------------------------------------
# FIND BLOOD DONORS
# --------------------------------------------------

@app.route("/find-donors")
def find_donors():
    blood_group = request.args.get("blood_group", "")
    city = request.args.get("city", "").strip()

    donors = []
    searched = False

    if blood_group in BLOOD_GROUPS and city:
        searched = True
        compatible = COMPATIBLE_DONORS[blood_group]

        donors = db.session.scalars(
            db.select(DonorProfile)
            .join(User)
            .where(
                DonorProfile.blood_group.in_(compatible),
                func.lower(DonorProfile.city) == city.lower(),
                DonorProfile.is_available.is_(True),
                DonorProfile.consent_to_contact.is_(True),
            )
            .order_by(DonorProfile.created_at.desc())
        ).all()

    return render_template(
        "find_donors.html",
        donors=donors,
        blood_groups=BLOOD_GROUPS,
        selected_group=blood_group,
        city=city,
        searched=searched,
    )


# --------------------------------------------------
# SUBMIT EMERGENCY BLOOD REQUEST
# --------------------------------------------------

@app.route("/request-blood", methods=["GET", "POST"])
@login_required
def request_blood():
    if current_user.role != "requester":
        flash(
            "Only requester accounts can submit blood requests.",
            "error",
        )
        return redirect(url_for("index"))

    if request.method == "POST":
        patient_name = request.form.get("patient_name", "").strip()
        blood_group = request.form.get("blood_group", "")
        city = request.form.get("city", "").strip()
        hospital_name = request.form.get("hospital_name", "").strip()
        units_required = request.form.get("units_required", type=int)
        urgency = request.form.get("urgency", "")

        if (
            not patient_name
            or blood_group not in BLOOD_GROUPS
            or not city
            or not hospital_name
            or units_required is None
            or not 1 <= units_required <= 20
            or urgency not in ("Normal", "Urgent", "Critical")
        ):
            flash(
                "Please enter valid details for every field.",
                "error",
            )
            return render_template(
                "request_blood.html",
                blood_groups=BLOOD_GROUPS,
            )

        # Set the initial status based on whether a suitable donor exists.
        compatible_groups = COMPATIBLE_DONORS[blood_group]
        matching_donor_exists = DonorProfile.query.filter(
            DonorProfile.blood_group.in_(compatible_groups),
            func.lower(DonorProfile.city) == city.lower(),
            DonorProfile.is_available.is_(True),
            DonorProfile.consent_to_contact.is_(True),
        ).first() is not None

        blood_request = BloodRequest(
            requester_id=current_user.id,
            patient_name=patient_name,
            blood_group=blood_group,
            city=city,
            hospital_name=hospital_name,
            units_required=units_required,
            urgency=urgency,
            status="Matching" if matching_donor_exists else "Pending",
        )

        db.session.add(blood_request)
        db.session.commit()

        flash(
            "Your blood request has been submitted successfully!",
            "success",
        )
        return redirect(url_for("my_requests"))

    return render_template(
        "request_blood.html",
        blood_groups=BLOOD_GROUPS,
    )


# --------------------------------------------------
# REQUESTER DASHBOARD AND DONOR MATCHING
# --------------------------------------------------

@app.route("/my-requests")
@login_required
def my_requests():
    if current_user.role != "requester":
        flash("This page is only for requester accounts.", "error")
        return redirect(url_for("index"))

    blood_requests = BloodRequest.query.filter_by(
        requester_id=current_user.id
    ).order_by(BloodRequest.created_at.desc()).all()

    matching_donors = {}
    assigned_donors = {}
    status_changed = False

    for blood_request in blood_requests:
        if blood_request.status in ("Pending", "Matching"):
            compatible_groups = COMPATIBLE_DONORS.get(
                blood_request.blood_group,
                [],
            )

            declined_donor_ids = db.select(
                DonorResponse.donor_id
            ).where(
                DonorResponse.blood_request_id == blood_request.id,
                DonorResponse.response == "Declined",
            )

            donors = DonorProfile.query.filter(
                DonorProfile.blood_group.in_(compatible_groups),
                func.lower(DonorProfile.city) == blood_request.city.lower(),
                DonorProfile.is_available.is_(True),
                DonorProfile.consent_to_contact.is_(True),
                ~DonorProfile.id.in_(declined_donor_ids),
            ).order_by(
                DonorProfile.created_at.desc()
            ).all()

            matching_donors[blood_request.id] = donors

            new_status = "Matching" if donors else "Pending"
            if blood_request.status != new_status:
                blood_request.status = new_status
                status_changed = True
        else:
            matching_donors[blood_request.id] = []

        if blood_request.status in ("Accepted", "In Progress", "Completed"):
            assigned_donors[blood_request.id] = (
                DonorProfile.query
                .join(
                    DonorResponse,
                    DonorResponse.donor_id == DonorProfile.id,
                )
                .filter(
                    DonorResponse.blood_request_id == blood_request.id,
                    DonorResponse.response == "Accepted",
                )
                .first()
            )
        else:
            assigned_donors[blood_request.id] = None

    if status_changed:
        db.session.commit()

    return render_template(
        "my_requests.html",
        blood_requests=blood_requests,
        matching_donors=matching_donors,
        assigned_donors=assigned_donors,
    )


# --------------------------------------------------
# CANCEL BLOOD REQUEST
# --------------------------------------------------

@app.route("/cancel-request/<int:request_id>", methods=["POST"])
@login_required
def cancel_request(request_id):
    if current_user.role != "requester":
        flash("Only requesters can cancel requests.", "error")
        return redirect(url_for("index"))

    blood_request = BloodRequest.query.filter_by(
        id=request_id,
        requester_id=current_user.id,
    ).first_or_404()

    if blood_request.status not in ("Pending", "Matching"):
        flash(
            "Only pending or matching requests can be cancelled.",
            "error",
        )
    else:
        blood_request.status = "Cancelled"
        db.session.commit()
        flash("Blood request cancelled successfully.", "success")

    return redirect(url_for("my_requests"))


# --------------------------------------------------
# DONOR DASHBOARD
# --------------------------------------------------

@app.route("/donor-dashboard")
@login_required
def donor_dashboard():
    if current_user.role != "donor":
        flash("This page is only for donor accounts.", "error")
        return redirect(url_for("index"))

    donor_profile = DonorProfile.query.filter_by(
        user_id=current_user.id
    ).first()

    if donor_profile is None:
        flash("Donor profile not found.", "error")
        return redirect(url_for("index"))

    compatible_recipient_groups = [
        recipient_group
        for recipient_group, donor_groups in COMPATIBLE_DONORS.items()
        if donor_profile.blood_group in donor_groups
    ]

    blood_requests = []

    if donor_profile.is_available and donor_profile.consent_to_contact:
        responded_request_ids = db.select(
            DonorResponse.blood_request_id
        ).where(
            DonorResponse.donor_id == donor_profile.id
        )

        blood_requests = BloodRequest.query.filter(
            func.lower(BloodRequest.city) == donor_profile.city.lower(),
            BloodRequest.blood_group.in_(compatible_recipient_groups),
            BloodRequest.status.in_(("Pending", "Matching")),
            ~BloodRequest.id.in_(responded_request_ids),
        ).order_by(
            BloodRequest.created_at.desc()
        ).all()

    accepted_requests = (
        BloodRequest.query
        .join(
            DonorResponse,
            DonorResponse.blood_request_id == BloodRequest.id,
        )
        .filter(
            DonorResponse.donor_id == donor_profile.id,
            DonorResponse.response == "Accepted",
            BloodRequest.status.in_(("Accepted", "In Progress")),
        )
        .order_by(BloodRequest.created_at.desc())
        .all()
    )

    completed_donations = (
        BloodRequest.query
        .join(
            DonorResponse,
            DonorResponse.blood_request_id == BloodRequest.id,
        )
        .filter(
            DonorResponse.donor_id == donor_profile.id,
            DonorResponse.response == "Accepted",
            BloodRequest.status == "Completed",
        )
        .order_by(BloodRequest.created_at.desc())
        .all()
    )

    return render_template(
        "donor_dashboard.html",
        donor_profile=donor_profile,
        blood_requests=blood_requests,
        accepted_requests=accepted_requests,
        completed_donations=completed_donations,
    )


# --------------------------------------------------
# DONOR ACCEPT OR DECLINE A REQUEST
# --------------------------------------------------

@app.route(
    "/respond-to-request/<int:request_id>/<action>",
    methods=["POST"],
)
@login_required
def respond_to_request(request_id, action):
    if current_user.role != "donor":
        flash("Only donors can respond to requests.", "error")
        return redirect(url_for("index"))

    if action not in ("accept", "decline"):
        flash("Invalid response.", "error")
        return redirect(url_for("donor_dashboard"))

    donor_profile = DonorProfile.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    blood_request = BloodRequest.query.get_or_404(request_id)

    if not donor_profile.is_available:
        flash("You must be available to respond.", "error")
        return redirect(url_for("donor_dashboard"))

    if not donor_profile.consent_to_contact:
        flash("You must consent to being contacted before responding.", "error")
        return redirect(url_for("donor_dashboard"))

    if blood_request.status not in ("Pending", "Matching"):
        flash("This request is no longer available.", "error")
        return redirect(url_for("donor_dashboard"))

    compatible_donors = COMPATIBLE_DONORS.get(
        blood_request.blood_group,
        [],
    )

    if (
        donor_profile.blood_group not in compatible_donors
        or donor_profile.city.lower() != blood_request.city.lower()
    ):
        flash("This request does not match your profile.", "error")
        return redirect(url_for("donor_dashboard"))

    existing_response = DonorResponse.query.filter_by(
        donor_id=donor_profile.id,
        blood_request_id=blood_request.id,
    ).first()

    if existing_response:
        flash("You have already responded to this request.", "error")
        return redirect(url_for("donor_dashboard"))

    if action == "accept":
        donor_response = DonorResponse(
            donor_id=donor_profile.id,
            blood_request_id=blood_request.id,
            response="Accepted",
        )
        blood_request.status = "Accepted"
        flash("You have accepted the blood request!", "success")
    else:
        donor_response = DonorResponse(
            donor_id=donor_profile.id,
            blood_request_id=blood_request.id,
            response="Declined",
        )
        flash("You have declined the blood request.", "success")

    db.session.add(donor_response)
    db.session.commit()

    return redirect(url_for("donor_dashboard"))


# --------------------------------------------------
# CHANGE DONOR AVAILABILITY
# --------------------------------------------------

@app.route("/toggle-availability", methods=["POST"])
@login_required
def toggle_availability():
    if current_user.role != "donor":
        flash("Only donors can change availability.", "error")
        return redirect(url_for("index"))

    donor_profile = DonorProfile.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    donor_profile.is_available = not donor_profile.is_available
    db.session.commit()

    if donor_profile.is_available:
        flash("You are now available for blood requests.", "success")
    else:
        flash("You are now unavailable for blood requests.", "success")

    return redirect(url_for("donor_dashboard"))


# --------------------------------------------------
# MOVE AN ACCEPTED REQUEST TO IN PROGRESS
# --------------------------------------------------

@app.route("/start-donation/<int:request_id>", methods=["POST"])
@login_required
def start_donation(request_id):
    if current_user.role != "donor":
        flash("Only donors can update donation status.", "error")
        return redirect(url_for("index"))

    donor_profile = DonorProfile.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    DonorResponse.query.filter_by(
        donor_id=donor_profile.id,
        blood_request_id=request_id,
        response="Accepted",
    ).first_or_404()

    blood_request = BloodRequest.query.get_or_404(request_id)

    if blood_request.status != "Accepted":
        flash("This request cannot be moved to In Progress.", "error")
        return redirect(url_for("donor_dashboard"))

    blood_request.status = "In Progress"
    db.session.commit()

    flash("Request status updated to In Progress.", "success")
    return redirect(url_for("donor_dashboard"))


# --------------------------------------------------
# MARK A DONATION REQUEST AS COMPLETED
# --------------------------------------------------

@app.route("/complete-donation/<int:request_id>", methods=["POST"])
@login_required
def complete_donation(request_id):
    if current_user.role != "donor":
        flash("Only donors can update donation status.", "error")
        return redirect(url_for("index"))

    donor_profile = DonorProfile.query.filter_by(
        user_id=current_user.id
    ).first_or_404()

    DonorResponse.query.filter_by(
        donor_id=donor_profile.id,
        blood_request_id=request_id,
        response="Accepted",
    ).first_or_404()

    blood_request = BloodRequest.query.get_or_404(request_id)

    if blood_request.status != "In Progress":
        flash("This request must be In Progress before completion.", "error")
        return redirect(url_for("donor_dashboard"))

    blood_request.status = "Completed"
    db.session.commit()

    flash("Request marked as completed successfully!", "success")
    return redirect(url_for("donor_dashboard"))


# --------------------------------------------------
# DATABASE INITIALIZATION
# --------------------------------------------------

@app.cli.command("init-db")
def init_db():
    """Create database tables for local development."""
    db.create_all()
    print("Database tables created.")


# --------------------------------------------------
# RUN APPLICATION
# --------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)
