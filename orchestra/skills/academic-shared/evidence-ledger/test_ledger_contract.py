import json
import os
import re
import unittest
from pathlib import Path

from jsonschema import Draft7Validator

ROOT = Path(os.environ.get('ACADEMIC_SKILLS_ROOT', str(Path(__file__).resolve().parents[2])))
SCHEMA = json.loads((ROOT / 'academic-shared/evidence-ledger/ledger-schema.json').read_text(encoding='utf-8-sig'))


class LedgerContractTest(unittest.TestCase):
    def setUp(self):
        self.validator = Draft7Validator(SCHEMA)
        self.entry = dict(claim_id='CLM-001', section='3', paragraph_index=0,
                          claim_text='Accuracy is 92.3% on the held-out test set.',
                          source_ref='', source_excerpt=None, confidence='low',
                          claim_type='result', audit_status='pending')

    def valid(self, **changes):
        self.validator.validate(dict(self.entry, **changes))

    def test_protocol_json_examples(self):
        protocol = (ROOT / 'academic-shared/evidence-ledger/ledger-protocol.md').read_text(encoding='utf-8')
        examples = re.findall(r'```json\n(.*?)\n```', protocol, re.S)
        self.assertTrue(examples, 'Protocol must contain a valid example')
        for example in examples:
            self.validator.validate(json.loads(example))

    def test_legacy_pending_entry(self):
        self.valid()

    def test_contribution_link(self):
        self.valid(contribution_id='C1')

    def test_uncited_result_links_to_artifact(self):
        self.valid(evidence_kind='experiment', artifact_path='runs/EXP-001/metrics.json',
                   locator='metrics.test_accuracy', audit_status='verified',
                   confidence='high', claim_revision=1, manuscript_revision='draft-2')

    def test_missing_evidence_remains_auditable(self):
        self.valid(evidence_kind='missing', audit_status='orphan')

    def test_verified_needs_evidence_and_locator(self):
        for change in [dict(audit_status='verified'),
                       dict(audit_status='verified', source_excerpt='Measured accuracy 92.3%')]:
            with self.subTest(change=change):
                self.assertTrue(list(self.validator.iter_errors(dict(self.entry, **change))))

    def test_verified_literature(self):
        self.valid(evidence_kind='literature', source_ref='example2026',
                   source_excerpt='Measured accuracy was 92.3% on the test set.',
                   locator='p. 4, Table 2', audit_status='verified')

    def test_rejects_noncanonical_status(self):
        for status in ['discrepancy_found', 'needs_review']:
            with self.subTest(status=status):
                self.assertTrue(list(self.validator.iter_errors(dict(self.entry, audit_status=status))))

    def test_rejects_negative_paragraph_index(self):
        self.assertTrue(list(self.validator.iter_errors(dict(self.entry, paragraph_index=-1))))


if __name__ == '__main__':
    unittest.main()
