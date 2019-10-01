"""Ambianic pipeline interpreter module."""
import logging
from .avsource.av_element import AVSourceElement
import time
import threading

from ambianic.pipeline.ai.object_detect import ObjectDetector
from ambianic.pipeline.ai.face_detect import FaceDetector
from ambianic.pipeline.store import SaveDetectionSamples
from ambianic.pipeline import PipeElement, HealthChecker
from ambianic.util import ThreadedJob, ManagedService

log = logging.getLogger(__name__)


def get_pipelines(pipelines_config):
    pipelines = []
    if pipelines_config:
        for pname, pdef in pipelines_config.items():
            log.info("loading %s pipeline configuration", pname)
            p = Pipeline(pname=pname, pconfig=pdef)
            pipelines.append(p)
    else:
        log.warning('No pipelines configured.')
    return pipelines


class PipelineServer(ManagedService):
    """Main pipeline interpreter class.

    Responsible for loading, running and overseeing the health
    of all Ambianic pipelines.

    """

    def __init__(self, config=None):
        """Initialize and configure.

        Parameters
        ----------
        config : dict
            Python representation of the yaml configuration file.

        """
        self._config = config
        self._threaded_jobs = []
        self._pipelines = []
        if config:
            pipelines_config = config.get('pipelines', None)
            if pipelines_config:
                self._pipelines = get_pipelines(pipelines_config)
                for pp in self._pipelines:
                    pj = ThreadedJob(pp)
                    self._threaded_jobs.append(pj)

    def healthcheck(self):
        """
            Check the health of all managed pipelines.
            Return the oldest heartbeat among all managed pipeline heartbeats.
            Try to heal pipelines that haven't reported a heartbeat and awhile.

            :returns: (timestamp, status) tuple with most outdated heartbeat
                and worst known status among managed pipelines
        """
        oldest_heartbeat = time.monotonic()
        for j in self._threaded_jobs:
            # get the pipeline object out of the threaded job wrapper
            p = j.job
            if j.is_alive():
                latest_heartbeat, status = p.healthcheck()
                now = time.monotonic()
                lapse = now - latest_heartbeat
                if lapse > 60:
                    log.error('Pipeline %s in terminal condition. '
                              'Unable to recover.'
                              'Latest heartbeat was %f seconds ago. ',
                              p.name, lapse)
                    # more than a reasonable amount of time has passed
                    # since the pipeline reported a heartbeat.
                    # Let's recycle it
                elif lapse > 20:
                    log.warning('Pipeline "%s" is not responsive. '
                                'Latest heartbeat was %f seconds ago. '
                                'Will attempt to heal it.', p.name, lapse)
                    self.heal_pipeline_job(j)
                if oldest_heartbeat > latest_heartbeat:
                    oldest_heartbeat = latest_heartbeat
            # something went wrong with a threaded job
            else:
                log.error('Pipeline "%s" thread ended unexpectedly. '
                          'Please report a bug.', p.name)
        status = True  # At some point status may carry richer information
        return oldest_heartbeat, status

    def heal():
        """Heal the PipelineServer.

        PipelineServer manages its own health as best possible.
        Not much to do here at this time.
        """

    def heal_pipeline_job(self, threaded_job=None):
        assert threaded_job
        pipeline = threaded_job.job
        log.debug('pipline %s healing request...', pipeline.name)
        threaded_job.heal()
        log.debug('pipeline %s healing request completed.', pipeline.name)

    def start(self):
        # Start pipeline interpreter threads
        log.info('pipeline jobs starting...')
        for tj in self._threaded_jobs:
            tj.start()
        log.info('pipeline jobs started')

    def stop(self):
        log.info('pipeline jobs stopping...')
        # Signal pipeline interpreter threads to close
        for tj in self._threaded_jobs:
            tj.stop()
        # Wait for the pipeline interpreter threads to close...
        for tj in self._threaded_jobs:
            tj.join()
        log.info('pipeline jobs stopped.')


class HealingThread(threading.Thread):
    """ A thread focused on healing a broken pipeline. """

    def __init__(self, target=None, on_finished=None):
        assert target, 'Healing target required'
        assert on_finished, 'on_finished callback required'
        threading.Thread.__init__(self, daemon=True)
        self._target = target
        self._on_finished = on_finished

    def run(self):
        self._target()
        self._on_finished()


