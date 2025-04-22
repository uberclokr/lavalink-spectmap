# map_renderer.py
import folium
import numpy as np
from scipy.ndimage import zoom
from rasterio.transform import Affine
from folium.plugins import HeatMap
from folium.raster_layers import ImageOverlay
from .models.antenna import Antenna
from .coverage_calculator import CoverageCalculator
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import yaml
import rasterio
import asyncio
from typing import List, Tuple
from PIL import Image

def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)
    
config = load_config(Path("config/config.yaml"))

def frequency_to_color(antenna: Antenna) -> str:
    """
    Map a frequency to a color based on a gradient.
    
    :param frequency: The frequency to map.
    :param min_freq: The minimum frequency in the spectrum.
    :param max_freq: The maximum frequency in the spectrum.
    :return: A hex color string.
    """
    # Get band range
    min_freq = antenna.frequency_band[0]
    max_freq = antenna.frequency_band[1]
    
    # Normalize the frequency to a 0-1 range
    norm = mcolors.Normalize(vmin=min_freq, vmax=max_freq)
    
    # Create a colormap (e.g., from blue to red)
    band = antenna.frequency_band_name
    if band.lower() == 'ism': # 3GHz to 7GHz - mainly concerned with 5Ghz
        colormap = plt.cm.get_cmap('hot')
    elif 'u-nii' in band.lower():
        if '1' in band:
            colormap = plt.cm.get_cmap('spring')
        elif '2A' in band:
            colormap = plt.cm.get_cmap('summer')
        elif '2B' in band:
            colormap = plt.cm.get_cmap('autumn')
        elif '2C' in band:
            colormap = plt.cm.get_cmap('winter')
        elif '3' in band:
            colormap = plt.cm.get_cmap('gist_ncar')
        elif '4' in band:
            colormap = plt.cm.get_cmap('turbo')
        elif '5' in band:
            colormap = plt.cm.get_cmap('gist_ncar')
    elif band.lower() == 'vband': # 60Ghz   
        colormap = plt.cm.get_cmap('autumn')
    else:
        colormap = plt.cm.get_cmap('hsv')

    # Map the normalized frequency to a color
    rgba_color = colormap(norm(antenna.frequency))
    
    # Convert the RGBA color to a hex string
    return mcolors.to_hex(rgba_color)

