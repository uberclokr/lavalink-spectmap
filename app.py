from flask import Flask, send_file
from src.visualization.map_renderer import MapRenderer
from src.api.unms_client import UNMSClient
from pathlib import Path
import asyncio
import yaml
import sys
import traceback
import signal

app = Flask(__name__)

config = None

def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)

def handle_shutdown_signal(signal, frame):
    """
    Handle termination signals to ensure proper cleanup.
    """
    loop = asyncio.get_event_loop()
    asyncio.run(shutdown(loop))
    sys.exit(0)

# Define the shutdown function
async def shutdown(loop):
    """
    Cancel all running tasks and stop the event loop.
    """
    tasks = [t for t in asyncio.all_tasks(loop) if t is not asyncio.current_task(loop)]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

@app.route("/")
def main():
    """
    Generate the map and serve it as an HTML file.
    """
    try:
        # Create a new event loop for the current thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(generate_map())
    except Exception as e:
        return f"An error occurred: {e}", 500
    
async def generate_map():
    """
        Asynchronous logic to generate the map.
    """
    try:
        # Initialize UNMS client
        unms = UNMSClient(base_url=config['unms']['url'], api_key=config['unms']['api_key'])

        # Fetch antennas
        antennas = unms.get_aps()

        # Initialize MapRenderer and center map on locality
        renderer = MapRenderer(config['map']['center_lat'], config['map']['center_lon'])

        # Add antenna coverage to the map
        #for antenna in antennas:
        #    renderer.add_antenna_directional_cone(antenna)
        tasks = [renderer.add_antenna_directional_cone(antenna) for antenna in antennas]
        await asyncio.gather(*tasks)

        # Finalize and save the map
        renderer.finalize_map()
        output_file = "output_map.html"
        renderer.save_map(output_file)

        # Serve the generated map
        return send_file(output_file)

    except Exception as e:
        # Get the exception information
        exc_type, exc_value, exc_traceback = sys.exc_info()

        # Print the exception information
        traceback.print_exception(exc_type, exc_value, exc_traceback)

        # Alternatively, format the stack trace into a string
        formatted_traceback = traceback.format_exc()

        return f"<h4>An error occurred: {e}</h4><pre>{formatted_traceback}</pre>", 500

if __name__ == "__main__":
    # Load configuration
    try:
        config_path = Path("config/config.yaml")
        config = load_config(config_path)
    except Exception as e:
        print(f"Failed to load config: {e}")
        sys.exit(1)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    # Start the Flask server
    try:
        app.run(host="0.0.0.0", port=config['app']['server_port'], debug=True)
    except KeyboardInterrupt:
        print("Shutting down gracefully...")