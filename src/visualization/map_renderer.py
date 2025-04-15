# map_renderer.py
import folium
from folium.plugins import HeatMap
from typing import List
from .models.antenna import Antenna
from .coverage_calculator import CoverageCalculator
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import yaml

def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)
config = load_config(Path("config/config.yaml"))

def frequency_to_color(frequency: float, min_freq: float, max_freq: float) -> str:
    """
    Map a frequency to a color based on a gradient.
    
    :param frequency: The frequency to map.
    :param min_freq: The minimum frequency in the spectrum.
    :param max_freq: The maximum frequency in the spectrum.
    :return: A hex color string.
    """
    # Normalize the frequency to a 0-1 range
    norm = mcolors.Normalize(vmin=min_freq, vmax=max_freq)
    
    # Create a colormap (e.g., from blue to red)
    colormap = plt.cm.get_cmap('jet')  # You can use other colormaps like 'plasma', 'coolwarm', etc.
    
    # Map the normalized frequency to a color
    rgba_color = colormap(norm(frequency))
    
    # Convert the RGBA color to a hex string
    return mcolors.to_hex(rgba_color)

class MapRenderer:

    def __init__(self, center_lat: float = 0, center_lon: float = 0, zoom_start: int = 12, add_elevation_layer: bool = False):
        self.map = folium.Map(location=[center_lat, center_lon], tiles="Cartodb Positron", zoom_start=zoom_start)

        # Add a satellite view tileset
        folium.TileLayer(
            tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
            attr="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
            name="OpenStreetMap",
        ).add_to(self.map)

        # Add an elevation layer if requested
        folium.TileLayer(
            tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
            attr="Map data: &copy; <a href='https://opentopomap.org/'>OpenTopoMap</a> contributors",
            name="Elevation (OpenTopoMap)",
            overlay=False
        ).add_to(self.map)

    def add_antenna_coverage(self, antenna: Antenna):
        """Add a coverage cone for a single antenna"""
        try:
            calculator = CoverageCalculator(
                antenna_height=antenna.height,
                beamwidth=antenna.beamwidth_horizontal,
                beamheight=antenna.beamwidth_vertical
                )
        except Exception as e:
            print(f"Error calculating coverage for {type(antenna)} {antenna.name}: {e}")
            return
        
    
        coverage_points = calculator.calculate_coverage_cone(
            antenna.latitude, 
            antenna.longitude, 
            antenna.azimuth, 
            antenna.downtilt,
            distance_m=antenna._model_range_m()
            )
        
        # Get color based on frequency band
        band_min = antenna.frequency_band[0]
        band_max = antenna.frequency_band[1]
        fill_color = frequency_to_color(antenna.frequency,band_min,band_max)
        
        folium.Polygon(
            locations=coverage_points,
            color=fill_color,
            fill=True,
            fill_opacity=0.2,
            weight=1,
            popup=f"<a target=\"_blank\" rel=\"noopener noreferrer\" href=\"{config['unms']['url']}/nms/devices#id={antenna.id}&panelType=device-panel\">{antenna.name}</a><br>Center: {antenna.frequency}<br>Width: {antenna.channel_width}"
        ).add_to(self.map)
        
        # Add antenna marker
        folium.Marker(
            location=[antenna.latitude, antenna.longitude],
            popup=f"<b><a target=\"_blank\" rel=\"noopener noreferrer\" href=\"{config['unms']['url']}/nms/devices#id={antenna.id}&panelType=device-panel\">{antenna.name}</a></b><br>Azimuth: {antenna.azimuth}°<br>Tilt: {antenna.downtilt}°",
            icon=folium.Icon(color='black', icon='wifi', prefix='fa')
        ).add_to(self.map)
    
    def _get_frequency_band(self, frequency: float) -> int:
        """Round frequency to nearest standard band"""
        if frequency < 3000:
            return 2400
        elif 3000 <= frequency < 7000:
            return 5000
        elif 55000 <= frequency < 72000:
            return 60000
    
    def save_map(self, filename: str):
        self.map.save(filename)