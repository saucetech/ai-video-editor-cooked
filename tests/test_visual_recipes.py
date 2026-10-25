import importlib
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/ai-editor/lib/ai_editor'))

class RecipeTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('visual_recipes'),'Shared scene renderer missing')
        return importlib.import_module('visual_recipes')
    def row(self,**changes):
        return dict(caption='Make every frame count.',caption_treatment='editorial',caption_style=None,motion='none',motion_text='',motion_result='',start_frame=90,end_frame=210,**changes)
    def test_caption_paging_uses_original_word_gaps_and_retains_editable_words(self):
        m=self.module();r=self.row();r['caption_treatment']='spotlight'
        words=[{'word':t,'start':a,'end':b} for t,a,b in [('Make',3.1,3.5),('every',3.7,4),('frame',4.2,4.5),('count.',4.8,5.2)]]
        s=m.build(r,'caption',640,360,30,words)
        texts=[n for n in s['nodes'] if n['type']=='text']
        self.assertEqual([n['text'] for n in texts if n.get('role')=='base'],['Make','every','frame','count.'])
        active=[n for n in texts if n.get('role')=='accent']
        self.assertEqual(active[0]['alpha'][0],0);self.assertEqual(active[0]['alpha'][3],1)
        self.assertEqual(active[0]['alpha'][15],0)
        self.assertEqual(s['timing'],'word timestamps')
        graph,checks=m.fusion(s,640,360)
        self.assertEqual(len([c for c in checks if c['input']=='StyledText']),8)
        self.assertNotIn('Loader',graph)
    def test_caption_correction_is_static_and_dense_text_is_rejected(self):
        m=self.module();r=self.row();r['caption']='A corrected caption';r['caption_treatment']='spotlight'
        s=m.build(r,'caption',360,640,30,[{'word':'Original','start':3.1,'end':4}])
        self.assertEqual(s['timing'],'passage fallback')
        self.assertTrue(any('passage' in n for n in s['notes']))
        for n in s['nodes']:
            if n['type']=='text':self.assertTrue(.05*360<n['x']<.95*360)
        r['caption']=' '.join(['Oversized']*70)
        with self.assertRaisesRegex(ValueError,'dense|Shorten|two lines'):m.build(r,'caption',360,640,30,[])
    def test_hook_entrance_hold_exit_render_real_alpha_and_short_hooks_reject(self):
        m=self.module();r=self.row();r['motion_text']='A clear opening'
        for kind in ('hero','outline','prompt_result'):
            r['motion_result']='A visible result'
            s=m.build(r,kind,640,360,30,[])
            self.assertEqual(m.render(s,0).getbbox(),None)
            self.assertIsNotNone(m.render(s,30).getbbox())
            self.assertEqual(m.render(s,119).getbbox(),None)
            graph,checks=m.fusion(s,640,360)
            self.assertTrue(any(c['frame']==30 and c['value']==1 for c in checks if c['input']=='Blend'))
            self.assertTrue(all(n['y']<.65*360 for n in s['nodes'] if n['type']=='text'))
        r['end_frame']=96
        with self.assertRaisesRegex(ValueError,'short|hold'):m.build(r,'hero',640,360,30,[])
    def test_real_bundle_uses_scene_metadata_and_transparent_native_carrier(self):
        import tempfile,subprocess,json
        import board_visuals as v
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);source=p/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=s=320x180:r=30','-t','2','-c:v','libx264',str(source)],check=True)
            r=v.row_defaults(dict(text='A clear opening',caption='A clear opening',caption_enabled=True,caption_treatment='editorial',motion='outline',motion_text='Make it clear',keep=True,start_frame=0,end_frame=60,zoom=1))
            b=v.compile_bundle(p,[r],{'source':str(source),'fps':30})
            self.assertEqual(len(b['layers']),2)
            for layer in b['layers']:
                self.assertTrue(layer.get('checks'),'Native controls must be declared, not just caption text')
                self.assertTrue(layer.get('scene'))
                info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries','stream=nb_read_frames','-of','json',str(p/layer['preview_media'])]))
                self.assertEqual(info['streams'][0]['nb_read_frames'],'60')
                alpha=subprocess.check_output(['ffmpeg','-v','error','-i',str(p/layer['media']),'-vf','alphaextract','-frames:v','1','-f','rawvideo','-pix_fmt','gray','-'])
                self.assertEqual(max(alpha),0)
            v.verify_bundle(p)

    def test_serif_font_and_size_are_the_same_scene_contract_for_both_renderers(self):
        m=self.module();s=m.build(self.row(),'caption',640,360,30,[])
        graph,checks=m.fusion(s,1280,720)
        font=[c['value'] for c in checks if c['input']=='Font']
        self.assertTrue(font);self.assertEqual(set(font),{'Georgia'})
        self.assertIsNotNone(m.render(s,30).getbbox())
        self.assertTrue(any(c['input']=='Size' and .02<c['value']<.12 for c in checks))

if __name__=='__main__':unittest.main()
