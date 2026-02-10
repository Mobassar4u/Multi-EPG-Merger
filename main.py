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
    try:
        if os.path.exists('channels.json'):
            with open('channels.json', 'r', encoding='utf-8') as f:
                return json.load(f)
    except: return {"translate_channels": [], "skip_channels": []}
    return {"translate_channels": [], "skip_channels": []}

def shift_time(time_str, offset_str):
    if not time_str or not offset_str: return time_str
    try:
        fmt = "%Y%m%d%H%M%S"
        base = time_str.split(" ")[0]
        dt = datetime.strptime(base, fmt)
        hours, mins = int(offset_str[1:3]), int(offset_str[3:5])
        delta = timedelta(hours=hours, minutes=mins)
        dt = dt + delta if offset_str.startswith('+') else dt - delta
        return dt.strftime(fmt) + " " + offset_str
    except: return time_str

class EPGTranslator:
    def __init__(self, config, trans_list):
        self.enabled = config['translation']['enabled']
        self.cache_path = config['translation']['cache_file']
        self.trans_list = trans_list
        self.translator = GoogleTranslator(source='auto', target=config['translation']['target_lang'])
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def save_cache(self):
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

def run():
    config = load_config()
    user = load_user_data()
    translator = EPGTranslator(config, user.get('translate_channels', []))
    
    merged_root = ET.Element("tv", {"generator-info-name": "Technical-Karam-Singh-EPG"})
    seen_ch, seen_prog = set(), set()
    skip_ids = set(user.get('skip_channels', []))

    for src in sorted(config['sources'], key=lambda x: x['priority']):
        if not src.get('active'): continue
        print(f"Processing: {src['name']}")
        try:
            r = requests.get(src['url'], timeout=60)
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as f:
                root = ET.parse(f).getroot()
                for ch in root.findall('channel'):
                    cid = ch.get('id')
                    if cid not in skip_ids and cid not in seen_ch:
                        dn = ch.find('display-name')
                        if dn is not None: dn.text = translator.translate(dn.text, cid)
                        merged_root.append(ch)
                        seen_ch.add(cid)

                for pg in root.findall('programme'):
                    cid = pg.get('channel')
                    key = f"{cid}:{pg.get('start')}"
                    if cid in seen_ch and key not in seen_prog:
                        pg.set('start', shift_time(pg.get('start'), src.get('offset')))
                        pg.set('stop', shift_time(pg.get('stop'), src.get('offset')))
                        t, d = pg.find('title'), pg.find('desc')
                        if t is not None: t.text = translator.translate(t.text, cid)
                        if d is not None: d.text = translator.translate(d.text, cid)
                        merged_root.append(pg)
                        seen_prog.add(key)
        except Exception as e: print(f"Error: {e}")

    translator.save_cache()
    
    # Generate the XML string
    tree = ET.ElementTree(merged_root)
    ET.indent(tree, space="  ")
    
    # Step 1: Save regular XML (Optional, for debugging)
    output_xml = config['output_file'] # "merged_epg.xml"
    tree.write(output_xml, encoding='utf-8', xml_declaration=True)
    
    # Step 2: Create the GZ compressed file
    output_gz = output_xml + ".gz" # "merged_epg.xml.gz"
    with open(output_xml, 'rb') as f_in:
        with gzip.open(output_gz, 'wb') as f_out:
            f_out.writelines(f_in)
            
    print(f"Successfully created: {output_gz}")

if __name__ == "__main__":
    run()
