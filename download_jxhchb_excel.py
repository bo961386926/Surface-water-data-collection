import requests
from bs4 import BeautifulSoup
import os
import re
import urllib3
import time
import sys
import json

# Custom print that writes to both stdout and log file
class Logger(object):
    def __init__(self, filename="download_log.txt"):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_site_name(soup, item_url):
    """
    Extract site name (污水处理厂) from the detail page soup.
    """
    share_div = soup.find('div', class_='social-share')
    if share_div and share_div.get('data-title'):
        title = share_div.get('data-title')
        match = re.search(r'(.+?(?:污水处理厂|水业环保|运营中心|化验室|环保有限公司|水处理厂))', title)
        if match:
            site_name = match.group(1).strip()
            site_name = site_name.replace("欢迎光临", "").strip()
            return site_name
    
    article_title = soup.find('div', class_='article-title')
    if article_title:
        title = article_title.text.strip()
        match = re.search(r'(.+?(?:污水处理厂|水业环保|运营中心|化验室|环保有限公司|水处理厂))', title)
        if match:
            site_name = match.group(1).strip()
            site_name = site_name.replace("欢迎光临", "").strip()
            return site_name
            
    for tag in ['p', 'div', 'span', 'h1', 'h2']:
        for element in soup.find_all(tag):
            text = element.get_text().strip()
            if len(text) < 100:
                match = re.search(r'(.+?(?:污水处理厂|水业环保|运营中心|化验室|环保有限公司|水处理厂))', text)
                if match:
                    site_name = match.group(1).strip()
                    site_name = site_name.replace("欢迎光临", "").strip()
                    if site_name and len(site_name) > 4:
                        return site_name
            
    text = soup.get_text()
    match = re.search(r'([^\s\r\n]+?(?:污水处理厂|水业环保|环保有限公司))', text)
    if match:
        return match.group(1).strip()
        
    return "未知厂站"

