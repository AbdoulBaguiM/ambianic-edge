import logging
from .gstreamer import InputStreamProcessor
import time

from ambianic.pipeline.ai.object_detect import ObjectDetect
from ambianic.pipeline.ai.face_detect import FaceDetect
from .store import SaveSamples
from . import PipeElement, HealthChecker
from ambianic.service import ThreadedJob

log = logging.getLogger(__name__)


def get_pipelines(pipelines_config):
    assert pipelines_config
    pipelines = []
    for pname, pdef in pipelines_config.items():
        log.info("loading %s pipeline configuration", pname)
        p = Pipeline(pname=pname, pconfig=pdef)
        pipelines.append(p)
    return pipelines


class PipelineServer:

    def __init__(self, config=None):
        assert config
        self._config = config
        pipelines_config = config['pipelines']
        self._pipelines = get_pipelines(pipelines_config)
        self._jobs = []
        for pp in self._pipelines:
            pj = ThreadedJob(pp)
            self._jobs.append(pj)

    def healthcheck(self):
        """
            Check the health of all managed pipelines.
            Return the oldest heartbeat among all managed pipeline heartbeats.
            Try to heal pipelines that haven't reported a heartbeat and awhile.

            :returns: (timestamp, status) tuple with most outdated heartbeat and worst known status
                among managed pipelines
        """
        oldest_heartbeat = time.monotonic()
        for p in self._pipelines:
            latest_heartbeat, status = p.healthcheck()
            now = time.monotonic()
            if now - latest_heartbeat > 4:
                # more than a reasonable amount of time has passed
                # since the pipeline reported a heartbeat.
                # Let's recycle it
                p.stop()
                p.start()
            if oldest_heartbeat > latest_heartbeat:
                oldest_heartbeat = latest_heartbeat
        status = True  # At some point status may carry richer information
        return oldest_heartbeat, status

    def start(self):
        # Start pipeline interpreter threads
        log.info('pipeline jobs starting...')
        for j in self._jobs:
            j.start()
        log.info('pipeline jobs started')

    def stop(self):
        log.info('pipeline jobs stopping...')
        # Signal pipeline interpreter threads to close
        for j in self._jobs:
            j.stop()
        # Wait for the pipeline interpreter threads to close...
        for j in self._jobs:
            j.join()
        log.info('pipeline jobs stopped.')


class Pipeline:
    """ The main Ambianic processing structure. Data flow is arranged in independent pipelines. """

    # valid pipeline operators
    PIPELINE_OPS = {
        'source': InputStreamProcessor,
        'detect_objects': ObjectDetect,
        'save_samples': SaveSamples,
        'detect_faces': FaceDetect,
    }

    def __init__(self, pname=None, pconfig=None):
        """ Load pipeline config """
        assert pname, "Pipeline name required"
        self.name = pname
        assert pconfig, "Pipeline config required"
        self.config = pconfig
        assert self.config[0]["source"], "Pipeline config must begin with a source element"
        self.pipe_elements = []
        self.state = False
        self._latest_heartbeat_time = time.monotonic()
        self._latest_health_status = True  # in the future status may represent a spectrum of health issues
        for element_def in self.config:
            log.info('Pipeline %s loading next element: %s', pname, element_def)
            element_name = [*element_def][0]
            element_config = element_def[element_name]
            element_class = self.PIPELINE_OPS.get(element_name, None)
            if element_class:
                log.info('Pipeline %s adding element %s with config %s', pname, element_name, element_config)
                element = element_class(element_config)
                self.pipe_elements.append(element)
            else:
                log.warning('Pipeline definition has unknown pipeline element: %s .'
                            ' Ignoring element and moving forward.', element_name)
        return

    def _heartbeat(self):
        """
            Sets the heartbeat timestamp to time.monotonic()
        """
        log.debug('Pipeline %s heartbeat', self.name)
        self._latest_heartbeat_time = time.monotonic()

    def start(self):
        """
            Starts a thread that iteratively and in order of definitions feeds
            each element the output of the previous one. Stops the pipeline when a stop signal is received.
        """

        log.info("Starting %s main pipeline loop", self.__class__.__name__)

        if not self.pipe_elements:
            return

        # connect pipeline elements as defined by user
        for i in range(1, len(self.pipe_elements)):
            e = self.pipe_elements[i-1]
            assert isinstance(e, PipeElement)
            e_next = self.pipe_elements[i]
            assert isinstance(e_next, PipeElement)
            e.connect_to_next_element(e_next)

        last_element = self.pipe_elements[len(self.pipe_elements)-1]
        hc = HealthChecker(health_status_callback=self._heartbeat)
        last_element.connect_to_next_element(hc)
        self.pipe_elements[0].start()

        log.info("Stopped %s", self.__class__.__name__)
        return

    def healthcheck(self):
        """
        :return: (timestamp, status) - a tuple of
            monotonically increasing timestamp of the last known healthy heartbeat
            and a status with additional health information
        """
        return self._latest_heartbeat_time, self._latest_health_status

    def stop(self):
        log.info("Stopping %s", self.__class__.__name__)
        self.pipe_elements[0].stop()
        return
