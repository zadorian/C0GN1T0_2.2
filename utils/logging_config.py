import logging
import sys
from pathlib import Path

# Create module-level loggers
debug_logger = logging.getLogger('debug')
content_logger = logging.getLogger('content')
api_logger = logging.getLogger('api')
progress_logger = logging.getLogger('progress')

def configure_logging(log_file: Path = None):
    """Configure all loggers with consistent settings"""
    
    # Configure all our custom loggers
    for logger in [debug_logger, content_logger, api_logger, progress_logger]:
        logger.propagate = False
        logger.handlers = []
        
        # Console handler for minimal output
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(console)
        
        # Add file handler if specified
        if log_file:
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            logger.addHandler(file_handler)
        
        # Set default levels
        logger.setLevel(logging.WARNING)
    
    # Configure specific logger levels
    debug_logger.setLevel(logging.DEBUG)
    progress_logger.setLevel(logging.INFO)
    
    # Silence all other loggers
    logging.basicConfig(
        level=logging.WARNING,
        format='%(message)s',
        handlers=[logging.NullHandler()]
    )
    
    # Explicitly silence ALL other loggers
    for name in logging.root.manager.loggerDict:
        if name not in ['debug', 'content', 'api', 'progress']:
            other_logger = logging.getLogger(name)
            other_logger.setLevel(logging.WARNING)
            other_logger.propagate = False
            other_logger.handlers = [logging.NullHandler()] 