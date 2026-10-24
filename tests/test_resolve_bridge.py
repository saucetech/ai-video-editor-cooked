"""Resolve API contract tests; no installed Resolve or customer footage required."""
import importlib
import http.client
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/ai-editor/lib'))


class Item:
    def __init__(self, info, n):
        self.info, self.uid = info, str(n)
        self.props = {'ZoomX': 1.0, 'ZoomY': 1.0, 'Pan': 0.0}
    def GetUniqueId(self): return self.uid
    def GetStart(self): return self.info['recordFrame']
    def GetEnd(self): return self.GetStart() + self.GetDuration()
    def GetDuration(self): return self.info['endFrame'] - self.info['startFrame']
    def GetSpeed(self): return {'speed': 100.0, 'reverse': False}
    def GetClipEnabled(self): return True
    def GetLeftOffset(self): return self.info['startFrame']
    def GetRightOffset(self): return 300 - self.info['endFrame']
    def GetMediaPoolItem(self): return self.info['mediaPoolItem']
    def GetProperties(self): return dict(self.props)
    def SetProperties(self, props): self.props.update(props); return True


class Media:
    def __init__(self, path): self.path = path
    def GetUniqueId(self): return 'source-1'
    def GetClipProperty(self): return {'File Path': self.path, 'FPS': '29.97', 'Frames': '300'}


class Timeline:
    def __init__(self, name, uid): self.name, self.uid, self.items = name, uid, []
    def GetName(self): return self.name
    def GetUniqueId(self): return self.uid
    def SetSettings(self, settings): self.settings = settings; return True
    def GetSettings(self): return self.settings
    def GetStartFrame(self): return 0
    def GetTrackCount(self, kind): return 1 if kind == 'video' else 0
    def GetItemListInTrack(self, kind, track): return self.items


class Project:
    def __init__(self):
        self.current, self.timelines = 'manual-current-timeline', []
        self.switches, self.appends = [], []
    def GetUniqueId(self): return 'project-1'
    def GetCurrentTimeline(self): return self.current
    def SetCurrentTimeline(self, timeline): self.current = timeline; self.switches.append(timeline); return True
    def GetMediaPool(self): return self
    def ImportMedia(self, clips):
        # Video uses the file-path overload. FilePath dictionaries describe image sequences.
        return [Media(clips[0])] if isinstance(clips[0], str) else []
    def CreateEmptyTimeline(self, name):
        t = Timeline(name, 'timeline-' + str(len(self.timelines)))
        self.timelines.append(t); self.current = t
        return t
    def AppendToTimeline(self, infos):
        self.appends.extend(infos)
        self.current.items = [Item(info, n) for n, info in enumerate(infos)]
        return self.current.items
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self, index): return self.timelines[index - 1]


class Resolve:
    def __init__(self): self.project, self.saved = Project(), 0
    def GetVersionString(self): return '21.1.1'
    def GetProjectManager(self): return self
    def GetCurrentProject(self): return self.project
    def SaveProject(self): self.saved += 1; return True


class ResolveBridgeTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module('ai_editor.resolve_bridge')
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.edit = Path(self.tmp.name)
        (self.edit / 'raw.mov').write_bytes(b'synthetic')
        self.report = {'source': 'raw.mov', 'fps': 29.97, 'frames': [[30, 90], [150, 210]]}
        self.write('report.json', self.report)
        self.write('decisions.json', [{'start': 30 / 29.97, 'end': 90 / 29.97},
                                      {'start': 150 / 29.97, 'end': 210 / 29.97}])
        self.plan = {'zooms': [{'start': 30 / 29.97, 'end': 60 / 29.97,
                                'kind': 'punch', 'scale': 1.2, 'ease_s': 0}]}
        self.write('plan.json', self.plan)
        self.resolve = Resolve()
        self.bridge = self.mod.ResolveBridge(resolve=self.resolve)
    def write(self, name, data): (self.edit / name).write_text(json.dumps(data), encoding='utf-8')
    def create(self):
        result = self.bridge.create_timeline(self.edit)
        self.assertTrue(result['ok'], result)
        return self.resolve.project.timelines[0]

    def test_visual_timeline_settings_are_applied_away_from_active_fusion_viewer(self):
        pages=[];current=['edit'];project=self.resolve.project;create=project.CreateEmptyTimeline
        self.resolve.GetCurrentPage=lambda:current[0]
        def open_page(page):current[0]=page;pages.append(page);return True
        self.resolve.OpenPage=open_page
        def new_timeline(name):
            tl=create(name);set_settings=tl.SetSettings
            def configure(settings):
                self.assertEqual(current[0],'media','An active Fusion viewer can hold the render lock during settings synchronization')
                return set_settings(settings)
            tl.SetSettings=configure;return tl
        project.CreateEmptyTimeline=new_timeline
        with patch('ai_editor.resolve_visuals.load_bundle',return_value={'width':640,'height':360,'layers':[]}):
            self.create()
        self.assertEqual(pages,['media','edit'])
        self.assertEqual(project.current,'manual-current-timeline')

    def test_status_only_reads_connection(self):
        self.assertTrue(self.bridge.status()['connected'])
        self.assertEqual(self.bridge.status()['version'], '21.1.1')
        self.assertEqual(self.resolve.project.switches, [])
        self.assertEqual(self.resolve.project.timelines, [])

    def test_native_original_ranges_exclusive_end_and_ntsc(self):
        timeline = self.create()
        self.assertEqual([(x['startFrame'], x['endFrame'], x['recordFrame']) for x in self.resolve.project.appends],
                         [(30, 60, 0), (60, 90, 30), (150, 210, 60)])
        self.assertEqual(timeline.settings['timelineFrameRate'], '29.97')
        self.assertEqual(timeline.items[1].props['ZoomX'], 1.2)
        manifest = json.loads((self.edit / 'resolve-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['rate'], [30000, 1001])
        self.assertEqual(manifest['state'], 'ready')
        self.assertEqual(self.resolve.project.current, 'manual-current-timeline')
        self.assertEqual(self.resolve.saved, 1)

    def test_updates_only_zoom_preserves_manual_pan(self):
        timeline = self.create(); self.resolve.project.switches.clear()
        timeline.items[1].props['Pan'] = 42
        self.plan['zooms'][0]['scale'] = 1.4; self.write('plan.json', self.plan)
        result = self.bridge.update_timeline(self.edit)
        self.assertTrue(result['ok'], result)
        self.assertEqual(timeline.items[1].props, {'ZoomX': 1.4, 'ZoomY': 1.4, 'Pan': 42})
        self.assertEqual(self.resolve.project.switches, [])
        self.assertEqual(len(self.resolve.project.appends), 3)

    def test_manual_managed_zoom_conflicts_before_any_writes(self):
        timeline = self.create(); timeline.items[2].props['ZoomX'] = 1.1
        self.plan['zooms'][0]['scale'] = 1.4; self.write('plan.json', self.plan)
        result = self.bridge.update_timeline(self.edit)
        self.assertFalse(result['ok']); self.assertEqual(result['code'], 'manual_changes')
        self.assertEqual(timeline.items[1].props['ZoomX'], 1.2)

    def test_manual_trim_conflicts(self):
        timeline = self.create(); timeline.items[0].info['startFrame'] += 1
        self.assertEqual(self.bridge.update_timeline(self.edit)['code'], 'manual_changes')

    def test_recuts_and_changed_zoom_boundaries_require_new_timeline(self):
        self.create(); self.plan['zooms'][0]['end'] += 1 / 29.97; self.write('plan.json', self.plan)
        result = self.bridge.update_timeline(self.edit)
        self.assertFalse(result['ok']); self.assertEqual(result['code'], 'structure_changed')

    def test_unreadable_original_and_stale_report_fail_before_import(self):
        (self.edit / 'raw.mov').unlink()
        self.assertFalse(self.bridge.create_timeline(self.edit)['ok'])
        self.assertEqual(self.resolve.project.timelines, [])
        (self.edit / 'raw.mov').write_bytes(b'synthetic')
        self.report['frames'] = [[31, 90], [150, 210]]; self.write('report.json', self.report)
        self.assertFalse(self.bridge.create_timeline(self.edit)['ok'])
        self.assertEqual(self.resolve.project.timelines, [])

    def test_missing_project_actionable_without_changes(self):
        self.resolve.project = None
        result = self.bridge.create_timeline(self.edit)
        self.assertFalse(result['ok']); self.assertIn('project', result['message'].lower())

    def test_repeat_create_does_not_duplicate(self):
        self.create()
        self.assertFalse(self.bridge.create_timeline(self.edit)['ok'])
        self.assertEqual(len(self.resolve.project.timelines), 1)

    def test_animated_zooms_are_reported_not_claimed_native(self):
        self.plan['zooms'][0]['kind'] = 'push'; self.write('plan.json', self.plan)
        result = self.bridge.create_timeline(self.edit)
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['warnings'])
        self.assertTrue(all(i.props['ZoomX'] == 1 for i in self.resolve.project.timelines[0].items))

    def test_relinked_original_is_detected(self):
        timeline = self.create()
        timeline.items[0].GetMediaPoolItem().path = '/different/original.mov'
        self.assertEqual(self.bridge.update_timeline(self.edit)['code'], 'manual_changes')

    def test_embedded_transport_uses_internal_resolve_without_subprocess(self):
        runtime = self.edit / 'runtime'
        result = self.mod.start_embedded(self.resolve, runtime=runtime)
        self.addCleanup(self.mod.stop_embedded)
        self.assertTrue(result['connected'])
        self.assertNotIn('token', result)
        bridge = self.mod.ResolveBridge(runtime=runtime, command=['must-not-be-executed'])
        self.assertTrue(bridge.status()['connected'])
        self.assertTrue(bridge.create_timeline(self.edit)['ok'])
        descriptor = runtime / 'resolve-bridge.json'
        self.assertEqual(descriptor.stat().st_mode & 0o777, 0o600)
        self.assertIn('token', json.loads(descriptor.read_text(encoding='utf-8')))

    def test_embedded_rejects_origin_host_and_bad_token(self):
        runtime = self.edit / 'runtime'
        self.mod.start_embedded(self.resolve, runtime=runtime)
        self.addCleanup(self.mod.stop_embedded)
        descriptor = json.loads((runtime / 'resolve-bridge.json').read_text(encoding='utf-8'))
        for changes in ({'Origin': 'http://evil.example'}, {'Host': 'evil.example'},
                        {'Authorization': 'Bearer invalid'}):
            conn = http.client.HTTPConnection('127.0.0.1', descriptor['port'], timeout=3)
            headers = {'Host': '127.0.0.1:' + str(descriptor['port']),
                       'Authorization': 'Bearer ' + descriptor['token'], 'Content-Type': 'application/json'}
            headers.update(changes)
            conn.request('POST', '/resolve', body='{"action":"status"}', headers=headers)
            response = conn.getresponse()
            self.assertEqual(response.status, 403)
            response.read(); conn.close()
        self.assertEqual(self.resolve.project.timelines, [])

    def test_installer_writes_only_local_import_bootstrap(self):
        utility = self.edit / 'Utility'
        result = self.mod.install_internal_bridge(runtime=self.edit / 'runtime', scripts_dir=utility)
        self.assertTrue(result['ok'])
        source = Path(result['path']).read_text(encoding='utf-8')
        self.assertIn('start_embedded', source)
        self.assertNotIn('token', source)
        compile(source, result['path'], 'exec')
        self.assertTrue(Path(result['lua_path']).is_file())
        self.assertIn('dofile(', result['console_command'])
        self.assertEqual((self.edit / 'runtime/resolve-lua/helper.lua').stat().st_mode & 0o777, 0o600)

    def test_subprocess_failure_is_actionable(self):
        bridge = self.mod.ResolveBridge(command=['missing-resolve-python'], runtime=self.edit / 'isolated-runtime')
        result = bridge.status()
        self.assertFalse(result['connected']); self.assertTrue(result['message'])

    def test_stale_lua_or_quarantine_never_falls_through_to_another_transport(self):
        import os
        folder = self.edit / 'isolated-runtime/resolve-lua'
        folder.mkdir(parents=True)
        ready = folder / 'ready.json'
        ready.write_text('{"generation":"busy-helper"}', encoding='utf-8')
        os.utime(ready, (1,1))
        bridge = self.mod.ResolveBridge(runtime=folder.parent)
        with patch.object(self.mod.subprocess, 'run', side_effect=AssertionError('must not replay through Python')):
            self.assertEqual(bridge.create_timeline(self.edit)['code'], 'lua_unavailable')
            ready.write_text('{}', encoding='utf-8')
            (folder/'client.lock').write_text('{"state":"quarantined"}', encoding='utf-8')
            self.assertEqual(bridge.create_timeline(self.edit)['code'], 'lua_unavailable')


if __name__ == '__main__': unittest.main()
