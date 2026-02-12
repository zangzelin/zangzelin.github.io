import requests
from bs4 import BeautifulSoup
import yaml
import os
import re

def get_scholar_stats(user_id):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    url = f'https://scholar.google.com/citations?user={user_id}&hl=en'
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # The citation table usually has "Citations" in the first row, second column (All)
            # Structure: table#gsc_rsb_st -> tbody -> tr -> td.gsc_rsb_std
            stats_table = soup.find('table', id='gsc_rsb_st')
            if stats_table:
                # First row is Citations
                citations_row = stats_table.find_all('tr')[1] # 0 is header? No, usually trs are direct.
                # Actually let's look for the row with "Citations"
                
                rows = stats_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if cells and 'Citations' in row.text:
                        # cells[0] is label, cells[1] is All, cells[2] is Since 20xx
                        total_citations = cells[1].text
                        return total_citations
            
            return None
        else:
            print(f"Failed to fetch page: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def update_data_file(citations):
    data_dir = '_data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    file_path = os.path.join(data_dir, 'scholar.yml')
    
    data = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                data = yaml.safe_load(f) or {}
            except:
                data = {}
    
    data['citations'] = citations
    data['citation_count'] = int(citations) if citations.isdigit() else citations
    
    with open(file_path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)
    
    print(f"Updated {file_path} with {citations} citations")

if __name__ == "__main__":
    # Try to read user ID from _config.yml
    user_id = "foERjnQAAAAJ" # Default fallback
    try:
        with open('_config.yml', 'r') as f:
            config = yaml.safe_load(f)
            scholar_url = config.get('author', {}).get('googlescholar', '')
            # Extract user ID from URL like https://scholar.google.com/citations?user=foERjnQAAAAJ&hl=zh-CN
            match = re.search(r'user=([^&]+)', scholar_url)
            if match:
                user_id = match.group(1)
                print(f"Found Google Scholar ID in _config.yml: {user_id}")
    except Exception as e:
        print(f"Could not read _config.yml: {e}, using default ID")

    citations = get_scholar_stats(user_id)
    
    if citations:
        update_data_file(citations)
    else:
        print("Could not fetch citations.")
