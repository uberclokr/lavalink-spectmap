from flask import Flask, request, jsonify
from pathlib import Path
import argparse
import sys
import rasterio
import yaml
from rasterio.transform import from_origin
from rasterio.merge import merge
from rasterio.plot import show

def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)
    
config = load_config(Path("config/config.yaml"))

app = Flask(__name__)

# Load the SRTM GeoTIFF file
SRTM_FILE = "maps/merged/merged.tif"

# Global variable to store the preloaded dataset
dataset = None

def preload_tiff():
    """
    Preload the GeoTIFF file into memory when the Flask app starts.
    """
    global dataset
    try:
        dataset = rasterio.open(SRTM_FILE)
        print(f"Preloaded GeoTIFF file: {SRTM_FILE}")
    except Exception as e:
        print(f"Failed to preload GeoTIFF file: {e}")
        sys.exit(1)

@app.route("/elevation/<lat>/<lon>", methods=["GET"])
def get_elevation(lat: float, lon: float):
    """
    Get elevation data for a given latitude and longitude.
    """
    global dataset

    if lat is None or lon is None:
        print("Missing latitude or longitude parameters")
        return jsonify({"error": "Please provide 'lat' and 'lon' parameters"}), 400

    try:
        # Use the preloaded dataset
        elevation = get_elevation_from_dataset(dataset, float(lat), float(lon))
        return jsonify({"latitude": lat, "longitude": lon, "elevation": elevation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_elevation_from_dataset(dataset, lat: float, lon: float) -> float:
    """
    Get elevation data from a preloaded GeoTIFF dataset for a given latitude and longitude.

    :param dataset: Preloaded rasterio dataset.
    :param lat: Latitude of the point.
    :param lon: Longitude of the point.
    :return: Elevation value at the given point.
    """
    # Convert lat/lon to row/col in the raster
    row, col = dataset.index(lon, lat)
    # Get the elevation value
    elevation = dataset.read(1)[row, col]
    return float(elevation)

def get_elevation_from_tif(tif_file: str, lat: float, lon: float) -> float:
    """
    Get elevation data from a GeoTIFF file for a given latitude and longitude.

    :param tif_file: Path to the GeoTIFF file.
    :param lat: Latitude of the point.
    :param lon: Longitude of the point.
    :return: Elevation value at the given point.
    """
    with rasterio.open(tif_file) as dataset:
        # Convert lat/lon to row/col in the raster
        row, col = dataset.index(lon, lat)
        # Get the elevation value
        elevation = dataset.read(1)[row, col]
        return float(elevation)

def merge_tif_files(tif_files: list, output_path: str):
    """
    Merge multiple GeoTIFF files into a single file.

    :param tif_files: List of paths to the GeoTIFF files.
    :param output_path: Path to save the merged GeoTIFF file.
    """
    src_files_to_mosaic = []

    # Open each GeoTIFF file
    for tif_file in tif_files:
        src = rasterio.open(tif_file)
        src_files_to_mosaic.append(src)

    # Merge the files
    mosaic, out_transform = merge(src_files_to_mosaic)

    # Save the merged file
    out_meta = src_files_to_mosaic[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform
    })

    with rasterio.open(output_path, "w", **out_meta) as dest:
        dest.write(mosaic)

    print(f"Merged GeoTIFF saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Rasterizer utility for elevation data.")
    parser.add_argument(
        "-m", "--merge", 
        metavar="tiff_directory", 
        type=str, 
        help="Merge all TIFF files located within the provided directory."
    )
    args = parser.parse_args()

    if args.merge:
        # Merge all TIFF files in the specified directory
        tiff_directory = Path(args.merge)
        if not tiff_directory:
            print(f"Using default map directory: {config['map']['map_directory']}")
        if not tiff_directory.is_dir():
            print(f"Error: {tiff_directory} is not a valid directory.")
            sys.exit(1)

        # Find all TIFF files in the directory
        tiff_files = list(tiff_directory.glob("*.tif"))
        if not tiff_files:
            print(f"No TIFF files found in directory: {tiff_directory}")
            sys.exit(1)

        # Merge the TIFF files
        if not (tiff_directory / "merged").exists():
            (tiff_directory / "merged").mkdir(parents=True)
        output_path = tiff_directory / "merged/merged.tif"
        merge_tif_files(tiff_files, str(output_path))
    else:
        # Start the Flask server
        app.run(host="0.0.0.0", port=config['map']['elevation_server_port'])

if __name__ == "__main__":
    #preload_tiff()
    main()