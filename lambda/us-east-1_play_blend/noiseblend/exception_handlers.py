import logging

from ask_sdk_core.dispatch_components import AbstractExceptionHandler
from ask_sdk_model.canfulfill import CanFulfillIntentRequest
from ask_sdk_model.services import ServiceException
from ask_sdk_model.ui import LinkAccountCard
from requests import HTTPError
from sentry_sdk import capture_exception

from .constants import (
    BLEND_FAILURE,
    NOTIFY_LINK_ACCOUNT,
    NOTIFY_RELINK_ACCOUNT,
    UNKNOWN_SLOT,
)
from .exceptions import UnknownSlotError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class NoiseblendUnknownSlotExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return isinstance(exception, UnknownSlotError)

    def handle(self, handler_input, exception):
        logger.exception(exception)
        capture_exception(exception)

        return handler_input.response_builder.speak(
            UNKNOWN_SLOT.format(slot=exception.slot)
        ).response


class NoiseblendAuthExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return isinstance(exception, HTTPError)

    def handle(self, handler_input, exception):
        logger.exception(exception)
        capture_exception(exception)

        if exception.response.status_code in (401, 403):
            handler_input.response_builder.speak(NOTIFY_RELINK_ACCOUNT).set_card(
                LinkAccountCard()
            )
        else:
            handler_input.response_builder.speak(BLEND_FAILURE).ask(BLEND_FAILURE)

        return handler_input.response_builder.response


class NoiseblendExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return isinstance(exception, ServiceException)

    def handle(self, handler_input, exception):
        logger.exception(exception)
        capture_exception(exception)

        if isinstance(handler_input.request_envelope.request, CanFulfillIntentRequest):
            return handler_input.response_builder.response

        if exception.status_code == 403:
            handler_input.response_builder.speak(NOTIFY_LINK_ACCOUNT).set_card(
                LinkAccountCard()
            )
        else:
            handler_input.response_builder.speak(BLEND_FAILURE).ask(BLEND_FAILURE)

        return handler_input.response_builder.response


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.exception(exception)
        capture_exception(exception)

        speech = "Sorry, there was some problem. Please try again in a few minutes!"
        handler_input.response_builder.speak(speech)

        return handler_input.response_builder.response
