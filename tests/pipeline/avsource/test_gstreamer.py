"""Test GStreamer Service."""
from ambianic.pipeline.avsource.gst_process import GstService
import threading
import os
import time
import pathlib
from multiprocessing import Queue
import logging
from PIL import Image
import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstBase', '1.0')
from gi.repository import Gst

Gst.init(None)

log = logging.getLogger()
log.setLevel(logging.DEBUG)


class _TestGstService(GstService):

    def __init__(self):
        self._source_shape = self.ImageShape()


class _TestSourceCaps:

    def get_structure(self, index=None):
        assert index == 0
        struct = {
            'width': 200,
            'height': 100,
        }
        return struct


def test_on_auto_plugin():
    gst = _TestGstService()
    gst.on_autoplug_continue(None, None, _TestSourceCaps())
    assert gst._source_shape.width == 200
    assert gst._source_shape.height == 100


class _TestGstService2(GstService):

    def _register_sys_signal_handler(self):
        print('skipping sys handler registration')
        # system handlers can be only registered in
        # the main process thread
        pass


def _test_start_gst_service2(source_conf=None,
                             out_queue=None,
                             stop_signal=None,
                             eos_reached=None):
    print('_test_start_gst_service2 starting _TestGstService2')
    try:
        svc = _TestGstService2(source_conf=source_conf,
                               out_queue=out_queue,
                               stop_signal=stop_signal,
                               eos_reached=eos_reached)
    except Exception as e:
        print('Exception caught while starting _TestGstService2: %r'
              % e)
    else:
        svc.run()
    print('_test_start_gst_service2: Exiting GST thread')


def test_image_source_one_sample():
    """An jpg image source should produce one sample."""
    dir = os.path.dirname(os.path.abspath(__file__))
    source_file = os.path.join(
        dir,
        '../ai/person.jpg'
        )
    abs_path = os.path.abspath(source_file)
    source_uri = pathlib.Path(abs_path).as_uri()
    _gst_out_queue = Queue(10)
    _gst_stop_signal = threading.Event()
    _gst_eos_reached = threading.Event()
    _gst_thread = threading.Thread(
        target=_test_start_gst_service2,
        name='Gstreamer Service Process',
        daemon=True,
        kwargs={'source_conf': {'uri': source_uri, 'type': 'image'},
                'out_queue': _gst_out_queue,
                'stop_signal': _gst_stop_signal,
                'eos_reached': _gst_eos_reached,
                }
        )
    _gst_thread.daemon = True
    _gst_thread.start()
    print('Gst service started. Waiting for a sample.')
    sample_img = _gst_out_queue.get(timeout=5)
    print('sample: %r' % (sample_img.keys()))
    assert sample_img
    type = sample_img['type']
    # only image type supported at this time
    assert type == 'image'
    # make sure the sample is in RGB format
    format = sample_img['format']
    assert format == 'RGB'
    width = sample_img['width']
    assert width == 1280
    height = sample_img['height']
    assert height == 720
    bytes = sample_img['bytes']
    img = Image.frombytes(format, (width, height),
                          bytes, 'raw')
    assert img
    _gst_stop_signal.set()
    _gst_thread.join(timeout=30)
    assert not _gst_thread.is_alive()


class _TestGstService3(GstService):

    def __init__(self):
        self._on_bus_message_eos_called = False
        self._eos_reached = threading.Event()
        self._on_bus_message_warning_called = False
        self._on_bus_message_error_called = False
        self._gst_cleanup_called = False
        pass

    def _on_bus_message_eos(self, message):
        self._on_bus_message_eos_called = True
        super()._on_bus_message_eos(message)

    def _on_bus_message_warning(self, message):
        self._on_bus_message_warning_called = True
        super()._on_bus_message_warning(message)

    def _gst_cleanup(self):
        self._gst_cleanup_called = True

    def _on_bus_message_error(self, message):
        self._on_bus_message_error_called = True
        super()._on_bus_message_error(message)


class _TestBusMessage3:

    def __init__(self):
        self.type = None

    def parse_warning(self):
        return None, None

    def parse_error(self):
        return None, None


def test_on_bus_message_warning():
    gst = _TestGstService3()
    message = _TestBusMessage3()
    message.type = Gst.MessageType.WARNING
    assert gst._on_bus_message(bus=None, message=message, loop=None)
    assert gst._on_bus_message_warning_called
    assert not gst._gst_cleanup_called


