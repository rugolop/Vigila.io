"""
Vigila.io Local Agent - Configuration
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Agent configuration loaded from environment variables."""
    
    # Required
    token: str
    server_url: str
    agent_name: str
    
    # Optional
    local_port: int = 8554
    heartbeat_interval: int = 30
    network_range: str = None
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        token = os.getenv("VIGILA_TOKEN")
        server_url = os.getenv("VIGILA_SERVER_URL")
        agent_name = os.getenv("AGENT_NAME")
        
        if not token:
            raise ValueError("VIGILA_TOKEN is required. Get it from your Vigila.io dashboard.")
        if not server_url:
            raise ValueError("VIGILA_SERVER_URL is required.")
        if not agent_name:
            raise ValueError("AGENT_NAME is required.")
        
        return cls(
            token=token,
            server_url=server_url.rstrip("/"),
            agent_name=agent_name,
            local_port=int(os.getenv("LOCAL_PORT", "8554")),
            heartbeat_interval=int(os.getenv("HEARTBEAT_INTERVAL", "30")),
            network_range=os.getenv("NETWORK_RANGE"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
