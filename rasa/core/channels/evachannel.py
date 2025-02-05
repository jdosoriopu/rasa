import logging
from typing import Text, Dict, Optional, Callable, Awaitable, Any

from sanic import Blueprint, response
from sanic.request import Request

from rasa.core.channels.channel import (
    OutputChannel,
    UserMessage,
    RestInput,
    InputChannel,
)
from rasa.utils.endpoints import EndpointConfig, ClientResponseError
from sanic.response import HTTPResponse

logger = logging.getLogger(__name__)


class EvaOutput(OutputChannel):
    @classmethod
    def name(cls) -> Text:
        return "evachannel"

    def __init__(self, endpoint: EndpointConfig, device: Text) -> None:

        self.eva_endpoint = endpoint
        self.device = device
        super().__init__()

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        """Send a message through this channel."""

        try:
            await self.eva_endpoint.request(
                "post", content_type="application/json", json={ "from": self.device, "to": recipient_id, "text": text }
            )
        except ClientResponseError as e:
            logger.error(
                "Failed to send output message to WhatsAppi. "
                "Status: {} Response: {}"
                "".format(e.status, e.text)
            )


class EvaInput(RestInput):

    @classmethod
    def name(cls) -> Text:
        return "evachannel"

    @classmethod
    def from_credentials(cls, credentials: Optional[Dict[Text, Any]]) -> InputChannel:
        return cls(EndpointConfig.from_dict(credentials))

    def __init__(self, endpoint: EndpointConfig) -> None:
        self.eva_endpoint = endpoint

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        evachannel_webhook = Blueprint("evachannel_webhook", __name__)

        @evachannel_webhook.route("/", methods=["GET"])
        async def health(_: Request):
            return response.json({"status": "ok"})

        @evachannel_webhook.route("/webhook", methods=["POST"])
        async def webhook(request: Request) -> HTTPResponse:
            sender = request.json.get("contact", None)
            text = request.json.get("message", None)
            device = request.json.get("device", None)

            output_channel = self.get_output_channel(device)

            if "#eva" in text.lower():       

                await on_new_message(
                    UserMessage("/restart", output_channel, sender, input_channel=self.name())
                )

                await on_new_message(
                    UserMessage("/start_bot", output_channel, sender, input_channel=self.name())
                )

            else:
                
                await on_new_message(
                    UserMessage(text, output_channel, sender, input_channel=self.name())
                )
                
            return response.text("success")

        return evachannel_webhook

    def get_output_channel(self, device: Text) -> OutputChannel:
        return EvaOutput(self.eva_endpoint, device)