def process_items(items, base_url, category_name, total_files):
    for item in items:
        href = item.get('href')
        if not href:
            continue
            
        full_url = base_url + href
        print(f"Checking {full_url}...")
        
        try:
            time.sleep(0.3)
            item_resp = requests.get(full_url, verify=False, timeout=15)
            item_resp.encoding = 'utf-8'
            if item_resp.status_code != 200:
                print(f"Failed to fetch detail page: {full_url}")
                continue
                
            item_soup = BeautifulSoup(item_resp.text, 'html.parser')
            site_name = get_site_name(item_soup, full_url)
            
            safe_site_name = "".join([c for c in site_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
            site_folder = os.path.join("水质数据分类", safe_site_name, category_name)
            
            if not os.path.exists(site_folder):
                os.makedirs(site_folder)
            
            links = item_soup.find_all('a', href=re.compile(r'\.xlsx?$'))
            
            for link in links:
                file_href = link.get('href')
                file_name = link.text.strip()
                if not file_name:
                    file_name = os.path.basename(file_href)
                
                file_name = "".join([c for c in file_name if c.isalnum() or c in (' ', '.', '_', '-')]).strip()
                if not file_name:
                    file_name = os.path.basename(file_href)

                if not file_name.lower().endswith(('.xls', '.xlsx')):
                    ext = '.xlsx' if '.xlsx' in file_href.lower() else '.xls'
                    file_name += ext
                
                file_path = os.path.join(site_folder, file_name)
                file_url = base_url + file_href if file_href.startswith('/') else file_href
                
                if os.path.exists(file_path):
                    print(f"File already exists, skipping: {file_name}")
                    continue

                print(f"Downloading {file_name} to {site_folder}...")
                file_resp = requests.get(file_url, verify=False, timeout=20)
                if file_resp.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(file_resp.content)
                    total_files += 1
                else:
                    print(f"Failed to download {file_url}")
                    
        except Exception as e:
            print(f"Error processing item {full_url}: {e}")
    return total_files

def download_excel_files(base_url, channel_id, category_name):
    print(f"\nProcessing category: {category_name} (Channel: {channel_id})")
    
    current_page_url = f"{base_url}/channels/{channel_id}.html"
    page_count = 1
    total_files = 0
    ajax_params = None
    
    while current_page_url:
        print(f"\n--- Fetching Page {page_count}: {current_page_url} ---")
        try:
            response = requests.get(current_page_url, verify=False, timeout=15)
            response.encoding = 'utf-8'
            if response.status_code != 200:
                print(f"Failed to fetch {current_page_url}")
                break
        except Exception as e:
            print(f"Error fetching page: {e}")
            break

        soup = BeautifulSoup(response.text, 'html.parser')
        items = soup.select('.com-list-item')
        
        if not items:
            print("No items found via SSR. Checking for AJAX parameters...")
            # Try to extract AJAX parameters
            scripts = soup.find_all('script')
            for script in scripts:
                if script.string and 'stlPageContentsElement' in script.string:
                    try:
                        site_id_match = re.search(r'siteId:\s*(\d+)', script.string)
                        channel_id_match = re.search(r'pageChannelId:\s*(\d+)', script.string)
                        template_id_match = re.search(r'templateId:\s*(\d+)', script.string)
                        element_match = re.search(r"stlPageContentsElement:\s*'([^']+)'", script.string)
                        
                        if site_id_match and channel_id_match and template_id_match and element_match:
                            ajax_params = {
                                "siteId": int(site_id_match.group(1)),
                                "pageChannelId": int(channel_id_match.group(1)),
                                "templateId": int(template_id_match.group(1)),
                                "stlPageContentsElement": element_match.group(1)
                            }
                            print(f"Found AJAX parameters: {ajax_params}")
                            break
                    except Exception as e:
                        print(f"Error parsing script for AJAX params: {e}")
            
            if ajax_params:
                # Start AJAX loop
                ajax_url = f"{base_url}/api/stl/actions/pagecontents"
                while True:
                    ajax_params["currentPageIndex"] = page_count - 1
                    print(f"--- Fetching AJAX Page {page_count} (Index {page_count-1}) ---")
                    try:
                        time.sleep(0.5)
                        ajax_resp = requests.post(ajax_url, json=ajax_params, verify=False, timeout=15)
                        if ajax_resp.status_code == 200:
                            data = ajax_resp.json()
                            html_content = data.get('html', '')
                            if not html_content or '载入中' in html_content:
                                print("No more items found via AJAX.")
                                break
                            
                            ajax_soup = BeautifulSoup(html_content, 'html.parser')
                            ajax_items = ajax_soup.select('.com-list-item')
                            if not ajax_items:
                                print("No items in AJAX HTML.")
                                break
                                
                            print(f"Found {len(ajax_items)} items via AJAX.")
                            total_files = process_items(ajax_items, base_url, category_name, total_files)
                            page_count += 1
                        else:
                            print(f"AJAX request failed: {ajax_resp.status_code}")
                            break
                    except Exception as e:
                        print(f"Error during AJAX request: {e}")
                        break
                # Once AJAX loop finishes, we are done with this channel
                break
            else:
                print("No items and no AJAX parameters found. Stopping.")
                break
            
        print(f"Found {len(items)} items on this page via SSR.")
        total_files = process_items(items, base_url, category_name, total_files)
        
        # Look for the next page link
        next_page_div = soup.find('div', class_='com-page-next')
        if next_page_div:
            next_page_link = next_page_div.find('a')
            if next_page_link and next_page_link.get('href') and next_page_link.get('href') != 'javascript:;':
                current_page_url = base_url + next_page_link.get('href')
                page_count += 1
            else:
                current_page_url = None
        else:
            current_page_url = None
            
    return total_files

if __name__ == "__main__":
    base = "https://www.jxhchb.com"
    target_channels = {
        '46': '每日报表',
        '47': '每月报表',
        '48': '季度报表',
        '58': '年度报表'
    }
    
    if not os.path.exists("水质数据分类"):
        os.makedirs("水质数据分类")
        
    total_downloaded = 0
    for cid, category in target_channels.items():
        count = download_excel_files(base, cid, category)
        total_downloaded += count
        
    print(f"\nAll tasks finished! Total downloaded: {total_downloaded} files across all pages and categories.")
