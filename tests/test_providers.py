from copy import deepcopy
import base64
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from security_lab.budget import BudgetLedger
from security_lab.contracts import BudgetExceeded, ModelError, ReceivedResponseError
from security_lab.providers import API_URL, OpenAIModel, _NoRedirect, _http_transport, validate_config


CONFIG = {
    'enabled': True, 'model': 'configured-test-model', 'max_completion_tokens': 100,
    'max_input_tokens': 20000, 'timeout_seconds': 1, 'input_eur_per_million': 1,
    'output_eur_per_million': 2, 'run_budget_eur': 0.1, 'max_requests': 3,
    'price_reference': 'test-only invented rates, not actual prices', 'price_checked_on': '2026-10-22',
}
MESSAGES = [{'role': 'user', 'content': 'Read the synthetic ticket.'}]
TOOLS = [{'type': 'function', 'function': {'name': 'read_ticket', 'strict': True,
         'parameters': {'type': 'object', 'properties': {'ticket_id': {'type': 'string'}},
                        'required': ['ticket_id'], 'additionalProperties': False}}}]


def response(text='Example answer', args=None, usage=True):
    message = {'role': 'assistant', 'content': text}
    finish = 'stop'
    if args is not None:
        message['tool_calls'] = [{'id': 'call_1', 'type': 'function',
                                 'function': {'name': 'read_ticket', 'arguments': args}}]
        finish = 'tool_calls'
    value = {'id': 'response-test', 'model': 'resolved-test-model',
             'choices': [{'message': message, 'finish_reason': finish}]}
    if usage:
        value['usage'] = {'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120}
    return value


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = BudgetLedger(Path(self.tmp.name) / 'budget.json', 1, 1)

    def make_model(self, transport, **changes):
        return OpenAIModel({**CONFIG, **changes}, 'FAKE-TEST-KEY', self.ledger, transport)

    def test_disabled_config_cannot_send_requests(self):
        with self.assertRaises(ValueError):
            self.make_model(lambda *args: self.fail('transport called'), enabled=False)
        with self.assertRaises(ValueError):
            self.make_model(lambda *args: self.fail('transport called'), model='')
        with self.assertRaises(ValueError):
            self.make_model(lambda *args: self.fail('transport called'), input_eur_per_million=None)
        self.assertFalse(self.ledger.path.exists())

    def test_config_whitelist_rejects_nested_secrets_before_reserving_or_sending(self):
        for fields in ({'auth': {'api_key': 'FAKE-NESTED-SECRET'}},
                       {'metadata': [{'authorization': 'FAKE-NESTED-SECRET'}]},
                       {'price_reference': {'api_key': 'FAKE-NESTED-SECRET'}},
                       {'model': ['FAKE-NESTED-SECRET']}):
            with self.subTest(fields=fields), self.assertRaises(ValueError) as caught:
                self.make_model(lambda *args: self.fail('transport called'), **fields)
            self.assertNotIn('FAKE-NESTED-SECRET', str(caught.exception))
        self.assertFalse(self.ledger.path.exists())

    def test_validated_config_is_safe_and_disabled_template_remains_loadable(self):
        value = validate_config(CONFIG)
        self.assertEqual(value['input_eur_per_million'], '1')
        self.assertEqual(value['run_budget_eur'], '0.1')
        self.assertIsNot(value, CONFIG)
        json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
        template = json.loads((Path(__file__).parents[1] / 'configs/api.example.json').read_text())
        self.assertFalse(validate_config(template)['enabled'])
        for fields in ({'model': '\ud800'}, {'temperature': float('nan')},
                       {'timeout_seconds': float('inf')}, {'input_eur_per_million': 'NaN'},
                       {'enabled': 1}, {'max_requests': True}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                validate_config({**CONFIG, **fields})

    def test_payload_and_response_are_auditable_and_reserved_first(self):
        captured = []
        def transport(payload, key, timeout):
            self.assertGreater(float(self.ledger.snapshot()['accounted_eur']), 0)
            captured.append(payload)
            return response(None, '{"ticket_id":"A17"}')
        reply = self.make_model(transport).respond(MESSAGES, TOOLS)
        self.assertFalse(captured[0]['parallel_tool_calls'])
        self.assertFalse(captured[0]['store'])
        self.assertNotIn('temperature', captured[0])
        self.assertEqual(captured[0]['max_completion_tokens'], 100)
        self.assertEqual(reply.tool_calls[0].arguments, {'ticket_id': 'A17'})
        self.assertEqual(reply.usage['model'], 'resolved-test-model')
        self.assertEqual(reply.usage['accounting'], 'reported_usage')
        self.assertEqual(float(self.ledger.snapshot()['accounted_eur']), 0.00014)
        self.assertNotIn('FAKE-TEST-KEY', self.ledger.path.read_text())
        self.assertNotIn('FAKE-TEST-KEY', json.dumps(reply.usage))

    def test_transport_failure_is_sanitized_and_not_retried(self):
        calls = []
        def fail(*args):
            calls.append(1)
            raise OSError('FAKE-TEST-KEY proxy-secret')
        with self.assertRaises(ModelError) as caught:
            self.make_model(fail).respond(MESSAGES, TOOLS)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('FAKE-TEST-KEY', str(caught.exception))
        state = self.ledger.snapshot()
        self.assertGreater(float(state['accounted_eur']), 0)
        self.assertEqual(next(iter(state['reservations'].values()))['state'], 'reserved')

    def test_missing_usage_keeps_reservation_but_preserves_response(self):
        reply = self.make_model(lambda *args: response(usage=False)).respond(MESSAGES, TOOLS)
        self.assertEqual(reply.usage['accounting'], 'reservation_retained')
        self.assertGreater(float(self.ledger.snapshot()['accounted_eur']), 0)
        self.assertEqual(reply.text, 'Example answer')

    def test_generated_invalid_arguments_remain_observable_proposals(self):
        for args in ('{bad json', '[]', 'null', 'true', '{"value":NaN}',
                     '{"value":Infinity}', '{"value":-Infinity}', '{"value":1e309}',
                     '{"text":"\\ud800"}', '{"nested":[{"value":NaN}]}'):
            with self.subTest(args=args):
                reply = self.make_model(lambda *a: response(None, args)).respond(MESSAGES, TOOLS)
                self.assertEqual(reply.tool_calls[0].arguments, {'__invalid_arguments_json__': args})
                self.assertEqual(reply.usage['raw_response']['choices'][0]['message']['tool_calls'][0]['function']['arguments'], args)
                json.dumps(reply.usage, ensure_ascii=False, allow_nan=False).encode('utf-8')
                json.dumps(reply.tool_calls[0].arguments, ensure_ascii=False, allow_nan=False).encode('utf-8')

    def test_unsafe_response_values_keep_escaped_evidence_and_valid_accounting(self):
        for position in ('content', 'refusal', 'model', 'id', 'usage', 'tool_id', 'tool_name'):
            raw = response(None, '{"ticket_id":"A17"}')
            if position in ('content', 'refusal'):
                raw['choices'][0]['message'][position] = '\ud800'
            elif position in ('model', 'id'):
                raw[position] = '\ud800'
            elif position == 'usage':
                raw['usage']['details'] = {'unsafe': float('inf')}
            elif position == 'tool_id':
                raw['choices'][0]['message']['tool_calls'][0]['id'] = '\ud800'
            else:
                raw['choices'][0]['message']['tool_calls'][0]['function']['name'] = '\ud800'
            with self.subTest(position=position), self.assertRaises(ReceivedResponseError) as caught:
                self.make_model(lambda *args: raw).respond(MESSAGES, TOOLS)
            usage = caught.exception.usage
            self.assertIsNone(usage['raw_response'])
            self.assertEqual(usage['raw_response_escaped'], json.dumps(raw, ensure_ascii=True, allow_nan=True))
            self.assertFalse(usage['raw_response_escaped_truncated'])
            self.assertEqual(usage['accounting'], 'reported_usage')
            json.dumps(usage, ensure_ascii=False, allow_nan=False).encode('utf-8')

    def test_invalid_response_structure_still_settles_and_preserves_exact_raw(self):
        raw = response(None, '{"ticket_id":"A17"}')
        raw['choices'][0]['message']['tool_calls'] *= 2
        with self.assertRaises(ReceivedResponseError) as caught:
            self.make_model(lambda *args: raw).respond(MESSAGES, TOOLS)
        self.assertEqual(caught.exception.usage['raw_response'], raw)
        self.assertEqual(caught.exception.usage['accounting'], 'reported_usage')
        self.assertEqual(float(self.ledger.snapshot()['accounted_eur']), 0.00014)

    def test_received_invalid_http_body_has_bounded_evidence_not_transport_uncertainty(self):
        for body in (b'{invalid-json', b'\xff', b'[]'):
            opener = unittest.mock.MagicMock()
            received = opener.open.return_value.__enter__.return_value
            received.status = 200
            received.read.return_value = body
            with self.subTest(body=body), patch('security_lab.providers.urllib.request.build_opener', return_value=opener):
                with self.assertRaises(ReceivedResponseError) as caught:
                    self.make_model(_http_transport).respond(MESSAGES, TOOLS)
            usage = caught.exception.usage
            self.assertEqual(usage['accounting'], 'reservation_retained')
            self.assertIn('reservation_id', usage)
            json.dumps(usage, ensure_ascii=False, allow_nan=False).encode('utf-8')

    def test_http_open_failure_does_not_claim_received_response(self):
        for failure in (TimeoutError('FAKE-TEST-KEY'), OSError('FAKE-TEST-KEY')):
            opener = unittest.mock.Mock()
            opener.open.side_effect = failure
            with self.subTest(failure=type(failure).__name__), patch(
                    'security_lab.providers.urllib.request.build_opener', return_value=opener):
                with self.assertRaises(ModelError) as caught:
                    self.make_model(_http_transport).respond(MESSAGES, TOOLS)
            self.assertNotIsInstance(caught.exception, ReceivedResponseError)
            self.assertNotIn('FAKE-TEST-KEY', str(caught.exception))
            self.assertEqual(opener.open.call_count, 1)
        self.assertTrue(all(value['state'] == 'reserved' for value in self.ledger.snapshot()['reservations'].values()))

    def test_oversized_received_evidence_is_bounded_and_marked_truncated(self):
        raw = response('x' * 2000)
        with patch('security_lab.providers.MAX_RESPONSE_BYTES', 1024):
            with self.assertRaises(ReceivedResponseError) as caught:
                self.make_model(lambda *args: raw).respond(MESSAGES, TOOLS)
        usage = caught.exception.usage
        self.assertEqual(len(usage['raw_response_escaped']), 1024)
        self.assertTrue(usage['raw_response_escaped_truncated'])
        self.assertGreater(usage['raw_response_escaped_bytes'], 1024)
        self.assertEqual(len(usage['raw_response_escaped_sha256']), 64)
        self.assertEqual(usage['accounting'], 'reported_usage')
        opener = unittest.mock.MagicMock()
        received = opener.open.return_value.__enter__.return_value
        received.status = 200
        received.read.return_value = b'x' * 1025
        with patch('security_lab.providers.MAX_RESPONSE_BYTES', 1024), patch(
                'security_lab.providers.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(ReceivedResponseError) as caught:
                self.make_model(_http_transport).respond(MESSAGES, TOOLS)
        usage = caught.exception.usage
        self.assertEqual(base64.b64decode(usage['raw_response_body_base64']), b'x' * 1024)
        self.assertTrue(usage['raw_response_body_truncated'])
        self.assertEqual(usage['accounting'], 'reservation_retained')

    def test_malformed_response_keeps_reservation(self):
        with self.assertRaises(ModelError):
            self.make_model(lambda *args: {'choices': []}).respond(MESSAGES, TOOLS)
        self.assertGreater(float(self.ledger.snapshot()['accounted_eur']), 0)

    def test_budget_and_input_limits_prevent_transport(self):
        fail = lambda *args: self.fail('transport called')
        with self.assertRaises(BudgetExceeded):
            self.make_model(fail, run_budget_eur=0.000001).respond(MESSAGES, TOOLS)
        with self.assertRaises(BudgetExceeded):
            self.make_model(fail, max_input_tokens=1).respond(MESSAGES, TOOLS)
        self.assertFalse(self.ledger.path.exists())

    def test_request_count_is_bounded(self):
        model = self.make_model(lambda *args: response(), max_requests=1)
        model.respond(MESSAGES, TOOLS)
        with self.assertRaises(BudgetExceeded):
            model.respond(MESSAGES, TOOLS)

    def test_accounting_overrun_records_cost_and_blocks_next_call(self):
        large = response()
        large['usage'] = {'prompt_tokens': 100000, 'completion_tokens': 0, 'total_tokens': 100000}
        model = self.make_model(lambda *args: large, run_budget_eur=1)
        reply = model.respond(MESSAGES, TOOLS)
        self.assertTrue(reply.usage['budget_overrun'])
        self.assertTrue(self.ledger.snapshot()['halted'])
        with self.assertRaises(BudgetExceeded):
            model.respond(MESSAGES, TOOLS)

    def test_refusals_and_output_limits_are_retained(self):
        refusal = response(None)
        refusal['choices'][0]['message']['refusal'] = 'Unable to comply'
        reply = self.make_model(lambda *args: refusal).respond(MESSAGES, TOOLS)
        self.assertEqual(reply.finish_reason, 'content_filter')
        self.assertEqual(reply.text, 'Unable to comply')
        limited = response('Partial')
        limited['choices'][0]['finish_reason'] = 'length'
        reply = self.make_model(lambda *args: limited).respond(MESSAGES, TOOLS)
        self.assertEqual(reply.finish_reason, 'length')

    def test_post_response_settlement_failure_keeps_received_evidence(self):
        model = self.make_model(lambda *args: response(None, '{"ticket_id":"A17"}'))
        with patch.object(self.ledger, 'settle', side_effect=BudgetExceeded('locked')):
            reply = model.respond(MESSAGES, TOOLS)
        self.assertTrue(reply.usage['accounting_error'])
        self.assertEqual(reply.usage['accounting'], 'settlement_failed')
        self.assertEqual(reply.usage['raw_response']['id'], 'response-test')
        self.assertEqual(reply.tool_calls[0].arguments, {'ticket_id': 'A17'})
        self.assertEqual(next(iter(self.ledger.snapshot()['reservations'].values()))['state'], 'reserved')

    def test_model_drift_is_flagged_without_losing_response_or_accounting(self):
        responses = [response(), response(None, '{"ticket_id":"A17"}'), response()]
        responses[1]['model'] = 'unexpected-new-snapshot'
        model = self.make_model(lambda *args: responses.pop(0))
        first = model.respond(MESSAGES, TOOLS)
        self.assertFalse(first.usage['model_version_changed'])
        changed = model.respond(MESSAGES, TOOLS)
        self.assertTrue(changed.usage['model_version_changed'])
        self.assertEqual(changed.usage['expected_returned_model'], 'resolved-test-model')
        self.assertEqual(changed.usage['raw_response']['model'], 'unexpected-new-snapshot')
        self.assertEqual(changed.usage['accounting'], 'reported_usage')
        self.assertEqual(changed.tool_calls[0].arguments, {'ticket_id': 'A17'})
        third = model.respond(MESSAGES, TOOLS)
        self.assertTrue(third.usage['model_version_changed'])
        self.assertAlmostEqual(float(self.ledger.snapshot()['accounted_eur']), 0.00042)

    def test_expected_model_detects_drift_in_first_request(self):
        model = self.make_model(lambda *args: response(), expected_returned_model='frozen-snapshot')
        reply = model.respond(MESSAGES, TOOLS)
        self.assertTrue(reply.usage['model_version_changed'])
        self.assertEqual(reply.usage['expected_returned_model'], 'frozen-snapshot')
        self.assertEqual(reply.usage['accounting'], 'reported_usage')

    def test_duplicate_call_ids_and_inconsistent_finish_reason_rejected(self):
        duplicate = response(None, '{"ticket_id":"A17"}')
        duplicate['choices'][0]['message']['tool_calls'] *= 2
        stopped = response(None, '{"ticket_id":"A17"}')
        stopped['choices'][0]['finish_reason'] = 'stop'
        for invalid in (duplicate, stopped):
            with self.subTest(invalid=invalid), self.assertRaises(ModelError):
                self.make_model(lambda *args: invalid).respond(MESSAGES, TOOLS)

    def test_redirects_are_refused_without_forwarding_credentials(self):
        request = urllib.request.Request(API_URL, headers={'Authorization': 'Bearer FAKE-TEST-KEY'})
        self.assertIsNone(_NoRedirect().redirect_request(request, None, 302, '', {}, 'https://example.invalid'))
        opener = unittest.mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError(API_URL, 302, 'redirect', {}, None)
        with patch('security_lab.providers.urllib.request.build_opener', return_value=opener):
            with self.assertRaises(ModelError) as caught:
                _http_transport({}, 'FAKE-TEST-KEY', 1)
        self.assertNotIn('FAKE-TEST-KEY', str(caught.exception))
        self.assertEqual(opener.open.call_count, 1)


if __name__ == '__main__':
    unittest.main()
