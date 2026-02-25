import os
import logging
from flask import Flask, render_template, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import database
import scraper
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

def scheduled_job():
    """Function to be run by the scheduler"""
    logger.info("Starting scheduled scraping job...")
    try:
        data = scraper.fetch_water_quality_data()
        if data:
            count = database.save_to_db(data)
            logger.info(f"Job finished. Saved {count} records.")
        else:
            logger.info("Job finished. No data fetched.")
    except Exception as e:
        logger.error(f"Job failed: {e}")

@app.route('/')
def index():
    """Dashboard to view data"""
    # Fetch latest 100 records
    data = database.get_latest_data(limit=100)
    return render_template('index.html', data=data)

@app.route('/api/trigger', methods=['POST'])
def trigger_scrape():
    """Manual trigger endpoint"""
    # Run in background to avoid timeout
    scheduler.add_job(scheduled_job, 'date', run_date=datetime.now())
    return jsonify({"status": "Job triggered", "message": "Scraping job started in background."})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

# Initialize Scheduler
scheduler = BackgroundScheduler()
# Run every 2 hours
scheduler.add_job(
    func=scheduled_job,
    trigger=IntervalTrigger(hours=2),
    id='water_quality_scraper',
    name='Scrape water quality data every 2 hours',
    replace_existing=True
)

def initialize_app():
    """Initialize DB and Scheduler"""
    with app.app_context():
        # Wait a bit for DB to be ready in Docker
        # In a real production app, we might want a retry loop in database.py
        database.init_db()
        
        # Start scheduler
        if not scheduler.running:
            scheduler.start()
            logger.info("Scheduler started.")
            
            # Optional: Run immediately on startup if DB is empty or just to ensure data
            # scheduled_job() 

if __name__ == '__main__':
    # When running locally
    initialize_app()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
else:
    # When running with gunicorn
    initialize_app()
