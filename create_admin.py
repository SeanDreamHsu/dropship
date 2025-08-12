# create_admin.py

from app import app, db, User
from werkzeug.security import generate_password_hash

# Use the Flask application context to access the database
with app.app_context():
    # Check if an admin user already exists
    admin_user = User.query.filter_by(is_admin=True).first()

    if admin_user:
        print("An admin user already exists. No new admin account was created.")
    else:
        # If no admin user exists, create one with default credentials
        hashed_password = generate_password_hash('password123')
        default_admin = User(
            phone_number='1234567890',
            password=hashed_password,
            is_admin=True
        )

        db.session.add(default_admin)
        db.session.commit()

        print("Default admin user created successfully.")
        print("Credentials:")
        print("  Phone Number: 1234567890")
        print("  Password: password123")
