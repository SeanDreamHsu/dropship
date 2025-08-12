import os
from datetime import datetime, timezone, timedelta
from io import BytesIO
from functools import wraps
from collections import defaultdict
import pytz

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from dotenv import load_dotenv

# Removed Flask-Migrate imports as we are using db.create_all() directly for simplicity
# from flask_migrate import Migrate 

# Import TypeDecorator for custom SQLAlchemy type handling
from sqlalchemy.types import TypeDecorator, DateTime
# from sqlalchemy import create_engine # Not strictly needed for this file

# Load environment variables from .env file
load_dotenv()

# --- IMPORTANT: WeasyPrint Dependency Check ---
HTML = None 
# try:
#     from weasyprint import HTML
# except ImportError:
#     HTML = None
#     print("\n--------------------------------------------------------------")
#     print("WARNING: WeasyPrint not installed or its system dependencies missing.")
#     print("PDF generation will be disabled. To enable, install WeasyPrint and its dependencies.")
#     print("For Linux (Debian/Ubuntu): sudo apt-get install python3-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg-dev zlib1g-dev libpango1.0-dev libcairo2-dev")
#     print("For macOS (Homebrew): brew install cairo pango gdk-pixbuf libffi")
#     print("For Windows: Refer to WeasyPrint docs for complex setup, or omit PDF feature.")
#     print("--------------------------------------------------------------\n")

if HTML:
    print("\n--------------------------------------------------------------")
    print("WeasyPrint (PDF generation) is ENABLED. Ensure system dependencies are met.")
    print("--------------------------------------------------------------\n")
else:
    print("\n------------------------------------------------------------------------------------")
    print("WARNING: WeasyPrint (PDF generation) is DISABLED. PDF download will not function.")
    print("To enable, uncomment 'from weasyprint import HTML' and remove 'HTML = None',")
    print("then install system dependencies as per WeasyPrint documentation.")
    print("------------------------------------------------------------------------------------\n")


app = Flask(__name__)

# Flask App Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'a_default_secret_key_if_not_set')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///site.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Flask-Mail Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# Removed Flask-Migrate initialization as we are using db.create_all() directly
# migrate = Migrate(app, db) 

# Company Information (can be stored in DB or .env if needed)
COMPANY_NAME = os.getenv('COMPANY_NAME', 'MAIL+PC')
COMPANY_ADDRESS = os.getenv('COMPANY_ADDRESS', '310 E Orangethorpe Ave Ste M Placentia CA 92870')

# Define the timezone for display purposes (e.g., Pacific Time)
DISPLAY_TIMEZONE = pytz.timezone('America/Los_Angeles')


# --- Custom SQLAlchemy Type for UTC Datetimes ---
class UTCDateTime(TypeDecorator):
    """
    A DateTime type that forces UTC and timezone awareness.
    Stores datetimes as UTC in the database and loads them as timezone-aware UTC datetimes.
    """
    impl = DateTime 
    cache_ok = True 

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            else:
                return value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return value

