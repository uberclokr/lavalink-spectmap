import numpy as np
from geopy import distance
from typing import Tuple, List
from pathlib import Path
import asyncio
import yaml
import time
import sys
from pathlib import Path
import rasterio
import yaml
from rasterio.transform import from_origin
from rasterio.merge import merge
from rasterio.plot import show

# Load configuration file
def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)
config = load_config(Path("config/config.yaml"))

# Global variable to store the preloaded GeoTIFF dataset
dataset = None

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

class CoverageCalculator:
    def __init__(self, name: str, antenna_height: float, beamwidth: float = 60.0, beamheight: float = 30.0):
        """
        :param antenna_height: Height above ground in meters
        :param beamwidth: Horizontal beamwidth in degrees (default 60° for typical sector antennas)
        """
        self.name = name
        self.antenna_height = antenna_height
        self.beamwidth = beamwidth
        self.beamheight = beamheight

    @staticmethod
    def preload_tiff():
        """
        Preload the GeoTIFF file into memory as a NumPy array when the Flask app starts.
        """
        global dataset, raster_array, raster_transform, raster_crs
        try:
            with rasterio.open(config['map']['srtm_file']) as src:
                # Read the raster data into a NumPy array
                raster_array = src.read(1)  # Read the first band (elevation data)
                raster_transform = src.transform  # Store the transform for georeferencing
                raster_crs = src.crs  # Store the CRS for spatial reference
                print(f"VIEWSHED RENDERING - Preloaded GeoTIFF file: {config['map']['srtm_file']} into memory")
                return src
        except Exception as e:
            print(f"Failed to preload GeoTIFF file: {e}")
            sys.exit(1)

    async def get_elevation(self, lat: float, lon: float) -> float:
        """
        Fetch elevation data for a given latitude and longitude using windowed reads.
        """
        start_time = time.time()  # Start stopwatch
        try:
            #print(f"[{time.time():.2f}] Task started for ({lat}, {lon})")

            # Offload blocking rasterio operations to a separate thread                
            def fetch_elevation():
                # Use the preloaded dataset
                row, col = dataset.index(lon, lat)
                window = rasterio.windows.Window(col, row, 1, 1)
                elevation = dataset.read(1, window=window)[0, 0]
                return elevation

            elevation_value = await asyncio.to_thread(fetch_elevation)

            elapsed_time = time.time() - start_time  # Stop stopwatch
            #print(f"[{time.time():.2f}] Task completed for ({lat}, {lon}) in {elapsed_time:.2f} seconds")
            return float(elevation_value)
        except Exception as e:
            elapsed_time = time.time() - start_time  # Stop stopwatch
            print(f"[{time.time():.2f}] Error fetching elevation for ({lat}, {lon}) in {elapsed_time:.2f} seconds: {e}")
            return 0.0  # Default elevation on error
        
    async def calculate_viewshed(self, center_lat: float, center_lon: float,
                                azimuth: float, downtilt: float, distance_m: float = 5000,
                                station_height: float = 6.0) -> List[Tuple[float, float]]:
        """
        Calculate the viewshed boundary based on terrain collision points.
        """
        azimuth_rad = np.radians(azimuth)
        downtilt_rad = np.radians(abs(downtilt))
        points = []
        steps = config['map']['arc_steps']  # Number of points in the arc
        points_per_line = config['map']['arc_radial_points']  # Number of points along each radial line

        semaphore = asyncio.Semaphore(config['map']['processing_threads'])  # Limit concurrent tasks

        async def fetch_with_semaphore(lat, lon):
            async with semaphore:
                return await self.get_elevation(lat, lon)

        # Prepare tasks for asynchronous elevation fetching
        tasks = []
        for i in range(steps + 1):
            angle = azimuth_rad - np.radians(self.beamwidth / 2) + np.radians(self.beamwidth) * i / steps
            for dist in np.linspace(0, distance_m, num=points_per_line):
                # Calculate the point's latitude and longitude
                new_point = distance.distance(meters=dist).destination(
                    point=(center_lat, center_lon),
                    bearing=np.degrees(angle)
                )
                lat, lon = new_point.latitude, new_point.longitude
                tasks.append(fetch_with_semaphore(lat, lon))

        # Fetch elevations concurrently
        elevations = await asyncio.gather(*tasks, return_exceptions=True)

        # Process the results
        task_index = 0
        for i in range(steps + 1):
            angle = azimuth_rad - np.radians(self.beamwidth / 2) + np.radians(self.beamwidth) * i / steps
            for dist in np.linspace(0, distance_m, num=points_per_line):
                # Calculate the point's latitude and longitude
                new_point = distance.distance(meters=dist).destination(
                    point=(center_lat, center_lon),
                    bearing=np.degrees(angle)
                )
                lat, lon = new_point.latitude, new_point.longitude

                # Get the corresponding elevation
                elevation_result = elevations[task_index]
                task_index += 1

                # Handle exceptions in elevation results
                if isinstance(elevation_result, Exception):
                    print(f"Error fetching elevation for ({lat}, {lon}): {elevation_result}")
                    continue

                terrain_elevation = elevation_result

                # Calculate the height of the signal at this distance
                signal_height = self.antenna_height - (dist * np.tan(downtilt_rad))

                # Check if the terrain obstructs the signal
                if terrain_elevation > signal_height + station_height:
                    break  # Stop adding points along this line if obstructed

                # Add the point to the viewshed
                points.append((lat, lon))

        # Include the origin point to create a radiating cone
        if self.beamwidth != 360 and self.beamwidth != 0:
            points.insert(0, (center_lat, center_lon))

        return points

    def calculate_coverage_cone(self, center_lat: float, center_lon: float,
                              azimuth: float, downtilt: float, distance_m: float = 1000) -> List[Tuple[float, float]]:
        """
        Calculate polygon points for the coverage area
        
        :param distance_m: Maximum distance to calculate coverage (in meters)
        :return: List of (lat, lon) points forming the coverage polygon
        """
        # Convert angles to radians
        azimuth_rad = np.radians(azimuth)
        downtilt_rad = np.radians(abs(downtilt))
        
        # Calculate the main direction point
        points = []
        steps = 36  # Number of points in the arc
        
        # Handle downtilt = 0 to avoid division by zero
        if downtilt_rad <= 0:
            ground_distance = distance_m  # Or use a large default value
        else:
            ground_distance = self.antenna_height / np.tan(downtilt_rad)
            #print(f"Ground distance calculated: {ground_distance} m")


        for i in range(steps + 1):
            angle = azimuth_rad - np.radians(self.beamwidth/2) + np.radians(self.beamwidth) * i/steps
            dist = min(ground_distance, distance_m)
            
            # Calculate new point
            new_point = distance.distance(meters=dist).destination(
                point=(center_lat, center_lon),
                bearing=np.degrees(angle)
            )
            
            points.append((new_point.latitude, new_point.longitude))
        

        # Include origin point to create radiating cone (except for omnidirectional antennas)
        if self.beamwidth != 360 and self.beamwidth != 0:
            points.insert(0, (center_lat, center_lon))

        return points
    
    def calculate_viewshed_raster(self, center_lat: float, center_lon: float, azimuth: float, downtilt: float, distance_m: float) -> np.ndarray:
        """
        Calculate a viewshed raster within the confines of the cone using the preloaded raster array.
        """
        # Get the raster bounds
        bounds = rasterio.transform.array_bounds(raster_array.shape[0], raster_array.shape[1], raster_transform)

        # Create an empty viewshed array
        viewshed = np.zeros(raster_array.shape, dtype=np.uint8)

        # Iterate over the cone's area
        for angle in np.linspace(azimuth - self.beamwidth / 2, azimuth + self.beamwidth / 2, num=36):
            for dist in np.linspace(0, distance_m, num=100):
                # Calculate the target point's lat/lon
                target_point = distance.distance(meters=dist).destination(
                    point=(center_lat, center_lon),
                    bearing=angle
                )
                target_lat, target_lon = target_point.latitude, target_point.longitude

                # Check if the target point is within the raster bounds
                if not (bounds[0] <= target_lon <= bounds[2] and bounds[1] <= target_lat <= bounds[3]):
                    continue  # Skip points outside the raster bounds

                # Convert target lat/lon to row/col
                try:
                    target_row, target_col = rasterio.transform.rowcol(raster_transform, target_lon, target_lat)
                except ValueError:
                    continue  # Skip points that cannot be indexed

                # Ensure indices are within the raster's dimensions
                if not (0 <= target_row < raster_array.shape[0] and 0 <= target_col < raster_array.shape[1]):
                    continue  # Skip points outside the raster dimensions

                # Get the elevation at the target point
                elevation = raster_array[target_row, target_col]

                # Calculate the height of the signal at this distance
                signal_height = self.antenna_height - (dist * np.tan(np.radians(downtilt)))

                # Mark the point as visible if it is not obstructed
                if elevation <= signal_height:
                    viewshed[target_row, target_col] = 1

        return viewshed