import requests, gzip, json, yaml, os, shutil
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def shift_time(ts, off):
    if not ts or not off: return ts
    try:
        fmt = "%Y%m%d%H%M%S"
        dt = datetime.strptime(ts.split(" ")[0], fmt)
        h, m = int(off[1:3]), int(off[3:5])
        delta = timedelta(hours=h, minutes=m)
        dt = dt + delta if off.startswith('+') else dt - delta
        return dt.strftime(fmt) + " " + off
    except: return ts

class EPGTranslator:
    def __init__(self, cfg, t_list):
        self.enabled = cfg['translation']['enabled']
        self.cache_path = cfg['translation']['cache_file']
        self.t_list = t_list
        self.cache = load_json(self.cache_path)
        self.translator = GoogleTranslator(source='auto', target=cfg['translation']['target_lang'])

    def translate(self, text, cid):
        if not self.enabled or not text or cid not in self.t_list: return text
        if text in self.cache: return self.cache[text]
        try:
            res = self.translator.translate(text)
            self.cache[text] = res
            return res
        except: return text

def run():
    cfg = yaml.safe_load(open('config.yml'))
    user = load_json('channels.json')
    trans = EPGTranslator(cfg, user.get('translate_channels', []))
    root = ET.Element("tv", {"generator-info-name": "Technical-Karam-Singh"})
    seen_ch, seen_pg, skip = set(), set(), set(user.get('skip_channels', []))

    for s in sorted(cfg['sources'], key=lambda x: x['priority']):
        if not s['active']: continue
        try:
            r = requests.get(s['url'], timeout=30)
            with gzip.open(BytesIO(r.content)) as f:
                src_root = ET.parse(f).getroot()
                for ch in src_root.findall('channel'):
                    cid = ch.get('id')
                    if cid not in skip and cid not in seen_ch:
                        dn = ch.find('display-name')
                        if dn is not None: dn.text = trans.translate(dn.text, cid)
                        root.append(ch); seen_ch.add(cid)
                for pg in src_root.findall('programme'):
                    cid, start = pg.get('channel'), pg.get('start')
                    if cid in seen_ch and f"{cid}:{start}" not in seen_pg:
                        pg.set('start', shift_time(start, s['offset']))
                        pg.set('stop', shift_time(pg.get('stop'), s['offset']))
                        t, d = pg.find('title'), pg.find('desc')
                        if t is not None: t.text = trans.translate(t.text, cid)
                        if d is not None: d.text = trans.translate(d.text, cid)
                        root.append(pg); seen_pg.add(f"{cid}:{start}")
        except: continue

    with open(trans.cache_path, 'w', encoding='utf-8') as f: json.dump(trans.cache, f, indent=2)
    tree = ET.ElementTree(root)
    ET.indent(tree); tree.write('merged_epg.xml', encoding='utf-8', xml_declaration=True)
    with open('merged_epg.xml', 'rb') as f_in, gzip.open('merged_epg.xml.gz', 'wb') as f_out: shutil.copyfileobj(f_in, f_out)
    
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f: f.write(f"total={len(seen_ch)}\n")

if __name__ == "__main__": run()
