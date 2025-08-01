import sys
import time

from log import logger

from watchdog.observers import Observer
from watcher import MemoryProxyWatcher


def main() -> None:
    watcher = MemoryProxyWatcher(Observer())

    try:
        if not watcher.start():
            logger.error("Failed to start watcher")
            sys.exit(1)

        logger.info("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        watcher.stop()


if __name__ == "__main__":
    main()
