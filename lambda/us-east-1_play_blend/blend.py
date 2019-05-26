import warnings  # isort:skip

warnings.filterwarnings("ignore", category=DeprecationWarning)  # isort:skip
warnings.filterwarnings("ignore", category=UserWarning)  # isort:skip

import logging

import addict
from fuzzywuzzy import fuzz

import sentry_sdk
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_request_type
from aws_xray_sdk.core import patch_all
from noiseblend import NoiseblendRequestHandler, NoiseblendSkillBuilder
from noiseblend.can_fulfill import (
    CanFulfillDecreaseTuneableAttributeIntentHandler,
    CanFulfillDislikeIntentHandler,
    CanFulfillFadeDownIntentHandler,
    CanFulfillFadeIntentHandler,
    CanFulfillFadeUpIntentHandler,
    CanFulfillGenericIntentHandler,
    CanFulfillIncreaseTuneableAttributeIntentHandler,
    CanFulfillLikeIntentHandler,
    CanFulfillListTuneablesIntentHandler,
    CanFulfillListTuningIntentHandler,
    CanFulfillMaxTuneableAttributeIntentHandler,
    CanFulfillMinTuneableAttributeIntentHandler,
    CanFulfillPlayBlendIntentHandler,
    CanFulfillPlayRadioArtistIntentHandler,
    CanFulfillPlayRadioGenreIntentHandler,
    CanFulfillPlayRadioTrackIntentHandler,
    CanFulfillPlayRandomIntentHandler,
    CanFulfillResetTuneableAttributeIntentHandler,
    CanFulfillResetTuneableAttributesIntentHandler,
    CanFulfillTuneAttributeIntentHandler,
)
from noiseblend.constants import (
    DISLIKED_ARTIST,
    EMPTY_TUNING,
    FADE_LIMIT,
    FADE_LIMIT_EXCEEDED,
    NOT_IMPLEMENTED_YET,
    NOTHING_PLAYING,
    RESET_TUNEABLE,
    RESET_TUNEABLE_ANNOUNCE,
    SAVING_TRACK,
    SET_TUNEABLE_ANNOUNCE,
    TUNEABLE_DEFAULTS,
    TUNEABLE_LIST,
    TUNEABLE_NAMES,
)
from noiseblend.default_intents import (
    CancelOrStopIntentHandler,
    FallbackIntentHandler,
    HelpIntentHandler,
    LaunchRequestHandler,
    SessionEndedRequestHandler,
)
from noiseblend.exception_handlers import (
    CatchAllExceptionHandler,
    NoiseblendAuthExceptionHandler,
    NoiseblendExceptionHandler,
    NoiseblendUnknownSlotExceptionHandler,
)
from noiseblend.helpers import cap, listify
from sentry_sdk.integrations.aws_lambda import AwsLambdaIntegration

logger = logging.getLogger()
logger.setLevel(logging.INFO)

patch_all()
sentry_dsn_file = Path(__file__).parent / "secrets" / "sentry_dsn"
sentry_sdk.init(sentry_dsn_file.read_text(), integrations=[AwsLambdaIntegration()])

sb = NoiseblendSkillBuilder(table_name="noiseblend", auto_create_table=False)


class NotImplementedHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return True

    def handle(self, handler_input):
        handler_input.response_builder.speak(NOT_IMPLEMENTED_YET)
        return handler_input.response_builder.response


class DislikeIntentHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        playback = addict.Dict(self.api_get("playback").json())
        artists = playback.item.artists

        speak = ""
        artist_slot = self.slot("artist")
        if artist_slot:
            artist = max(
                artists,
                key=lambda a: fuzz.ratio(artist_slot.name.lower(), a.name.lower()),
            )
            self.api_post("dislike", artist=artist.id)
            speak = DISLIKED_ARTIST.format(artist.name)
        elif len(artists) > 1:
            self.api_post("dislike", artists=[artist.id for artist in artists])
            speak = DISLIKED_ARTIST.format(listify(a.name for a in artists))
        else:
            artist = artists[0]
            self.api_post("dislike", artist=artist.id)
            speak = DISLIKED_ARTIST.format(artist.name)

        self.play_last_thing()
        return self.speak(speak)


class PlayBlendIntentHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        blend_slot = self.slot("blend")
        blend = self.resolution(blend_slot)

        result = self.find_device()
        if result:
            return result

        self.attr["last_blend"] = blend.to_dict()
        if "last_radio" in self.attr:
            del self.attr["last_radio"]
        if "attributes" in self.attr and blend.id in self.attr["attributes"]:
            del self.attr["attributes"][blend.id]
        self.save_attr()

        return self.play_blend(blend, volume=self.volume)


class PlayRandomIntentHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        result = self.find_device()
        if result:
            return result

        self.attr["last_blend"] = {"id": "random", "name": "Random"}
        if "last_radio" in self.attr:
            del self.attr["last_radio"]
        if "attributes" in self.attr and "random" in self.attr["attributes"]:
            del self.attr["attributes"]["random"]
        self.save_attr()

        return self.play_random(volume=self.volume)


class PlayRadioIntentHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input, item_type):
        resp = super().handle(handler_input)
        if resp:
            return resp

        items = self.slot(item_type).value
        comma_separated_items = items.split(",")
        and_separated_items = comma_separated_items[-1].split(" and ", maxsplit=1)
        if len(comma_separated_items) > 1:
            items = comma_separated_items[:-1] + and_separated_items
        else:
            items = and_separated_items

        result = self.find_device()
        if result:
            return result

        self.attr["last_radio"] = {f"{item_type[:-1]}_names": items}
        if "last_blend" in self.attr:
            del self.attr["last_blend"]
        if "attributes" in self.attr and "radio" in self.attr["attributes"]:
            del self.attr["attributes"]["radio"]
        self.save_attr()

        return self.play_radio(volume=self.volume, **self.attr["last_radio"])


class PlayRadioArtistIntentHandler(PlayRadioIntentHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        return super().handle(handler_input, "artists")


class PlayRadioTrackIntentHandler(PlayRadioIntentHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        return super().handle(handler_input, "tracks")


class PlayRadioGenreIntentHandler(PlayRadioIntentHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        return super().handle(handler_input, "genres")


class LikeIntentHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        self.api_post("save-track")
        return self.speak(SAVING_TRACK)


class FadeAbstractIntentHandler(NoiseblendRequestHandler):
    DEFAULT_DURATION = 5
    DEFAULT_VOLUME = None
    DEFAULT_VOLUME_BY_DIRECTION = {"up": 60, "down": 0}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minutes = self.DEFAULT_DURATION
        self.fade_volume = self.DEFAULT_VOLUME

    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        duration = self.slot("duration")
        volume = self.slot("volume")
        self.minutes = self.DEFAULT_DURATION
        self.fade_volume = self.DEFAULT_VOLUME

        if duration is not None and duration.value is not None:
            self.minutes = int(duration.value)

        if volume is not None and volume.value is not None:
            self.fade_volume = int(volume.value)

        if self.minutes is not None:
            if not 1 <= self.minutes <= FADE_LIMIT:
                return self.speak(FADE_LIMIT_EXCEEDED)

        if self.fade_volume is not None:
            self.fade_volume = cap(self.fade_volume, 0, 100)

        return None


class FadeIntentHandler(FadeAbstractIntentHandler):

    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        direction_slot = self.slot("direction")
        direction = self.resolution(direction_slot).id

        if self.fade_volume is not None:
            speak = f"Fading volume {direction} to {self.fade_volume} percent in {self.minutes} minutes"
        else:
            speak = f"Fading volume {direction} in {self.minutes} minutes"
            self.fade_volume = self.DEFAULT_VOLUME_BY_DIRECTION[direction]

        self.api_post(
            "fade",
            direction=-1 if direction == "down" else 1,
            stop_volume=self.fade_volume,
            time_minutes=self.minutes,
        )
        card_text = f"Fading volume {direction} to {self.fade_volume}% in {self.minutes} minutes"
        return (
            self.response_builder.speak(speak)
            .set_card(self.card("Volume fade", card_text))
            .response
        )


class FadeDownIntentHandler(FadeAbstractIntentHandler):
    DEFAULT_DURATION = 20
    DEFAULT_VOLUME = 0

    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        speak = f"Fading volume down in {self.minutes} minutes"

        self.api_post(
            "fade",
            direction=-1,
            stop_volume=self.fade_volume,
            time_minutes=self.minutes,
        )
        return (
            self.response_builder.speak(speak)
            .set_card(self.card(f"Sleep timer", f"00:{self.minutes}:00"))
            .response
        )


class FadeUpIntentHandler(FadeAbstractIntentHandler):
    DEFAULT_DURATION = 2
    DEFAULT_VOLUME = 70

    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        speak = f"Fading volume up in {self.minutes} minutes"

        self.api_post(
            "fade", direction=1, stop_volume=self.fade_volume, time_minutes=self.minutes
        )
        return (
            self.response_builder.speak(speak)
            .set_card(self.card(f"Fading up", f"00:{self.minutes}:00"))
            .response
        )


class ListTuneablesIntentHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        return self.speak(TUNEABLE_LIST)


class TuneableAttributeHandler(NoiseblendRequestHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if "last_blend" in self.attr:
            blend = addict.Dict(self.attr["last_blend"])
            self.last_attributes = (self.attr.get("attributes") or {}).get(
                blend.id
            ) or {}
            self.last_thing = blend.id
        elif "last_radio" in self.attr:
            self.last_attributes = (self.attr.get("attributes") or {}).get(
                "radio", {}
            ) or {}
            self.last_thing = "radio"
        else:
            self.last_attributes = {}
            self.last_thing = None

        if not self.last_thing:
            return self.speak(NOTHING_PLAYING)

        return None

    @property
    def is_reverse(self):
        return self.tuneable.id.startswith("reverse_")

    @staticmethod
    def normalize_tuneable_value(tuneable, value):
        value = value / TUNEABLE_DEFAULTS[tuneable].max
        return cap(int(round(value * 10)), 0, 10)

    def tid(self, tuneable):
        if self.is_reverse:
            return tuneable[8:]

        return tuneable

    @property
    def defaults(self):
        return TUNEABLE_DEFAULTS[self.tuneable_id]

    @property
    def last_tuneable_value(self):
        return float(self.last_attributes.get(self.tuneable_id, self.defaults.default))

    def set_tuneable_value(self, value):
        self.last_attributes[self.tuneable_id] = f"{value:.2f}"

    def delete_tuneable_value(self):
        if self.tuneable_id in self.last_attributes:
            del self.last_attributes[self.tuneable_id]

    def announce_tuneable(self):
        tuneable_name = TUNEABLE_NAMES[self.tuneable_id]
        if self.tuneable_id not in self.last_attributes:
            return self.speak(RESET_TUNEABLE_ANNOUNCE.format(tuneable=tuneable_name))

        value = self.normalize_tuneable_value(
            self.tuneable_id, self.last_tuneable_value
        )

        return self.speak(
            SET_TUNEABLE_ANNOUNCE.format(tuneable=tuneable_name, value=value)
        )

    def save_last_attributes(self):
        if not "attributes" in self.attr:
            self.attr["attributes"] = {self.last_thing: {}}
        elif self.last_thing not in self.attr["attributes"]:
            self.attr["attributes"][self.last_thing] = {}

        for tuneable, value in self.last_attributes.items():
            if not isinstance(value, str):
                value = f"{value:.2f}"
            self.attr["attributes"][self.last_thing][tuneable] = value
        self.save_attr()

    def increase(self):
        if self.tuneable_id not in self.last_attributes:
            self.set_tuneable_value(self.defaults.default + self.defaults.step)
            return

        if self.last_tuneable_value < self.defaults.max:
            self.set_tuneable_value(
                cap(
                    self.last_tuneable_value + self.defaults.step,
                    self.defaults.min,
                    self.defaults.max,
                )
            )

    def decrease(self):
        if self.tuneable_id not in self.last_attributes:
            self.set_tuneable_value(self.defaults.default - self.defaults.step)
            return

        if self.last_tuneable_value > self.defaults.min:
            self.set_tuneable_value(
                cap(
                    self.last_tuneable_value - self.defaults.step,
                    self.defaults.min,
                    self.defaults.max,
                )
            )

    @property
    def tuneable(self):
        tuneable_slot = self.slot("tuneable")
        tuneable = self.resolution(tuneable_slot)
        return tuneable

    @property
    def tuneable_id(self):
        return self.tid(self.tuneable.id)


class ListTuningIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if not self.last_attributes:
            return self.speak(EMPTY_TUNING)

        tuning = ", ".join(
            f"{TUNEABLE_NAMES[tuneable]} is at {self.normalize_tuneable_value(tuneable, float(value))}"
            for tuneable, value in self.last_attributes.items()
        )
        return self.speak(tuning, end_session=False)


class TuneAttributeIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        tuneable_value = self.slot("tuneableValue").value
        tuneable_value = cap(int(tuneable_value), 0, 10)

        min_value = self.defaults.min
        max_value = self.defaults.max

        value = (tuneable_value / 10.0) * (max_value - min_value) + min_value
        value = cap(value, min_value, max_value)
        if self.is_reverse:
            value = 10 - value
        self.set_tuneable_value(value)

        self.save_last_attributes()
        self.play_last_thing()
        return self.announce_tuneable()


class IncreaseTuneableAttributeIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if self.is_reverse:
            self.decrease()
        else:
            self.increase()

        self.save_last_attributes()
        self.play_last_thing()
        return self.announce_tuneable()


class DecreaseTuneableAttributeIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if self.is_reverse:
            self.increase()
        else:
            self.decrease()

        self.save_last_attributes()
        self.play_last_thing()
        return self.announce_tuneable()


class MaxTuneableAttributeIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if self.is_reverse:
            self.set_tuneable_value(self.defaults.min)
        else:
            self.set_tuneable_value(self.defaults.max)

        self.save_last_attributes()
        self.play_last_thing()
        return self.announce_tuneable()


class MinTuneableAttributeIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if self.is_reverse:
            self.set_tuneable_value(self.defaults.max)
        else:
            self.set_tuneable_value(self.defaults.min)

        self.save_last_attributes()
        self.play_last_thing()
        return self.announce_tuneable()


class ResetTuneableAttributeIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        self.delete_tuneable_value()
        self.save_last_attributes()
        self.play_last_thing()

        return self.announce_tuneable()


class ResetTuneableAttributesIntentHandler(TuneableAttributeHandler):
    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        self.last_attributes = {}
        self.save_last_attributes()
        self.play_last_thing()

        return self.speak(RESET_TUNEABLE)


class ISPResponseHandler(NoiseblendRequestHandler):
    """This handles the Connections.Response event."""

    def can_handle(self, handler_input):
        return (
            is_request_type("Connections.Response")(handler_input)
            and handler_input.request_envelope.request.name
            == self.__class__.__name__[:-15]
        )

    # pylint: disable=arguments-differ
    def handle(self, handler_input):
        resp = super().handle(handler_input)
        if resp:
            return resp

        if self.req_envelope.request.status.code != "200":
            logger.error(
                "Connections.Response indicated failure. Error: %s",
                self.req_envelope.request.status.message,
            )
            return self.speak(
                "There was an error handling your request. "
                "Please try again or contact us for help."
            )
        return None


sb.add_request_handler(DecreaseTuneableAttributeIntentHandler())
sb.add_request_handler(DislikeIntentHandler())
sb.add_request_handler(FadeIntentHandler())
sb.add_request_handler(FadeDownIntentHandler())
sb.add_request_handler(FadeUpIntentHandler())
sb.add_request_handler(IncreaseTuneableAttributeIntentHandler())
sb.add_request_handler(LikeIntentHandler())
sb.add_request_handler(MaxTuneableAttributeIntentHandler())
sb.add_request_handler(MinTuneableAttributeIntentHandler())
sb.add_request_handler(PlayBlendIntentHandler())
sb.add_request_handler(PlayRadioArtistIntentHandler())
sb.add_request_handler(PlayRadioGenreIntentHandler())
sb.add_request_handler(PlayRadioTrackIntentHandler())
sb.add_request_handler(PlayRandomIntentHandler())
sb.add_request_handler(ResetTuneableAttributeIntentHandler())
sb.add_request_handler(ResetTuneableAttributesIntentHandler())
sb.add_request_handler(TuneAttributeIntentHandler())
sb.add_request_handler(ListTuneablesIntentHandler())
sb.add_request_handler(ListTuningIntentHandler())

sb.add_request_handler(CanFulfillDecreaseTuneableAttributeIntentHandler())
sb.add_request_handler(CanFulfillDislikeIntentHandler())
sb.add_request_handler(CanFulfillFadeDownIntentHandler())
sb.add_request_handler(CanFulfillFadeIntentHandler())
sb.add_request_handler(CanFulfillFadeUpIntentHandler())
sb.add_request_handler(CanFulfillIncreaseTuneableAttributeIntentHandler())
sb.add_request_handler(CanFulfillLikeIntentHandler())
sb.add_request_handler(CanFulfillListTuneablesIntentHandler())
sb.add_request_handler(CanFulfillListTuningIntentHandler())
sb.add_request_handler(CanFulfillMaxTuneableAttributeIntentHandler())
sb.add_request_handler(CanFulfillMinTuneableAttributeIntentHandler())
sb.add_request_handler(CanFulfillPlayBlendIntentHandler())
sb.add_request_handler(CanFulfillPlayRadioArtistIntentHandler())
sb.add_request_handler(CanFulfillPlayRadioGenreIntentHandler())
sb.add_request_handler(CanFulfillPlayRadioTrackIntentHandler())
sb.add_request_handler(CanFulfillPlayRandomIntentHandler())
sb.add_request_handler(CanFulfillResetTuneableAttributeIntentHandler())
sb.add_request_handler(CanFulfillResetTuneableAttributesIntentHandler())
sb.add_request_handler(CanFulfillTuneAttributeIntentHandler())
sb.add_request_handler(CanFulfillGenericIntentHandler())

sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

sb.add_exception_handler(NoiseblendUnknownSlotExceptionHandler())
sb.add_exception_handler(NoiseblendExceptionHandler())
sb.add_exception_handler(NoiseblendAuthExceptionHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

handler = sb.lambda_handler()
