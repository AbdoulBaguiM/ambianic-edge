import logging

from .inference import TfImageDetection

log = logging.getLogger(__name__)


class ObjectDetect(TfImageDetection):
    """Detects objects in an image."""

    def __init__(self, element_config=None):
        super().__init__(element_config=element_config)

    def receive_next_sample(self, **sample):
        log.debug("%s received new sample", self.__class__.__name__)
        if not sample:
            # pass through empty samples to next element
            if self.next_element:
                self.next_element.receive_next_sample()
        else:
            try:
                image = sample['image']
                inference_result = super().detect(image=image)
                # pass on the results to the next connected pipe element
                if self.next_element:
                    self.next_element.receive_next_sample(
                        image=image,
                        inference_result=inference_result)
            except Exception as e:
                log.warning('Error "%s" while processing sample. '
                            'Dropping sample: %s',
                            str(e),
                            str(sample))
