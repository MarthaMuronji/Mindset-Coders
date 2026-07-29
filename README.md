# Mindset Coders Uganda — Website Rebuild

A full website rebuild for Mindset Coders Uganda, a STEM education nonprofit, built from scratch with Django and a custom front-end.

## Overview

A responsive, mobile-first site designed and built end-to-end — from initial brand system and layout through production deployment — for a nonprofit focused on STEM education. Currently in active development ahead of public launch, iterating directly with the client on content, branding, and page layout.

## Features

- **Custom brand system** — designed a visual identity and applied it consistently across the site
- **Responsive, mobile-first UI** — including scroll animations and a collapsible mobile navigation menu
- **Production deployment on Render** — managed PostgreSQL database, environment-based configuration, and static file optimization via WhiteNoise
- **Client collaboration workflow** — structured feedback cycles with the client to refine content and layout pre-launch

## Tech stack

Django · Python · HTML/CSS · JavaScript · PostgreSQL · Render · WhiteNoise

## Getting started locally

```bash
# Clone the repo
git clone https://github.com/MarthaMuronji/mindset-coders-website.git
cd mindset-coders-website

# Set up a virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env  # then fill in your own values

# Run migrations
python manage.py migrate

# Start the development server
python manage.py runserver
```

## Status

🔧 In active development — ahead of public launch.

## Screenshots

*(Add 2–3 screenshots here once the design is further along — homepage and mobile nav work well)*
