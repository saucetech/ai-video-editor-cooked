import importlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/ai-editor/lib/ai_editor'))


class BoardVisualTests(unittest.TestCase):
    def setUp(self):
        self.mod = importlib.import_module('board_visuals')

    def test_removed_passages_do_not_leave_visuals_or_shift_source_offsets(self):
        rows = [dict(start_frame=0,end_frame=30,keep=True,caption_enabled=True,caption='First',motion='title',motion_text='One',zoom=1,broll='',broll_start=0),
                dict(start_frame=30,end_frame=90,keep=False,caption_enabled=True,caption='Removed',motion='none',motion_text='',zoom=1,broll='',broll_start=0),
                dict(start_frame=90,end_frame=150,keep=True,caption_enabled=True,caption='Last',motion='lower_third',motion_text='Result',zoom=1.2,broll='',broll_start=0)]
        cues = self.mod.cues(rows)
        self.assertEqual([(c['start'],c['end'],c['source_start']) for c in cues],[(0,30,0),(30,90,90)])
        self.assertEqual([c['caption'] for c in cues],['First','Last'])

    def test_legacy_defaults_do_not_enable_caption_or_motion(self):
        row=self.mod.row_defaults({'text':'Original transcript','note':'A planning note','emphasis':'Emphasis'})
        self.assertFalse(row['caption_enabled']);self.assertEqual(row['motion'],'none');self.assertEqual(row['caption'],'Original transcript')
        self.assertEqual(row['motion_text'],'')

    def test_native_text_is_escaped_and_animation_has_real_keyframes(self):
        comp=self.mod.fusion_comp('A "title"\\path\nNext',60,'title')
        self.assertIn('TextPlus',comp);self.assertIn('BezierSpline',comp)
        self.assertIn('StyledText',comp);self.assertNotIn('Expression',comp)
        self.assertIn('\\"title\\"',comp)

    def test_bad_visual_values_and_outside_broll_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots=[Path(tmp)]
            for changes in [{'caption_enabled':'yes'},{'caption':'x'*501},{'motion':'script'},{'broll_start':float('nan')},{'broll':'/tmp/outside.mp4'}]:
                row=self.mod.row_defaults({'text':'Test'});row.update(changes)
                with self.subTest(changes=changes),self.assertRaises(ValueError):self.mod.validate_row(row,roots)

    def test_real_visual_bundle_has_exact_frames_alpha_carriers_and_native_broll(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'source.mp4';broll=path/'broll.mp4'
            for file,rate in [(source,30),(broll,24)]:
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'testsrc2=size=320x180:rate={rate}',
                    '-t','1','-an','-c:v','libx264',str(file)],check=True)
            row=self.mod.validate_row(dict(text='Caption',start_frame=0,end_frame=15,keep=True,zoom=1,
                caption_enabled=True,motion='title',motion_text='Title',broll=str(broll),broll_start=.25),[path])
            bundle=self.mod.compile_bundle(path,[row],{'source':str(source),'fps':30})
            self.assertEqual({l['track'] for l in bundle['layers']},{2,3,4})
            for layer in bundle['layers']:
                info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(path/layer['media'])]))
                self.assertEqual(int(info['streams'][0]['nb_read_frames']),15)
                self.assertEqual(len(info['streams']),1)
                if layer['kind']!='broll':
                    alpha=subprocess.check_output(['ffmpeg','-v','error','-i',str(path/layer['media']),'-vf','alphaextract','-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
                    self.assertEqual(max(alpha),0,'Native carriers must be blank: only editable Fusion nodes supply the text')
            self.mod.verify_bundle(path)
            row['broll_start']=.9
            (path/'short').mkdir()
            with self.assertRaisesRegex(ValueError,'shorter'):
                self.mod.compile_bundle(path/'short', [row], {'source':str(source),'fps':30})

    def test_native_canvas_preserves_source_resolution_while_preview_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=1600x900:r=30',
                '-frames:v','6','-c:v','libx264',str(source)],check=True)
            row=self.mod.validate_row(dict(text='Full resolution',start_frame=0,end_frame=6,keep=True,zoom=1,caption_enabled=True,broll=str(source)),[path])
            bundle=self.mod.compile_bundle(path,[row],{'source':str(source),'fps':30})
            self.assertEqual((bundle['native_width'],bundle['native_height']),(1600,900))
            self.assertEqual((bundle['width'],bundle['height']),(1280,720))
            for layer in bundle['layers']:
                carrier=self.mod.media_info(path/layer['media'])
                self.assertEqual((carrier['width'],carrier['height']),(1600,900))

    def test_bundle_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);file=path/'caption.comp';file.write_text('original',encoding='utf-8')
            bundle={'schema':1,'files':{'caption.comp':self.mod.file_hash(file)},'layers':[]}
            (path/'visuals.json').write_text(json.dumps(bundle),encoding='utf-8')
            self.mod.verify_bundle(path)
            file.write_text('modified',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'changed|integrity'):self.mod.verify_bundle(path)

if __name__=='__main__':unittest.main()