def test_on_bus_message_error():
    gst = _TestGstService3()
    message = _TestBusMessage3()
    message.type = Gst.MessageType.ERROR
    assert gst._on_bus_message(bus=None, message=message, loop=None)
    assert gst._on_bus_message_error_called
    assert gst._gst_cleanup_called


def test_on_bus_message_eos():
    gst = _TestGstService3()
    message = _TestBusMessage3()
    message.type = Gst.MessageType.EOS
    assert gst._on_bus_message(bus=None, message=message, loop=None)
    assert gst._on_bus_message_eos_called
    assert gst._gst_cleanup_called
    assert gst._eos_reached.is_set()


def test_on_bus_message_other():
    gst = _TestGstService3()
    message = _TestBusMessage3()
    message.type = Gst.MessageType.ANY
    assert gst._on_bus_message(bus=None, message=message, loop=None)


def test_still_image_source_one_sample_main_thread():
    """An jpg image source should produce one sample and exit gst loop."""
    dir = os.path.dirname(os.path.abspath(__file__))
    source_file = os.path.join(
        dir,
        '../ai/person.jpg'
        )
    abs_path = os.path.abspath(source_file)
    source_uri = pathlib.Path(abs_path).as_uri()
    _gst_out_queue = Queue(10)
    _gst_stop_signal = threading.Event()
    _gst_eos_reached = threading.Event()
    _test_start_gst_service2(
        source_conf={'uri': source_uri, 'type': 'image'},
        out_queue=_gst_out_queue,
        stop_signal=_gst_stop_signal,
        eos_reached=_gst_eos_reached
        )
    print('Gst service started. Waiting for a sample.')
    sample_img = _gst_out_queue.get(timeout=5)
    print('sample: %r' % (sample_img.keys()))
    assert sample_img
    type = sample_img['type']
    # only image type supported at this time
    assert type == 'image'
    # make sure the sample is in RGB format
    format = sample_img['format']
    assert format == 'RGB'
    width = sample_img['width']
    assert width == 1280
    height = sample_img['height']
    assert height == 720
    bytes = sample_img['bytes']
    img = Image.frombytes(format, (width, height),
                          bytes, 'raw')
    assert img


class _TestGstService4(GstService):

    _new_sample_out_queue_full = False

    def _on_new_sample_out_queue_full(self, sink):
        print('_on_new_sample_out_queue_full enter')
        result = super()._on_new_sample_out_queue_full(sink)
        if result == Gst.FlowReturn.OK:
            self._new_sample_out_queue_full = True
            print('self._new_sample_out_queue_full = True')
        print('_on_new_sample_out_queue_full exit')
        return result


def _test_start_gst_service4(source_conf=None,
                             out_queue=None,
                             stop_signal=None,
                             eos_reached=None):
    print('_test_start_gst_service4 starting _TestGstService2')
    try:
        svc = _TestGstService4(source_conf=source_conf,
                               out_queue=out_queue,
                               stop_signal=stop_signal,
                               eos_reached=eos_reached)
    except Exception as e:
        print('Exception caught while starting _TestGstService4: %r'
              % e)
    else:
        svc.run()
    print('_test_start_gst_service4: Exiting GST thread')


def test_sample_out_queue_full_on_sample():
    """When out queue is full samples should be ignored without blocking."""
    dir = os.path.dirname(os.path.abspath(__file__))
    source_file = os.path.join(
        dir,
        '../ai/person.jpg'
        )
    abs_path = os.path.abspath(source_file)
    source_uri = pathlib.Path(abs_path).as_uri()
    _gst_out_queue = Queue(1)
    last_in = 'only one sample allowed in this queue'
    _gst_out_queue.put(last_in)
    assert _gst_out_queue.full()
    _gst_stop_signal = threading.Event()
    _gst_eos_reached = threading.Event()
    _test_start_gst_service4(
        source_conf={'uri': source_uri, 'type': 'image'},
        out_queue=_gst_out_queue,
        stop_signal=_gst_stop_signal,
        eos_reached=_gst_eos_reached
        )
    print('Gst service started. Waiting for a sample.')
    _gst_eos_reached.wait(timeout=2)
    assert _gst_eos_reached.is_set()
    assert _gst_out_queue.full()
    first_out = _gst_out_queue.get(timeout=1)
    assert first_out == last_in
