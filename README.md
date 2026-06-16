# PyCrack (WiFi Auditing Tool)

> Educational WiFi auditing project that attempts to connect to a selected WiFi network using passwords loaded from a wordlist.

## Features
- Scan nearby WiFi networks and list unique SSIDs
- Load a text wordlist (`.txt`) containing candidate passwords
- Attempt to connect to the selected SSID using each password
- Simple GUI with logging and start/stop controls

## Disclaimer
Use only with explicit authorization (e.g., your own networks or networks you have permission to test). Unauthorized access to computer systems is illegal and unethical.

## Requirements
- Python 3.x
- A WiFi adapter supported by your OS and by the `pywifi` library
- Dependencies listed below

## Install
From the project root:

```bash
pip install customtkinter pywifi
```

If you prefer, you can install other GUI dependencies as needed by your Python environment.

## Run
```bash
python main.py
```

## How to use
1. Click **Scan Networks** to discover nearby SSIDs.
2. Select a network from the list.
3. Click **Load Wordlist** and choose a `.txt` file with one password per line.
4. Click **Start Attack**.
5. Stop anytime using **Stop Attack**.

## Notes / Limitations
- This project tries WPA2-PSK using `pywifi` profiles.
- Connection success detection is time-based (it checks for a connected status within a short timeout per password).
- Results and behavior vary depending on adapter/OS support and WiFi environment.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.