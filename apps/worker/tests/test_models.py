import asyncio
from types import SimpleNamespace

import httpx2
import openai
import pytest
from azure.core.exceptions import ClientAuthenticationError
from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential

from pivot_worker import models
from pivot_worker.models import FoundryModelClient, ModelUnavailable, credential_from_env

REQUEST = httpx2.Request("POST", "https://example.openai.azure.com/openai/deployments/d/chat/completions")


def status_error(cls, code, param=None, message="error"):
    body = {"code": str(code), "param": param, "message": message}
    return cls(message, response=httpx2.Response(code, request=REQUEST), body=body)


def ok(text='{"ok": true}'):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
                           usage=SimpleNamespace(total_tokens=7))


class FakeCompletions:
    """Plays back a script of results; an exception is raised, a float sleeps that long first."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        step = self.script.pop(0)
        if isinstance(step, float):
            await asyncio.sleep(step)
            return ok()
        if isinstance(step, Exception):
            raise step
        return step


def client(*script):
    completions = FakeCompletions(script)
    fake = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return FoundryModelClient("https://x", {"standard": "std", "mini": "mini"}, client=fake), completions


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(models, "BACKOFF_SECONDS", 0.0)


def ask(foundry, timeout=1.0):
    return asyncio.run(foundry.complete_json("mini", [{"role": "user", "content": "hi"}], timeout=timeout))


@pytest.mark.parametrize("error", [
    ClientAuthenticationError("bad secret"),
    status_error(openai.AuthenticationError, 401),
    status_error(openai.NotFoundError, 404),
    status_error(openai.BadRequestError, 400, message="content filtered"),
])
def test_errors_that_will_not_go_away_are_unavailable_at_once(error):
    foundry, calls = client(error)
    with pytest.raises(ModelUnavailable, match=type(error).__name__):
        ask(foundry)
    assert len(calls.calls) == 1


@pytest.mark.parametrize("error", [
    status_error(openai.InternalServerError, 500),
    status_error(openai.RateLimitError, 429),
    openai.APIConnectionError(request=REQUEST),
])
def test_passing_errors_are_retried_then_unavailable(error):
    foundry, calls = client(error, error, error)
    with pytest.raises(ModelUnavailable):
        ask(foundry)
    assert len(calls.calls) == models.RETRIES + 1


def test_a_retry_can_succeed():
    foundry, calls = client(status_error(openai.InternalServerError, 503), ok("{}"))
    assert ask(foundry).text == "{}" and len(calls.calls) == 2


def test_the_timeout_covers_the_whole_attempt():
    foundry, calls = client(5.0, 5.0, 5.0)
    with pytest.raises(ModelUnavailable, match="TimeoutError"):
        ask(foundry, timeout=0.05)
    assert len(calls.calls) == models.RETRIES + 1


def test_a_refused_temperature_is_dropped_for_that_deployment():
    refused = status_error(openai.BadRequestError, 400, param="temperature",
                           message="Unsupported parameter: 'temperature' is not supported with this model.")
    foundry, calls = client(refused, ok(), ok())
    assert ask(foundry).text == '{"ok": true}'
    assert ask(foundry).text == '{"ok": true}'
    assert "temperature" in calls.calls[0]
    assert all("temperature" not in c and c["response_format"] == {"type": "json_object"} for c in calls.calls[1:])


def test_a_service_principal_is_used_when_its_secret_is_set(monkeypatch):
    monkeypatch.setenv("AZURE_TENANT_ID", "tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "not-a-real-secret")
    credential = credential_from_env()
    assert isinstance(credential, ClientSecretCredential)
    asyncio.run(credential.close())


def test_a_secret_without_its_ids_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("AZURE_TENANT_ID", raising=False)
    monkeypatch.setenv("AZURE_CLIENT_ID", "client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "not-a-real-secret")
    with pytest.raises(ValueError, match="AZURE_TENANT_ID"):
        credential_from_env()


def test_without_a_secret_managed_identity_is_never_probed(monkeypatch):
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)
    credential = credential_from_env()
    assert isinstance(credential, DefaultAzureCredential)
    assert not any("ManagedIdentity" in type(c).__name__ for c in credential.credentials)
    asyncio.run(credential.close())
