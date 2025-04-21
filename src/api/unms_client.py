# unms_client.py
import requests
import math
import json
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from cachetools import cached, TTLCache
from src.visualization.models.antenna import Antenna
    
class UNMSClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({'x-auth-token': api_key})
    
    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def get_devices(self) -> List[Dict]:
        response = self.session.get(f"{self.base_url}/v2.1/devices")
        response.raise_for_status()
        return response.json()
    
    @cached(cache=TTLCache(maxsize=100, ttl=300))
    def get_sites(self) -> List[Dict]:
        response = self.session.get(f"{self.base_url}/v2.1/sites")
        response.raise_for_status()
        return response.json()

    def get_aps(self) -> List[Antenna]:
        devices = self.get_devices()
        antennas = []
        
        # Dump the raw JSON response to a file for debugging
        with open('devices.json', 'w') as f:
            json.dump(devices, f, indent=4)

        for device in devices:
            if self._is_ap(device) and self._is_infrastructure(device):
                if self._is_wave(device) or self._is_airfiber_60(device):
                    antennas.append(Antenna(
                        id=device['identification']['id'],
                        name=device['identification']['name'],
                        latitude=device['location']['latitude'],
                        longitude=device['location']['longitude'],
                        azimuth=self.get_azimuth(device),
                        downtilt=device['location']['tilt'] if device['location'].get('tilt') else 0,
                        frequency=device['overview']['frequency'],
                        channel_width=device['overview']['channelWidth'],
                        height=device['location']['altitude'], # MSL, may need converting to AGL
                        model=device['identification']['model'], 
                        antenna=device['overview']['antenna']['name'] 
                    ))
                elif self._is_airmax(device):
                    antennas.append(Antenna(
                        id=device['identification']['id'],
                        name=device['identification']['name'],
                        latitude=device['location']['latitude'],
                        longitude=device['location']['longitude'],
                        azimuth=self.get_azimuth(device),
                        downtilt=device['location']['tilt'] if device['location'].get('tilt') else 0,
                        frequency=device['overview']['frequency'],
                        channel_width=device['overview']['channelWidth'],
                        height=device['location']['altitude'], # MSL, may need converting to AGL
                        model=device['identification']['model'],
                        antenna=device['overview']['antenna']['name'] 
                    ))
        return antennas

    def get_azimuth(self, device: Dict) -> int:
        # Implement logic to extract azimuth from device data
        if device.get('location') and device['location'].get('heading'):
            print(f"{device['identification']['name']} - has compass sensor data.")
            return int(device['location']['heading'])
        
        # If azimuth note exists in UNMS for this device, override compass sensor data
        # Note: This assumes the note is a JSON string with an "azimuth" key
        # UNMS device note example: {"azimuth": 45}
        if device.get('meta').get('note'):
            note_json = json.loads(device['meta']['note'])
            print(f"{device['identification']['name']} - has a note with override, azimuth: {int(note_json['azimuth'])}")
            if 'azimuth' in note_json:
                return int(note_json['azimuth'])
            
        # If no azimuth sensor data or note override exists, estimate azimuth based on child stations
        return self.estimate_ap_azimuth(device)

    def _is_infrastructure(self, device: Dict) -> bool:
        sites = self.get_sites()
        # Implement logic to identify infrastructure devices
        for site in sites:
            if site.get('identification').get('type') == 'site' and site.get('identification').get('id') == device.get('identification').get('site').get('id'):
                    return True
        return False

    def _is_airmax(self, device: Dict) -> bool:
        # Implement logic to identify AirMax devices
        if device.get('identification').get('type').lower() == 'airmax':
            return True
        return False

    def _is_wave(self, device: Dict) -> bool:
        # Implement logic to identify Wave devices
        if device.get('identification').get('type').lower() == 'wave':
            return True
        return False
    
    def _is_airfiber_60(self, device: Dict) -> bool:
        # Implement logic to identify AirFiber devices
        if device.get('identification').get('type').lower() == 'airfiber' and 'af60' in device.get('identification').get('model').lower():
            return True
        return False

    def _is_ap(self, device: Dict) -> bool:
        # Implement logic to identify antenna devices
        if device.get('overview') and device.get('overview').get('wirelessMode') and 'ap-' in device.get('overview').get('wirelessMode').lower():
            return True
        return False

    def get_child_stations_coords(self, ap_device: Dict) -> List[Tuple[float, float]]:
        """
        Get the GPS coordinates of all child stations connected to the given AP.
        
        :param ap_device: The AP device dictionary.
        :return: A list of (latitude, longitude) tuples for all child stations.
        """

        devices = []
        child_coords = []

        # Check if devices.json exists. Should always exist since this method relies on APs being loaded.
        if Path('devices.json').exists():
            with open('devices.json', 'r') as f:
                devices = json.load(f)
        else:
            devices = self.get_devices()

        for device in devices:
            if device.get('attributes') and device.get('attributes').get('ssid') == ap_device.get('attributes').get('ssid'):
                lat = device.get('location').get('latitude')
                lon = device.get('location').get('longitude')
                if lat is not None and lon is not None:
                    child_coords.append((lat, lon))

        return child_coords

    def estimate_ap_azimuth(self, ap_device: Dict) -> float:
        """
        Estimate the azimuth of an AP based on the spatial distribution of its child stations.
        
        :param ap_device: The AP device dictionary.
        :return: The estimated azimuth in degrees.
        """
        child_station_coords = self.get_child_stations_coords(ap_device)
        if not child_station_coords:
            return 0.0  # Default azimuth if no child stations are available

        # Get the AP's coordinates
        ap_lat = ap_device['location']['latitude']
        ap_lon = ap_device['location']['longitude']

        # Calculate the vectors to each child station
        x_sum = 0
        y_sum = 0
        for lat, lon in child_station_coords:
            # Convert lat/lon to radians
            lat_rad = math.radians(lat)
            lon_rad = math.radians(lon)
            ap_lat_rad = math.radians(ap_lat)
            ap_lon_rad = math.radians(ap_lon)

            # Calculate the vector components
            delta_lon = lon_rad - ap_lon_rad
            x = math.cos(lat_rad) * math.sin(delta_lon)
            y = math.cos(ap_lat_rad) * math.sin(lat_rad) - math.sin(ap_lat_rad) * math.cos(lat_rad) * math.cos(delta_lon)

            x_sum += x
            y_sum += y

        # Calculate the medial radian (average direction)
        azimuth_rad = math.atan2(x_sum, y_sum)
        azimuth_deg = math.degrees(azimuth_rad)

        # Normalize the azimuth to 0-360 degrees
        if azimuth_deg < 0:
            azimuth_deg += 360

        print(f"{ap_device['identification']['name']} - found {len(child_station_coords)} child stations, estimated azimuth: {azimuth_deg:.2f}°")

        return azimuth_deg