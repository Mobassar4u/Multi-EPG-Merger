import requests, gzip, json, yaml, os, shutil
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

# --- HELPER FUNCTIONS ---

def load_json(path):
    """Safely loads a JSON file or returns an empty dictionary."""
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: 
                return json.load(f)
        except: 
            return {}
    return {}

def shift_time(ts, off):
    """Adjusts EPG time based on the offset provided in config.yml."""
    if not ts or not off: return ts
    try:
        fmt = "%Y%m%d%H%M%S"
        dt = datetime.strptime(ts.split(" ")[0], fmt)
        h, m = int(off[1:3]), int(off[3:5])
        delta = timedelta(hours=h, minutes=m)
        dt = dt + delta if off.startswith('+') else dt - delta
        return dt.strftime(fmt) + " " + off
    except: 
        return ts

class EPGTranslator:
    """Handles automatic translation and caching of EPG text."""
    def __init__(self, cfg, t_list):
        self.enabled = cfg['translation']['enabled']
        self.cache_path = cfg['translation']['cache_file']
        self.t_list = t_list
        self.cache = load_json(self.cache_path)
        self.translator = GoogleTranslator(source='auto', target=cfg['translation']['target_lang'])

    def translate(self, text, cid):
        if not self.enabled or not text or cid not in self.t_list: 
            return text
        if text in self.cache: 
            return self.cache[text]
        try:
            res = self.translator.translate(text)
            self.cache[text] = res
            return res
        except: 
            return text

# --- MAIN RUNNER ---

def run():
    # 1. Load Configurations
    cfg = yaml.safe_load(open('config.yml'))
    user = load_json('channels.json') # Fixed: Now properly defined above
    
    trans = EPGTranslator(cfg, user.get('translate_channels', []))
    root = ET.Element("tv", {"generator-info-name": "Technical-Karam-Singh"})
    
    seen_ch, seen_pg = set(), set()
    skip = set(user.get('skip_channels', []))

    # 2. Fetch and Merge from Sources
    for s in sorted(cfg['sources'], key=lambda x: x['priority']):
        if not s['active']: continue
        try:
            r = requests.get(s['url'], timeout=30)
            with gzip.open(BytesIO(r.content)) as f:
                src_root = ET.parse(f).getroot()
                
                # Process Channels
                for ch in src_root.findall('channel'):
                    cid = ch.get('id')
                    if cid not in skip and cid not in seen_ch:
                        dn = ch.find('display-name')
                        if dn is not None: 
                            dn.text = trans.translate(dn.text, cid)
                        root.append(ch)
                        seen_ch.add(cid)
                
                # Process Programmes
                for pg in src_root.findall('programme'):
                    cid, start = pg.get('channel'), pg.get('start')
                    if cid in seen_ch and f"{cid}:{start}" not in seen_pg:
                        pg.set('start', shift_time(start, s['offset']))
                        pg.set('stop', shift_time(pg.get('stop'), s['offset']))
                        
                        t, d = pg.find('title'), pg.find('desc')
                        if t is not None: t.text = trans.translate(t.text, cid)
                        if d is not None: d.text = trans.translate(d.text, cid)
                        
                        root.append(pg)
                        seen_pg.add(f"{cid}:{start}")
        except Exception as e:
            print(f"Skipping source {s.get('name')}: {e}")
            continue

    # 3. Save Cache and Export to Gzip (Memory-to-File System)
    with open(trans.cache_path, 'w', encoding='utf-8') as f: 
        json.dump(trans.cache, f, indent=2)
    
    tree = ET.ElementTree(root)
    ET.indent(tree)
    
    # Save directly to .gz to avoid storage problems
    with gzip.open('in.tv_epg.xml.gz', 'wb') as f_out:
        tree.write(f_out, encoding='utf-8', xml_declaration=True)
    
    # 4. Output for GitHub Actions
    channel_count = len(seen_ch)
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"total={channel_count}\n")
    
    print(f"Merge Complete: {channel_count} channels found. No .xml file created.")

if __name__ == "__main__": 
    run()
