import logging
import datetime
import os
import pathlib
import json

from . import PipeElement

log = logging.getLogger(__name__)


class SaveSamples(PipeElement):
    """ Saves samples to an external storage location """

    def __init__(self, element_config=None):
        log.info('Loading pipe element: %s with config %s', self.__class__.__name__, element_config)
        PipeElement.__init__(self)
        self.config = element_config
        self.output_directory = self.config.get('output_directory', None)
        assert self.output_directory, 'Pipe element %s: requires argument output_directory:' % self.__class__.__name__
        self.output_directory = pathlib.Path(self.output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)
        os.makedirs(self.output_directory, exist_ok=True)  # succeeds even if directory exists.
        # by default save samples with detections every 2 seconds
        di = float(self.config.get('detections_interval', 2))
        self.detections_interval = datetime.timedelta(seconds=di)
        # set the clock to sufficiently outdated timestamp to ensure that we won't miss saving the very first sample
        self.time_latest_saved_detection = datetime.datetime.now() - datetime.timedelta(days=1)
        # by default save samples without any detections every ten minutes
        ii = float(self.config.get('idle_interval', 600))
        self.idle_interval = datetime.timedelta(seconds=ii)
        self.time_latest_saved_idle = self.time_latest_saved_detection

    def _save_sample(self, now, image, inference_result):
        time_prefix = now.strftime("%Y%m%d-%H%M%S-{ftype}.{fext}")
        image_file = time_prefix.format(ftype='image', fext='jpg')
        image_path = self.output_directory / image_file
        json_file = time_prefix.format(ftype='ai', fext='json')
        json_path = self.output_directory / json_file
        inf_json = []
        for category, confidence, box in inference_result:
            log.info('category: %s , confidence: %.0f, box: %s', category, confidence, box)
            one_inf = {
                'category': category,
                'confidence': float(confidence),
                'box': {
                    'xmin': float(box[0]),
                    'ymin': float(box[1]),
                    'xmax': float(box[2]),
                    'ymax': float(box[3]),
                }
            }
            inf_json.append(one_inf)

        ai_json = {
            'datetime': now.isoformat(),
            'image': image_file,
            'inference_result': inf_json,
        }
        image.save(image_path)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(ai_json, f, ensure_ascii=False, indent=4)
        # ... save samples to local disk
        # ... pass notifications to flask server via cross-process queue or pipe or topic
        # ... run flask web app in a separate process. It does not need to get in the way of pipeline processing

    def receive_next_sample(self, image, inference_result):
        log.info("Pipe element %s received new sample: %s", self.__class__.__name__, str(inference_result))
        now = datetime.datetime.now()
        if inference_result:
            # non-empty result, there is a detection
            # let's save it if its been longer than the user specified detections_interval
            if now - self.time_latest_saved_detection >= self.detections_interval:
                self._save_sample(now, image, inference_result)
                self.time_latest_saved_detection = now
            else:
                pass
        else:
            # non-empty result, there is a detection
            # let's save it if its been longer than the user specified detections_interval
            if now - self.time_latest_saved_idle >= self.idle_interval:
                self._save_sample(now, image, inference_result)
                self.time_latest_saved_idle = now
            else:
                pass


