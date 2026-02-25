import requests
import time
import urllib3
import re
from datetime import datetime
import database  # Import the newly created database module

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def clean_text(text):
    """
    Clean text by removing HTML tags and special characters.
    """
    if not isinstance(text, str):
        return text
    
    clean_text = re.sub(r'<[^>]+>', '', text)
    clean_text = clean_text.replace('&nbsp;', ' ')
    return clean_text.strip()

def fetch_water_quality_data():
    """
    Fetch real-time data from the national water quality monitoring platform.
    """
    print(f"[{datetime.now()}] Starting data fetch...")
    
    session = requests.Session()
    
    common_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    }
    
    # 1. Initialize session
    try:
        print("Initializing session...")
        session.get('https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/Main.html', headers=common_headers, verify=False, timeout=15)
        session.get('https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/RealDatas.html', headers=common_headers, verify=False, timeout=15)
    except Exception as e:
        print(f"Session initialization failed: {e}")
        return []

    api_url = 'https://szzdjc.cnemc.cn:8070/GJZ/Ajax/Publish.ashx'
    
    post_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://szzdjc.cnemc.cn:8070',
        'Referer': 'https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/RealDatas.html',
    }
    
    all_data = []
    page_index = 1
    page_size = 60
    
    while True:
        data = {
            'AreaID': '',
            'RiverID': '',
            'MNName': '',
            'PageIndex': str(page_index),
            'PageSize': str(page_size),
            'action': 'getRealDatas'
        }
        
        print(f"Fetching page {page_index}...", end='', flush=True)
        try:
            resp = session.post(api_url, headers=post_headers, data=data, verify=False, timeout=20)
            
            if resp.status_code != 200:
                print(f"\nRequest failed, status code: {resp.status_code}")
                break
                
            try:
                json_data = resp.json()
            except Exception as e:
                print(f"\nJSON parsing failed: {e}")
                break
            
            if not json_data.get('result'):
                 print("\nNo data returned or error in result.")
                 break
                 
            tbody = json_data.get('tbody', [])
            total_pages = json_data.get('total', 0)
            
            if not tbody:
                print("\nNo data on this page.")
                break
                
            # Clean data
            cleaned_tbody = []
            for row in tbody:
                cleaned_row = [clean_text(cell) for cell in row]
                cleaned_tbody.append(cleaned_row)
                
            all_data.extend(cleaned_tbody)
            print(f" Success: {len(tbody)} records.")
            
            if page_index >= total_pages:
                print(f"Fetched all {total_pages} pages.")
                break
            
            page_index += 1
            time.sleep(1) 
            
        except Exception as e:
            print(f"\nError occurred: {e}")
            break
            
    return all_data

def run_scraper_task():
    """
    Main task to be scheduled
    """
    try:
        data = fetch_water_quality_data()
        if data:
            database.save_to_db(data)
            print(f"[{datetime.now()}] Task completed successfully.")
        else:
            print(f"[{datetime.now()}] No data fetched.")
    except Exception as e:
        print(f"[{datetime.now()}] Scraper task failed: {e}")

if __name__ == "__main__":
    # For testing purposes
    database.init_db()
    run_scraper_task()
