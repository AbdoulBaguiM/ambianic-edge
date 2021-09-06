
from fastapi import HTTPException, status
from ambianic import config
from pydantic import BaseModel

import logging

log = logging.getLogger(__name__)

# Base class for pipeline input sources such as cameras and microphones
class SensorSource(BaseModel):
    id: str
    uri: str
    type: str
    live: bool = True

source_types = ["video", "audio", "image"]

def get(source_id):
    """Retrieve a source by id"""
    log.info("Get source_id=%s", source_id)
    source = config.sources[source_id]
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="source id not found")
    return source


def remove(source_id):
    """Remove source by id"""
    log.info("Removing source_id=%s", source_id)
    get(source_id)
    del config.sources[source_id]


def save(source_id, source: SensorSource):
    """Save source configuration information"""
    log.info("Saving source_id=%s", source_id)
    config.sources[source["id"]] = source
    return config.sources[source["id"]]
