"""Utilities to send notifications."""

import hashlib
import logging
import os
import urllib
from string import Template

import ambianic
import apprise
import pkg_resources
import yaml
from ambianic.configuration import get_root_config
from requests import post

log = logging.getLogger(__name__)

UI_BASE_URL_DEFAULT = "https://ui.ambianic.ai"


def sendCloudNotification(data):
    # r+ flag causes a permission error
    try:
        premiumFile = pkg_resources.resource_filename("ambianic.webapp", "premium.yaml")

        with open(premiumFile) as file:
            configFile = yaml.safe_load(file)

            userId = configFile["credentials"]["USER_AUTH0_ID"]
            endpoint = configFile["credentials"]["NOTIFICATION_ENDPOINT"]
            if userId:
                return post(
                    url=f"{endpoint}/notification",
                    json={
                        "userId": userId,
                        "notification": {
                            "title": "Ambianic.ai New {} event".format(data["label"]),
                            "message": "New {} detected with a {} confidence level".format(
                                data["label"], data["confidence"]
                            ),
                        },
                    },
                )

    except FileNotFoundError as err:
        log.warning(f"Error locating file: {err}")

    except Exception as error:
        log.warning(f"Error sending email: {str(error)}")


class Notification:
    def __init__(
        self, event: str = "detection", data: dict = {}, providers: list = ["all"]
    ):
        self.event: str = event
        self.providers: list = providers
        self.title: str = None
        self.message: str = None
        self.attach: list = []
        self.data: dict = data

    def add_attachments(self, *args):
        self.attach.append(*args)

    def to_dict(self) -> dict:
        return dict(vars(self))


class NotificationHandler:
    def __init__(self, config: dict = None):
        if config is None:
            config = ambianic.configuration.get_root_config()
        self.apobj = apprise.Apprise(debug=True)
        self.config = config.get("notifications", {})
        for name, cfg in self.config.items():
            providers = cfg.get("providers", [])
            for provider in providers:
                if not self.apobj.add(provider, tag=name):
                    log.warning(
                        f"Failed to add notification provider: {name}={provider}"
                    )
                else:
                    log.info(f"Apprise: added notification provider: {name}={provider}")

    def send(self, notification: Notification):
        log.debug("preparing notification")
        for provider in notification.providers:
            log.debug(f"preparing notification payload for provider {provider}")
            cfg = self.config.get(provider, None)

            if cfg:
                enabled = cfg.get("enabled", True)
                if not enabled:
                    log.debug(f"notification disabled for provider {provider}")
                    return
                else:
                    log.debug(f"notification enabled for provider {provider}")

                templates = cfg.get("templates", {})

                title = notification.title
                if title is None:
                    title = templates.get("title", "[Ambianic.ai] New ${event} event")

                log.debug(f"template title: {title}")

                message = notification.message
                if message is None:
                    message = templates.get("message", "New ${event} recognized")

                log.debug(f"template message: {message}")

                attachments = []
                for a in notification.attach:
                    if not os.path.exists(a) or not os.path.isfile(a):
                        log.warning("Attachment is not a valid file %s")
                        continue
                    attachments.append(a)

                url_params = {**notification.data}

                peer_id = get_root_config().get("peerId", None)
                if peer_id is None:
                    log.warn(
                        "peerId not found. Notification will not include link bank to peer."
                    )
                else:
                    peerid_hash_input = peer_id + notification.data["id"]
                    peerid_hash = hashlib.sha256(
                        peerid_hash_input.encode("utf-8")
                    ).hexdigest()
                    # send peerid hashed with event_id as salt to avoid replay attacks
                    # UI can lookup the actual peerid be going over its stored peerid's
                    # and generating salted hashes for each
                    # until one matches the URL paramter.
                    url_params["peerid_hash"] = peerid_hash

                url_query = urllib.parse.urlencode(url_params)

                ui_config = get_root_config().get(
                    "ui", {"baseurl", UI_BASE_URL_DEFAULT}
                )
                ui_base_url = ui_config["baseurl"]

                template_args = {
                    "event_type": notification.event,
                    "event": notification.data.get("label", notification.event),
                    "event_details_url": f"{ui_base_url}/event?{url_query}",
                }
                template_args = {**template_args, **notification.data}

                log.debug(f"template_args: {template_args}")

                # resolve template references for title and message
                title = Template(title).safe_substitute(template_args)
                message = Template(message).safe_substitute(template_args)

                log.debug(f"template resolved title: {title}")
                log.debug(f"template resolved message: {message}")

                include_attachments = cfg.get("include_attachments", False)
                ok = self.apobj.notify(
                    title=title,
                    body=message,
                    tag=provider,
                    attach=attachments if include_attachments else [],
                )
                if ok:
                    log.debug(
                        "Sent notification for %s to %s"
                        % (notification.event, provider)
                    )
                else:
                    log.warning(
                        "Error sending notification for %s to %s"
                        % (notification.event, provider)
                    )
            else:
                log.warning("Skipping unknown provider %s" % provider)
                continue
