"""Behavioral board tests use original media and immutable revision artifacts."""
import copy
import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

LIB = Path(__file__).resolve().parents[1] / 'plugins/ai-editor/lib/ai_editor'
sys.path.insert(0, str(LIB))


class EditBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_tmp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.media_tmp.name) / 'source.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=30',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '8',
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', str(cls.source)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.media_tmp.cleanup()

    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('edit_board'), 'Edit board is not implemented')
        self.mod = importlib.import_module('edit_board')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.edit = Path(self.tmp.name)
        self.original = {'source': str(self.source), 'fps': 30, 'frames': [[0, 60], [120, 240]]}
        (self.edit / 'report.json').write_text(json.dumps(self.original), encoding='utf-8')
        (self.edit / 'decisions.json').write_text(json.dumps([{'start': 0, 'end': 2}, {'start': 4, 'end': 8}]), encoding='utf-8')
        (self.edit / 'words.raw.json').write_text(json.dumps([
            {'word': 'Start', 'start': .2, 'end': 1}, {'word': 'Hold', 'start': 2.2, 'end': 3.8},
            {'word': 'Finish', 'start': 4.2, 'end': 6}]), encoding='utf-8')

    def ready(self):
        state = self.mod.load(self.edit)
        out = self.mod.preview(self.edit, state['version'])
        rid = out['revision']['id']
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            state = self.mod.load(self.edit)
            rev = next(r for r in state['revisions'] if r['id'] == rid)
            if rev['state'] != 'rendering':
                self.assertEqual(rev['state'], 'ready', rev)
                return state, rid
            time.sleep(.08)
        self.fail('Preview did not finish')

    def test_revision_binds_word_snapshot_without_changing_legacy_digest(self):
        state,rid=self.ready()
        folder=self.mod.revision_dir(self.edit,rid)
        self.assertTrue((folder/'words.json').is_file(), 'Revision must snapshot word timings')
        before=self.mod.artifacts(folder)
        (folder/'words.json').write_text('[]',encoding='utf-8')
        self.assertNotEqual(self.mod.artifacts(folder),before)
        (folder/'words.json').unlink()
        legacy=self.mod.fingerprint([folder/x for x in ('decisions.json','report.json','plan.json','board-rows.json')])
        self.assertEqual(self.mod.artifacts(folder),legacy)

    def test_compare_requires_approved_current_native_revision(self):
        self.assertTrue(hasattr(self.mod,'compare_resolve'),'Resolve comparison is missing')
        state,rid=self.ready()
        with self.assertRaisesRegex(ValueError,'Approve|native|timeline'):self.mod.compare_resolve(self.edit,rid,state['version'])
        self.mod.approve(self.edit,rid,state['version'])
        with self.assertRaisesRegex(ValueError,'native|timeline'):self.mod.compare_resolve(self.edit,rid,state['version'])

    def test_nonfinite_word_metadata_becomes_static_fallback_without_changing_source(self):
        original=json.dumps([{'word':'Broken','start':0,'end':float('nan')}])
        (self.edit/'words.raw.json').write_text(original,encoding='utf-8')
        state=self.mod.load(self.edit);state['rows'][0].update(caption='Timing fallback',caption_enabled=True,caption_treatment='clean')
        self.mod.save(self.edit,state['version'],state['rows'])
        state,rid=self.ready();folder=self.mod.revision_dir(self.edit,rid)
        self.assertEqual(json.loads((folder/'words.json').read_text(encoding='utf-8'))[0]['end'],None)
        self.assertEqual(json.loads((folder/'visuals.json').read_text(encoding='utf-8'))['layers'][0]['timing'],'passage fallback')
        self.assertEqual((self.edit/'words.raw.json').read_text(encoding='utf-8'),original)

    def test_ready_preview_exposes_actual_timing_fallback_before_approval(self):
        state=self.mod.load(self.edit);state['rows'][0].update(caption='A correction',caption_enabled=True,caption_treatment='spotlight')
        self.mod.save(self.edit,state['version'],state['rows']);state,rid=self.ready()
        rev=next(r for r in state['revisions'] if r['id']==rid)
        self.assertTrue(rev.get('visual_summary'),'Compiled timing needs a pre-approval surface')
        caption=next(v for v in rev['visual_summary'] if v['kind']=='caption')
        self.assertEqual(caption['timing'],'passage fallback');self.assertEqual(caption['passage_id'],state['rows'][0]['id'])

    def test_restore_maps_source_intervals_and_preserves_original_files(self):
        state = self.mod.load(self.edit)
        self.assertEqual([(r['start_frame'], r['end_frame'], r['keep']) for r in state['rows']],
                         [(0, 60, True), (60, 120, False), (120, 240, True)])
        self.assertEqual(state['rows'][1]['text'], 'Hold')
        rows = copy.deepcopy(state['rows']); rows[1].update(keep=True, protected=True, note='Let action finish')
        saved = self.mod.save(self.edit, state['version'], rows)
        self.assertEqual(saved['selected_frames'], 240)
        self.assertEqual(self.mod.load(self.edit)['rows'][1]['note'], 'Let action finish')
        self.assertEqual(json.loads((self.edit / 'report.json').read_text(encoding='utf-8')), self.original)
        self.assertEqual(json.loads((self.edit / 'decisions.json').read_text(encoding='utf-8')),
                         [{'start': 0, 'end': 2}, {'start': 4, 'end': 8}])

    def test_stale_save_does_not_erase_another_tabs_correction(self):
        state = self.mod.load(self.edit)
        rows = copy.deepcopy(state['rows']); rows[0]['note'] = 'Keep this correction'
        self.mod.save(self.edit, state['version'], rows)
        with self.assertRaisesRegex(ValueError, 'changed|Reload'):
            self.mod.save(self.edit, state['version'], state['rows'])
        self.assertEqual(self.mod.load(self.edit)['rows'][0]['note'], 'Keep this correction')

    def test_missing_version_cannot_bypass_concurrent_save_guard(self):
        s = self.mod.load(self.edit)
        for version in (None, True, '1'):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.mod.save(self.edit, version, s['rows'])

    def test_protected_hold_requires_unprotecting_before_drop(self):
        s = self.mod.load(self.edit); rows = copy.deepcopy(s['rows'])
        rows[0]['protected'] = True
        s = self.mod.save(self.edit, s['version'], rows)
        rows[0]['keep'] = False
        with self.assertRaisesRegex(ValueError, 'protected|Protected'):
            self.mod.save(self.edit, s['version'], rows)

    def test_invalid_row_identity_ranges_and_zoom_never_save(self):
        state = self.mod.load(self.edit)
        for key, value in [('id', '../other'), ('end_frame', 9999), ('zoom', float('nan')),
                           ('keep', 'true'), ('note', 'x' * 4001)]:
            with self.subTest(key=key):
                rows = copy.deepcopy(state['rows']); rows[0][key] = value
                with self.assertRaises(ValueError): self.mod.save(self.edit, state['version'], rows)
        self.assertEqual(self.mod.load(self.edit)['version'], state['version'])

    def test_changed_inputs_invalidate_draft_before_render(self):
        s = self.mod.load(self.edit)
        (self.edit / 'decisions.json').write_text('[]', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed|source|Source'):
            self.mod.preview(self.edit, s['version'])

    def test_preview_contains_exact_selected_frames_and_audio(self):
        s, rid = self.ready()
        p = self.edit / 'board-revisions' / rid
        self.assertEqual(json.loads((p / 'report.json').read_text(encoding='utf-8'))['frames'], [[0, 60], [120, 240]])
        data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
            '-show_streams', '-of', 'json', str(p / 'cut.mp4')]))
        video = next(x for x in data['streams'] if x['codec_type'] == 'video')
        self.assertEqual(int(video['nb_read_frames']), 180)
        self.assertTrue(any(x['codec_type'] == 'audio' for x in data['streams']))
        self.assertIsNone(s['approved_revision'])

    def test_draft_change_invalidates_approval_and_never_dispatches_stale_revision(self):
        s, rid = self.ready()
        self.mod.approve(self.edit, rid, s['version'])
        rows = copy.deepcopy(s['rows']); rows[0]['emphasis'] = 'New emphasis'
        s = self.mod.save(self.edit, s['version'], rows)
        self.assertIsNone(s['approved_revision'])
        with patch('edit_board.resolve.create_timeline', side_effect=AssertionError('Stale dispatch')):
            with self.assertRaisesRegex(ValueError, 'approv|revision|changed'):
                self.mod.send_to_resolve(self.edit, rid, s['version'])

    def test_unknown_revision_and_unapproved_revision_cannot_reach_resolve(self):
        s = self.mod.load(self.edit)
        with patch('edit_board.resolve.create_timeline', side_effect=AssertionError('Unapproved dispatch')):
            for rid in ('../outside', 'f' * 32):
                with self.assertRaises(ValueError): self.mod.send_to_resolve(self.edit, rid, s['version'])

    def test_native_send_is_idempotent_and_failure_is_not_replayed(self):
        s, rid = self.ready(); self.mod.approve(self.edit, rid, s['version'])
        calls = []
        def create(folder, name=None):
            calls.append(str(folder))
            return {'ok': True, 'timeline_id': 'native-one', 'timeline_name': name, 'clips': 2, 'warnings': []}
        with patch('edit_board.resolve.status', return_value={'connected': True}), patch('edit_board.resolve.create_timeline', side_effect=create):
            one = self.mod.send_to_resolve(self.edit, rid, s['version'])
            two = self.mod.send_to_resolve(self.edit, rid, s['version'])
        self.assertEqual(one['timeline_id'], 'native-one'); self.assertEqual(two['timeline_id'], 'native-one')
        self.assertEqual(len(calls), 1)

    def test_incomplete_native_outcome_is_never_automatically_replayed(self):
        s, rid = self.ready(); self.mod.approve(self.edit, rid, s['version'])
        with patch('edit_board.resolve.status', return_value={'connected': True}), patch('edit_board.resolve.create_timeline', return_value={'ok':False,'message':'Interrupted'}) as native:
            with self.assertRaisesRegex(ValueError, 'Interrupted'):
                self.mod.send_to_resolve(self.edit, rid, s['version'])
            with self.assertRaisesRegex(ValueError, 'interrupted|incomplete'):
                self.mod.send_to_resolve(self.edit, rid, s['version'])
            self.assertEqual(native.call_count, 1)
        rev = self.mod.load(self.edit)['revisions'][0]
        self.assertEqual(rev['native_state'], 'blocked')

    def test_modified_preview_or_revision_cannot_be_approved(self):
        s, rid = self.ready()
        path = self.edit / 'board-revisions' / rid
        (path / 'plan.json').write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.mod.approve(self.edit, rid, s['version'])

    def test_duplicate_preview_request_reuses_the_same_revision(self):
        s = self.mod.load(self.edit)
        first = self.mod.preview(self.edit, s['version'])
        second = self.mod.preview(self.edit, s['version'])
        self.assertEqual(first['revision']['id'], second['revision']['id'])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.mod.load(self.edit)['revisions'][0]['state'] != 'rendering': break
            time.sleep(.08)
        self.assertEqual(len(self.mod.load(self.edit)['revisions']), 1)

    def test_damaged_preview_can_be_rebuilt_without_overwriting_old_revision(self):
        s, rid = self.ready()
        old = self.edit / 'board-revisions' / rid / 'cut.mp4'
        old.unlink()
        result = self.mod.preview(self.edit, s['version'])
        self.assertNotEqual(result['revision']['id'], rid)
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.mod.load(self.edit)['revisions'][0]['state'] != 'rendering': break
            time.sleep(.08)
        self.assertEqual(self.mod.load(self.edit)['revisions'][0]['state'], 'ready')
        self.assertEqual(json.loads((old.parent / 'revision.json').read_text(encoding='utf-8'))['state'], 'failed')

    def test_nominal_source_rate_matches_existing_cut_pipeline_with_dropped_frame(self):
        output = {'streams':[{'codec_type':'video','r_frame_rate':'30/1','avg_frame_rate':'119/4',
                              'nb_frames':'119','duration':'4'}], 'format':{'duration':'4'}}
        with patch('edit_board.subprocess.run', return_value=subprocess.CompletedProcess([],0,json.dumps(output),'')):
            self.assertEqual(self.mod.probe(self.source), (30.0,119))

    def test_sample_is_labelled_ready_in_library_without_a_fabricated_job_or_approval(self):
        root = self.edit / 'sample-library'
        with patch.dict(os.environ, {'AI_EDITOR_HOME':str(self.edit / 'runtime'), 'AI_EDITOR_LIBRARY':str(root)}):
            s = self.mod.create_sample(root)
            import library
            row = library.entry(Path(s['edit']))
            self.assertEqual(row['status'], 'ready')
            self.assertTrue(row['sample'])
            self.assertIsNotNone(row['video'])
            review = json.loads((Path(s['edit']) / 'review.json').read_text(encoding='utf-8'))
            self.assertEqual(review['events'], [])
            self.assertIsNone(s['approved_revision'])

    @unittest.skipUnless(os.name == 'posix', 'Process-group contract on POSIX')
    def test_renderer_timeout_stops_its_descendants(self):
        pidfile = self.edit / 'child.pid'
        program = ('import subprocess,sys,time; '
                   'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]); '
                   f'open({str(pidfile)!r},"w").write(str(p.pid)); time.sleep(60)')
        self.assertTrue(hasattr(self.mod, 'run_renderer'), 'Whole-renderer process cleanup is missing')
        try:
            with self.assertRaises(subprocess.TimeoutExpired):
                self.mod.run_renderer([sys.executable, '-c', program], timeout=1)
            pid = int(pidfile.read_text(encoding='utf-8'))
            status = subprocess.run(['ps','-p',str(pid),'-o','stat='], capture_output=True,text=True).stdout.strip()
            self.assertTrue(not status or status.startswith('Z'), 'Timed-out renderer left a running child')
        finally:
            if pidfile.exists():
                try: os.kill(int(pidfile.read_text(encoding='utf-8')), 9)
                except ProcessLookupError: pass


if __name__ == '__main__': unittest.main()
