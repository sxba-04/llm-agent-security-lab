"""Public trace-context boundary regression for GHSA-mf5v-w3w3-f6cg.

FastAPI's web dependencies provide this parser. These tests exercise it directly
because the application does not configure a tracing provider by default.
"""
from __future__ import annotations

import unittest

try:
    from opentelemetry import trace
    from opentelemetry.context import Context
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    TraceContextTextMapPropagator = None


@unittest.skipUnless(TraceContextTextMapPropagator, "Install the web extra for trace-context tests")
class TraceContextBoundaryTests(unittest.TestCase):
    TRACE_ID = "1234567890abcdef1234567890abcdef"
    SPAN_ID = "1234567890abcdef"

    def setUp(self):
        self.propagator = TraceContextTextMapPropagator()

    def header(self, version="00"):
        return f"{version}-{self.TRACE_ID}-{self.SPAN_ID}-01"

    def test_sampled_context_and_tracestate_round_trip(self):
        carrier = {"traceparent": self.header(), "tracestate": "lab=review"}
        extracted = self.propagator.extract(carrier, context=Context())
        span_context = trace.get_current_span(extracted).get_span_context()
        self.assertTrue(span_context.is_valid)
        self.assertTrue(span_context.is_remote)
        self.assertEqual(span_context.trace_id, int(self.TRACE_ID, 16))
        self.assertEqual(span_context.span_id, int(self.SPAN_ID, 16))
        self.assertEqual(span_context.trace_flags, trace.TraceFlags.SAMPLED)
        self.assertEqual(span_context.trace_state["lab"], "review")

        injected = {}
        self.propagator.inject(injected, context=extracted)
        self.assertEqual(injected, carrier)

    def test_future_version_at_512_characters_is_accepted(self):
        prefix = self.header("01") + "-"
        header = prefix + "a" * (512 - len(prefix))
        self.assertEqual(len(header), 512)
        extracted = self.propagator.extract({"traceparent": header}, context=Context())
        span_context = trace.get_current_span(extracted).get_span_context()
        self.assertTrue(span_context.is_valid)
        self.assertTrue(span_context.is_remote)
        self.assertEqual(span_context.trace_id, int(self.TRACE_ID, 16))
        self.assertEqual(span_context.span_id, int(self.SPAN_ID, 16))

    def test_513_character_header_preserves_existing_context(self):
        # Version 1.45.1 imports this remote parent; the patched parser rejects it.
        prefix = self.header("01") + "-"
        header = prefix + "a" * (513 - len(prefix))
        self.assertEqual(len(header), 513)
        existing_span = trace.NonRecordingSpan(trace.SpanContext(
            trace_id=1, span_id=2, is_remote=False,
        ))
        original = trace.set_span_in_context(existing_span, Context())
        extracted = self.propagator.extract({"traceparent": header}, context=original)
        self.assertIs(extracted, original)
        self.assertIs(trace.get_current_span(extracted), existing_span)

    def test_malformed_whitespace_and_newline_suffix_is_rejected(self):
        # Keep the malformed carrier bounded; no wall-clock timing assertion.
        header = self.header("01") + "-" + " " * 100 + "\nx"
        original = Context()
        extracted = self.propagator.extract({"traceparent": header}, context=original)
        self.assertIs(extracted, original)
        self.assertFalse(trace.get_current_span(extracted).get_span_context().is_valid)


if __name__ == "__main__":
    unittest.main()