class MapRenderer:

    def __init__(self, center_lat: float = 0, center_lon: float = 0, zoom_start: int = 12, add_elevation_layer: bool = False):
        self.map = folium.Map(location=[center_lat, center_lon], tiles="Cartodb Positron", zoom_start=zoom_start)
        # Preload dataset to be used for elevation data
        self.dataset = CoverageCalculator.preload_tiff()

        # Add an elevation layer if requested
        folium.TileLayer(
            tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            attr="Map data: &copy; <a href='https://opentopomap.org/'>OpenTopoMap</a> contributors",
            name="Elevation (OpenTopoMap)",
            overlay=False
        ).add_to(self.map)

        # Create feature groups for 60GHz and 5GHz radios
        self.layer_60ghz = folium.FeatureGroup(name="60GHz Radios", show=True)
        self.layer_5ghz = folium.FeatureGroup(name="5GHz Radios", show=False)
        self.layer_2ghz = folium.FeatureGroup(name="2.4GHz Radios")

    async def add_antenna_directional_cone(self, antenna: Antenna):
        """Add a coverage cone for a single antenna asynchronously."""
        try:
            # Debugging: Log antenna details
            print(f"Processing antenna: {antenna.name}, Lat: {antenna.latitude}, Lon: {antenna.longitude}, Azimuth: {antenna.azimuth}")

            # Initialize the CoverageCalculator
            calculator = CoverageCalculator(
                name=antenna.name,
                antenna_height=antenna.height,
                beamwidth=antenna.beamwidth_horizontal,
                beamheight=antenna.beamwidth_vertical
            )

            # Calculate the coverage polygon
            coverage_points = await asyncio.to_thread(
                calculator.calculate_coverage_cone,
                antenna.latitude,
                antenna.longitude,
                antenna.azimuth,
                antenna.downtilt,
                antenna._model_range_m()
            )
            if coverage_points is None:
                raise ValueError(f"Coverage points calculation returned None for antenna: {antenna.name}")

            # Only calculate and render viewshed for PTMP APs. Naming convention includes 'AP' in the name.
            viewshed_png = f"tmp/viewshed_{antenna.name}.png"
            if 'AP' in antenna.name:
                # Only calculate and render viewshed if viewshed PNG does not exist
                if not Path(viewshed_png).exists():

                    # Calculate the viewshed raster
                    viewshed = await asyncio.to_thread(
                        calculator.calculate_viewshed_raster,
                        antenna.latitude,
                        antenna.longitude,
                        antenna.azimuth,
                        antenna.downtilt,
                        antenna._model_range_m()
                    )
                    if viewshed is None:
                        raise ValueError(f"Viewshed raster calculation returned None for antenna: {antenna.name}")

                    # Save the viewshed raster as an image if Access Point
                    await self._save_viewshed_as_image(viewshed, viewshed_png, coverage_points)  
            
                # Add viewshed PNG to the map
                await self.add_viewshed_to_map(viewshed_png, coverage_points)

            # Add the polygon to the map
            fill_color = frequency_to_color(antenna)
            polygon = folium.Polygon(
                locations=coverage_points,
                color=fill_color,
                fill=True,
                fill_opacity=0.2,
                weight=1,
                popup=f"<a target=\"_blank\" rel=\"noopener noreferrer\" href=\"{config['unms']['url']}/nms/devices#id={antenna.id}&panelType=device-panel\">{antenna.name}</a><br>Center: {antenna.frequency}<br>Width: {antenna.channel_width}"
            )
            if antenna.frequency < 7000:
                self.layer_5ghz.add_child(polygon)
            elif 55000 <= antenna.frequency < 72000:
                self.layer_60ghz.add_child(polygon)

        except Exception as e:
            print(f"Error calculating coverage for {antenna.name}: {e}")

    def downsample_raster(self, raster: np.ndarray, scale: float) -> np.ndarray:
        """
        Downsample a raster array by a given scale factor.
        :param raster: The original raster array.
        :param scale: The scale factor (e.g., 0.5 to reduce resolution by half).
        :return: The downsampled raster array.
        """
        return zoom(raster, zoom=scale, order=1)  # Use bilinear interpolation (order=1)

    def adjust_transform(self, original_transform: Affine, scale: float) -> Affine:
        """
        Adjust the raster transform for the downsampled resolution.
        :param original_transform: The original raster transform.
        :param scale: The scale factor (e.g., 0.5 to reduce resolution by half).
        :return: The adjusted transform.
        """
        return original_transform * Affine.scale(1 / scale, 1 / scale)
    
    async def _save_viewshed_raster(self, viewshed, filepath, scale=0.5):
        """
        Save the viewshed raster as a GeoTIFF asynchronously, with optional downsampling.
        :param viewshed: The original viewshed raster array.
        :param filepath: The file path to save the raster.
        :param scale: The scale factor for downsampling (default is 0.5).
        """
        # Downsample the raster
        downsampled_viewshed = zoom(viewshed, zoom=scale, order=1)  # Bilinear interpolation

        # Adjust the transform for the downsampled raster
        downsampled_transform = self.adjust_transform(self.dataset.transform, scale)

        # Save the downsampled raster
        with rasterio.open(
            filepath,
            "w",
            driver="GTiff",
            height=downsampled_viewshed.shape[0],
            width=downsampled_viewshed.shape[1],
            count=1,
            dtype=np.uint8,
            crs=self.dataset.crs,
            transform=downsampled_transform,
        ) as dst:
            dst.write(downsampled_viewshed, 1)

    def _get_frequency_band(self, frequency: float) -> int:
        """Round frequency to nearest standard band"""
        if frequency < 3000:
            return 2400
        elif 3000 <= frequency < 7000:
            return 5000
        elif 55000 <= frequency < 72000:
            return 60000
    
    async def _save_viewshed_as_image(self, viewshed: np.ndarray, output_path: str, coverage_points: List[Tuple[float, float]]):
        """
        Save the viewshed raster as a transparent green image, cropped to remove empty space.
        """
        def create_cropped_image():
            # Find the bounding box of non-zero pixels
            non_zero_rows, non_zero_cols = np.nonzero(viewshed)
            if len(non_zero_rows) == 0 or len(non_zero_cols) == 0:
                raise ValueError("Viewshed raster is empty, cannot create image.")

            # Calculate the bounding box
            min_row, max_row = non_zero_rows.min(), non_zero_rows.max()
            min_col, max_col = non_zero_cols.min(), non_zero_cols.max()

            # Crop the viewshed array
            cropped_viewshed = viewshed[min_row:max_row + 1, min_col:max_col + 1]

            # Create the cropped image
            height, width = cropped_viewshed.shape
            image = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Fully transparent background
            for row in range(height):
                for col in range(width):
                    if cropped_viewshed[row, col] == 1:  # Visible point
                        image.putpixel((col, row), (0, 255, 0, 128))  # Green with 50% transparency

            # Save the cropped image
            image.save(output_path, "PNG")

            # Return the bounding box for further use
            return min_row, max_row, min_col, max_col

        # Offload the image creation to a separate thread
        min_row, max_row, min_col, max_col = await asyncio.to_thread(create_cropped_image)

        # Adjust the coverage points to reflect the cropped area
        # (Optional: You can use this bounding box to adjust map bounds if needed)

    def adjust_transform_for_crop(original_transform: Affine, min_row: int, min_col: int) -> Affine:
        """
        Adjust the raster transform for the cropped area.
        :param original_transform: The original raster transform.
        :param min_row: The minimum row of the cropped area.
        :param min_col: The minimum column of the cropped area.
        :return: The adjusted transform.
        """
        return original_transform * Affine.translation(min_col, min_row)

    async def add_viewshed_to_map(self, viewshed_image_path: str, bounds: List[Tuple[float, float]]):
        """
        Add the viewshed image to the map as an overlay.
        :param viewshed_image_path: Path to the viewshed image file.
        :param bounds: The geographical bounds of the viewshed image (southwest and northeast corners).
        """
        # Calculate bounds if not already in the correct format
        if len(bounds) > 2:
            lats, lons = zip(*bounds)
            bounds = [(min(lats), min(lons)), (max(lats), max(lons))]

        # Add the image overlay to the map
        folium.raster_layers.ImageOverlay(
            image=viewshed_image_path,
            bounds=bounds,
            opacity=0.5,  # Adjust transparency
            name="Viewshed"
        ).add_to(self.map)

    def finalize_map(self):
        """Finalize the map by adding layers and controls"""
        # Add the feature groups to the map only if they contain features
        print(f"60GHz Layer contains {int(len(self.layer_60ghz._children))} infrastructure access points.")
        print(f"5GHz Layer contains {int(len(self.layer_5ghz._children))} infrastructure access points.")
        if len(self.layer_60ghz._children) > 0:
            self.layer_60ghz.add_to(self.map)
        if len(self.layer_5ghz._children) > 0:
            self.layer_5ghz.add_to(self.map)

        # Add a layer control to toggle between layers
        folium.LayerControl().add_to(self.map)

        #self.map.add_child(folium.ClickForMarker(popup=folium.Popup(), callback=click_handler))

        print("Map finalized with layers and controls.")

    def save_map(self, filename: str):
        """Write map object to object file"""
        with open('debug/debug-map.json', 'w') as f:
            f.write(self.map.to_json())
        self.map.save(filename)