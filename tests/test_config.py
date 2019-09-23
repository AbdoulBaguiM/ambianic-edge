"""Test configuration functions."""
import pytest
import logging
import ambianic
import os
import pathlib


def test_log_config_with_file():
    log_config = {
        'file': '/tmp/test-log.txt'
    }
    ambianic._configure_logging(config=log_config)
    handlers = logging.getLogger().handlers
    for h in handlers:
        if isinstance(h, logging.FileHandler):
            log_fn = h.baseFilename
            assert log_fn == log_config['file']


def test_log_config_without_file():
    log_config = {
    }
    ambianic._configure_logging(config=log_config)
    handlers = logging.getLogger().handlers
    for h in handlers:
        assert not isinstance(h, logging.FileHandler)


def test_log_config_with_level():
    log_config = {
        'level': 'DEBUG'
    }
    ambianic._configure_logging(config=log_config)
    root_logger = logging.getLogger()
    effective_level = root_logger.getEffectiveLevel()
    lname = logging.getLevelName(effective_level)
    assert lname == log_config['level']


def test_log_config_without_level():
    log_config = {}
    ambianic._configure_logging(config=log_config)
    root_logger = logging.getLogger()
    effective_level = root_logger.getEffectiveLevel()
    assert effective_level == ambianic.DEFAULT_LOG_LEVEL


def test_log_config_bad_level1():
    log_config = {
        'level': '_COOCOO_'
    }
    ambianic._configure_logging(config=log_config)
    root_logger = logging.getLogger()
    effective_level = root_logger.getEffectiveLevel()
    assert effective_level == ambianic.DEFAULT_LOG_LEVEL


def test_log_config_bad_level2():
    log_config = {
        'level': 2.56
    }
    ambianic._configure_logging(config=log_config)
    root_logger = logging.getLogger()
    effective_level = root_logger.getEffectiveLevel()
    assert effective_level == ambianic.DEFAULT_LOG_LEVEL


def test_config_with_secrets():
    ambianic.SECRETS_FILE = 'test-config-secrets.yaml'
    ambianic.CONFIG_FILE = 'test-config.yaml'
    dir = os.path.dirname(os.path.abspath(__file__))
    conf = ambianic.configure(dir)
    assert conf
    assert conf['logging']['level'] == 'DEBUG'
    assert conf['sources']['front_door_camera']['uri'] == 'secret_uri'


def test_config_without_secrets_failed_ref():
    ambianic.SECRETS_FILE = '__no__secrets__.lmay__'
    ambianic.CONFIG_FILE = 'test-config.yaml'
    dir = os.path.dirname(os.path.abspath(__file__))
    conf = ambianic.configure(dir)
    assert not conf


def test_config_without_secrets_no_ref():
    ambianic.SECRETS_FILE = '__no__secrets__.lmay__'
    ambianic.CONFIG_FILE = 'test-config2.yaml'
    dir = os.path.dirname(os.path.abspath(__file__))
    conf = ambianic.configure(dir)
    assert conf
    assert conf['logging']['level'] == 'DEBUG'
    assert conf['sources']['front_door_camera']['uri'] == 'no_secret_uri'
