"""Import approved, generated visual layers without flattening source media or text."""
import math
from pathlib import Path
try:
    from . import board_visuals
except ImportError:
    import board_visuals


def load_bundle(edit, total, rate):
    path = Path(edit)
    if not (path/'visuals.json').exists(): return None
    bundle = board_visuals.verify_bundle(path)
    if bundle['duration'] != total or not math.isclose(bundle['fps'],float(rate),abs_tol=.005):
        raise ValueError('Visual bundle timing differs from the approved source cut.')
    previous = {}
    for layer in sorted(bundle['layers'],key=lambda l:(l['track'],l['start'])):
        track = layer['track']; a,b=layer['start'],layer['end']
        expected=2 if layer['kind']=='broll' else 4 if layer['kind']=='caption' else 3
        if track!=expected or any(type(v) is not int for v in (a,b)) or not 0<=a<b<=total or a<previous.get(track,0):
            raise ValueError('Invalid or overlapping visual layer timing.')
        previous[track]=b
        for key in ('media','comp'):
            if key in layer and layer[key] not in bundle['files']:raise ValueError('Visual layer is missing its verified asset.')
        if layer['kind']!='broll' and not layer.get('comp'):raise ValueError('Editable text composition is missing.')
    return {**bundle,'root':str(path)}


def append_layers(pool, timeline, bundle, start):
    if not bundle or not bundle['layers']:return []
    for track in range(timeline.GetTrackCount('video')+1,5):
        if not timeline.AddTrack('video'):raise ValueError('Resolve could not create the visual tracks.')
    for track,name in [(1,'GenMedia source'),(2,'GenMedia B-roll'),(3,'GenMedia motion'),(4,'GenMedia captions')]:
        if not timeline.SetTrackName('video',track,name):raise ValueError('Resolve could not name the visual tracks.')
    records=[]
    for layer in bundle['layers']:
        media=pool.ImportMedia([str(Path(bundle['root'])/layer['media'])])
        if not media:raise ValueError('Resolve could not import a visual asset.')
        info={'mediaPoolItem':media[0],'startFrame':0,'endFrame':layer['end']-layer['start'],
              'recordFrame':start+layer['start'],'trackIndex':layer['track'],'mediaType':1}
        clips=pool.AppendToTimeline([info])
        if not clips or len(clips)!=1:raise ValueError('Resolve did not append the visual clip.')
        clip=clips[0]
        if any(abs(float(actual)-expected)>.001 for actual,expected in [(clip.GetStart(),info['recordFrame']),
            (clip.GetDuration(),info['endFrame']),(clip.GetLeftOffset(),0)]):
            raise ValueError('Resolve returned different visual frame boundaries.')
        record={**layer,'native_id':clip.GetUniqueId()}
        if layer.get('comp'):
            comp=clip.ImportFusionComp(str(Path(bundle['root'])/layer['comp']))
            if not comp:raise ValueError('Resolve could not import editable Fusion text.')
            text=comp.FindTool('GenMediaText')
            if not text or text.GetInput('StyledText')!=layer['text']:raise ValueError('Resolve returned different caption or motion text.')
            record['text']=text.GetInput('StyledText')
            if layer['kind']!='caption' and info['endFrame']>=4:
                output=comp.FindTool('GenMediaOutput');ramp=max(1,min(8,info['endFrame']//3))
                values=[output.GetInput('Blend',0),output.GetInput('Blend',ramp)] if output else []
                if len(values)!=2 or abs(float(values[0]))>.001 or abs(float(values[1])-1)>.001:
                    raise ValueError('Resolve motion keyframes did not survive import.')
                record['animation_readback']=values
        records.append(record)
    return records


def matching_template(project, bundle, rate):
    """Avoid Resolve 21.1's Fusion render-lock stall when changing timeline settings."""
    timelines=[project.GetTimelineByIndex(i) for i in range(1,project.GetTimelineCount()+1)]
    width=bundle.get('native_width',bundle['width']);height=bundle.get('native_height',bundle['height'])
    for timeline in timelines:
        settings=timeline.GetSettings()
        if (math.isclose(float(settings['timelineFrameRate']),float(rate),abs_tol=.005)
                and int(settings['timelineResolutionWidth'])==width and int(settings['timelineResolutionHeight'])==height):
            return timeline
    for timeline in timelines:
        for track in range(1,timeline.GetTrackCount('video')+1):
            if any(clip.GetFusionCompCount() for clip in (timeline.GetItemListInTrack('video',track) or [])):
                raise ValueError('This Resolve project has Fusion graphics but no compatible timeline format. Open a fresh dedicated project for this frame rate and canvas, then create a new approved revision. No timeline was created.')
    return None


def clear_duplicate(timeline):
    """Only the newly duplicated timeline is changed; its source template stays intact."""
    def items():
        return [clip for kind in ('video','audio','subtitle')
                for track in range(1,timeline.GetTrackCount(kind)+1)
                for clip in (timeline.GetItemListInTrack(kind,track) or [])]
    clips=items()
    if clips and not timeline.DeleteClips(clips,False):raise ValueError('Resolve could not clear the new timeline copy. Inspect its incomplete manifest.')
    if items():raise ValueError('The new timeline copy still contains clips. Inspect its incomplete manifest.')
