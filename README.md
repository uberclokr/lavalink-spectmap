ubiquiti_spectrum_mapper/
│
├── config/
│   ├── config.yaml       # API credentials, map settings
│   └── styles.yaml      # Color schemes for frequencies
│
├── data/
│   ├── cache/           # Cached API responses
│   └── exports/         # Generated maps
│
├── src/
│   ├── api/
│   │   └── unms_client.py  # UNMS/UISP API wrapper
│   ├── models/
│   │   └── antenna.py      # Antenna data model
│   ├── visualization/
│   │   ├── map_renderer.py # Map drawing logic
│   │   └── cone_calculator.py # Coverage area calculations
│   └── utils.py         # Helper functions
├── main.py             # CLI interface
├── app.py              # Web interface
├── requirements.txt
└── README.md