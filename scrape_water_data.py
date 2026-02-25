import requests
import time
import urllib3
import pandas as pd
import re
import sqlite3
import os
from datetime import datetime

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = 'water_quality.db'

def init_db():
    """
    初始化数据库
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 创建表
    # 根据已知的表头结构创建字段
    # ['省份', '流域', '断面名称', '监测时间', '水质类别', '水温(℃)', 'pH(无量纲)', '溶解氧(mg/L)', '电导率(μS/cm)', '浊度(NTU)', '高锰酸盐指数(mg/L)', '氨氮(mg/L)', '总磷(mg/L)', '总氮(mg/L)', '叶绿素α(mg/L)', '藻密度(cells/L)']
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS water_quality (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        province TEXT,
        river_basin TEXT,
        section_name TEXT,
        monitor_time TEXT,
        quality_class TEXT,
        temperature TEXT,
        ph TEXT,
        dissolved_oxygen TEXT,
        conductivity TEXT,
        turbidity TEXT,
        permanganate_index TEXT,
        ammonia_nitrogen TEXT,
        total_phosphorus TEXT,
        total_nitrogen TEXT,
        chlorophyll_a TEXT,
        algal_density TEXT,
        scrape_time TEXT,
        UNIQUE(section_name, monitor_time)
    )
    ''')
    conn.commit()
    conn.close()
    print("数据库初始化完成。")

def save_to_db(data):
    """
    保存数据到SQLite数据库
    """
    if not data:
        print("没有数据可保存到数据库。")
        return
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    scrape_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    count = 0
    
    for row in data:
        # 确保row有足够的数据列，如果不足补None
        # 预期的列数是16个数据字段 + scrape_time
        # 这里的row是原始抓取的数据列表
        
        # 构建插入数据元组
        # 注意：row中的数据顺序必须与表结构对应
        # 假设row的前16个字段对应表中的前16个字段（排除id和scrape_time）
        
        # 处理可能的数据长度不一致问题
        current_row = list(row)
        if len(current_row) < 16:
            current_row.extend([None] * (16 - len(current_row)))
        elif len(current_row) > 16:
            current_row = current_row[:16]
            
        # 添加抓取时间
        current_row.append(scrape_time)
        
        try:
            cursor.execute('''
            INSERT OR IGNORE INTO water_quality (
                province, river_basin, section_name, monitor_time, quality_class, 
                temperature, ph, dissolved_oxygen, conductivity, turbidity, 
                permanganate_index, ammonia_nitrogen, total_phosphorus, total_nitrogen, 
                chlorophyll_a, algal_density, scrape_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', current_row)
            if cursor.rowcount > 0:
                count += 1
        except Exception as e:
            print(f"插入数据失败: {e} - Row: {current_row}")
            
    conn.commit()
    conn.close()
    print(f"成功保存 {count} 条新记录到数据库 (忽略 {len(data) - count} 条重复记录)。")

def clean_text(text):
    """
    清洗文本，移除HTML标签和特殊字符
    """
    if not isinstance(text, str):
        return text
    
    # 移除HTML标签
    clean_text = re.sub(r'<[^>]+>', '', text)
    # 替换特殊字符
    clean_text = clean_text.replace('&nbsp;', ' ')
    return clean_text.strip()

def fetch_water_quality_data():
    """
    抓取国家水质自动综合监管平台实时数据
    """
    print(f"[{datetime.now()}] 开始抓取数据...")
    
    # 创建会话以保持Cookies
    session = requests.Session()
    
    # 浏览器伪装头
    common_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    }
    
    # 1. 访问主页和数据页以获取必要的Cookies和建立会话
    try:
        print("正在初始化会话...")
        session.get('https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/Main.html', headers=common_headers, verify=False, timeout=15)
        session.get('https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/RealDatas.html', headers=common_headers, verify=False, timeout=15)
    except Exception as e:
        print(f"初始化会话失败: {e}")
        return []

    # API 地址
    api_url = 'https://szzdjc.cnemc.cn:8070/GJZ/Ajax/Publish.ashx'
    
    # API 请求头
    post_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': 'https://szzdjc.cnemc.cn:8070',
        'Referer': 'https://szzdjc.cnemc.cn:8070/GJZ/Business/Publish/RealDatas.html',
    }
    
    all_data = []
    final_headers = []
    page_index = 1
    page_size = 60 # 默认每页数量
    
    while True:
        # 请求参数
        data = {
            'AreaID': '',   # 省份ID，为空表示全国
            'RiverID': '',  # 流域ID，为空表示所有流域
            'MNName': '',   # 断面名称搜索
            'PageIndex': str(page_index),
            'PageSize': str(page_size),
            'action': 'getRealDatas'
        }
        
        print(f"正在抓取第 {page_index} 页...", end='', flush=True)
        try:
            resp = session.post(api_url, headers=post_headers, data=data, verify=False, timeout=20)
            
            if resp.status_code != 200:
                print(f"\n请求失败，状态码: {resp.status_code}")
                break
                
            try:
                json_data = resp.json()
            except Exception as e:
                print(f"\n解析JSON失败: {e}")
                break
            
            # 检查是否有数据
            # result 字段通常为 1 表示成功
            if not json_data.get('result'):
                 print("\n返回结果显示无数据或错误。")
                 break
                 
            tbody = json_data.get('tbody', [])
            total_pages = json_data.get('total', 0)
            thead = json_data.get('thead', [])
            
            if not tbody:
                print("\n本页无数据。")
                break
                
            # 如果是第一页，提取并清理表头
            if page_index == 1 and thead:
                final_headers = [clean_text(h) for h in thead]
            
            # 清洗每一行的数据
            cleaned_tbody = []
            for row in tbody:
                cleaned_row = [clean_text(cell) for cell in row]
                cleaned_tbody.append(cleaned_row)
                
            all_data.extend(cleaned_tbody)
            print(f" 成功获取 {len(tbody)} 条记录。")
            
            # 检查是否已获取所有页
            if page_index >= total_pages:
                print(f"已抓取所有 {total_pages} 页数据。")
                break
            
            page_index += 1
            # 礼貌性延迟，避免对服务器造成过大压力
            time.sleep(1) 
            
        except Exception as e:
            print(f"\n发生错误: {e}")
            break
            
    return all_data, final_headers

def save_to_csv(data, headers):
    """
    保存数据到CSV文件
    """
    if not data:
        print("没有数据可保存。")
        return
        
    filename = f"water_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    try:
        # 如果获取到了表头且长度匹配，则使用表头
        if headers and len(data) > 0 and len(headers) == len(data[0]):
            df = pd.DataFrame(data, columns=headers)
        else:
            # 否则使用默认索引
            df = pd.DataFrame(data)
            
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"数据已保存至: {filename}")
        print(f"总计: {len(df)} 条记录")
    except Exception as e:
        print(f"保存文件失败: {e}")

def main():
    # 初始化数据库
    init_db()
    
    while True:
        print(f"\n[{datetime.now()}] 开始新一轮抓取任务...")
        data, headers = fetch_water_quality_data()
        
        # 保存到数据库
        save_to_db(data)
        
        # 同时保存CSV备份 (可选，如果不需要可以注释掉)
        # save_to_csv(data, headers)
        
        print(f"[{datetime.now()}] 本轮任务结束。等待 2 小时后继续...")
        # 等待2小时 (2 * 60 * 60 秒)
        time.sleep(2 * 60 * 60)

if __name__ == "__main__":
    main()
