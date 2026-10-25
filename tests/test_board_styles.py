"""Style portability: inference is disclosed, timing never invented, paths bounded."""
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/ai-editor/lib/ai_editor'))

class StyleTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('board_styles'), 'Style adapter missing')
        return importlib.import_module('board_styles')

    def test_inferred_serif_does_not_claim_measured_caption_or_exact_font(self):
        m=self.module()
        data={'captions':{'present':False},'look':{'font_class':'serif','closest_google_font':'Playfair Display','font_confident':False}}
        s=m.normalize(data,'Reference','abc')
        self.assertEqual(s['font'],'Georgia');self.assertEqual(s['treatment'],'editorial')
        self.assertEqual(s['source']['digest'],'abc')
        self.assertIn('inferred',s['transfer']['font']['basis'])
        self.assertTrue(any('Playfair Display' in n and 'Georgia' in n for n in s['transfer']['notes']))
        self.assertTrue(any('absent' in n.lower() for n in s['transfer']['notes']))
        self.assertNotIn('caption_enabled',s)

    def test_normalized_values_are_bounded_and_analysis_remains_untouched(self):
        m=self.module();data={'captions':{'present':True,'size_pct':float('nan'),'y_pct':300,'words_per_caption':999,'color':'url(x)','case':'javascript'}}
        original=json.dumps(data)
        s=m.normalize(data,'Synthetic','x')
        self.assertEqual(s['size_pct'],4.4);self.assertEqual(s['y_pct'],82)
        self.assertEqual(s['words_per_phrase'],5);self.assertEqual(s['color'],'#FFFFFF')
        self.assertEqual(json.dumps(data),original)
        with self.assertRaises(ValueError):m.validate({**s,'y_pct':float('inf')})

    def test_advanced_row_options_are_validated_and_legacy_defaults_stay_off(self):
        import board_visuals as v
        s=self.module().normalize({},'Synthetic','x')
        row=v.row_defaults({'text':'Hello','caption_treatment':'editorial','caption_style':s,'motion':'hero','motion_text':'A clear opening'})
        self.assertEqual(v.validate_row(row,[])['caption_treatment'],'editorial')
        self.assertFalse(row['caption_enabled'])
        for change in ({'caption_treatment':'execute'}, {'caption_style':{**s,'size_pct':float('nan')}}, {'motion_result':'x'*181}):
            with self.subTest(change=change),self.assertRaises(ValueError):v.validate_row({**row,**change},[])

    def test_catalog_rejects_escape_and_symlink(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'creator-teardowns'/'original';folder.mkdir(parents=True)
            (folder/'style.json').write_text('{}')
            self.assertEqual(m.catalog(root)[0]['id'],'original')
            with self.assertRaises(ValueError):m.load(root,'../outside')
            (root/'creator-teardowns'/'escape').symlink_to(root.parent,target_is_directory=True)
            self.assertEqual(len(m.catalog(root)),1)

    def test_real_word_alignment_keeps_gaps_and_corrections_fall_back(self):
        m=self.module();row={'caption':'Hello, world!','start_frame':90,'end_frame':150}
        words=[{'word':'Hello','start':3.1,'end':3.4},{'word':'world','start':4,'end':4.4}]
        aligned,note=m.align_words(row,words,30)
        self.assertEqual([(w['start'],w['end']) for w in aligned],[(3,12),(30,42)])
        self.assertIsNone(note)
        aligned,note=m.align_words({**row,'caption':'Changed words'},words,30)
        self.assertIsNone(aligned);self.assertIn('passage',note)
        aligned,note=m.align_words(row,[{**words[0],'end':float('nan')},words[1]],30)
        self.assertIsNone(aligned)

if __name__=='__main__':unittest.main()
