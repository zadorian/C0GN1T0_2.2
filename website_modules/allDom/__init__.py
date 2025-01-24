# Use relative import
from .alldom import main

# Export main at package level
__all__ = ["main"]

async def handle_alldom_command(command: str) -> str:
    """Handle alldom command."""
    try:
        parts = command.split()
        if len(parts) < 2:
            return "Please provide a domain for alldom analysis"
            
        domain = parts[1].strip()
        # Your existing alldom analysis code here
        return f"Running complete analysis for {domain}..."
        
    except Exception as e:
        return f"Error in alldom analysis: {str(e)}"
