import os
import pymysql
import logging
from sqlalchemy import create_engine, text

# Get DB config from environment variables
DB_HOST = os.getenv('DB_HOST', 'db')
DB_PORT = int(os.getenv('DB_PORT', 3306))
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
DB_NAME = os.getenv('DB_NAME', 'water_quality_db')

# Create SQLAlchemy engine
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, pool_recycle=3600)

def init_db():
    """Initialize the database schema"""
    try:
        # Connect without DB name first to create it if it doesn't exist
        temp_url = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}"
        temp_engine = create_engine(temp_url)
        with temp_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"Database {DB_NAME} checked/created.")
        
        # Now use the main engine to create table
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS water_quality (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    province VARCHAR(50),
                    river_basin VARCHAR(50),
                    section_name VARCHAR(100),
                    monitor_time DATETIME,
                    quality_class VARCHAR(20),
                    temperature VARCHAR(20),
                    ph VARCHAR(20),
                    dissolved_oxygen VARCHAR(20),
                    conductivity VARCHAR(20),
                    turbidity VARCHAR(20),
                    permanganate_index VARCHAR(20),
                    ammonia_nitrogen VARCHAR(20),
                    total_phosphorus VARCHAR(20),
                    total_nitrogen VARCHAR(20),
                    chlorophyll_a VARCHAR(20),
                    algal_density VARCHAR(20),
                    scrape_time DATETIME,
                    UNIQUE KEY unique_record (section_name, monitor_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """))
            print("Table water_quality checked/created.")
            conn.commit()
    except Exception as e:
        print(f"Error initializing database: {e}")

def save_to_db(data):
    """Save data to MySQL database"""
    if not data:
        return 0
    
    count = 0
    try:
        with engine.connect() as conn:
            for row in data:
                # Ensure row has enough columns (16 data columns + scrape_time will be added here)
                # The scraper returns list of lists with raw data.
                # We need to map it correctly.
                # Expected row: [province, basin, section, time, class, temp, ph, do, cond, turb, perm, nh3, tp, tn, chla, algal]
                
                if len(row) < 16:
                    continue # Skip invalid rows

                # Prepare parameters
                params = {
                    'province': row[0],
                    'river_basin': row[1],
                    'section_name': row[2],
                    'monitor_time': row[3], # String format "2024-02-25 10:00"
                    'quality_class': row[4],
                    'temperature': row[5],
                    'ph': row[6],
                    'dissolved_oxygen': row[7],
                    'conductivity': row[8],
                    'turbidity': row[9],
                    'permanganate_index': row[10],
                    'ammonia_nitrogen': row[11],
                    'total_phosphorus': row[12],
                    'total_nitrogen': row[13],
                    'chlorophyll_a': row[14],
                    'algal_density': row[15]
                }
                
                # Use INSERT IGNORE or ON DUPLICATE KEY UPDATE
                # Since we want to ignore duplicates based on (section_name, monitor_time)
                sql = text("""
                    INSERT IGNORE INTO water_quality (
                        province, river_basin, section_name, monitor_time, quality_class, 
                        temperature, ph, dissolved_oxygen, conductivity, turbidity, 
                        permanganate_index, ammonia_nitrogen, total_phosphorus, total_nitrogen, 
                        chlorophyll_a, algal_density, scrape_time
                    ) VALUES (
                        :province, :river_basin, :section_name, :monitor_time, :quality_class, 
                        :temperature, :ph, :dissolved_oxygen, :conductivity, :turbidity, 
                        :permanganate_index, :ammonia_nitrogen, :total_phosphorus, :total_nitrogen, 
                        :chlorophyll_a, :algal_density, NOW()
                    )
                """)
                
                result = conn.execute(sql, params)
                count += result.rowcount
            
            conn.commit()
            print(f"Saved {count} records to database.")
    except Exception as e:
        print(f"Error saving to database: {e}")
    
    return count

def get_latest_data(limit=100):
    """Fetch latest data for display"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM water_quality ORDER BY monitor_time DESC, id DESC LIMIT :limit"), {"limit": limit})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result]
    except Exception as e:
        print(f"Error fetching data: {e}")
        return []
