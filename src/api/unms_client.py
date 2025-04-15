# unms_client.py
import requests
import json
from typing import List, Dict
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
    
    def get_aps(self) -> List[Antenna]:
        devices = self.get_devices()
        antennas = []
        
        # Dump the raw JSON response to a file for debugging
        with open('devices.json', 'w') as f:
            json.dump(devices, f, indent=4)

        for device in devices:
            if self._is_ap(device):
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
                        model=device['identification']['model'] 
                    ))
        return antennas

    def get_azimuth(self, device: Dict) -> int:
        # Implement logic to extract azimuth from device data
        if device.get('location') and device['location'].get('heading'):
            return int(device['location']['heading'])
        elif device.get('meta').get('note'):
            note_json = json.loads(device['meta']['note'])
            if 'azimuth' in note_json:
                return int(note_json['azimuth'])
        return 0

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