import logging
from copy import deepcopy
from functools import lru_cache

import addict
import requests
import stringcase
from first import first
from fuzzywuzzy import fuzz
from sentry_sdk import capture_exception, configure_scope

from ask_sdk.standard import StandardSkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_intent_name, is_request_type
from ask_sdk_model.canfulfill import CanFulfillIntentRequest
from ask_sdk_model.dialog import ElicitSlotDirective
from ask_sdk_model.slu.entityresolution.status_code import StatusCode
from ask_sdk_model.ui import LinkAccountCard, StandardCard
from ask_sdk_model.ui.image import Image
from ask_sdk_runtime.dispatch_components.request_components import GenericHandlerAdapter
from aws_xray_sdk.core import xray_recorder

from .constants import (
    CHOOSE_DEVICE,
    MISSING_DEVICE,
    NO_DEVICES,
    NOISEBLEND_IMG,
    NOTIFY_LINK_ACCOUNT,
    PLAYING_BLEND,
    PLAYING_RADIO,
    PLAYING_RANDOM,
    WHAT_DEVICE,
)
from .exceptions import UnknownSlotError
from .helpers import cap

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def api(path):
    return f"https://api.noiseblend.com/{path}"


class NoiseblendHandlerAdapter(GenericHandlerAdapter):
    @staticmethod
    def serialize_tuneables(handler):
        attrs = deepcopy(handler.attr["attributes"])
        for thing, tuneables in attrs.items():
            for tuneable, value in tuneables.items():
                if not isinstance(value, str):
                    handler.attr["attributes"][thing][tuneable] = f"{value:.2f}"

    def save_attributes(self, handler):
        try:
            segment = xray_recorder.current_subsegment()
            segment.put_metadata("attributes", handler.attr)

            if "attributes" in handler.attr:
                self.serialize_tuneables(handler)

            handler.handler_input.attributes_manager.save_persistent_attributes()
        except Exception as exc:
            logger.exception(exc)
            capture_exception(exc)
        finally:
            xray_recorder.end_subsegment()

    def execute(self, handler_input, handler):
        xray_recorder.begin_subsegment("Handling request")
        try:
            response = handler.handle(handler_input)
            segment = xray_recorder.current_subsegment()

            if response:
                segment.put_metadata("response", response.to_dict())
            else:
                segment.put_metadata("response", response)

            if getattr(handler, "should_save_attr", False):
                xray_recorder.begin_subsegment("Saving attributes")
                self.save_attributes(handler)
        except Exception as exc:
            logger.exception(exc)
            capture_exception(exc)
            raise exc
        finally:
            xray_recorder.end_subsegment()

        return response


