# 📡 Service Uptime Monitor

A real-time, self-hosted service monitoring dashboard built with Python and Flask. Perfect for keeping an eye on the health of your APIs, websites, TCP ports, and SSL certificates.

**Live Demo:** [View the Live Dashboard](https://uptime-monitor-z45i.onrender.com/)

---

## Preview

<img width="1605" height="712" alt="um" src="https://github.com/user-attachments/assets/ed333d2f-da41-4c1f-8dd4-51dfa443edd9" />

---

## Features

- **Multi-Protocol Checks**: Monitor HTTP/HTTPS websites, TCP ports, and SSL certificate expiry dates.
- **Live Dashboard**: Beautiful teal-themed UI with auto-refresh and a countdown timer.
- **Persistent History**: All uptime data is stored in a SQLite database. Restart the server without losing your history.
- **Rolling Uptime Metrics**: View uptime percentages for the last 1 hour, 24 hours, and 7 days.
- **Smart Alerts**: Sends email notifications when a service goes down and when it recovers (optional, configurable via environment variables).
- **Dockerized**: Easy to deploy anywhere using Docker.

---

## Tech Stack

- **Backend**: Python 3.13, Flask
- **Database**: SQLite
- **Containerization**: Docker
- **Frontend**: HTML5, CSS3 (Custom Teal Theme), Vanilla JavaScript
- **Deployment**: Render

---

## Quick Start (Run Locally)

Get your own instance running in seconds:

1. Clone the repository:
   git clone https://github.com/Vojislav77/uptime-monitor.git
   cd uptime-monitor

2. Run the launcher script (sets up everything automatically):
   ./start.sh

3. Open your browser and go to: http://localhost:5000

The start.sh script automatically creates a Python virtual environment, installs flask and requests, and launches the app. No manual setup required!

---

## Run with Docker (Portfolio Bonus)

Prefer containers? Build and run using Docker:

docker build -t uptime-monitor .
docker run -p 5000:5000 uptime-monitor

Then visit http://localhost:5000.

---

## Configuration

### Adding Your Own Services
Open uptime_monitor.py and find the SERVICES list. Add your endpoints like this:

HTTP/HTTPS:
{"name": "My Website", "url": "https://mywebsite.com", "type": "http"},

TCP Port Check:
{"name": "Database Server", "host": "db.mycompany.com", "port": 5432, "type": "tcp"},

SSL Certificate Expiry:
{"name": "SSL Cert Check", "host": "mywebsite.com", "port": 443, "type": "ssl"},

### Email Alerts (Optional)
By default, email alerts are turned OFF. This keeps public deployments secure.

To enable them (e.g., on Render), set these environment variables:
- EMAIL_ENABLED = true
- EMAIL_SENDER = your_email@gmail.com
- EMAIL_PASSWORD = your_gmail_app_password
- EMAIL_RECIPIENT = your_phone@txt.att.net
- SMTP_SERVER = smtp.gmail.com (or your provider's SMTP)

---

## Project Structure

    uptime-monitor/
    ├── uptime_monitor.py     # Main application
    ├── requirements.txt      # Python dependencies
    ├── Dockerfile            # Docker configuration
    ├── start.sh              # One-click local launcher
    ├── .gitignore            # Ignored files
    └── README.md             # This file

---

## Author

**Vojislav77**  
GitHub Profile: https://github.com/Vojislav77

---

## License

This project is open source and available under the MIT License.
