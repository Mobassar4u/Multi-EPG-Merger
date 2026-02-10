import requests, gzip, json, yaml, os
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
from deep_translator import GoogleTranslator

# ... [Keep your load_json, shift_time, and EPGTranslator classes as they were] ...

def run():
    cfg = yaml.safe_load(open('config.yml'))
    user = load_json('channels.json')
    trans = EPGTranslator(cfg, user.get('translate_channels', []))
    
    root = ET.Element("tv", {"generator-info-name": "Technical-Karam-Singh"})
    seen_ch, seen_pg, skip = set(), set(), set(user.get('skip_channels', []))

    # Logic to merge from multiple sources based on priority
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

    with open(trans.cache_path, 'w', encoding='utf-8') as f: 
        json.dump(trans.cache, f, indent=2)
    
    # --- NO .XML FILE SYSTEM ---
    # Stream the XML object directly into a Gzip compressed file
    tree = ET.ElementTree(root)
    ET.indent(tree)
    with gzip.open('in.tv_epg.xml.gz', 'wb') as f_out:
        tree.write(f_out, encoding='utf-8', xml_declaration=True)
    
    channel_count = len(seen_ch)
    if 'GITHUB_OUTPUT' in os.environ:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
            f.write(f"total={channel_count}\n")
    print(f"Merge Complete: {channel_count} channels. Saved directly to .gz")

if __name__ == "__main__": run()
