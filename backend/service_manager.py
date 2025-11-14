"""
Service Manager - Auto-loads and manages services like Wikipedia and MusicBrainz
"""
import asyncio
from typing import Dict, Any

from logging_manager import log_info, log_debug, log_error, log_warning

# Import services
from services import (
    wikipedia_service, 
    musicbrainz_service,
    noaa_weather_service,
    tvmaze_service,
    rest_countries_service,
    open_library_service,
    open_trivia_service
)

class ServiceManager:
    """Manages service initialization and lifecycle"""
    
    def __init__(self):
        self.services = {}
        self.initialization_status = {
            "wikipedia": {"status": "uninitialized", "error": None},
            "musicbrainz": {"status": "uninitialized", "error": None},
            "noaa_weather": {"status": "uninitialized", "error": None},
            "tvmaze": {"status": "uninitialized", "error": None},
            "rest_countries": {"status": "uninitialized", "error": None},
            "open_library": {"status": "uninitialized", "error": None},
            "open_trivia": {"status": "uninitialized", "error": None},
        }
        self.auto_load_complete = False
    
    async def initialize_wikipedia(self):
        """Initialize the Wikipedia service"""
        try:
            log_debug("Initializing Wikipedia service...", category="service")
            # Wikipedia service doesn't need explicit initialization
            # It's ready to use immediately
            self.services["wikipedia"] = wikipedia_service
            self.initialization_status["wikipedia"] = {"status": "ready", "error": None}
            log_info("✅ Wikipedia service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize Wikipedia service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["wikipedia"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_musicbrainz(self):
        """Initialize the MusicBrainz service"""
        try:
            log_debug("Initializing MusicBrainz service...", category="service")
            # MusicBrainz service doesn't need explicit initialization
            # It's ready to use immediately
            self.services["musicbrainz"] = musicbrainz_service
            self.initialization_status["musicbrainz"] = {"status": "ready", "error": None}
            log_info("✅ MusicBrainz service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize MusicBrainz service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["musicbrainz"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_noaa_weather(self):
        """Initialize the NOAA Weather service"""
        try:
            log_debug("Initializing NOAA Weather service...", category="service")
            self.services["noaa_weather"] = noaa_weather_service
            self.initialization_status["noaa_weather"] = {"status": "ready", "error": None}
            log_info("✅ NOAA Weather service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize NOAA Weather service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["noaa_weather"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_tvmaze(self):
        """Initialize the TVmaze service"""
        try:
            log_debug("Initializing TVmaze service...", category="service")
            self.services["tvmaze"] = tvmaze_service
            self.initialization_status["tvmaze"] = {"status": "ready", "error": None}
            log_info("✅ TVmaze service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize TVmaze service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["tvmaze"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_rest_countries(self):
        """Initialize the REST Countries service"""
        try:
            log_debug("Initializing REST Countries service...", category="service")
            self.services["rest_countries"] = rest_countries_service
            self.initialization_status["rest_countries"] = {"status": "ready", "error": None}
            log_info("✅ REST Countries service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize REST Countries service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["rest_countries"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_open_library(self):
        """Initialize the Open Library service"""
        try:
            log_debug("Initializing Open Library service...", category="service")
            self.services["open_library"] = open_library_service
            self.initialization_status["open_library"] = {"status": "ready", "error": None}
            log_info("✅ Open Library service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize Open Library service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["open_library"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_open_trivia(self):
        """Initialize the Open Trivia DB service"""
        try:
            log_debug("Initializing Open Trivia DB service...", category="service")
            self.services["open_trivia"] = open_trivia_service
            self.initialization_status["open_trivia"] = {"status": "ready", "error": None}
            log_info("✅ Open Trivia DB service ready", category="service")
            return True
        except Exception as e:
            error_msg = f"Failed to initialize Open Trivia DB service: {str(e)}"
            log_error(error_msg, category="service")
            self.initialization_status["open_trivia"] = {"status": "failed", "error": str(e)}
            return False
    
    async def initialize_all_services(self):
        """Initialize all services on startup"""
        log_info("Auto-loading services on startup...", category="app")
        
        # Start initialization tasks concurrently
        tasks = [
            self.initialize_wikipedia(),
            self.initialize_musicbrainz(),
            self.initialize_noaa_weather(),
            self.initialize_tvmaze(),
            self.initialize_rest_countries(),
            self.initialize_open_library(),
            self.initialize_open_trivia(),
        ]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for any failures
        failures = sum(1 for r in results if r is False or isinstance(r, Exception))
        
        if failures > 0:
            log_warning(f"Auto-loading services completed with {failures} failures", category="app")
        else:
            log_info("✅ All services loaded successfully", category="app")
        
        self.auto_load_complete = True
        return self.get_status()
    
    def get_status(self):
        """Get current status of all services"""
        return {
            "auto_load_complete": self.auto_load_complete,
            "services": self.initialization_status
        }
    
    def get_service(self, service_name: str):
        """Get a service by name if initialized"""
        return self.services.get(service_name)

# Create singleton instance
service_manager = ServiceManager()

# Auto-load function to be called on startup
async def auto_load_services():
    """Auto-load all services on application startup"""
    await service_manager.initialize_all_services()

