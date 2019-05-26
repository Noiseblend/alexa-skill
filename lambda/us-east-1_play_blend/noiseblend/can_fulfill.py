import logging

from ask_sdk_core.utils import is_canfulfill_intent_name
from ask_sdk_model.canfulfill import (
    CanFulfillIntent,
    CanFulfillIntentRequest,
    CanFulfillIntentValues,
    CanFulfillSlot,
    CanFulfillSlotValues,
    CanUnderstandSlotValues,
)

from .request_handler import NoiseblendRequestHandler

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALL_INTENTS = {
    "DecreaseTuneableAttributeIntent",
    "DislikeIntent",
    "FadeDownIntent",
    "FadeIntent",
    "FadeUpIntent",
    "IncreaseTuneableAttributeIntent",
    "LikeIntent",
    "ListTuneablesIntent",
    "ListTuningIntent",
    "MaxTuneableAttributeIntent",
    "MinTuneableAttributeIntent",
    "PlayBlendIntent",
    "PlayRadioArtistIntent",
    "PlayRadioGenreIntent",
    "PlayRadioTrackIntent",
    "PlayRandomIntent",
    "ResetTuneableAttributeIntent",
    "ResetTuneableAttributesIntent",
    "TuneAttributeIntent",
}


class CanFulfillIntentHandler(NoiseblendRequestHandler):
    CAN_FULFILL_AND_UNDERSTAND = set()
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = set()
    CAN_FULFILL_AND_MAYBE_UNDERSTAND = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.slots_fulfillment = []
        self.can_fulfill_intent_text = None
        self.handler_name = self.__class__.__name__[10:-7]

    def can_handle(self, handler_input):
        return is_canfulfill_intent_name(self.handler_name)(handler_input)

    def can_fulfill_intent(self, no=False, maybe=False):
        if no:
            self.can_fulfill_intent_text = CanFulfillIntentValues.NO
        elif maybe and (
            self.can_fulfill_intent_text is None
            or self.can_fulfill_intent_text == CanFulfillIntentValues.YES
        ):
            self.can_fulfill_intent_text = CanFulfillIntentValues.MAYBE
        elif self.can_fulfill_intent_text is None:
            self.can_fulfill_intent_text = CanFulfillIntentValues.YES

    def can_fulfill_and_understand(self, slot):
        self.slots_fulfillment.append(
            self.slot_state(slot, can_fulfill=True, can_understand=True)
        )

    def can_fulfill_and_maybe_understand(self, slot):
        self.slots_fulfillment.append(
            self.slot_state(slot, can_fulfill=True, can_understand=None)
        )

    def can_fulfill(self, slot):
        self.slots_fulfillment.append(
            self.slot_state(slot, can_fulfill=True, can_understand=False)
        )

    def can_understand(self, slot):
        self.slots_fulfillment.append(
            self.slot_state(slot, can_fulfill=False, can_understand=True)
        )

    def cannot_fulfill(self, slot):
        self.slots_fulfillment.append(
            self.slot_state(slot, can_fulfill=False, can_understand=False)
        )

    @staticmethod
    def fulfill_text(value):
        if value is True:
            return CanFulfillSlotValues.YES
        return CanFulfillSlotValues.NO

    @staticmethod
    def understand_text(value):
        if value is True:
            return CanUnderstandSlotValues.YES
        if value is None:
            return CanUnderstandSlotValues.MAYBE
        return CanUnderstandSlotValues.NO

    def slot_state(self, name, can_fulfill=False, can_understand=False):
        return {
            "name": name,
            "can_fulfill": self.fulfill_text(can_fulfill),
            "can_understand": self.understand_text(can_understand),
        }

    def build_response(self):
        return self.response_builder.set_can_fulfill_intent(
            CanFulfillIntent(
                can_fulfill=self.can_fulfill_intent_text or CanFulfillIntentValues.NO,
                slots={
                    slot["name"]: CanFulfillSlot(
                        can_understand=slot["can_understand"],
                        can_fulfill=slot["can_fulfill"],
                    )
                    for slot in self.slots_fulfillment
                },
            )
        ).response

    def check_slots(self):
        if not self.slots:
            return

        for slot, _ in self.slots.items():
            if slot in self.CAN_FULFILL_AND_UNDERSTAND:
                self.can_fulfill_and_understand(slot)
            elif slot in self.CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION:
                self.can_fulfill_and_understand(slot)
            elif slot in self.CAN_FULFILL_AND_MAYBE_UNDERSTAND:
                self.can_fulfill_and_understand(slot)
            else:
                self.cannot_fulfill(slot)

    # pylint: disable=arguments-differ,too-many-branches
    def handle(self, handler_input):
        self.can_fulfill_intent()

        super().handle(handler_input)
        self.check_slots()
        response = self.build_response()

        return response


class CanFulfillGenericIntentHandler(CanFulfillIntentHandler):
    def can_handle(self, handler_input):
        return isinstance(
            handler_input.request_envelope.request, CanFulfillIntentRequest
        ) and (handler_input.request_envelope.request.intent.name not in ALL_INTENTS)

    # pylint: disable=arguments-differ,too-many-branches
    def handle(self, handler_input):
        super().handle(handler_input)
        self.can_fulfill_intent(no=True)
        self.check_slots()
        return self.build_response()


class CanFulfillPlayRandomIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"volume", "volume_percent"}


class CanFulfillPlayBlendIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"volume", "volume_percent"}
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"blend"}
    CAN_FULFILL_AND_MAYBE_UNDERSTAND = {"device"}


class CanFulfillPlayRadioArtistIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"volume", "volume_percent"}
    CAN_FULFILL_AND_MAYBE_UNDERSTAND = {"artists"}


class CanFulfillPlayRadioTrackIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"volume", "volume_percent"}
    CAN_FULFILL_AND_MAYBE_UNDERSTAND = {"tracks"}


class CanFulfillPlayRadioGenreIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"volume", "volume_percent"}
    CAN_FULFILL_AND_MAYBE_UNDERSTAND = {"genres"}


class CanFulfillDislikeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"thing"}
    CAN_FULFILL_AND_MAYBE_UNDERSTAND = {"artist"}


class CanFulfillDecreaseTuneableAttributeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"tuneable"}
    CAN_FULFILL_AND_UNDERSTAND = {"value"}


class CanFulfillFadeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"direction"}
    CAN_FULFILL_AND_UNDERSTAND = {"duration", "volume"}


class CanFulfillFadeDownIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"duration", "volume"}


class CanFulfillFadeUpIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND = {"duration", "volume"}


class CanFulfillIncreaseTuneableAttributeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"tuneable"}


class CanFulfillLikeIntentHandler(CanFulfillIntentHandler):
    pass


class CanFulfillMaxTuneableAttributeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"tuneable"}


class CanFulfillMinTuneableAttributeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"tuneable"}


class CanFulfillResetTuneableAttributeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"tuneable"}


class CanFulfillResetTuneableAttributesIntentHandler(CanFulfillIntentHandler):
    pass


class CanFulfillTuneAttributeIntentHandler(CanFulfillIntentHandler):
    CAN_FULFILL_AND_UNDERSTAND_WITH_RESOLUTION = {"tuneable"}
    CAN_FULFILL_AND_UNDERSTAND = {"tuneableValue"}


class CanFulfillListTuneablesIntentHandler(CanFulfillIntentHandler):
    pass


class CanFulfillListTuningIntentHandler(CanFulfillIntentHandler):
    pass
