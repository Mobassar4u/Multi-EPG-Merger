import requests
import gzip
import yaml
import json
import os
import xml.etree.ElementTree as ET
from io import BytesIO
from deep_translator import GoogleTranslator

def load_config(path='config.yml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_cache(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def fetch_gz_xml(url):
    print(f"Fetching: {url}")
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        with gzip.GzipFile(fileobj=BytesIO(r.content)) as gz:
            return ET.fromstring(gz.read())
    except Exception as e:
        print(f"Error: {e}")
        return None

def translate(text, target, cache):
    if not text or len(text.strip()) < 2: return text
    if text in cache: return cache[text]
    try:
        result = GoogleTranslator(source='auto', target=target).translate(text)
        cache[text] = result
        return result
    except:
        return text

def run():
    cfg = load_config()
    cache = load_cache(cfg['translation']['cache_file'])
    mapping = cfg.get('mapping', {})
    filter_list = cfg.get('filter', [])
    
    new_root = ET.Element("tv")
    seen_ids = set()
    channels, items = [], []

    for src in cfg['sources']:
        root = fetch_gz_xml(src['url'])
        if root is None: continue

        # Process Channels
        for ch in root.findall('channel'):
            orig_id = ch.get('id')
            if orig_id in filter_list: continue # Skip filtered channels
            
            tid = mapping.get(orig_id, orig_id)
            if tid not in seen_ids:
                ch.set('id', tid)
                if cfg['translation']['enabled']:
                    name = ch.find('display-name')
                    if name is not None:
                        name.text = translate(name.text, cfg['translation']['target_lang'], cache)
                seen_ids.add(tid)
                channels.append(ch)

        # Process Programmes
        for prog in root.findall('programme'):
            orig_ch_id = prog.get('channel')
            if orig_ch_id in filter_list: continue # Skip filtered programmes
            
            tid = mapping.get(orig_ch_id, orig_ch_id)
            prog.set('channel', tid)
            
            if cfg['translation']['enabled']:
                for tag in ['title', 'desc']:
                    el = prog.find(tag)
                    if el is not None and el.get('lang') != 'en':
                        el.text = translate(el.text, cfg['translation']['target_lang'], cache)
                        el.set('lang', 'en')
            items.append(prog)

    new_root.extend(channels)
    new_root.extend(items)
    
    # Save standard XML
    tree = ET.ElementTree(new_root)
    ET.indent(tree, space="  ")
    tree.write(cfg['output_file'], encoding='utf-8', xml_declaration=True)
    
    # Save Compressed GZ
    with open(cfg['output_file'], 'rb') as f_in:
        with gzip.open(f"{cfg['output_file']}.gz", 'wb') as f_out:
            f_out.writelines(f_in)

    save_cache(cfg['translation']['cache_file'], cache)
    print(f"Done! Created {cfg['output_file']} and {cfg['output_file']}.gz")

if __name__ == "__main__":
    run()
