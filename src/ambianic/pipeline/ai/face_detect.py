import logging

from .inference import TfInference

log = logging.getLogger(__name__)


class FaceDetect(TfInference):
    """ FaceDetect is a pipeline element responsible for detecting objects in an image """

    def __init__(self, element_config=None):
        super().__init__(element_config=element_config)
        self.topk = element_config.get('top-k', 3)  # default to top 3 person detections

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

    def receive_next_sample(self, **sample):
        log.debug("Pipe element %s received new sample with keys %s.", self.__class__.__name__, str([*sample]))
        if not sample:
            # pass through empty samples to next element
            if self.next_element:
                self.next_element.receive_next_sample()
        else:
            try:
                image = sample['image']
                inference_result = sample.get('inference_result', None)
                log.debug("sample: %s", str(inference_result))
                # - crop out top-k person detections
                # - apply face detection to cropped person areas
                # - pass face detections on to next pipe element
                face_regions = []
                for category, confidence, box in inference_result:
                    if category == 'person' and confidence >= self.confidence_threshold:
                        face_regions.append(box)
                face_regions = face_regions[:self.topk]  # get only topk person detecions
                log.debug('Detected %d faces', len(face_regions))
                if not face_regions:
                    # if no faces were detected, let the next pipe element know that we have nothing to share
                    if self.next_element:
                        self.next_element.receive_next_sample()
                else:
                    for box in face_regions:
                        person_image = self.crop_image(image, box)
                        inference_result = super().detect(image=person_image)
                        if self.next_element:
                            self.next_element.receive_next_sample(image=person_image, inference_result=inference_result)
            except Exception as e:
                log.warning('Error "%s" while processing sample. Dropping sample: %s', str(e), str(sample))