class NoiseblendSkillBuilder(StandardSkillBuilder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def skill_configuration(self):
        skill_config = super().skill_configuration
        skill_config.handler_adapters = [NoiseblendHandlerAdapter()]
        return skill_config


# pylint: disable=too-many-public-methods
class NoiseblendRequestHandler(AbstractRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.token = None
        self.response_builder = None
        self.handler_input = None
        self.req_envelope = None
        self.device_id = None
        self.last_attributes = {}
        self.last_thing = None
        self.should_save_attr = False

    def can_handle(self, handler_input):
        handler_name = self.__class__.__name__[:-7]
        return is_request_type("IntentRequest")(handler_input) and is_intent_name(
            handler_name
        )(handler_input)

    def api_get(self, path, **params):
        resp = requests.get(
            api(path), headers={"Authorization": f"Bearer {self.token}"}, params=params
        )
        resp.raise_for_status()
        return resp

    def api_post(self, path, **params):
        resp = requests.post(
            api(path), headers={"Authorization": f"Bearer {self.token}"}, json=params
        )
        resp.raise_for_status()
        return resp

    @property
    def slots(self):
        return self.req_envelope.request.intent.slots

    @property
    def attr(self):
        if self.handler_input.attributes_manager.persistent_attributes is None:
            self.handler_input.attributes_manager.persistent_attributes = {}
        return self.handler_input.attributes_manager.persistent_attributes

    @property
    def req_attr(self):
        if self.handler_input.attributes_manager.request_attributes is None:
            self.handler_input.attributes_manager.request_attributes = {}
        return self.handler_input.attributes_manager.request_attributes

    @staticmethod
    def resolution(slot, raise_exc=True):
        res = first(
            slot.resolutions.resolutions_per_authority,
            key=lambda r: r.status.code == StatusCode.ER_SUCCESS_MATCH,
        )
        if not res:
            if raise_exc:
                raise UnknownSlotError(slot.name)
            return None
        return res.values[0].value

    def slot(self, slot_name):
        if not self.slots:
            return None
        return self.slots.get(slot_name)

    def save_attr(self):
        self.should_save_attr = True

    @property
    @lru_cache(maxsize=1)
    def isp_response(self):
        """Get the In-skill product response from monetization service."""
        locale = self.req_envelope.request.locale
        ms = self.handler_input.service_client_factory.get_monetization_service()
        return ms.get_in_skill_products(locale)

    def speak(self, text, end_session=True):
        self.response_builder.speak(text).set_should_end_session(end_session)
        return self.response_builder.response

    def play_blend(self, blend, speak=None, card=None, volume=None):
        blend_attributes = self.get_tuneable_attributes(blend.id)
        attributes = self.api_post(
            "blend",
            blend=blend.id,
            play=True,
            return_early=True,
            device=self.req_attr.get(self.device_id),
            attributes=blend_attributes,
            volume=volume,
        ).json()

        if not blend_attributes:
            self.set_tuneable_attributes(blend.id, attributes)
            self.save_attr()

        if speak is None or speak is True:
            speak = (
                PLAYING_RANDOM
                if blend.id == "random"
                else PLAYING_BLEND.format(blend.name)
            )
        if card is None or card is True:
            card = (
                self.card(
                    "Playing a fresh playlist",
                    "The music will be based on your listening history",
                )
                if blend.id == "random"
                else self.card("Playing Blend", blend.name.title(), blend=blend.id)
            )

        if speak:
            self.response_builder.speak(speak)

        if card:
            self.response_builder.set_card(card)

        return self.response_builder.response

    @staticmethod
    def card(title, text=None, blend=None):
        if blend:
            blend = stringcase.spinalcase(blend)
            image = Image(
                f"{NOISEBLEND_IMG}/bg/blend/bg_{blend}_768.jpg",
                f"{NOISEBLEND_IMG}/bg/blend/bg_{blend}_1280.jpg",
            )
        else:
            image = Image(
                f"{NOISEBLEND_IMG}/icons/app/app-android-512x512.png",
                f"{NOISEBLEND_IMG}/icons/app/app-android-1024x1024.png",
            )

        return StandardCard(title, text, image)

    @property
    def volume(self):
        volume_slot = self.slot("volume")
        volume = (
            int(volume_slot.value) * 10
            if (volume_slot and volume_slot.value is not None)
            else None
        )
        volume_percent_slot = self.slot("volume_percent")
        volume = (
            int(volume_percent_slot.value)
            if (volume_percent_slot and volume_percent_slot.value is not None)
            else None
        )
        if volume is not None:
            volume = cap(volume, 0, 100)
        return volume

    def play_random(self, **kwargs):
        random_blend = addict.Dict({"id": "random", "name": "Random"})
        return self.play_blend(random_blend, **kwargs)

    def play_radio(self, volume=None, **seeds):
        self.api_post(
            "radio",
            return_early=True,
            device=self.req_attr.get(self.device_id),
            attributes=self.get_tuneable_attributes("radio"),
            volume=volume,
            **seeds,
        )
        return self.speak(PLAYING_RADIO)

    def get_tuneable_attributes(self, thing):
        attributes = (self.attr.get("attributes") or {}).get(thing)
        if attributes:
            for key, val in attributes.items():
                attributes[key] = float(val)
        return attributes

    def set_tuneable_attributes(self, thing, attributes):
        if attributes:
            for key, val in attributes.items():
                attributes[key] = f"{val:.2f}"
        self.attr["attributes"] = {thing: attributes}

    def play_last_thing(self):
        if "last_blend" in self.attr:
            self.play_blend(
                addict.Dict(self.attr["last_blend"]), speak=False, card=False
            )
        elif "last_radio" in self.attr:
            self.play_radio(**self.attr["last_radio"])
        else:
            self.play_random(speak=False, card=False)

    @xray_recorder.capture()
    def save_speaker(self, speaker):
        self.req_attr[self.device_id] = speaker.name

    @xray_recorder.capture()
    def choose_speaker(self, speakers, device_slot):
        speaker_list = list(speakers.values())

        device_name = device_slot.name
        speaker = max(
            speaker_list, key=lambda s: fuzz.ratio(device_name.lower(), s.name.lower())
        )
        if speaker:
            self.save_speaker(speaker)
            return None

        return self.ask_device(speaker_list, MISSING_DEVICE)

    @xray_recorder.capture()
    def ask_device(self, speaker_list, message):
        choose_device = CHOOSE_DEVICE.format(", ".join(s.name for s in speaker_list))
        return (
            self.response_builder.speak(f"{message} {choose_device}")
            .ask(choose_device)
            .add_directive(ElicitSlotDirective(slot_to_elicit="device"))
            .response
        )

    def find_device(self):
        device_slot = self.slot("device")

        try:
            devices = self.api_get("devices", playback=False).json()
            logger.info(devices)

            devices = [addict.Dict(d) for d in devices]

            speakers = {d.name: d for d in devices if d.type == "Speaker"}
            not_speakers = {d.name: d for d in devices if d.type != "Speaker"}
        except Exception as e:
            logger.exception(e)
            if self.device_id in self.req_attr:
                del self.req_attr[self.device_id]
            return None

        speaker_list = list(speakers.values())
        not_speaker_list = list(not_speakers.values())

        if len(speaker_list) == 1:
            logger.info("Found 1 speaker, using it as the playing device")
            self.save_speaker(speaker_list[0])
        elif len(speaker_list) > 1:
            logger.info("Found %s speakers", len(speaker_list))
            if self.device_id not in self.req_attr:
                if device_slot:
                    logger.info("Searching for %s device in speakers", device_slot)
                    return self.choose_speaker(speakers, device_slot)
            elif self.req_attr[self.device_id] not in (
                speakers.keys() | not_speakers.keys()
            ):
                logger.info(
                    "Saved speaker does not exist: %s", self.req_attr[self.device_id]
                )
                device = first(speaker_list, key=lambda s: s.is_active) or first(
                    speaker_list, key=lambda s: not s.is_restricted
                )
                self.save_speaker(device)
                if device:
                    logger.info(
                        "Using speaker %s because it is %s",
                        device,
                        ("active" if device.is_active else "not restricted"),
                    )
                else:
                    logger.info(
                        "Couldn't find a usable speaker, letting Noiseblend find one for us"
                    )
        elif len(not_speaker_list) == 1:
            logger.info("Found 1 device (not speaker), using it as the playing device")
            self.save_speaker(not_speaker_list[0])
        elif len(not_speaker_list) > 1 and device_slot:
            logger.info("Found %s devices", len(not_speaker_list))
            if self.device_id not in self.req_attr:
                if device_slot:
                    logger.info("Searching for %s device in not speakers", device_slot)
                    return self.choose_speaker(not_speakers, device_slot)
            elif self.req_attr[self.device_id] not in (
                speakers.keys() | not_speakers.keys()
            ):
                logger.info(
                    "Saved device does not exist: %s", self.req_attr[self.device_id]
                )

                device = first(not_speaker_list, key=lambda s: s.is_active) or first(
                    not_speaker_list, key=lambda s: not s.is_restricted
                )
                self.save_speaker(device)
                if device:
                    logger.info(
                        "Using device %s because it is %s",
                        device,
                        ("active" if device.is_active else "not restricted"),
                    )
                else:
                    logger.info(
                        "Couldn't find a usable device, letting Noiseblend find one for us"
                    )

        return None

    def can_fulfill_intent(self, no=False, maybe=False):
        pass

    # pylint: disable=arguments-differ
    def handle(self, handler_input, with_auth=True):
        try:
            self.handler_input = handler_input
            self.response_builder = handler_input.response_builder
            self.req_envelope = handler_input.request_envelope
            self.device_id = self.req_envelope.context.system.device.device_id

            with configure_scope() as scope:
                scope.user = {"id": self.req_envelope.session.user.user_id}
                scope.set_tag("handler", self.__class__.__name__[:-7])
                scope.set_extra("context", self.req_envelope.context.to_dict())
                scope.set_extra("request", self.req_envelope.request.to_dict())

            if (
                with_auth
                and not self.req_envelope.session.user
                or not self.req_envelope.session.user.access_token
            ):
                if isinstance(self.req_envelope.request, CanFulfillIntentRequest):
                    # self.can_fulfill_intent(maybe=True)
                    return None

                self.response_builder.speak(NOTIFY_LINK_ACCOUNT).set_card(
                    LinkAccountCard()
                )
                return self.response_builder.response

            self.token = self.req_envelope.session.user.access_token

            return None
        except Exception as exc:
            logger.exception(exc)
            raise exc
