"""Timestamped native frame comparisons. A capture is evidence, never a fidelity score."""
import json
import math
import re
import subprocess
import time
import uuid
from pathlib import Path
import board_visuals
import resolve_lua
import resolve_visuals


def timecode(frame, fps):
    nominal=round(fps);frame=round(frame)
    return f'{frame//(3600*nominal):02}:{frame//(60*nominal)%60:02}:{frame//nominal%60:02}:{frame%nominal:02}'


def verify_files(folder, report):
    folder=Path(folder).resolve()
    for name,digest in report['files'].items():
        file=folder/name
        if not re.fullmatch(r'(native|preview)-[0-9]{1,3}\.png',name) or file.resolve().parent!=folder or file.is_symlink() or not file.is_file() or board_visuals.file_hash(file)!=digest:
            raise ValueError('Comparison files changed. Run a fresh Resolve comparison.')
    for frame in report['frames']:
        if any(frame[k] not in report['files'] for k in ('native','preview')):raise ValueError('Comparison frame is not verified.')
    return report


def capture_native(resolve, revision, bundle, manifest, folder):
    from PIL import Image
    project=resolve.GetProjectManager().GetCurrentProject()
    if not project or project.GetUniqueId()!=manifest['project_id']:raise ValueError('Open the Resolve project that owns this revision before comparing.')
    timeline=next((t for i in range(1,project.GetTimelineCount()+1) if (t:=project.GetTimelineByIndex(i)).GetUniqueId()==manifest['timeline_id']),None)
    if not timeline:raise ValueError('The saved Resolve timeline is no longer available.')
    if manifest.get('state')!='ready':raise ValueError('Only a completed native timeline can be compared.')
    previous=project.GetCurrentTimeline();page=resolve.GetCurrentPage();tc=timeline.GetCurrentTimecode()
    if ';' in tc:raise ValueError('Drop-frame still comparison is not yet supported. Native import remains available.')
    fps=bundle['fps'];settings=timeline.GetSettings()
    if (not math.isclose(float(settings['timelineFrameRate']),fps,abs_tol=.005)
            or int(settings['timelineResolutionWidth'])!=bundle.get('native_width',bundle['width'])
            or int(settings['timelineResolutionHeight'])!=bundle.get('native_height',bundle['height'])):raise ValueError('Native canvas or frame rate changed. Compare against a matching timeline format.')
    differences=[];points=set();controls=[];notes=[]
    for layer in bundle['layers']:
        duration=layer['end']-layer['start']
        for local in (0,min(duration-1,round(fps*.35)),duration//2,duration-1):points.add(layer['start']+local)
        notes.extend(layer.get('transfer_notes',[]))
    points=sorted(points)
    if len(points)>24:points=[points[round(i*(len(points)-1)/23)] for i in range(24)]
    # The comparison deliberately samples frames, never claims whole-video equivalence.
    report={'created':time.time(),'project_id':manifest['project_id'],'timeline_id':manifest['timeline_id'],
            'control_status':'matches','differences':differences,'controls':controls,'frames':[],'files':{},
            'notes':list(dict.fromkeys(notes))+['Sampled frames only; inspect playback for motion and pacing. Native font rasterization and color management can differ.',
             'This is a timestamped capture. Native changes after capture require Compare Resolve again.']}
    try:
        if not project.SetCurrentTimeline(timeline) or not resolve.OpenPage('edit'):raise ValueError('Resolve could not select the comparison timeline.')
        native_layers=manifest.get('native_layers',[])
        if len(native_layers)!=len(bundle['layers']):differences.append({'input':'native layers','actual':'Layer count differs from the approved bundle.'})
        for expected in bundle['layers']:
            record=next((r for r in native_layers if all(r.get(k)==expected.get(k) for k in ('kind','track','start','end'))),None)
            if not record:
                differences.append({'input':'native layer','actual':'Approved layer missing from native mapping.'});continue
            clips=timeline.GetItemListInTrack('video',record['track']) or []
            clip=next((c for c in clips if c.GetUniqueId()==record['native_id']),None)
            if not clip:
                differences.append({'node':record['native_id'],'input':'clip','actual':'missing'});continue
            if abs(clip.GetStart()-(timeline.GetStartFrame()+record['start']))>.001 or abs(clip.GetDuration()-(record['end']-record['start']))>.001:
                differences.append({'node':record['native_id'],'input':'timing','actual':'changed'})
            if expected.get('comp') or expected.get('checks'):
                comp=clip.GetFusionCompByIndex(1)
                checks=expected.get('checks') or [{'node':'GenMediaText','input':'StyledText','frame':None,'value':expected['text']}]
                if comp:
                    result=resolve_visuals.read_controls(comp,checks);controls.extend(result['values']);differences.extend(result['differences'])
                else:differences.append({'node':record['native_id'],'input':'composition','actual':'missing'})
        if manifest.get('snapshot'):
            import resolve_bridge
            snapshot,_=resolve_bridge._snapshot(timeline)
            if snapshot!=manifest['snapshot']:differences.append({'input':'timeline clips/properties','actual':'Native source or layer structure differs from the saved import.'})
        for i,frame in enumerate(points):
            native=f'native-{i}.png';preview=f'preview-{i}.png'
            if not timeline.SetCurrentTimecode(timecode(timeline.GetStartFrame()+frame,fps)):raise ValueError('Resolve could not seek to a comparison frame.')
            if not project.ExportCurrentFrameAsStill(str(folder/native)):raise ValueError('Resolve could not export the comparison frame.')
            # Decode by frame index, avoiding timestamp/keyframe seek rounding.
            subprocess.run(['ffmpeg','-v','error','-y','-i',str(revision/'cut.mp4'),'-vf',f'select=eq(n\\,{frame})','-frames:v','1',str(folder/preview)],check=True,timeout=60)
            with Image.open(folder/native) as image:
                if image.size!=(bundle.get('native_width',bundle['width']),bundle.get('native_height',bundle['height'])):raise ValueError('Native export returned an unexpected frame size.')
            for name in (native,preview):report['files'][name]=board_visuals.file_hash(folder/name)
            report['frames'].append({'frame':frame,'seconds':frame/fps,'native':native,'preview':preview})
        report['control_status']='diverged' if differences else 'matches'
        return verify_files(folder,report)
    finally:
        # A poisoned file session refuses all further requests rather than replaying unknown operations.
        if not timeline.SetCurrentTimecode(tc):raise ValueError('Could not restore the native playhead after comparison.')
        if previous and not project.SetCurrentTimeline(previous):raise ValueError('Could not restore the previous Resolve timeline.')
        if page and not resolve.OpenPage(page):raise ValueError('Could not restore the previous Resolve page.')


def capture(revision, runtime=None):
    revision=Path(revision).resolve();runtime=Path(runtime or Path.home()/'.ai-video-editor')
    if not resolve_lua.available(runtime):raise ValueError('Start the local Resolve Lua connection to compare native frames.')
    bundle=board_visuals.verify_bundle(revision);manifest=json.loads((revision/'resolve-manifest.json').read_text(encoding='utf-8'))
    folder=revision/'resolve-proof'/uuid.uuid4().hex
    if folder.resolve()!=folder:raise ValueError('Proof storage must stay inside the revision.')
    folder.mkdir(parents=True)
    with resolve_lua.Session(runtime) as session:
        session.permit_exports(folder)
        report=capture_native(session.resolve,revision,bundle,manifest,folder)
    report.update(id=folder.name,revision=revision.name,bundle_digest=board_visuals.file_hash(revision/'visuals.json'))
    (folder/'report.json').write_text(json.dumps(report,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf-8')
    return report
