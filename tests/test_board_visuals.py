import importlib
import json
import sys
import subprocess
import shutil
from unittest.mock import patch
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

    def test_fractional_inpoint_cannot_approve_a_short_broll_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=30',
                '-frames:v','30','-c:v','libx264',str(source)],check=True)
            row=self.mod.validate_row(dict(start_frame=0,end_frame=30,keep=True,zoom=1,broll=str(source),broll_start=.01),[path])
            with self.assertRaisesRegex(ValueError,'shorter|frames'):
                self.mod.compile_bundle(path,[row],{'source':str(source),'fps':30})

    def test_saved_staged_broll_survives_staging_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);stage=path/'.staged/upload';stage.mkdir(parents=True);clip=stage/'shot.mp4';clip.write_bytes(b'owned video')
            row=self.mod.validate_row({'broll':str(clip)},[path])
            shutil.rmtree(path/'.staged')
            self.assertTrue(Path(row['broll']).is_file(),'Saved B-roll must live outside expiring upload staging')
            self.mod.validate_row(row,[path])

    def test_broll_conversion_reads_a_verified_revision_snapshot(self):
        import edit_board
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'source.mp4';replacement=path/'blue.mp4'
            for file,color in [(source,'red'),(replacement,'blue')]:
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',f'color=c={color}:s=320x180:r=30',
                    '-frames:v','30','-c:v','libx264',str(file)],check=True)
            row=self.mod.validate_row(dict(start_frame=0,end_frame=15,keep=True,zoom=1,broll=str(source)),[path])
            render=edit_board.run_renderer
            def replace_before_conversion(args,*a,**kw):
                shutil.copyfile(replacement,source)
                return render(args,*a,**kw)
            with patch.object(edit_board,'run_renderer',side_effect=replace_before_conversion):
                bundle=self.mod.compile_bundle(path,[row],{'source':str(source),'fps':30})
            pixel=subprocess.check_output(['ffmpeg','-v','error','-i',str(path/bundle['layers'][0]['media']),
                '-vf','scale=1:1','-frames:v','1','-f','rawvideo','-pix_fmt','rgb24','-'])
            self.assertGreater(pixel[0],pixel[2]+100,'The selected red footage must not be silently replaced by blue')
            self.mod.verify_bundle(path)

    def test_fusion_font_size_matches_preview_pixels_across_aspect_ratios(self):
        import re
        # Native Text+ calibration: Size is based on width, with a 3/4 font scale.
        for width,height,expected in [(640,360,.0375),(360,640,.1185185185)]:
            comp=self.mod.fusion_comp('Layout calibration',60,width=width,height=height,size=.05)
            actual=float(re.search(r'Size = Input \{ Value = ([0-9.e+-]+)',comp).group(1))
            self.assertAlmostEqual(actual,expected,places=8)

    def test_explicit_caption_line_breaks_survive_layout(self):
        image,wrapped,size=self.mod._text_image('First line\nSecond line',640,360,'caption')
        self.assertEqual(wrapped,'First line\nSecond line')

    def test_motion_preview_fades_to_zero_on_its_last_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);source=path/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=320x180:r=30',
                '-frames:v','6','-c:v','libx264',str(source)],check=True)
            row=self.mod.validate_row(dict(start_frame=0,end_frame=6,keep=True,zoom=1,motion='title',motion_text='Title'),[path])
            bundle=self.mod.compile_bundle(path,[row],{'source':str(source),'fps':30})
            movie=path/bundle['layers'][0]['preview_media']
            alpha=subprocess.check_output(['ffmpeg','-v','error','-i',str(movie),'-vf','alphaextract','-f','rawvideo','-pix_fmt','gray','-'])
            peaks=[max(alpha[i*57600:(i+1)*57600]) for i in range(6)]
            self.assertEqual(peaks[0],0);self.assertGreater(peaks[2],0);self.assertEqual(peaks[-1],0)

    def test_rotated_phone_video_uses_its_display_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);raw=path/'landscape.mp4';source=path/'phone.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=640x360:r=30',
                '-frames:v','6','-c:v','libx264',str(raw)],check=True)
            subprocess.run(['ffmpeg','-v','error','-i',str(raw),'-c','copy','-metadata:s:v:0','rotate=90',str(source)],check=True)
            data=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(source)]))
            if not any('rotation' in d for d in data['streams'][0].get('side_data_list',[])):
                # FFmpeg 8 replaced the old output rotate metadata option with an input override.
                subprocess.run(['ffmpeg','-v','error','-y','-display_rotation','90','-i',str(raw),'-c','copy',str(source)],check=True)
            row=self.mod.validate_row(dict(start_frame=0,end_frame=6,keep=True,zoom=1,caption_enabled=True,caption='Phone video',broll=str(raw)),[path])
            bundle=self.mod.compile_bundle(path,[row],{'source':str(source),'fps':30})
            self.assertEqual((bundle['native_width'],bundle['native_height']),(360,640))
            for layer in bundle['layers']:
                info=self.mod.media_info(path/layer['media'])
                self.assertEqual((info['width'],info['height']),(360,640))

    def test_bundle_tampering_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp);file=path/'caption.comp';file.write_text('original',encoding='utf-8')
            bundle={'schema':1,'files':{'caption.comp':self.mod.file_hash(file)},'layers':[]}
            (path/'visuals.json').write_text(json.dumps(bundle),encoding='utf-8')
            self.mod.verify_bundle(path)
            file.write_text('modified',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'changed|integrity'):self.mod.verify_bundle(path)

if __name__=='__main__':unittest.main()
