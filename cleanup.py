from pathlib import Path
import os
import shutil
import json

def cleanup():
    print("\n=== Starting cleanup ===")
    
    project_root = Path(__file__).parent
    
    # 1. Clean both cache locations
    cache_dir = project_root / 'cache'  # The correct one
    wrong_cache_dir = project_root / 'scraping' / 'website_searcher' / 'Content' / 'Cache'  # The wrong one
    
    print(f"Looking for cache directories:")
    print(f"- Correct cache: {cache_dir}")
    print(f"- Wrong cache: {wrong_cache_dir}")
    
    # Clean the wrong cache location first
    if wrong_cache_dir.exists():
        print("\nCleaning wrong cache location:")
        # Move any files to correct location first
        cache_dir.mkdir(parents=True, exist_ok=True)
        for file in wrong_cache_dir.rglob('*.json'):
            try:
                shutil.move(str(file), str(cache_dir / file.name))
                print(f"✓ Moved {file.name} to correct cache location")
            except Exception as e:
                print(f"Error moving file: {e}")
        
        # Then delete the wrong directory structure
        for file in wrong_cache_dir.rglob('*'):
            if file.is_file():
                file.unlink()
        for dir in reversed(list(wrong_cache_dir.parent.rglob('*'))):
            if dir.is_dir():
                dir.rmdir()
        print(f"✓ Removed wrong cache directory structure")
    
    # Now clean the correct cache
    if cache_dir.exists():
        print("\nCleaning correct cache location:")
        for file in cache_dir.rglob('*'):
            if file.is_file():
                try:
                    file.unlink()
                    print(f"✓ Deleted file: {file}")
                except Exception as e:
                    print(f"Error deleting file {file}: {e}")
    
    # 2. Clean and reset tag indexing
    tag_indexing_path = project_root / 'indexing' / 'tag_indexing'
    index_path = tag_indexing_path / 'index'  # This is where the index should be
    memory_path = tag_indexing_path / 'memory'
    
    print("\nCleaning tag indexing data:")
    
    # Clean only the index directory
    if index_path.exists():
        for file in index_path.glob('*'):
            try:
                file.unlink()
                print(f"✓ Deleted index file: {file.name}")
            except Exception as e:
                print(f"Error deleting index file {file}: {e}")
    
    # Ensure the directory exists
    index_path.mkdir(parents=True, exist_ok=True)
    
    # Clean only the memory directory contents
    if memory_path.exists():
        for file in memory_path.glob('*'):
            if file.is_file() and file.suffix == '.json':
                try:
                    file.unlink()
                    print(f"✓ Deleted memory file: {file.name}")
                except Exception as e:
                    print(f"Error deleting memory file {file}: {e}")
    
    # Recreate directories and initialize memory file
    index_path.mkdir(parents=True, exist_ok=True)
    memory_path.mkdir(parents=True, exist_ok=True)
    
    # Initialize empty tag memory file
    tag_memory_file = memory_path / 'tag_memory.json'
    tag_memory_file.write_text('[]')
    print(f"✓ Reset tag memory file")
    
    # 3. Reset tags.json
    tags_file = project_root / 'tags' / 'tags.json'
    print("\nResetting tags.json:")
    try:
        tags_file.parent.mkdir(parents=True, exist_ok=True)
        tags_file.write_text('[]')
        print(f"✓ Reset tags.json to empty array")
    except Exception as e:
        print(f"Error resetting tags.json: {e}")
    
    # 4. Clean scraping indexing
    scraping_index_path = project_root / 'indexing' / 'scraping_indexing'
    print("\nCleaning scraping indexing directory:")
    
    # Create scraping_indexing directory if it doesn't exist
    scraping_index_path.mkdir(parents=True, exist_ok=True)
    
    # Clean index files from scraping_indexing
    index_extensions = {'.toc', '.seg', '.pst', '.frq', '.prx', '.gen', '.del'}
    for file in scraping_index_path.glob('*'):
        if file.is_file() and file.suffix in index_extensions:
            file.unlink()
            print(f"✓ Deleted index file: {file.name}")
    
    # Verify final directory structure
    print("\n✓ Final directory structure verified:")
    print(f"  - {cache_dir}")
    print(f"  - {tag_indexing_path}")
    print(f"    ├─ index/")
    print(f"    └─ memory/tag_memory.json")
    print(f"  - {scraping_index_path}")
    print(f"  - {tags_file}")
    
    print("=== Cleanup complete ===\n")

if __name__ == "__main__":
    cleanup() 