import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/ai-editor/lib/ai_editor'))


class IntegrationRouteTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('integrations_http'), 'Integration routes are not implemented')
        self.routes = importlib.import_module('integrations_http')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.old = {key: os.environ.get(key) for key in ('AI_EDITOR_HOME', 'AI_EDITOR_LIBRARY')}
        os.environ['AI_EDITOR_HOME'] = str(Path(self.tmp.name) / 'runtime')
        os.environ['AI_EDITOR_LIBRARY'] = str(Path(self.tmp.name) / 'library')
        self.addCleanup(self.restore)
        self.home = importlib.import_module('home')
        self.home.update(lambda d: d.update(root=os.environ['AI_EDITOR_LIBRARY']))
        self.sent = []
        self.handler = type('Handler', (), {'send': lambda s, code, data: self.sent.append((code, data))})()

    def restore(self):
        for key, val in self.old.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val

    def test_unrecognized_edit_path_never_reaches_resolve(self):
        self.routes.route(self.handler, 'POST', '/integrations/resolve/create', {'edit': '/tmp/unrelated-project'}, self.home)
        self.assertEqual(self.sent[-1][0], 400)
        self.assertIn('library', self.sent[-1][1]['error'])

    def test_only_edits_with_source_decisions_are_offered_for_resolve(self):
        library = Path(os.environ['AI_EDITOR_LIBRARY'])
        for name in ('source-cut', 'preview-only'):
            (library / 'edits' / name).mkdir(parents=True)
        (library / 'edits/source-cut/decisions.json').write_text(json.dumps({'source': 'synthetic.mp4', 'keep': []}), encoding='utf-8')
        self.routes.route(self.handler, 'GET', '/integrations/edits', {}, self.home)
        self.assertEqual(self.sent[-1][0], 200)
        self.assertEqual([e['name'] for e in self.sent[-1][1]['edits']], ['source-cut'])

    def test_generation_requires_an_explicit_boolean_confirmation(self):
        self.routes.route(self.handler, 'POST', '/integrations/higgsfield/generate', {'quote_id': 'unknown', 'confirmed': 'true'}, self.home)
        self.assertEqual(self.sent[-1][0], 400)
        self.assertIn('confirm', self.sent[-1][1]['error'].lower())


if __name__ == '__main__':
    unittest.main()