class Pipeline(ManagedService):
    """ The main Ambianic processing structure.

    Data flow is arranged in independent pipelines.
    """

    # valid pipeline operators
    PIPELINE_OPS = {
        'source': AVSourceElement,
        'detect_objects': ObjectDetector,
        'save_detections': SaveDetectionSamples,
        'detect_faces': FaceDetector,
    }

    def __init__(self, pname=None, pconfig=None):
        """Init and load pipeline config."""
        assert pname, "Pipeline name required"
        self.name = pname
        assert pconfig, "Pipeline config required"
        self.config = pconfig
        assert self.config[0]["source"], \
            "Pipeline config must begin with a source element"
        self.pipe_elements = []
        self._latest_heartbeat_time = time.monotonic()
        # in the future status may represent a spectrum of health issues
        self._latest_health_status = True
        self._healing_thread = None
        for element_def in self.config:
            log.info('Pipeline %s loading next element: %s',
                     pname, element_def)
            element_name = [*element_def][0]
            element_config = element_def[element_name]
            element_class = self.PIPELINE_OPS.get(element_name, None)
            if element_class:
                log.info('Pipeline %s adding element %s with config %s',
                         pname, element_name, element_config)
                element = element_class(element_config)
                self.pipe_elements.append(element)
            else:
                log.warning('Pipeline definition has unknown '
                            'pipeline element: %s .'
                            ' Ignoring element and moving forward.',
                            element_name)
        return

    def _heartbeat(self):
        """Set the heartbeat timestamp to time.monotonic()."""
        log.debug('Pipeline %s heartbeat signal.', self.name)
        now = time.monotonic()
        lapse = now - self._latest_heartbeat_time
        log.debug('Pipeline %s heartbeat lapse %f', self.name, lapse)
        self._latest_heartbeat_time = now

    def start(self):
        """Start the pipeline loop.

        Run until the pipeline has input from its configured source
        or until a stop() signal is received.
        """
        log.info("Starting %s main pipeline loop", self.__class__.__name__)
        if not self.pipe_elements:
            return
        self._heartbeat()
        # connect pipeline elements as defined by user
        for i in range(1, len(self.pipe_elements)):
            e = self.pipe_elements[i-1]
            assert isinstance(e, PipeElement)
            e_next = self.pipe_elements[i]
            e.connect_to_next_element(e_next)
        last_element = self.pipe_elements[len(self.pipe_elements)-1]
        hc = HealthChecker(health_status_callback=self._heartbeat)
        last_element.connect_to_next_element(hc)
        self.pipe_elements[0].start()
        log.info("Stopped %s", self.__class__.__name__)
        return

    def healthcheck(self):
        """Return health vitals status report.

        :Returns:
        -------
        (timestamp, status)
            a tuple of
                monotonically increasing timestamp of the last known healthy
                heartbeat and a status with additional health information.

        """
        return self._latest_heartbeat_time, self._latest_health_status

    def heal(self):
        """Nonblocking asynchronous heal function."""
        # register a heartbeat to prevent looping back
        # into heal while healing
        self._heartbeat()
        if self._healing_thread:
            log.debug('pipeline %s healing thread in progress.'
                      ' Skipping request. '
                      'Thread id: %d. ',
                      self.name, self._healing_thread.ident)
        else:
            log.debug('pipeline %s launching healing thread...', self.name)
            heal_target = self.pipe_elements[0].heal

            def healing_finished():
                log.debug('pipeline %s healing thread id: %d ended. ',
                          self.name,
                          self._healing_thread.ident)
                self._healing_thread = None
                # let's notify healthchecker that progress is being made
                self._heartbeat()

            # launch healing function in a non-blocking way
            self._healing_thread = HealingThread(target=heal_target,
                                                 on_finished=healing_finished)
            self._healing_thread.start()
            log.debug('pipeline %s launched healing thread.',
                      self.name)

    def stop(self):
        """Stop pipeline processing.

        Disconnect from the source and all other external resources.
        """
        log.info("Requesting pipeline elements to stop... %s",
                 self.__class__.__name__)
        self.pipe_elements[0].stop()
        log.info("Completed request to pipeline elements to stop. %s",
                 self.__class__.__name__)
