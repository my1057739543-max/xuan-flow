"""Model factory — creates LLM instances from config.yaml.

Simplified from deer-flow: no reflection, no thinking/vision toggles.
Directly uses langchain_openai.ChatOpenAI for OpenAI-compatible APIs.
"""

import logging

from langchain_openai import ChatOpenAI

from xuan_flow.config.app_config import get_app_config

logger = logging.getLogger(__name__)


def create_chat_model(name: str | None = None, **kwargs) -> ChatOpenAI:
    """Create a ChatOpenAI instance from config.

    Args:
        name: Model name from config.yaml. If None, uses the first model.
        **kwargs: Additional kwargs passed to ChatOpenAI constructor.

    Returns:
        A ChatOpenAI instance.
    """
    config = get_app_config()

    if not config.models:
        raise ValueError("No models configured in config.yaml")

    if name is None:
        model_config = config.models[0]
    else:
        model_config = config.get_model_config(name)
        if model_config is None:
            logger.warning("Model '%s' not found, falling back to default '%s'", name, config.models[0].name)
            model_config = config.models[0]

    # Build constructor args from config
    model_kwargs = {
        "model": model_config.model,
        "temperature": model_config.temperature,
        "max_tokens": model_config.max_tokens,
    }

    if model_config.api_key:
        model_kwargs["api_key"] = model_config.api_key
    if model_config.base_url:
        model_kwargs["base_url"] = model_config.base_url

    # Caller overrides take precedence
    model_kwargs.update(kwargs)

    logger.info("Creating model: %s (%s)", model_config.name, model_config.model)
    return ChatOpenAI(**model_kwargs)
