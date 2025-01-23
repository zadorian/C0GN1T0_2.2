import asyncio
import sys

# Import the needed functions/classes from the existing modules
from archived_scraping import handle_command as archived_handle_command, content_controller as archived_content_controller
from current_scraping import content_controller as current_content_controller

async def main():
    print("\nUnified Content Retrieval System")
    print("================================\n")
    
    # Short usage instructions from both modules:
    print("ARCHIVED SCRAPING usage:")
    print(" - Single year:     e.g. 2022! domain.com?")
    print(" - Year range:      e.g. 2020-2023! domain.com?")
    print(" - Backwards:       e.g. 2020<-! domain.com?")
    print("\nCURRENT SCRAPING usage:")
    print(" - Normal URL:      e.g. example.com/page.html")
    print(" - Single page:     e.g. ?example.com/page.html")
    print(" - Full domain:     e.g. example.com?\n")
    
    print("Type 'quit' to exit.\n")

    while True:
        command = input("Enter command: ").strip()
        if command.lower() == "quit":
            break
        
        # If the user includes '!' or '<-!', we treat it as an archived (historic) command.
        # Otherwise, we treat it as a request for current content.
        if "!" in command or "<-!" in command:
            try:
                result = await archived_handle_command(command, archived_content_controller)
                print(f"\n{result}\n")
            except Exception as e:
                print(f"\nError processing archived command: {str(e)}\n")
        else:
            # Handle current scraping requests
            # The command is used as the URL (including possible `?` suffix or prefix).
            try:
                content = await current_content_controller.get_content(command)
                if content:
                    print("\nContent retrieved successfully!")
                    pages = content.get('pages', [])
                    print(f"Pages found: {len(pages)}\n")
                else:
                    print("\nNo content retrieved\n")
            except Exception as e:
                print(f"\nError processing current request: {str(e)}\n")

if __name__ == "__main__":
    asyncio.run(main())