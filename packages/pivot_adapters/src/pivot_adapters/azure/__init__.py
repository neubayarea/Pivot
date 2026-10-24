"""Profiles C1/C2: Azure adapters. Only the Web PubSub pair (A06) exists so far; A08 adds the rest
and wires them into `build_adapters`."""

from .webpubsub import WebPubSubLivePublisher, WebPubSubNegotiator, group_name

__all__ = ["WebPubSubLivePublisher", "WebPubSubNegotiator", "group_name"]
