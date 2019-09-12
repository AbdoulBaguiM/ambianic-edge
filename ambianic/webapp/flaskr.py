import os
from multiprocessing import Process
import logging
import time
from flask import Flask, jsonify
from flask_cors import CORS
import flask
from werkzeug.serving import make_server
from ambianic.service import ServiceExit, ThreadedJob

log = logging.getLogger(__name__)

# configuration
DEBUG = True


class FlaskJob:

    def __init__(self, config):
        self.config = config
        self.srv = None
        app = create_app()
        self.srv = make_server('0.0.0.0', 8778, app)
        ctx = app.app_context()
        ctx.push()
        self.flask_stopped = True
        log.debug('Flask process created')

    def start(self):
        log.debug('Flask starting main loop')
        self.flask_stopped = False
        try:
            self.srv.serve_forever()
        except ServiceExit:
            log.info('Service exit requested')
        self.flask_stopped = True
        log.debug('Flask ended main loop')

    def stop(self):
        if not self.flask_stopped:
            log.debug('Flask stopping main loop')
            self.srv.shutdown()
            log.debug('Flask main loop ended')


class FlaskServer:
    """ Thin wrapper around Flask constructs.

    Allows controlled start and stop of the web app server
    in a separate process.

    Parameters
    ----------
    config : yaml
        reference to the yaml configuration file

    """

    def __init__(self, config):
        self.config = config
        self.flask_job = None

    def start(self):
        log.info('Flask server job starting...')
        f = FlaskJob(self.config)
        self.flask_job = ThreadedJob(f)
        self.flask_job.start()
        log.info('Flask server job started')

    def healthcheck(self):
        # TODO: Implement actual health check for Flask
        # See if the /healthcheck URL returns a 200 quickly
        return time.monotonic(), True

    def stop(self):
        if self.flask_job:
            log.info('Flask server job stopping...')
            self.flask_job.stop()
            self.flask_job.join()
            log.info('Flask server job stopped.')

def create_app():
    log.debug('Creating Flask app...')

    # if Ambianic is in INFO or DEBUG mode, pass that info on to Flask
    if log.level <= logging.INFO:
        os.environ['FLASK_ENV'] = 'development'

    # create and configure the web app
    # set the project root directory as the static folder, you can set others.
    app = Flask(__name__, instance_relative_config=True)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # enable CORS for development
    CORS(app, resources={r'/*': {'origins': '*'}})

    # sanity check route
    @app.route('/ping', methods=['GET'])
    def ping_pong():
        return jsonify('pong!')

    # a simple page that says hello
    @app.route('/')
    def hello():
        return 'Ambianic! Halpful AI for home and business automation.'

    # healthcheck page available to docker-compose and other health monitoring tools
    @app.route('/ambianic/healthcheck')
    def health_check():
        return 'Ambianic is running in a cheerful healthy state!'

    # live view of ambianic pipelines
    @app.route('/ambianic/pipelines')
    def view_pipelines():
        return flask.render_template('pipelines.html')

    @app.route('/ambianic/static/<path:path>')
    def static_file(path):
        return flask.send_from_directory('static', path)

    @app.route('/ambianic/data/<path:path>')
    def data_file(path):
        return flask.send_from_directory('../../data', path)

    @app.route('/ambianic/client/<path:path>')
    def client_file(path):
        return flask.send_from_directory('client', path)

    log.debug('Flask url map: %s', str(app.url_map))
    log.debug('Flask config map: %s', str(app.config))
    log.debug('Flask running in %s mode', 'development' if app.config['DEBUG'] else 'production')

    log.debug('Flask app created.')
    return app
