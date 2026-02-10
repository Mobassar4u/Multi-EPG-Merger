import requests
import gzip
import json
import yaml
import os
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

def load_config():
    with open('config.yml', 'r') as f:
        return yaml.safe_load(f)

def load_user_data():
    with open('channels.json', 'r') as f:
        return json.load(f)

def shift_time(time_str, offset_str):
    """Adjusts EPG time string (e.g., 20260210180000 +0000) by offset."""
    if not time_str or not offset_str:
        return time_str
    try:
        # Parse: 20260210180000
        fmt = "%Y%m%d%H%M%S"
        base_time = time_str.split(" ")[0]
        dt = datetime.strptime(base_time, fmt)
        
        # Parse Offset: +0530 -> 5 hours, 30 mins
        hours = int(offset_str[1:3])
        minutes = int(offset_str[3:5])
        delta = timedelta(hours=hours, minutes=minutes)
        
        if offset_str.startswith('+'):
            dt += delta
        else:
            dt -= delta
            
        return dt.strftime(fmt) + " " + offset_str
    except:
        return time_str

class EPGTranslator:
    def __init__(self, config, translate_list):
        self.enabled = config.get('translation', {}).get('enabled', False)
        self.target = config.get('translation', {}).get('target_lang', 'en')
        self.cache_path = config.get('translation', {}).get('cache_file', 'cache.json')
        self.translate_list = translate_list
        self.cache = self._load_cache()
        self.translator = GoogleTranslator(source='auto', target=self.target)

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def save_cache(self):
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def translate(self, text, channel_id):
        if not self.enabled or not text or channel_id not in self.translate_list:
            return text
        if text in self.cache:
            return self.cache[text]
        try:
            res = self.translator.translate(text)
            self.cache[text] = res
            return res
        except:
            return text

def run_merger():
    config = load_config()
    user_data = load_user_data()
    target_ids = user_data.get('channels', [])
    trans_ids = user_data.get('translate_channels', [])
    
    translator = EPGTranslator(config, trans_ids)
    merged_root = ET.Element("tv")
    
    seen_channels = set()
    seen_programs = set()

    for src in config['sources']:
        if not src.get('active'): continue
        print(f"Fetching: {src['name']}")
        try:
            r = requests.get(src['url'], timeout=60)
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as f:
                root = ET.parse(f).getroot()

                for channel in root.findall('channel'):
                    cid = channel.get('id')
                    if cid in target_ids and cid not in seen_channels:
                        dn = channel.find('display-name')
                        if dn is not None: dn.text = translator.translate(dn.text, cid)
                        merged_root.append(channel)
                        seen_channels.add(cid)

                for prog in root.findall('programme'):
                    cid = prog.get('channel')
                    start = prog.get('start')
                    if cid in seen_channels and f"{cid}:{start}" not in seen_programs:
                        # Time Offset Logic
                        prog.set('start', shift_time(prog.get('start'), src.get('offset')))
                        prog.set('stop', shift_time(prog.get('stop'), src.get('offset')))
                        
                        # Translation Logic
                        title = prog.find('title')
                        desc = prog.find('desc')
                        if title is not None: title.text = translator.translate(title.text, cid)
                        if desc is not None: desc.text = translator.translate(desc.text, cid)
                        
                        merged_root.append(prog)
                        seen_programs.add(f"{cid}:{start}")
        except Exception as e:
            print(f"Source failed: {e}")

    translator.save_cache()
    tree = ET.ElementTree(merged_root)
    ET.indent(tree, space="  ")
    tree.write(config['output_file'], encoding='utf-8', xml_declaration=True)
    print(f"Final EPG created: {config['output_file']}")

if __name__ == "__main__":
    run_merger()
