from dataclasses import dataclass
from typing import Optional, Tuple, List
import math

@dataclass
class Antenna:
    """Data model representing a Ubiquiti antenna device"""
    id: str
    name: str
    model: str
    antenna: str
    latitude: float
    longitude: float
    azimuth: float          # Degrees (0-360)
    downtilt: float         # Degrees (typically 0-15)
    frequency: float        # MHz (e.g., 2400, 5500)
    channel_width: float    # MHz (e.g., 20, 40, 80)
    height: float           # Meters above ground
    tx_power: Optional[float] = None  # dBm
    gain: Optional[float] = None      # dBi
    beamwidth_h: Optional[float] = None  # Horizontal beamwidth in degrees
    beamwidth_v: Optional[float] = None  # Vertical beamwidth in degrees
    
    @property
    def coordinates(self) -> Tuple[float, float]:
        """Return (latitude, longitude) tuple"""
        return (self.latitude, self.longitude)
    
    @property
    def frequency_band(self) -> Tuple[int, int]:
        """Return the general frequency band"""
        if self.frequency < 3000: # 2.4GHz band 
            return [2400, 2495]
        elif 5150 <= self.frequency < 5250: # U-NII-1
            return [5150, 5250]
        elif 5250 <= self.frequency < 5350: # U-NII-2A
            return [5250, 5350]
        elif 5350 <= self.frequency < 5470: # U-NII-2B
            return [5350, 5470]
        elif 5470 <= self.frequency < 5725: # U-NII-2C
            return [5470, 5725]
        elif 5725 <= self.frequency < 5850: # U-NII-3
            return [5725, 5850]
        elif 5850 <= self.frequency < 5925: # U-NII-4
            return [5850, 5925]
        elif 5925 <= self.frequency < 7125: # U-NII-5 through U-NII-8
            return [5925, 7125]
        elif 58000 <= self.frequency < 70000: # 60GHz band
            return [58000, 70000]
        return None
    
    @property
    def frequency_band_name(self) -> Tuple[int, int]:
        """Return the general frequency band"""
        if self.frequency < 3000: # ISM 2.4GHz band 
            return "ISM"
        elif 5150 <= self.frequency < 5250: # U-NII-1
            return "U-NII-1"
        elif 5250 <= self.frequency < 5350: # U-NII-2A
            return "U-NII-2A"
        elif 5350 <= self.frequency < 5470: # U-NII-2B
            return "U-NII-2B"
        elif 5470 <= self.frequency < 5725: # U-NII-2C
            return "U-NII-2C"
        elif 5725 <= self.frequency < 5850: # U-NII-3
            return "U-NII-3"
        elif 5850 <= self.frequency < 5925: # U-NII-4
            return "U-NII-4"
        elif 5925 <= self.frequency < 7125: # U-NII-5 through U-NII-8
            return "U-NII-5...8"
        elif 58000 <= self.frequency < 70000: # 60GHz band
            return "Vband"
        return None

    @property
    def channel_60(self) -> str:
        """Return operating 60Ghz channel identifier"""
        if self.frequency == 58320:
            return 1
        elif self.frequency == 60480:
            return 2
        elif self.frequency == 62640:
            return 3
        elif self.frequency == 64800:
            return 4
        elif self.frequency == 66960:
            return 5
        elif self.frequency == 69120:
            return 6
        else:
            return None
        
    @property
    def channel_5(self) -> str:
        """Return operating 5Ghz channel identifier"""
        if self.channel_width == 20:
            if self.frequency == 5180:
                return 36
            elif self.frequency == 5200:
                return 40
            elif self.frequency == 5220:
                return 44
            elif self.frequency == 5240:
                return 48
            elif self.frequency == 5260:
                return 52
            elif self.frequency == 5280:
                return 56
            elif self.frequency == 5300:    
                return 60
            elif self.frequency == 5320:
                return 64
            elif self.frequency == 5500:
                return 100
            elif self.frequency == 5520:
                return 104
            elif self.frequency == 5540:
                return 108
            elif self.frequency == 5560:
                return 112
            elif self.frequency == 5580:
                return 116
            elif self.frequency == 5600:
                return 120
            elif self.frequency == 5620:
                return 124
            elif self.frequency == 5640:
                return 128
            elif self.frequency == 5660:
                return 132
            elif self.frequency == 5680:
                return 136
            elif self.frequency == 5700:
                return 140
            elif self.frequency == 5720:
                return 144
            elif self.frequency == 5745:
                return 149
            elif self.frequency == 5765:
                return 153
            elif self.frequency == 5785:
                return 157
            elif self.frequency == 5805:    
                return 161
            elif self.frequency == 5825:
                return 165
            elif self.frequency == 5845:
                return 169
        elif self.channel_width == 40:
            if self.frequency == 5190:
                return 38
            elif self.frequency == 5230:
                return 46
            elif self.frequency == 5270:
                return 54
            elif self.frequency == 5310:    
                return 62
            elif self.frequency == 5350:
                return 70
            elif self.frequency == 5390:
                return 78
            elif self.frequency == 5430:
                return 86
            elif self.frequency == 5470:
                return 94
            elif self.frequency == 5510:    
                return 102
            elif self.frequency == 5550:
                return 110
            elif self.frequency == 5590:
                return 118
            elif self.frequency == 5630:
                return 126
            elif self.frequency == 5670:
                return 134
            elif self.frequency == 5710:
                return 142
            elif self.frequency == 5755:
                return 151
            elif self.frequency == 5795:
                return 159
            elif self.frequency == 5835:
                return 167
            elif self.frequency == 5875:
                return 175
        elif self.channel_width == 80:
            if self.frequency == 5210:
                return 42
            elif self.frequency == 5290:
                return 58
            elif self.frequency == 5370:
                return 74
            elif self.frequency == 5450:
                return 90
            elif self.frequency == 5530:
                return 106
            elif self.frequency == 5610:
                return 122
            elif self.frequency == 5690:
                return 138
            elif self.frequency == 5775:
                return 155
            elif self.frequency == 5855:
                return 171
        elif self.channel_width == 160:
            if self.frequency == 5530:
                return 106
            elif self.frequency == 5610:
                return 122
            elif self.frequency == 5690:
                return 138
            elif self.frequency == 5775:
                return 155
            elif self.frequency == 5855:
                return 171    
        
 
        return None   

    @property
    def beamwidth_horizontal(self) -> float:
        """Return horizontal beamwidth with fallback to model defaults"""
        return self.beamwidth_h or self._model_beamwidth()[0]
    
    @property
    def beamwidth_vertical(self) -> float:
        """Return vertical beamwidth with fallback to model defaults"""
        return self.beamwidth_v or self._model_beamwidth()[1]
    
    def _model_beamwidth(self) -> Tuple[float, float]:
        """Return default beamwidths (H, V) for common Ubiquiti models"""
        model_lower = self.model.lower()
        antenna_lower = self.antenna.lower()

        if "r5ac" in model_lower: # If RocketAC radio
            if "amo-5g10" in antenna_lower:
                return (360.0, 12.0) # AMO 5G10 antenna
        
        if "lap-gps" in model_lower:
            return (90,20)

        if "airmax" in model_lower:
            if "ac" in model_lower:
                return (90.0, 7.0)  # Typical for AirMax AC sector antennas
            return (60.0, 12.0)     # Older AirMax models
        
        if "litemax" in model_lower:
            return (120.0, 10.0)
            
        if "powerbeam" in model_lower:
            return (30.0, 30.0)     # Typical for point-to-point
        
        if "wave-ap" in model_lower:
            if "micro" in model_lower:
                return (90.0, 30.0)
            return (30.0, 3.0)  # Wave AP sector antennas
        
        if "wave-pro" in model_lower:
            return (1.3, 1.3) # Wave Pro antennas
        
        if "af60" in model_lower:
            return (1.6, 1.6) # AirFiber 60GHz

        return (60.0, 15.0)         # Default fallback
    
    def _model_range_m(self) -> float:
        """Return effective range for common Ubiquiti models"""
        model_lower = self.model.lower()
        antenna_lower = self.antenna.lower()

        if "r5ac" in model_lower or "rp-5ac": # If RocketAC radio
            if "amo-5g10" in antenna_lower:
                return 750.0
            return 3000.0
        
        if "ps-5ac" in model_lower:
            if "horn" in antenna_lower:
                return 3000.0
            return 3000.0
        
        if "lap-gps" in model_lower:
            return 2000.0
            
        if "wave-ap" in model_lower:
            if "micro" in model_lower:
                return 6000.0 # Realistic
            return 8000.0
        
        if "wave-pro" in model_lower:
            return 15000.0 # Wave Pro antennas
        
        if "wave-lr" in model_lower:
            return 12000.0 # Wave LR antennas

        if "af60" in model_lower:
            return 12000.0 # AirFiber 60GHz
        
        return 5000.0  # Default fallback

    @property
    def coverage_radius(self) -> float:
        """Estimate coverage radius based on height and downtilt (in meters)"""
        if self.downtilt <= 0:
            return 1000  # Safety default
            
        # Simple trigonometry: radius = height / tan(downtilt)
        # Convert degrees to radians for math.tan
        return self.height / math.tan(math.radians(self.downtilt))
    
    def to_feature_dict(self) -> dict:
        """Convert to GeoJSON feature dictionary"""
        return {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [self.longitude, self.latitude]
            },
            "properties": {
                "name": self.name,
                "model": self.model,
                "azimuth": self.azimuth,
                "frequency": self.frequency,
                "channel_width": self.channel_width
            }
        }
    
    @classmethod
    def from_unms_data(cls, device_data: dict) -> 'Antenna':
        """Factory method to create from UNMS API response"""
        radio = device_data.get('radio', {})
        identification = device_data.get('identification', {})
        site = identification.get('site', {})
        
        return cls(
            id=device_data.get('id'),
            name=identification.get('name', 'Unknown'),
            model=device_data.get('model', 'Unknown'),
            latitude=site.get('latitude', 0),
            longitude=site.get('longitude', 0),
            azimuth=radio.get('azimuth', 0),
            downtilt=radio.get('downtilt', 5),
            frequency=radio.get('frequency', 0),
            channel_width=radio.get('channel_width', 20),
            height=radio.get('height', 30),
            tx_power=radio.get('tx_power'),
            gain=radio.get('gain')
        )