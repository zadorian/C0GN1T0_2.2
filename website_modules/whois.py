import requests
import json
import datetime
from config import config

async def handle_whois_command(command: str) -> str:
    """Handle WHOIS command."""
    try:
        parts = command.split()
        if len(parts) < 2:
            return "Please provide a domain for WHOIS lookup"
            
        domain = parts[1].strip()
        # Your existing WHOIS lookup code here
        return f"Looking up WHOIS for {domain}..."
        
    except Exception as e:
        return f"Error in WHOIS lookup: {str(e)}"

if __name__ == "__main__":
    domain_name = input("Enter the domain name to search for: ")
    result = handle_whois_command(domain_name)
    print(result)
