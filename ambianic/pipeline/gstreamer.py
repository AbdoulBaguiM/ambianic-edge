import gi
import logging
import time
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import GLib, GObject, Gst, GstBase
from PIL import Image
from . import PipeElement

Gst.init(None)

log = logging.getLogger(__name__)


def shadow_text(dwg, x, y, text, font_size=20):
    dwg.add(dwg.text(text, insert=(x + 1, y + 1), fill='black', font_size=font_size))
    dwg.add(dwg.text(text, insert=(x, y), fill='white', font_size=font_size))


def generate_svg(dwg, objs, labels, text_lines):
    width, height = dwg.attribs['width'], dwg.attribs['height']
    for y, line in enumerate(text_lines):
        shadow_text(dwg, 10, y * 20, line)
    for obj in objs:
        x0, y0, x1, y1 = obj.bounding_box.flatten().tolist()
        x, y, w, h = x0, y0, x1 - x0, y1 - y0
        x, y, w, h = int(x * width), int(y * height), int(w * width), int(h * height)
        percent = int(100 * obj.score)
        label = '%d%% %s' % (percent, labels[obj.label_id])
        shadow_text(dwg, x, y - 5, label)
        dwg.add(dwg.rect(insert=(x, y), size=(w, h),
                         fill='red', fill_opacity=0.3, stroke='white'))
        # print("SVG canvas width: {w}, height: {h}".format(w=width,h=height))
        # dwg.add(dwg.rect(insert=(0,0), size=(width, height),
        #                fill='green', fill_opacity=0.2, stroke='white'))