# Database Models
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    created_at = db.Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))
    trackings = db.relationship('Tracking', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Tracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    tracking_number = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(UTCDateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Tracking {self.tracking_number}>"

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Removed the create_tables_on_first_request decorator
# It's no longer necessary with db.create_all() in the main block
# def create_tables_on_first_request(f):
#     @wraps(f)
#     def decorated_function(*args, **kwargs):
#         if not hasattr(app, '_tables_created'):
#             with app.app_context():
#                 db.create_all()
#                 app._tables_created = True 
#             print("Database tables created (if they didn't exist).")
#         return f(*args, **kwargs)
#     return decorated_function

# --- Routes ---
@app.route('/')
# Removed the decorator from here
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')
        
        if not phone_number or not password:
            flash('Phone number and password are required.', 'danger')
            return render_template('register.html')

        if User.query.filter_by(phone_number=phone_number).first():
            flash('Phone number already registered. Please log in.', 'warning')
            return redirect(url_for('login'))

        new_user = User(phone_number=phone_number)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        phone_number = request.form.get('phone_number')
        password = request.form.get('password')

        user = User.query.filter_by(phone_number=phone_number).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid phone number or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    all_user_trackings = Tracking.query.filter_by(user_id=current_user.id).order_by(Tracking.timestamp.desc()).all()

    # Group trackings by date in the DISPLAY_TIMEZONE
    trackings_by_display_date = defaultdict(list)
    for tracking in all_user_trackings:
        display_timestamp = tracking.timestamp.astimezone(DISPLAY_TIMEZONE)
        drop_off_date = display_timestamp.date()
        trackings_by_display_date[drop_off_date].append(tracking)

    grouped_trackings = sorted(trackings_by_display_date.items(), key=lambda item: item[0], reverse=True)

    dashboard_data = []
    for date_obj, trackings_list in grouped_trackings:
        reference_tracking_id = trackings_list[0].id if trackings_list else None

        trackings_list_sorted = sorted(trackings_list, key=lambda t: t.timestamp)

        trackings_for_template = []
        for track in trackings_list_sorted:
            display_timestamp_item = track.timestamp.astimezone(DISPLAY_TIMEZONE)
            trackings_for_template.append({
                'id': track.id,
                'tracking_number': track.tracking_number,
                'timestamp': display_timestamp_item.strftime('%I:%M %p %Z'),
                'full_timestamp': display_timestamp_item.strftime('%Y-%m-%d %I:%M %p %Z')
            })

        dashboard_data.append({
            'date': date_obj.strftime('%Y-%m-%d'),
            'package_count': len(trackings_list),
            'trackings': trackings_for_template,
            'reference_id': reference_tracking_id
        })

    total_package_count = len(all_user_trackings)

    return render_template('dashboard.html', grouped_trackings=dashboard_data, total_package_count=total_package_count)

@app.route('/add-tracking', methods=['POST'])
@login_required
def add_tracking():
    tracking_number = request.form.get('tracking_number')
    if not tracking_number:
        flash('Tracking number is required.', 'danger')
        return redirect(url_for('dashboard'))

    existing_tracking = Tracking.query.filter_by(user_id=current_user.id, tracking_number=tracking_number).first()
    if existing_tracking:
        flash(f'Tracking number {tracking_number} already exists for your account.', 'warning')
        return redirect(url_for('dashboard'))

    new_tracking = Tracking(user_id=current_user.id, tracking_number=tracking_number)
    db.session.add(new_tracking)
    db.session.commit()
    flash('Package added successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/delete-tracking/<int:tracking_id>', methods=['POST'])
@login_required
def delete_tracking(tracking_id):
    tracking_to_delete = Tracking.query.filter_by(id=tracking_id, user_id=current_user.id).first()
    if tracking_to_delete:
        db.session.delete(tracking_to_delete)
        db.session.commit()
        flash('Tracking record deleted successfully.', 'success')
    else:
        flash('Tracking record not found or you do not have permission to delete it.', 'danger')
    return redirect(url_for('dashboard'))


@app.route('/get-tracking-details/<int:tracking_id>', methods=['GET'])
@login_required
def get_tracking_details(tracking_id):
    selected_tracking = Tracking.query.filter_by(id=tracking_id, user_id=current_user.id).first()
    if not selected_tracking:
        return jsonify({"success": False, "message": "Tracking record not found."}), 404

    receipt_date_obj_display_tz = selected_tracking.timestamp.astimezone(DISPLAY_TIMEZONE).date()

    start_of_day_display_tz = datetime.combine(receipt_date_obj_display_tz, datetime.min.time())
    end_of_day_display_tz = datetime.combine(receipt_date_obj_display_tz, datetime.max.time())

    start_of_day_utc = DISPLAY_TIMEZONE.localize(start_of_day_display_tz).astimezone(timezone.utc)
    end_of_day_utc = DISPLAY_TIMEZONE.localize(end_of_day_display_tz).astimezone(timezone.utc)


    same_day_trackings = Tracking.query.filter(
        Tracking.user_id == current_user.id,
        Tracking.timestamp >= start_of_day_utc,
        Tracking.timestamp <= end_of_day_utc
    ).order_by(Tracking.timestamp.asc()).all()

    if not same_day_trackings:
        return jsonify({"success": False, "message": "No tracking records found for this date."}), 404

    receipt_context = {
        "receipt_date": receipt_date_obj_display_tz.strftime('%Y-%m-%d'),
        "company_name": COMPANY_NAME,
        "company_address": COMPANY_ADDRESS,
        "trackings_for_day": [],
        "total_packages": len(same_day_trackings)
    }

    for track in same_day_trackings:
        display_timestamp_item = track.timestamp.astimezone(DISPLAY_TIMEZONE)
        receipt_context["trackings_for_day"].append({
            "tracking_number": track.tracking_number,
            "timestamp": display_timestamp_item.strftime('%I:%M %p %Z'),
            "full_timestamp": display_timestamp_item.strftime('%Y-%m-%d %I:%M %p %Z')
        })

    receipt_html = render_template('receipt.html', **receipt_context)
    return jsonify({"success": True, "receiptHtml": receipt_html, "receiptData": receipt_context})


@app.route('/email-receipt-dashboard/<int:tracking_id>', methods=['POST'])
@login_required
def email_receipt_dashboard(tracking_id):
    selected_tracking = Tracking.query.filter_by(id=tracking_id, user_id=current_user.id).first()
    if not selected_tracking:
        return jsonify({"success": False, "message": "Tracking record not found."}), 404

    receipt_date_obj_display_tz = selected_tracking.timestamp.astimezone(DISPLAY_TIMEZONE).date()

    start_of_day_display_tz = datetime.combine(receipt_date_obj_display_tz, datetime.min.time())
    end_of_day_display_tz = datetime.combine(receipt_date_obj_display_tz, datetime.max.time())

    start_of_day_utc = DISPLAY_TIMEZONE.localize(start_of_day_display_tz).astimezone(timezone.utc)
    end_of_day_utc = DISPLAY_TIMEZONE.localize(end_of_day_display_tz).astimezone(timezone.utc)

    same_day_trackings = Tracking.query.filter(
        Tracking.user_id == current_user.id,
        Tracking.timestamp >= start_of_day_utc,
        Tracking.timestamp <= end_of_day_utc
    ).order_by(Tracking.timestamp.asc()).all()

    if not same_day_trackings:
        return jsonify({"success": False, "message": "No tracking records found for this date to email."}), 404

    receipt_context = {
        "receipt_date": receipt_date_obj_display_tz.strftime('%Y-%m-%d'),
        "company_name": COMPANY_NAME,
        "company_address": COMPANY_ADDRESS,
        "trackings_for_day": [],
        "total_packages": len(same_day_trackings)
    }

    for track in same_day_trackings:
        display_timestamp_item = track.timestamp.astimezone(DISPLAY_TIMEZONE)
        receipt_context["trackings_for_day"].append({
            "tracking_number": track.tracking_number,
            "timestamp": display_timestamp_item.strftime('%I:%M %p %Z'),
            "full_timestamp": display_timestamp_item.strftime('%Y-%m-%d %I:%M %p %Z')
        })

    email_body_html = render_template('receipt.html', **receipt_context)

    try:
        recipient_email = request.form.get('recipient_email')
        if not recipient_email:
            return jsonify({"success": False, "message": "Recipient email is required."}), 400

        subject = f"Package Drop-off Receipt - {receipt_context['receipt_date']} ({receipt_context['total_packages']} items)"
        send_email(
            recipient_email,
            subject,
            email_body_html
        )
        return jsonify({"success": True, "message": "Receipt emailed successfully!"})
    except Exception as e:
        app.logger.error(f"Error sending email: {e}")
        return jsonify({"success": False, "message": f"Failed to send email: {str(e)}"}), 500


def send_email(to_email, subject, html_body):
    """Helper function to send email."""
    msg = Message(subject, recipients=[to_email])
    msg.html = html_body
    try:
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        raise


@app.route('/download-pdf-dashboard/<int:tracking_id>', methods=['GET'])
@login_required
def download_pdf_dashboard(tracking_id):
    selected_tracking = Tracking.query.filter_by(id=tracking_id, user_id=current_user.id).first()
    if not selected_tracking:
        return jsonify({"success": False, "message": "Tracking record not found."}), 404

    receipt_date_obj_display_tz = selected_tracking.timestamp.astimezone(DISPLAY_TIMEZONE).date()

    start_of_day_display_tz = datetime.combine(receipt_date_obj_display_tz, datetime.min.time())
    end_of_day_display_tz = datetime.combine(receipt_date_obj_display_tz, datetime.max.time())

    start_of_day_utc = DISPLAY_TIMEZONE.localize(start_of_day_display_tz).astimezone(timezone.utc)
    end_of_day_utc = DISPLAY_TIMEZONE.localize(end_of_day_display_tz).astimezone(timezone.utc)

    same_day_trackings = Tracking.query.filter(
        Tracking.user_id == current_user.id,
        Tracking.timestamp >= start_of_day_utc,
        Tracking.timestamp <= end_of_day_utc
    ).order_by(Tracking.timestamp.asc()).all()

    if not same_day_trackings:
        return jsonify({"success": False, "message": "No tracking records found for this date to generate PDF."}), 404

    receipt_context = {
        "receipt_date": receipt_date_obj_display_tz.strftime('%Y-%m-%d'),
        "company_name": COMPANY_NAME,
        "company_address": COMPANY_ADDRESS,
        "trackings_for_day": [],
        "total_packages": len(same_day_trackings)
    }

    for track in same_day_trackings:
        display_timestamp_item = track.timestamp.astimezone(DISPLAY_TIMEZONE)
        receipt_context["trackings_for_day"].append({
            "tracking_number": track.tracking_number,
            "timestamp": display_timestamp_item.strftime('%I:%M %p %Z'),
            "full_timestamp": display_timestamp_item.strftime('%Y-%m-%d %I:%M %p %Z')
        })

    if HTML: # Check if WeasyPrint was successfully imported
        rendered_html = render_template('receipt.html', **receipt_context)
        try:
            pdf_bytes = HTML(string=rendered_html).write_pdf()

            pdf_io = BytesIO(pdf_bytes)

            download_filename = f"receipt_{receipt_date_obj_display_tz.strftime('%Y%m%d')}_{receipt_context['total_packages']}_items.pdf"

            return send_file(
                pdf_io,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            app.logger.error(f"Error generating PDF: {e}")
            return jsonify({"success": False, "message": f"Failed to generate PDF: {str(e)}"}), 500
    else:
        return jsonify({"success": False, "message": "PDF generation (WeasyPrint) is not available on this server."}), 500


@app.route('/search-dropoffs')
@login_required
def search_dropoffs_page():
    """Renders the page for searching drop-offs by date range."""
    return render_template('search_dropoffs.html')

@app.route('/api/get-dropoffs-in-range', methods=['POST'])
@login_required
def get_dropoffs_in_range():
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')

    if not start_date_str or not end_date_str:
        return jsonify({"success": False, "message": "Start and end dates are required."}), 400

    try:
        # Interpret input dates as being in the DISPLAY_TIMEZONE
        start_date_display_tz = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_display_tz = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)

        # Localize these dates to the display timezone, then convert to UTC for database query
        start_date_utc = DISPLAY_TIMEZONE.localize(start_date_display_tz).astimezone(timezone.utc)
        # For the end date, ensure we include the entire day in the display timezone
        end_date_utc = DISPLAY_TIMEZONE.localize(end_date_display_tz + timedelta(days=1)).astimezone(timezone.utc)


    except ValueError:
        return jsonify({"success": False, "message": "Invalid date format. Please use YYYY-MM-DD."}), 400

    trackings_in_range = Tracking.query.filter(
        Tracking.user_id == current_user.id,
        Tracking.timestamp >= start_date_utc,
        Tracking.timestamp < end_date_utc
    ).order_by(Tracking.timestamp.asc()).all()

    results = []
    for track in trackings_in_range:
        # Convert UTC timestamp to display timezone for the response
        display_timestamp = track.timestamp.astimezone(DISPLAY_TIMEZONE)
        results.append({
            "tracking_number": track.tracking_number,
            "timestamp": display_timestamp.strftime('%Y-%m-%d %I:%M %p %Z')
        })

    return jsonify({
        "success": True,
        "trackings": results,
        "total_packages": len(results),
        "start_date": start_date_str,
        "end_date": end_date_str
    })

@app.route('/export-dropoffs-csv', methods=['GET'])
@login_required
def export_dropoffs_csv():
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    if not start_date_str or not end_date_str:
        flash('Start and end dates are required for CSV export.', 'danger')
        return redirect(url_for('search_dropoffs_page'))

    try:
        start_date_display_tz = datetime.strptime(start_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)
        end_date_display_tz = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=0, minute=0, second=0, microsecond=0)

        start_date_utc = DISPLAY_TIMEZONE.localize(start_date_display_tz).astimezone(timezone.utc)
        end_date_utc = DISPLAY_TIMEZONE.localize(end_date_display_tz + timedelta(days=1)).astimezone(timezone.utc)

    except ValueError:
        flash('Invalid date format for CSV export. Please use YYYY-MM-DD.', 'danger')
        return redirect(url_for('search_dropoffs_page'))

    trackings_in_range = Tracking.query.filter(
        Tracking.user_id == current_user.id,
        Tracking.timestamp >= start_date_utc,
        Tracking.timestamp < end_date_utc
    ).order_by(Tracking.timestamp.asc()).all()

    if not trackings_in_range:
        flash(f"No packages found for {start_date_str} to {end_date_str} to export.", 'info')
        return redirect(url_for('search_dropoffs_page'))

    from io import StringIO
    import csv 
    si = StringIO()
    cw = csv.writer(si)

    cw.writerow(['Tracking Number', 'Drop-off Date (Local Time)', 'Drop-off Time (Local Time)'])

    for track in trackings_in_range:
        display_timestamp = track.timestamp.astimezone(DISPLAY_TIMEZONE)
        cw.writerow([
            track.tracking_number,
            display_timestamp.strftime('%Y-%m-%d'),
            display_timestamp.strftime('%I:%M:%S %p %Z')
        ])

    output = si.getvalue()

    filename = f"dropoffs_{start_date_str}_to_{end_date_str}.csv"

    return send_file(
        BytesIO(output.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


if __name__ == '__main__':
    # This block ensures tables are created when you run 'python app.py' directly.
    # It's suitable for development.
    with app.app_context():
        db.create_all()
        print("Database tables created/checked.")
    app.run(debug=True)
