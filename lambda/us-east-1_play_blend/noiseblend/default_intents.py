from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_intent_name, is_request_type

from .constants import (
    AFTER_HELP_QUESTION,
    GOODBYE,
    HELP,
    UNHANDLED,
    WELCOME,
    WHAT_DO_YOU_WANT,
)


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(WELCOME).ask(WHAT_DO_YOU_WANT)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(HELP).ask(AFTER_HELP_QUESTION)
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.CancelIntent")(handler_input) or is_intent_name(
            "AMAZON.StopIntent"
        )(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(GOODBYE)
        return handler_input.response_builder.response


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        handler_input.response_builder.speak(UNHANDLED).ask(HELP)
        return handler_input.response_builder.response
