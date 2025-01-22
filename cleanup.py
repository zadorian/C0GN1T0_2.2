from pathlib import Path
import os
import shutil

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
    
    # Now clean the correct cache as before
    if cache_dir.exists():
        print("\nCleaning correct cache location:")
        for file in cache_dir.rglob('*'):
            if file.is_file():
                file.unlink()
                print(f"✓ Deleted file: {file}")
        cache_dir.rmdir()
        print(f"✓ Deleted cache at {cache_dir}")
    
    # 2. Move any index files from indexing/ to indexing/scraping_indexing/
    indexing_path = project_root / 'indexing'
    scraping_index_path = indexing_path / 'scraping_indexing'
    
    # Create scraping_indexing directory if it doesn't exist
    scraping_index_path.mkdir(parents=True, exist_ok=True)
    
    # Move any index files from root indexing to scraping_indexing
    index_extensions = {'.toc', '.seg', '.pst', '.frq', '.prx', '.gen', '.del'}
    for file in indexing_path.glob('*'):
        if file.is_file() and file.suffix in index_extensions:
            # Move file to scraping_indexing directory
            shutil.move(str(file), str(scraping_index_path / file.name))
            print(f"✓ Moved {file.name} to scraping_indexing/")
    
    # Then clean index files from scraping_indexing
    for file in scraping_index_path.glob('*'):
        if file.is_file() and file.suffix in index_extensions:
            file.unlink()
            print(f"✓ Deleted index file: {file.name}")
    
    # Recreate directory structures
    cache_dir.mkdir(parents=True, exist_ok=True)
    print("✓ Recreated directory structure:")
    print(f"  - {cache_dir}")
    print(f"  - {scraping_index_path}")
    
    print("=== Cleanup complete ===\n")

if __name__ == "__main__":
    cleanup() 