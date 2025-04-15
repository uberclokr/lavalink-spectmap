# main.py
import argparse
from pathlib import Path
from src.api.unms_client import UNMSClient
from src.visualization.map_renderer import MapRenderer
import yaml

def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)

def main():
    parser = argparse.ArgumentParser(description="Ubiquiti Antenna Spectrum Mapper")
    parser.add_argument('--config', default='config/config.yaml', help='Path to config file')
    parser.add_argument('--output', default='output_map.html', help='Output map filename')
    args = parser.parse_args()
    
    config = load_config(Path(args.config))
    
    # Initialize clients and renderer
    unms = UNMSClient(config['unms']['url'], config['unms']['api_key'])
    renderer = MapRenderer(config['map']['center_lat'], config['map']['center_lon'])
    
    # Get antennas and render coverage
    antennas = unms.get_aps()
    for antenna in antennas:
        print(f"{antenna.name}")
        renderer.add_antenna_coverage(antenna)
    
    # Save the map
    renderer.save_map(args.output)
    print(f"Map saved to {args.output}")

if __name__ == "__main__":
    main()