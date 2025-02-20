from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
import undetected_chromedriver as uc
import logging
import sys
import os
import tkinter as tk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BrowserManager:
    _instance = None
    
    @classmethod
    def initialize(cls):
        """Initialize the BrowserManager"""
        return cls.get_instance()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if BrowserManager._instance is not None:
            raise Exception("BrowserManager is a singleton! Use get_instance() instead.")
            
        self.driver = None
        try:
            chrome_options = self._configure_chrome_options()
            self._initialize_driver(chrome_options)
        except Exception as e:
            logger.error(f"Failed to initialize Chrome driver: {str(e)}")
            raise
            
        BrowserManager._instance = self
    
    @classmethod
    def _get_screen_size(cls):
        """Get the primary screen size using tkinter."""
        root = tk.Tk()
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root.destroy()
        return screen_width, screen_height
    
    def _configure_chrome_options(self):
        # Use undetected-chromedriver's Chrome options
        chrome_options = uc.ChromeOptions()
        
        # Get screen dimensions and calculate browser window size
        screen_width, screen_height = self._get_screen_size()
        window_width = screen_width // 2  # Use half of screen width
        window_height = screen_height  # Use full screen height
        
        logger.info(f"Screen size: {screen_width}x{screen_height}, Setting browser size to: {window_width}x{window_height}")
        
        # Set window size and position
        chrome_options.add_argument('--window-position=0,0')
        chrome_options.add_argument(f'--window-size={window_width},{window_height}')
        
        # Additional stability options
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        
        return chrome_options
    
    def _initialize_driver(self, chrome_options):
        try:
            logger.info("Initializing undetected Chrome driver...")
            
            # Let undetected-chromedriver handle driver management
            self.driver = uc.Chrome(
                options=chrome_options,
                headless=False,  # Headless mode is not recommended for undetected-chromedriver
                use_subprocess=True
            )
            
            # Test the driver
            self.driver.get("about:blank")
            logger.info("Undetected Chrome driver initialized successfully")
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            self.cleanup()
            raise
    
    def get_driver(self):
        if not self.driver:
            raise Exception("Chrome driver not initialized")
        return self.driver
    
    def cleanup(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                logger.info("Cleaning up Chrome driver...")
                self.driver.quit()
                logger.info("Chrome driver cleaned up successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")
            finally:
                self.driver = None
                BrowserManager._instance = None 