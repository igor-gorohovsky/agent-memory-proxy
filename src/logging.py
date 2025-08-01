import log

log.basicConfig(
    level=log.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = log.getLogger("agent-memory-proxy")
