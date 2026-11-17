# LifeLink — initial working foundation

## Requirements
- Python 3.10+
- Docker Desktop (for the local PostgreSQL database)
- VS Code

## Setup
1. Open this folder in VS Code.
2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and replace `SECRET_KEY` with a long random value.
5. Start PostgreSQL:
   ```bash
   docker compose up -d
   ```
6. Create tables:
   ```bash
   flask --app app init-db
   ```
7. Start the app:
   ```bash
   flask --app app run --debug
   ```
8. Visit http://127.0.0.1:5000

## Included in this first milestone
- Real PostgreSQL persistence
- Donor and requester account registration
- Password hashing
- Login/logout
- Donor profile with blood group, city, availability and contact consent
- Search by recipient blood group and exact city
- Red-cell compatibility filtering
- No sample donor records or fabricated statistics

## Important
This is an early development foundation, not a production-ready medical service. Before public launch, add CSRF protection, rate limiting, email verification, secure contact relay, audit logging, admin review, consent withdrawal, request/match workflows, backups, HTTPS, and professional security testing. Donor matches are not medical clearance; final eligibility and compatibility must be verified by a licensed blood bank.
