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
            """GENERATE DIRECTIONAL POLYGON"""
            # Initialize the CoverageCalculator
            calculator = CoverageCalculator(
                name=antenna.name,
                antenna_height=antenna.height,
                beamwidth=antenna.beamwidth_horizontal,
                beamheight=antenna.beamwidth_vertical
            )

            # Calculate the coverage polygon (synchronous, but lightweight)
            coverage_points = await asyncio.to_thread(
                calculator.calculate_coverage_cone,
                antenna.latitude,
                antenna.longitude,
                antenna.azimuth,
                antenna.downtilt,
                antenna._model_range_m()
            )

            """GENERATE VIEWSHED RASTER"""
            # Calculate the viewshed raster (offload to a thread)
            viewshed = await asyncio.to_thread(
                calculator.calculate_viewshed_raster,
                antenna.latitude,
                antenna.longitude,
                antenna.azimuth,
                antenna.downtilt,
                antenna._model_range_m()
            )

            # Save the viewshed raster as a GeoTIFF with downsampling
            raster_path = f"tmp/viewshed_{antenna.name}.tif"
            resolution_scale = 0.25 # Reduce resolution to 25%
            await self._save_viewshed_raster(viewshed, raster_path, scale=resolution_scale)

            # Add the viewshed raster to the map as an overlay
            bounds = [
                [antenna.latitude - 0.01, antenna.longitude - 0.01],  # Adjust bounds as needed
                [antenna.latitude + 0.01, antenna.longitude + 0.01]
            ]
            ImageOverlay(
                image=raster_path,
                bounds=bounds,
                opacity=0.5,
                name=f"Viewshed: {antenna.name}"
            ).add_to(self.map)

            """GENERATE AND FORMAT FOLIUM MAP"""
            # Get color based on frequency band
            fill_color = frequency_to_color(antenna)

            # Add the polygon to the map
            polygon = folium.Polygon(
                locations=coverage_points,
                color=fill_color,
                fill=True,
                fill_opacity=0.2,
                weight=1,
                popup=f"<a target=\"_blank\" rel=\"noopener noreferrer\" href=\"{config['unms']['url']}/nms/devices#id={antenna.id}&panelType=device-panel\">{antenna.name}</a><br>Center: {antenna.frequency}<br>Width: {antenna.channel_width}"
            )

            # Add the polygon to the appropriate layer
            if antenna.frequency < 7000:
                self.layer_5ghz.add_child(polygon)
            elif 55000 <= antenna.frequency < 72000:
                self.layer_60ghz.add_child(polygon)

            # Add frequency label to each coverage cone
            centroid_lat = sum(lat for lat, lon in coverage_points) / len(coverage_points)
            centroid_lon = sum(lon for lat, lon in coverage_points) / len(coverage_points)
            text_marker = folium.Marker(
                location=[centroid_lat, centroid_lon],
                icon=folium.DivIcon(
                    html=f"""
                    <div style="
                        text-align: center;
                        font-size: 12px;
                        font-weight: bold;
                        color: {fill_color};
                        text-align: center;
                        text-shadow: 0px 0px 2px black;
                    ">
                        {antenna.name.split('.')[0]}<br>{antenna.frequency}
                    </div>
                    """
                )
            )
            if antenna.frequency < 7000:
                self.layer_5ghz.add_child(text_marker)  # We want these on the same layer as the polygon
            elif 55000 <= antenna.frequency < 72000:
                self.layer_60ghz.add_child(text_marker)

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