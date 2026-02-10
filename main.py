import requests
import gzip
import json
import yaml
import xml.etree.ElementTree as ET
from io import BytesIO

def load_config():
    with open('config.yml', 'r') as f:
        return yaml.safe_load(f)

def load_user_channels():
    with open('channels.json', 'r') as f:
        data = json.load(f)
        return data.get('channels', [])

def run_merger():
    config = load_config()
    target_channels = load_user_channels()
    
    # Create the XMLTV root
    merged_root = ET.Element("tv")
    merged_root.set("generator-info-name", "Karam-EPG-Merger-v1")

    # Trackers to prevent duplicates
    processed_channel_ids = set()
    processed_program_keys = set() # Format: "channel_id:start_time"

    # Sort sources by priority
    sources = sorted(config['sources'], key=lambda x: x['priority'])

    for source in sources:
        if not source['active']: continue
        
        print(f"--- Fetching: {source['name']} ---")
        try:
            r = requests.get(source['url'], timeout=60)
            r.raise_for_status()
            
            with gzip.GzipFile(fileobj=BytesIO(r.content)) as f:
                tree = ET.parse(f)
                root = tree.getroot()

                # 1. Add Channels (if not already added by higher priority source)
                for channel in root.findall('channel'):
                    ch_id = channel.get('id')
                    if ch_id in target_channels and ch_id not in processed_channel_ids:
                        merged_root.append(channel)
                        processed_channel_ids.add(ch_id)

                # 2. Add Programs for the channels we just accepted
                for prog in root.findall('programme'):
                    ch_id = prog.get('channel')
                    start = prog.get('start')
                    prog_key = f"{ch_id}:{start}"

                    if ch_id in processed_channel_ids and prog_key not in processed_program_keys:
                        merged_root.append(prog)
                        processed_program_keys.add(prog_key)
                
                print(f"Current Stats: {len(processed_channel_ids)} channels active.\n")

        except Exception as e:
            print(f"Skipping {source['name']} due to error: {e}")

    # Write final output
    output_filename = config.get('output_file', 'merged_epg.xml')
    tree = ET.ElementTree(merged_root)
    
    # Indent for readability (Python 3.9+)
    ET.indent(tree, space="  ", level=0)
    
    tree.write(output_filename, encoding='utf-8', xml_declaration=True)
    print(f"DONE! Saved to {output_filename}")

if __name__ == "__main__":
    run_merger()
