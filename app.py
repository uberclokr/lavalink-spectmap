from flask import Flask, send_file
from src.visualization.map_renderer import MapRenderer
from src.api.unms_client import UNMSClient
from pathlib import Path
import yaml

app = Flask(__name__)

def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)
    
@app.route("/")

def generate_map():
    """
    Generate the map and serve it as an HTML file.
    """
    try:
        # Load configuration
        config_path = Path("config/config.yaml")
        config = load_config(config_path)

        # Initialize UNMS client
        unms = UNMSClient(base_url=config['unms']['url'], api_key=config['unms']['api_key'])

        # Fetch antennas
        antennas = unms.get_aps()

        # Initialize MapRenderer
        renderer = MapRenderer(config['map']['center_lat'], config['map']['center_lon'])

        # Add antenna coverage to the map
        for antenna in antennas:
            renderer.add_antenna_coverage(antenna)

        # Save the map to an HTML file
        output_file = "output_map.html"
        renderer.save_map(output_file)

        # Serve the generated map
        return send_file(output_file)

    except Exception as e:
        return f"An error occurred: {e}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)