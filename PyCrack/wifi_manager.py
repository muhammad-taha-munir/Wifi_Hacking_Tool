import time
import pywifi
from pywifi import const

class WifiManager:
    def __init__(self, logger):
        self.wifi = pywifi.PyWiFi()
        self.iface = self.wifi.interfaces()[0]  # Use the first wireless interface
        self.logger = logger

    def scan_networks(self):
        """Scans for available WiFi networks."""
        self.logger.info("Scanning for networks...")
        self.iface.scan()
        time.sleep(2)  # Wait for scan to complete
        results = self.iface.scan_results()
        
        networks = []
        seen_ssids = set()
        
        for network in results:
            ssid = network.ssid
            if ssid and ssid not in seen_ssids:
                networks.append(network)
                seen_ssids.add(ssid)
        
        self.logger.info(f"Found {len(networks)} networks.")
        return networks

    def connect_to_network(self, ssid, password):
        """Attempts to connect to a network with a specific password."""
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key = password

        self.iface.remove_all_network_profiles()
        tmp_profile = self.iface.add_network_profile(profile)

        self.iface.connect(tmp_profile)
        
        # Wait for connection
        start_time = time.time()
        while time.time() - start_time < 5: # 5 seconds timeout per password
            if self.iface.status() == const.IFACE_CONNECTED:
                self.logger.info(f"SUCCESS! Password for {ssid} is: {password}")
                return True
            time.sleep(0.5)
        
        self.iface.disconnect()
        return False
