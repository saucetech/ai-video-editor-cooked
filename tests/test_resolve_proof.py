"""Actual preview decoding with a deterministic vendor boundary, no live project changes."""
import importlib
import json
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/ai-editor/lib/ai_editor'))

class Tool:
    def GetInput(self,key,frame=None):return 'Manually finished' if key=='StyledText' else 'Arial'
class Comp:
    def FindTool(self,name):return Tool()
class Clip:
    def GetUniqueId(self):return 'clip'
    def GetFusionCompByIndex(self,n):return Comp()
    def GetStart(self):return 108000
    def GetDuration(self):return 60
class Timeline:
    def __init__(self,ident):self.ident=ident;self.tc='01:00:01:00'
    def GetUniqueId(self):return self.ident
    def GetCurrentTimecode(self):return self.tc
    def SetCurrentTimecode(self,value):self.tc=value;return True
    def GetStartFrame(self):return 108000
    def GetSettings(self):return {'timelineFrameRate':'30','timelineResolutionWidth':'320','timelineResolutionHeight':'180'}
    def GetItemListInTrack(self,kind,track):return [Clip()] if track==4 else []
class Project:
    def __init__(self):self.old=Timeline('old');self.target=Timeline('target');self.current=self.old;self.exports=[]
    def GetUniqueId(self):return 'project'
    def GetCurrentTimeline(self):return self.current
    def GetTimelineCount(self):return 2
    def GetTimelineByIndex(self,n):return [self.old,self.target][n-1]
    def SetCurrentTimeline(self,t):self.current=t;return True
    def ExportCurrentFrameAsStill(self,p):
        from PIL import Image
        self.exports.append(p);Image.new('RGB',(320,180),'#111111').save(p);return True
class Manager:
    def __init__(self,p):self.p=p
    def GetCurrentProject(self):return self.p
class Resolve:
    def __init__(self):self.p=Project();self.page='edit'
    def GetProjectManager(self):return Manager(self.p)
    def GetCurrentPage(self):return self.page
    def OpenPage(self,p):self.page=p;return True

class ProofTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('resolve_proof'),'Native comparison missing')
        return importlib.import_module('resolve_proof')
    def fixture(self,p):
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=black:s=320x180:r=30','-t','2','-c:v','libx264',str(p/'cut.mp4')],check=True)
        layer={'kind':'caption','track':4,'start':0,'end':60,'native_id':'clip','checks':[{'node':'GenMedia1','input':'StyledText','value':'Approved wording','frame':None}]}
        return {'width':320,'height':180,'fps':30,'duration':60,'layers':[layer]}, {'state':'ready','project_id':'project','timeline_id':'target','native_layers':[layer]}
    def test_native_edits_are_reported_without_overwriting_and_ui_is_restored(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);bundle,manifest=self.fixture(p);r=Resolve();out=p/'proof';out.mkdir()
            report=m.capture_native(r,p,bundle,manifest,out)
            self.assertEqual(report['control_status'],'diverged')
            self.assertEqual(report['differences'][0]['actual'],'Manually finished')
            self.assertIs(r.p.current,r.p.old);self.assertEqual(r.page,'edit');self.assertEqual(r.p.target.tc,'01:00:01:00')
            self.assertTrue(report['frames']);self.assertTrue(all((out/f['native']).is_file() and (out/f['preview']).is_file() for f in report['frames']))
            m.verify_files(out,report)
            (out/report['frames'][0]['native']).write_bytes(b'changed')
            with self.assertRaises(ValueError):m.verify_files(out,report)
    def test_proof_checks_approved_bundle_instead_of_changed_manifest_expectations(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);bundle,manifest=self.fixture(p);r=Resolve();out=p/'proof';out.mkdir()
            manifest['native_layers']=[{**manifest['native_layers'][0],'checks':[{'node':'GenMedia1','input':'StyledText','value':'Manually finished','frame':None}]}]
            report=m.capture_native(r,p,bundle,manifest,out)
            self.assertEqual(report['control_status'],'diverged','Changed manifest checks must not redefine the approved visual controls')

    def test_late_result_reveal_and_word_highlights_get_actual_capture_points(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);bundle,manifest=self.fixture(p);r=Resolve();out=p/'proof';out.mkdir()
            bundle['layers'][0]['checks'].append({'node':'ResultMerge','input':'Blend','frame':50,'value':1})
            report=m.capture_native(r,p,bundle,manifest,out)
            self.assertIn(50,[f['frame'] for f in report['frames']])

    def test_wrong_project_never_selects_or_exports_and_export_failure_restores(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);b,manifest=self.fixture(p);r=Resolve();out=p/'proof';out.mkdir()
            with self.assertRaisesRegex(ValueError,'project'):m.capture_native(r,p,b,{**manifest,'project_id':'other'},out)
            self.assertFalse(r.p.exports);self.assertIs(r.p.current,r.p.old)
            def fail(path):raise RuntimeError('vendor failure')
            r.p.ExportCurrentFrameAsStill=fail
            with self.assertRaises(RuntimeError):m.capture_native(r,p,b,manifest,out)
            self.assertIs(r.p.current,r.p.old);self.assertEqual(r.p.target.tc,'01:00:01:00')
    def test_fractional_non_drop_timecode_uses_nominal_frame_labels(self):
        m=self.module();self.assertEqual(m.timecode(108031,29.97),'01:00:01:01')
        self.assertEqual(m.timecode(60,30),'00:00:02:00')

if __name__=='__main__':unittest.main()
