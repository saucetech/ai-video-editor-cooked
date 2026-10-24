import importlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/ai-editor/lib/ai_editor'))


class Tool:
    def __init__(self,text):self.text=text
    def GetInput(self,key,frame=None):return self.text if key=='StyledText' else 0 if frame==0 else 1
class Comp:
    def FindTool(self,name):return Tool('Editable caption')
class Clip:
    def __init__(self,info):self.info=info
    def GetStart(self):return self.info['recordFrame']
    def GetDuration(self):return self.info['endFrame']-self.info['startFrame']
    def GetLeftOffset(self):return self.info['startFrame']
    def GetUniqueId(self):return 'native-clip'
    def ImportFusionComp(self,path):return Comp()
class Pool:
    def __init__(self):self.calls=[]
    def ImportMedia(self,paths):return [object()]
    def AppendToTimeline(self,infos):self.calls+=infos;return [Clip(i) for i in infos]
class Timeline:
    def __init__(self):self.count=1;self.names={}
    def GetTrackCount(self,kind):return self.count
    def AddTrack(self,kind):self.count+=1;return True
    def SetTrackName(self,kind,index,name):self.names[index]=name;return True


class ResolveVisualTests(unittest.TestCase):
    def setUp(self):self.mod=importlib.import_module('resolve_visuals')
    def test_native_layers_are_separate_video_only_and_text_is_read_back(self):
        pool,tl=Pool(),Timeline()
        bundle={'root':'/revision','layers':[{'kind':'broll','track':2,'start':30,'end':90,'source_start':0,'media':'broll.mov'},
            {'kind':'caption','track':4,'start':30,'end':90,'source_start':0,'media':'caption.mov','comp':'caption.comp','text':'Editable caption'}]}
        result=self.mod.append_layers(pool,tl,bundle,100)
        self.assertEqual([i['trackIndex'] for i in pool.calls],[2,4])
        self.assertTrue(all(i['mediaType']==1 for i in pool.calls))
        self.assertEqual([i['recordFrame'] for i in pool.calls],[130,130])
        self.assertEqual(result[1]['text'],'Editable caption')
        self.assertEqual(tl.count,4)
    def test_wrong_native_caption_text_is_failure_not_a_ready_timeline(self):
        layer={'kind':'caption','track':4,'start':0,'end':30,'source_start':0,'media':'c.mov','comp':'c.comp','text':'Wrong native value'}
        with self.assertRaisesRegex(ValueError,'text|caption'):self.mod.append_layers(Pool(),Timeline(),{'root':'/revision','layers':[layer]},0)
    def test_fusion_transport_methods_and_types_are_explicit(self):
        import resolve_lua
        self.assertIn('ImportFusionComp',resolve_lua.METHODS['TimelineItem'])
        self.assertEqual(resolve_lua.METHODS['FusionComp'],{'FindTool'})
        self.assertEqual(resolve_lua.METHODS['FusionTool'],{'GetInput','SetInput'})

if __name__=='__main__':unittest.main()