class InputStreamProcessor(PipeElement):
    """
        Pipe element that handles a wide range of media input sources and passes on samples to the next
        pipe element.
    """

    class ImageShape:
        width = height = None
        pass

    class PipelineSource:
        def __init__(self, source_conf=None):
            assert source_conf, "pipeline source configuration required."
            assert source_conf['uri'], "pipeline source config missing uri element"
            self.uri = source_conf['uri']  # rtsp://..., rtmp://..., http://..., file:///...
            self.type = source_conf.get('type', 'auto')  # video, image, audio, auto
        pass

    def __init__(self, source_conf=None):
        super()

        # pipeline source info
        self.source = self.PipelineSource(source_conf=source_conf)
        # Reference to Gstreamer main loop structure
        self.mainloop = None
        # Gstreamer pipeline for a given input source (could be image, audio or video)
        self.gst_pipeline = None
        self.gst_video_source = None
        self._gst_video_source_connect_id = None
        # shape of the input stream image or video
        self.source_shape = self.ImageShape()
        self.gst_queue = None
        self._gst_queue_connect_id = None
        self.gst_vconvert = None
        self.gst_vconvert_connect_id = None
        # gst_appsink handlies GStreamer callbacks for new media samples which it passes on to the next pipe element
        self.gst_appsink = None
        self._gst_appsink_connect_id = None
        self._stop_requested = False  # indicates whether stop was requested via the API
        self.gst_bus = None

    def on_autoplug_continue(self, src_bin, src_pad, src_caps):
        # print('on_autoplug_continue called for uridecodebin')
        # print('src_bin: {}'.format(str(src_bin)))
        # print('src_pad: {}'.format(str(src_pad)))
        # print('src_caps: {}'.format(str(src_caps)))
        struct = src_caps.get_structure(0)
        # print("src caps struct: {}".format(struct))
        self.source_shape.width = struct["width"]
        self.source_shape.height = struct["height"]
        if self.source_shape.width:
            log.info("Input source width: %d, height: %d", self.source_shape.width, self.source_shape.height)
        return True

    def on_bus_message(self, bus, message, loop):
        t = message.type
        if t == Gst.MessageType.EOS:
            log.info('End of stream. Exiting gstreamer loop for this video stream.')
            loop.quit()
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            log.warning('Warning: %s: %s', err, debug)
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            log.warning('Error: %s: %s', err, debug)
            loop.quit()
        return True

    def on_new_sample(self, sink):
        log.info('Input stream received new image sample.')
        if not (self.source_shape.width or self.source_shape.height):
            # source stream shape still unknown
            log.warning('New image sample received but source shape still unknown?!')
            return Gst.FlowReturn.OK
        sample = sink.emit('pull-sample')
        buf = sample.get_buffer()
        caps = sample.get_caps()
        struct = caps.get_structure(0)
        # print("gst_appsink caps struct: {}".format(struct))
        app_width = struct["width"]
        app_height = struct["height"]
        # print("gst_appsink(inference image) width: {}, height: {}".format(app_width, app_height))
        result, mapinfo = buf.map(Gst.MapFlags.READ)
        if result:
            img = Image.frombytes('RGB', (app_width, app_height), mapinfo.data, 'raw')
            # svg_canvas = svgwrite.Drawing('', size=(self.source_shape.width, self.source_shape.height))
            # pass image sample to next pipe element, e.g. ai inference
            if self.next_element:
                log.info('Input stream sending sample to next element.')
                self.next_element.receive_next_sample(image=img)
            else:
                log.info('Input stream has no next pipe element to send sample to.')
        buf.unmap(mapinfo)
        return Gst.FlowReturn.OK

    def _get_pipeline_args(self):
        PIPELINE = ' uridecodebin name=source latency=300 '
        PIPELINE += """
             ! {leaky_q} ! videoconvert name=vconvert ! {sink_caps} ! {sink_element}
             """
        LEAKY_Q = 'queue max-size-buffers=10 leaky=downstream name=queue'
        # Ask gstreamer to format the images in a way that are close to the TF model tensor
        # Note: Having gstreamer resize doesn't appear to make a big performance difference.
        # Need to look closer at hardware acceleration options where available.
        # ,width={width},pixel-aspect-ratio=1/1'
        SINK_CAPS = 'video/x-raw,format=RGB'
        SINK_ELEMENT = 'appsink name=appsink sync=false emit-signals=true max-buffers=1 drop=true'
        pipeline_args = PIPELINE.format(leaky_q=LEAKY_Q,
                                   sink_caps=SINK_CAPS,
                                   sink_element=SINK_ELEMENT)
        log.debug('Gstreamer pipeline args: %s', pipeline_args)
        return pipeline_args

    def _build_gst_pipeline(self):
        log.debug("Building new gstreamer pipeline")
        pipeline_args = self._get_pipeline_args()
        self.gst_pipeline = Gst.parse_launch(pipeline_args)
        self.gst_video_source = self.gst_pipeline.get_by_name('source')
        self.gst_video_source.props.uri = self.source.uri
        self.gst_video_source_connect_id = self.gst_video_source.connect('autoplug-continue', self.on_autoplug_continue)
        assert self.gst_video_source_connect_id
        self.gst_queue = self.gst_pipeline.get_by_name('queue')
        self.gst_vconvert = self.gst_pipeline.get_by_name('vconvert')
        self.gst_appsink = self.gst_pipeline.get_by_name('appsink')
        log.debug("appsink: %s", str(self.gst_appsink))
        log.debug("appsink will emit signals: %s", self.gst_appsink.props.emit_signals)
        # register to receive new image sample events from gst
        self._gst_appsink_connect_id = self.gst_appsink.connect('new-sample', self.on_new_sample)
        self.mainloop = GObject.MainLoop()

        if log.getEffectiveLevel() <= logging.DEBUG:
            # set Gst debug log level
            Gst.debug_set_active(True)
            Gst.debug_set_default_threshold(3)

        # Set up a pipeline bus watch to catch errors.
        self.gst_bus = self.gst_pipeline.get_bus()
        self.gst_bus.add_signal_watch()
        self.gst_bus.connect('message', self.on_bus_message, self.mainloop)

    def _run_gst_loop(self):
        # build new gst pipeline
        self._build_gst_pipeline()
        # Run pipeline.
        self.gst_pipeline.set_state(Gst.State.PLAYING)
        log.debug("Entering main gstreamer loop")
        self.mainloop.run()
        log.debug("Exited main gstreamer loop")

    def _cleanup_gst_resources(self):
        log.debug("GST cleaning up resources...")
        if self.gst_pipeline:
            self.gst_pipeline.set_state(Gst.State.NULL)
            self.gst_pipeline = None
            self.gst_video_source.set_state(Gst.State.NULL)
            # self.gst_video_source.disconnect(self._gst_video_source_connect_id)
            self.gst_video_source = None
            self.gst_queue.set_state(Gst.State.NULL)
            # self.gst_queue.disconnect()
            self.gst_queue = None
            self.gst_vconvert.set_state(Gst.State.NULL)
            # self.gst_vconvert.disconnect(self.gst_vconvert_connect_id)
            self.gst_vconvert = None
            self.gst_appsink.set_state(Gst.State.NULL)
            # self.gst_appsink.disconnect(self._gst_appsink_connect_id)
            self.gst_appsink = None
            self.gst_bus.remove_signal_watch()
            self.gst_bus = None
        while GLib.MainContext.default().iteration(False):
            pass
        if self.mainloop:
            self.mainloop.quit()
            self.mainloop = None
        log.debug("GST cleaned up resources.")

    def start(self):
        """ Start the gstreamer pipeline """
        super().start()
        log.info("Starting %s", self.__class__.__name__)

        self._stop_requested = False

        while not self._stop_requested:
            try:
                self._run_gst_loop()
            except Exception as e:
                log.warning("GST loop exited with error: {} ".format(str(e)))
                if not self._stop_requested:
                    log.warning("Gst pipeline damaged. Will attempt to repair.")
                    self.heal()
                    time.sleep(1)  # pause for a moment to give associated resources a chance to heal
        # Clean up.
        self._cleanup_gst_resources()
        log.info("Stopped %s", self.__class__.__name__)

    def heal(self):
        """ Attempt to heal a damaged gstream pipeline """
        log.debug("Entering healing method... %s", self.__class__.__name__)
        self._cleanup_gst_resources()
        super().heal()
        log.debug("Exiting healing method. %s", self.__class__.__name__)

    def stop(self):
        """ Gracefully stop the gstream pipeline """
        log.info("Entering stop method ... %s", self.__class__.__name__)
        self._stop_requested = True
        self._cleanup_gst_resources()
        super().stop()
        log.info("Exiting stop method. %s", self.__class__.__name__)
