import asyncio

from pivot_adapters.azure import WebPubSubLivePublisher, WebPubSubNegotiator


class FakeClient:
    """Stands in for azure.messaging.webpubsubservice.aio.WebPubSubServiceClient."""

    def __init__(self):
        self.sent = []
        self.token_requests = []

    async def send_to_group(self, group, message, *, content_type=None, **kwargs):
        self.sent.append((group, message, content_type))

    async def get_client_access_token(self, **kwargs):
        self.token_requests.append(kwargs)
        return {"token": "t", "baseUrl": "wss://x.webpubsub.azure.com/client/hubs/pivot",
                "url": "wss://x.webpubsub.azure.com/client/hubs/pivot?access_token=t"}


def test_publish_sends_the_envelope_json_to_the_match_group(make_envelope):
    client = FakeClient()
    asyncio.run(WebPubSubLivePublisher(client).publish(make_envelope(7)))
    [(group, message, content_type)] = client.sent
    assert group == "match.m1" and content_type == "application/json"
    assert message["seq"] == 7 and message["match_id"] == "m1" and message["payload"] == {"seq": 7}


def test_negotiate_returns_a_client_url_that_joins_the_match_group():
    client = FakeClient()
    url = asyncio.run(WebPubSubNegotiator(client, minutes_to_expire=30).negotiate("m1"))
    assert url.startswith("wss://") and "access_token=" in url
    assert client.token_requests == [{"groups": ["match.m1"], "minutes_to_expire": 30}]
