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
        return json.load(f)['channels']

def fetch_and_merge():
    config = load_config()
    target_channels = load_user_channels()
    
    # Root for the new XMLTV file
    merged_root = ET.Element("tv")
    merged_root.set("generator-info-name", "Gemini EPG Merger")

    processed_channels = set()
    processed_programmes = set()

    # Sort sources by priority (1 is highest)
    sources = sorted(config['sources'], key=lambda x: x['priority'])

    for source in sources:
        if not source['active']:
            continue
            
        print(f"Downloading: {source['name']} ({source['url']})")
        try:
            response = requests.get(source['url'], timeout=30)
            with gzip.GzipFile(fileobj=BytesIO(response.content)) as f:
                tree = ET.parse(f)
                root = tree.getroot()

                # 1. Process Channels
                for channel in root.findall('channel'):
                    ch_id = channel.get('id')
                    if ch_id in target_channels and ch_id not in processed_channels:
                        merged_root.append(channel)
                        processed_channels.add(ch_id)

                # 2. Process Programmes
                for prog in root.findall('programme'):
                    ch_id = prog.get('channel')
                    start = prog.get('start')
                    # Create a unique key for the show to avoid duplicates
                    prog_key = f"{ch_id}-{start}" 
                    
                    if ch_id in processed_channels and prog_key not in processed_programmes:
                        merged_root.append(prog)
                        processed_programmes.add(prog_key)

        except Exception as e:
            print(f"Error processing {source['url']}: {e}")

    # Write the final file
    tree = ET.ElementTree(merged_root)
    output_path = config.get('output_file', 'merged_epg.xml')
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    print(f"\nSuccess! Merged EPG saved to: {output_path}")

if __name__ == "__main__":
    fetch_and_merge()
