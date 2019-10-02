"""Face detection pipe element."""
import logging

from .image_detection import TFImageDetection
from ambianic.util import stacktrace

log = logging.getLogger(__name__)


class FaceDetector(TFImageDetection):
    """Detecting faces in an image."""

    def __init__(self, element_config=None):
        # log.warning('FaceDetector __init__ invoked')
        super().__init__(element_config=element_config)
        # log.warning('FaceDetector __init__ after super()')
        # default to top 3 face detections
        self.topk = element_config.get('top-k', 3)

    @staticmethod
    def crop_image(image, box):
        # Size of the image in pixels (size of orginal image)
        # (This is not mandatory)
        width, height = image.size

        # Setting the points for cropped image
        left = box[0]*width
        top = box[1]*height
        right = box[2]*width
        bottom = box[3]*height

        # Cropped image of above dimension
        # (It will not change orginal image)
        im1 = image.crop((left, top, right, bottom))
        return im1

    def process_sample(self, **sample):
        log.debug("Pipe element %s received new sample with keys %s.",
                  self.__class__.__name__,
                  str([*sample]))
        if not sample:
            # pass through empty samples to next element
            yield None
        else:
            try:
                image = sample['image']
                prev_inference_result = sample.get('inference_result', None)
                log.debug("Received sample with inference_result: %s",
                          str(prev_inference_result))
                person_regions = []
                if not prev_inference_result:
                    yield None
                else:
                    # - crop out top-k person detections
                    # - apply face detection to cropped person areas
                    # - pass face detections on to next pipe element
                    for category, confidence, box in prev_inference_result:
                        if category == 'person' and \
                          confidence >= self._tfengine.confidence_threshold:
                            person_regions.append(box)
                    # get only topk person detecions
                    person_regions = person_regions[:self.topk]
                    log.debug('Received %d person boxes for face detection',
                              len(person_regions))
                    for box in person_regions:
                        person_image = self.crop_image(image, box)
                        inference_result = self.detect(image=person_image)
                        log.warning('Face detection inference_result: %r',
                                    inference_result)
                        processed_sample = {
                            'image': person_image,
                            'inference_result': inference_result
                            }
                        yield processed_sample
            except Exception as e:
                log.warning('Error %r while processing sample. '
                            'Dropping sample: %r',
                            e,
                            sample)
                log.warning(stacktrace())
