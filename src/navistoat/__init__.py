"""Public package entry points for Mirurain."""

import logging
from importlib.metadata import version

from loguru import logger
from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.instrumentation.tortoiseorm import TortoiseORMInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .app import main


def entrypoint() -> None:
    """Start Mirurain from the installed console script entry point."""
    resource = Resource.create(
        {
            "service.name": "navistoat",
            "service.version": version("navistoat"),
        }
    )

    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    # Logs
    logger_provider = LoggerProvider(resource=resource)
    set_logger_provider(logger_provider)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))

    otel_handler = LoggingHandler(
        level=logging.NOTSET,
        logger_provider=logger_provider,
    )

    logger.add(otel_handler, level="INFO", format="{message}")

    AioHttpClientInstrumentor().instrument()
    TortoiseORMInstrumentor().instrument()

    main()
