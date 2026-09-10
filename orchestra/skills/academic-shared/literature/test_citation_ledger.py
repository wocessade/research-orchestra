import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(os.environ.get('ACADEMIC_SKILLS_ROOT', str(Path(__file__).resolve().parents[2])))
SCRIPT = ROOT / 'academic-shared/literature/verify_citations.py'
spec = importlib.util.spec_from_file_location('verify_citations_tested', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CitationLedgerTest(unittest.TestCase):
    def run_check(self, entries, refs):
        base = Path(os.environ.get('ACADEMIC_TEST_TMP', 'D:/Temp/academic-evidence-repair/tests'))
        base.mkdir(parents=True, exist_ok=True)
        self.folder = Path(tempfile.mkdtemp(dir=base))
        self.ledger = self.folder / 'ledger.jsonl'
        self.report = self.folder / 'report.json'
        self.ledger.write_text('\n'.join(json.dumps(e) for e in entries), encoding='utf-8')
        self.report.write_text(json.dumps({'entries': refs}), encoding='utf-8')
        module.validate_ledger(self.ledger, self.report, self.folder)
        return json.loads((self.folder / 'ledger_validation.json').read_text())

    def test_unknown_and_empty_references_are_not_silently_verified(self):
        r = self.run_check([{'claim_id': 'CLM-001', 'source_ref': ''},
                            {'claim_id': 'CLM-002', 'source_ref': 'unknown'}], [])
        self.assertEqual(r['orphan_claims'], 2)

    def test_title_verified_reference_does_not_require_doi(self):
        r = self.run_check([{'claim_id': 'CLM-001', 'source_ref': 'paper'}],
                          [{'citation_key': 'paper', 'doi': None, 'verdict': 'true'}])
        self.assertEqual(r['orphan_claims'], 0)
        self.assertEqual(r['metadata_matched_claims'], 1)
        self.assertEqual(r['support_check'], 'not_performed')

    def test_internal_artifact_is_not_an_orphan_citation(self):
        r = self.run_check([{'claim_id': 'CLM-001', 'source_ref': '',
                            'evidence_kind': 'experiment', 'artifact_path': 'metrics.json'}], [])
        self.assertEqual(r['orphan_claims'], 0)
        self.assertEqual(r['internal_evidence_claims'], 1)
        self.assertEqual(r['support_check'], 'not_performed')

    def test_revisions_do_not_hide_changed_missing_evidence(self):
        r = self.run_check([{'claim_id': 'CLM-001', 'source_ref': 'paper', 'claim_revision': 1},
                            {'claim_id': 'CLM-001', 'source_ref': '', 'claim_revision': 2}],
                          [{'citation_key': 'paper', 'doi': '10.1/example', 'verdict': 'true'}])
        self.assertEqual(r['ledger_entries'], 1)
        self.assertEqual(r['orphan_claims'], 1)

    def test_ledger_only_cli_needs_no_input_or_network(self):
        self.run_check([], [])
        r = subprocess.run([sys.executable, str(SCRIPT), '--validate-ledger', str(self.ledger),
                            '--verification-report', str(self.report), '--output-dir', str(self.folder)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main()
