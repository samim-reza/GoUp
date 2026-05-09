# GoUp

GoUp is a Django-based dashboard for Facebook Lead Ads automation. It connects a Facebook account, syncs pages and forms, ingests leads via webhooks, and triggers follow-up messaging rules (email, SMS, WhatsApp).

<p align="center">
  <img src="dashboard/static/dashboard/images/hero-mockup.png" alt="GoUp Dashboard Mockup" width="800"><br/>
  <em>GoUp Interface & Dashboard Automation</em>
</p>

<p align="center">
  <img src="dashboard/static/dashboard/images/hero-abstract.png" alt="GoUp Abstract Flow" width="800"><br/>
  <em>Automated workflow from Facebook to WhatsApp & Email</em>
</p>

## Features
- Facebook OAuth connect and page/form sync
- Lead ingestion via Meta webhooks
- Rules engine for automated messaging
- Multi-user workspaces (owner + members)
- Dashboard with leads, templates, rules, and logs

## Tech Stack
- Django + Django REST Framework
- Celery + Redis
- PostgreSQL (or SQLite for local dev)
- Meta Graph API
- Twilio + SMTP for messaging

## Quick Start (Local)
1. Create and activate a virtualenv.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the web server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```
6. Start Celery worker (separate terminal):
   ```bash
   celery -A config worker -l INFO
   ```

## Environment Variables
Minimum required for Meta integration:
- `META_APP_ID`
- `META_APP_SECRET`
- `META_REDIRECT_URI` (must match Meta OAuth settings)
- `META_VERIFY_TOKEN` (webhook verification)
- `META_WEBHOOK_SECRET` (webhook signature validation)
- `META_OAUTH_SCOPES` (defaults in settings)

Email and Twilio are optional unless you plan to send messages:
- `EMAIL_*` settings
- `TWILIO_*` settings

Security defaults when `DJANGO_DEBUG=False`:
- `DJANGO_ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

## Meta App Setup (Lead Ads)
1. Create a Meta app and add **Facebook Login** and **Webhooks** products.
2. Add OAuth redirect URI:
   - `META_REDIRECT_URI` value (must match exactly).
3. Subscribe to `page` and `leadgen` webhooks.
4. Request or enable these permissions:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_manage_metadata`
   - `leads_retrieval`
   - `pages_manage_ads` (for form listing in many cases)

If non-owner users see "Feature unavailable", add them as app testers or request Advanced Access.

## OAuth Mode
The app supports two OAuth modes:
- Classic scopes via `META_OAUTH_SCOPES`
- Facebook Login for Business via `META_LOGIN_CONFIG_ID`

If Business Login config causes login errors, clear `META_LOGIN_CONFIG_ID` to fall back to classic scopes.

## Webhook Testing (ngrok)
1. Start ngrok:
   ```bash
   ngrok http 8000
   ```
2. Set:
   - `META_REDIRECT_URI` to the ngrok HTTPS callback
   - `DJANGO_ALLOWED_HOSTS` includes `.ngrok-free.app`
   - `CSRF_TRUSTED_ORIGINS` includes `https://*.ngrok-free.app`

## Dashboard Flow
1. Sign in or sign up.
2. Connect Facebook (owner only).
3. Sync pages and forms.
4. Create message templates and rules.
5. Leads arrive via webhook and trigger messages.

## Team Access
- Workspace has one owner and multiple members.
- Owner can invite by email, remove members, and transfer ownership.
- Members can view data but cannot connect or sync Facebook.

## Notes
- Keep `.env` secrets out of git.
- Rotate credentials if they are ever exposed.

## License
Private project. All rights reserved.
