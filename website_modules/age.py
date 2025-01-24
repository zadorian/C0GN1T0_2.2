async def handle_age_command(command: str) -> str:
    """Handle age command."""
    try:
        parts = command.split()
        if len(parts) < 2:
            return "Please provide a domain for age analysis"
            
        domain = parts[1].strip()
        # Your existing age analysis code here
        return f"Analyzing age for {domain}..."
        
    except Exception as e:
        return f"Error in age analysis: {str(e)}" 