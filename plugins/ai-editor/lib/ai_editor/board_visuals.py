"""Explicit board visuals, immutable local media, and original editable Fusion recipes."""
import hashlib
import json
import math
import shutil
import uuid
import subprocess
from fractions import Fraction
from pathlib import Path

FIELDS = ('caption_enabled', 'caption', 'motion', 'motion_text', 'broll', 'broll_start')
VIDEO_EXTS = {'.mp4', '.mov', '.m4v', '.webm', '.mkv'}


def row_defaults(row):
    return {'caption_enabled': False, 'caption': row.get('text', '')[:500], 'motion': 'none',
            'motion_text': '', 'broll': '', 'broll_start': 0.0, **row}


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''): digest.update(chunk)
    return digest.hexdigest()


def media_info(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                            check=True, capture_output=True, text=True, timeout=30)
    data = json.loads(result.stdout)
    video = next(s for s in data['streams'] if s['codec_type'] == 'video')
    return {'width': int(video['width']), 'height': int(video['height']),
            'fps': float(Fraction(video['r_frame_rate'])),
            'duration': float(video.get('duration') or data['format']['duration'])}


def owned_video(value, roots):
    path = Path(value).expanduser().resolve()
    if not any(path.is_relative_to(Path(root).resolve()) for root in roots) or path.suffix.lower() not in VIDEO_EXTS or not path.is_file():
        raise ValueError('Choose B-roll from the library or upload a local video first.')
    return path


def copy_checked(source, destination, expected):
    """Copy bytes before preparation; the renderer never reopens a mutable selection."""
    temporary = destination.with_name(destination.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        shutil.copyfile(source, temporary)
        if file_hash(temporary) != expected:
            raise ValueError('Selected B-roll changed while copying. Select it again.')
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def promote_staged(path, roots):
    path = owned_video(str(path), roots)
    for root in map(lambda r: Path(r).resolve(), roots):
        if path.is_relative_to(root) and path.relative_to(root).parts[0] == '.staged':
            digest = file_hash(path)
            destination = (root / 'assets/broll' / digest / path.name).resolve()
            if not destination.is_relative_to(root):raise ValueError('B-roll storage must stay inside the library.')
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                if file_hash(destination) != digest:raise ValueError('Saved B-roll changed. Add the original again.')
                return destination
            return copy_checked(path, destination, digest)
    return path


def validate_row(row, roots):
    row = row_defaults(row)
    if type(row['caption_enabled']) is not bool: raise ValueError('Caption enabled must be checked or unchecked.')
    for key, limit in [('caption', 500), ('motion_text', 180)]:
        text = row[key]
        if not isinstance(text, str) or len(text) > limit or any(ord(c) < 32 and c not in '\n\t' for c in text):
            raise ValueError('Caption or motion text is invalid or too long.')
    if row['motion'] not in ('none', 'title', 'lower_third'): raise ValueError('Choose a supported motion treatment.')
    if row['caption_enabled'] and not row['caption'].strip(): raise ValueError('Enter caption text before enabling it.')
    if row['motion'] != 'none' and not row['motion_text'].strip(): raise ValueError('Enter the title or lower-third text.')
    offset = row['broll_start']
    if type(offset) not in (int, float) or not math.isfinite(offset) or offset < 0: raise ValueError('B-roll in-point must be a nonnegative number of seconds.')
    if not isinstance(row['broll'], str): raise ValueError('Choose a local B-roll video.')
    if row['broll']:
        path = promote_staged(row['broll'], roots)
        row['broll'] = str(path)
        row['broll_identity'] = file_hash(path)
    else: row.pop('broll_identity', None)
    return row


def cues(rows):
    result, record = [], 0
    for source in rows:
        row = row_defaults(source)
        if not row['keep']: continue
        duration = row['end_frame'] - row['start_frame']
        result.append({**row, 'start': record, 'end': record + duration, 'source_start': row['start_frame']})
        record += duration
    return result


def fusion_comp(text, frames, kind='caption', width=1920, height=1080, size=None):
    """A fixed node graph; user text is only a quoted StyledText value, never code."""
    text = json.dumps(text, ensure_ascii=False)
    center = '.15' if kind == 'caption' else '.7' if kind == 'title' else '.31'
    size = size or (.065 if kind == 'title' else .052)
    ramp = max(1, min(8, frames // 3))
    end_ramp = max(ramp + 1, frames - ramp - 1)
    opacity = 'Value = 1' if kind == 'caption' or frames < 4 else 'SourceOp = "GenMediaOpacity", Source = "Value"'
    return f'''{{
Tools = ordered() {{
 GenMediaText = TextPlus {{ Inputs = {{
  StyledText = Input {{ Value = {text} }}, Font = Input {{ Value = "Arial" }}, Style = Input {{ Value = "Bold" }},
  Size = Input {{ Value = {size} }}, Center = Input {{ Value = {{ .5, {center} }} }},
  Red1 = Input {{ Value = 1 }}, Green1 = Input {{ Value = 1 }}, Blue1 = Input {{ Value = 1 }},
  UseFrameFormatSettings = Input {{ Value = 1 }}
 }} }},
 GenMediaMask = RectangleMask {{ Inputs = {{ Center = Input {{ Value = {{ .5, {center} }} }}, Width = Input {{ Value = .88 }}, Height = Input {{ Value = .21 }}, CornerRadius = Input {{ Value = .04 }} }} }},
 GenMediaCard = Background {{ Inputs = {{ Width = Input {{ Value = {width} }}, Height = Input {{ Value = {height} }}, UseFrameFormatSettings = Input {{ Value = 1 }}, TopLeftRed = Input {{ Value = .025 }}, TopLeftGreen = Input {{ Value = .03 }}, TopLeftBlue = Input {{ Value = .04 }}, TopLeftAlpha = Input {{ Value = .82 }}, EffectMask = Input {{ SourceOp = "GenMediaMask", Source = "Mask" }} }} }},
 GenMediaPanel = Merge {{ Inputs = {{ Background = Input {{ SourceOp = "GenMediaCard", Source = "Output" }}, Foreground = Input {{ SourceOp = "GenMediaText", Source = "Output" }} }} }},
 GenMediaClear = Background {{ Inputs = {{ Width = Input {{ Value = {width} }}, Height = Input {{ Value = {height} }}, UseFrameFormatSettings = Input {{ Value = 1 }}, TopLeftAlpha = Input {{ Value = 0 }} }} }},
 GenMediaOutput = Merge {{ Inputs = {{ Background = Input {{ SourceOp = "GenMediaClear", Source = "Output" }}, Foreground = Input {{ SourceOp = "GenMediaPanel", Source = "Output" }}, Blend = Input {{ {opacity} }} }} }},
 GenMediaOpacity = BezierSpline {{ SplineColor = {{ Red = 180, Green = 200, Blue = 225 }}, KeyFrames = {{ [0] = {{ 0 }}, [{ramp}] = {{ 1 }}, [{end_ramp}] = {{ 1 }}, [{frames - 1}] = {{ 0 }} }} }},
 MediaOut1 = MediaOut {{ Inputs = {{ Index = Input {{ Value = "0" }}, Input = Input {{ SourceOp = "GenMediaOutput", Source = "Output" }} }} }}
}}, ActiveTool = "GenMediaText"
}}'''


def verify_bundle(path):
    path = Path(path).resolve()
    bundle = json.loads((path / 'visuals.json').read_text(encoding='utf-8'))
    if bundle.get('schema') != 1: raise ValueError('Unsupported visual bundle.')
    for name, expected in bundle['files'].items():
        file = (path / name).resolve()
        if not file.is_relative_to(path) or not file.is_file() or file_hash(file) != expected:
            raise ValueError('Visual asset integrity changed. Build and approve a new preview.')
    return bundle


def _font(size):
    from PIL import ImageFont
    choices = ['/System/Library/Fonts/Supplemental/Arial Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf']
    for font in choices:
        if Path(font).is_file(): return ImageFont.truetype(font, size)
    raise ValueError('A supported local caption font is missing (Arial Bold or DejaVu Sans Bold).')


def _text_image(text, width, height, kind):
    from PIL import Image, ImageDraw
    image = Image.new('RGBA', (width, height)); draw = ImageDraw.Draw(image)
    size = max(12, round(height * (.065 if kind == 'title' else .052)))
    while True:
        font = _font(size)
        lines, line = [], ''
        for word in text.split():
            candidate = (line + ' ' + word).strip()
            if draw.textlength(candidate, font=font) > width * .78 and line: lines.append(line); line = word
            else: line = candidate
        lines.append(line); wrapped = '\n'.join(lines)
        box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=4, align='center')
        if (box[2] - box[0] <= width * .82 and box[3] - box[1] <= height * .17) or size <= max(10, height * .025): break
        size -= 1
    if box[2] - box[0] > width * .84 or box[3] - box[1] > height * .18:
        raise ValueError('Caption or title is too dense for this frame. Shorten the text or split the source passage.')
    y = height * (.85 if kind == 'caption' else .3 if kind == 'title' else .69)
    draw.rounded_rectangle((width*.06, y-height*.105, width*.94, y+height*.105), radius=height*.015, fill=(6,8,10,209))
    draw.multiline_text((width/2, y), wrapped, font=font, fill='white', spacing=4, anchor='mm', align='center')
    return image, wrapped, size / height


def compile_bundle(path, rows, report):
    import edit_board
    path = Path(path); info = media_info(report['source']); fps = float(report['fps'])
    # Preview and native canvas share this bounded raster size; source clips remain original media.
    scale = min(1, 1280/max(info['width'],info['height']))
    width,height = [max(2, round(info[k]*scale/2)*2) for k in ('width','height')]
    rate = format(fps, '.10g'); events = cues(rows)
    bundle = {'schema':1,'width':width,'height':height,'native_width':info['width'],'native_height':info['height'],'fps':fps,'duration':sum(r['end']-r['start'] for r in events), 'layers':[], 'files':{}}
    srt=[]
    folder=path/'visual-media';folder.mkdir()
    for index,row in enumerate(events):
        duration=row['end']-row['start']; seconds=duration/fps
        if row['broll']:
            original=Path(row['broll'])
            if file_hash(original)!=row.get('broll_identity'):raise ValueError('Selected B-roll changed. Select it again before previewing.')
            snapshot=folder/f"original-broll-{row['broll_identity']}{original.suffix.lower()}"
            if not snapshot.exists():copy_checked(original,snapshot,row['broll_identity'])
            details=media_info(snapshot)
            if row['broll_start']+seconds > details['duration'] + 1e-6:raise ValueError('B-roll is shorter than this passage from the selected in-point.')
            out=folder/f'broll-{index}.mov'
            edit_board.run_renderer(['ffmpeg','-v','error','-y','-ss',str(row['broll_start']),'-i',str(snapshot),'-an','-vf',f"fps={rate},scale={info['width']}:{info['height']}:force_original_aspect_ratio=increase,crop={info['width']}:{info['height']},setsar=1",'-frames:v',str(duration),'-c:v','prores_ks','-profile:v','2',str(out)])
            count=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries','stream=nb_read_frames','-of','json',str(out)],timeout=60))
            if int(count['streams'][0]['nb_read_frames']) != duration:raise ValueError('Prepared B-roll has fewer frames than this passage. Choose an earlier in-point or a longer clip.')
            bundle['layers'].append({'kind':'broll','track':2,'start':row['start'],'end':row['end'],'media':out.relative_to(path).as_posix(),'source_start':0,'origin':str(original),'original_in':row['broll_start']})
        for kind,text in [('caption',row['caption'] if row['caption_enabled'] else ''),(row['motion'],row['motion_text'] if row['motion']!='none' else '')]:
            if not text.strip():continue
            image,wrapped,size=_text_image(text,width,height,kind)
            stem=f'{kind}-{index}';png=folder/(stem+'.png');movie=folder/(stem+'.mov');comp=folder/(stem+'.comp')
            image.save(png)
            filters='format=rgba'
            if kind!='caption' and duration>=4:
                ramp=max(1,min(8,duration//3))/fps
                filters+=f',fade=t=in:st=0:d={ramp}:alpha=1,fade=t=out:st={max(ramp,seconds-ramp)}:d={ramp}:alpha=1'
            edit_board.run_renderer(['ffmpeg','-v','error','-y','-loop','1','-framerate',rate,'-i',str(png),'-vf',filters,'-frames:v',str(duration),'-an','-c:v','prores_ks','-profile:v','4','-pix_fmt','yuva444p10le',str(movie)])
            carrier=folder/(stem+'-carrier.mov')
            edit_board.run_renderer(['ffmpeg','-v','error','-y','-f','lavfi','-i',f"color=c=black@0:s={info['width']}x{info['height']}:r={rate},format=rgba",'-frames:v',str(duration),'-an','-c:v','prores_ks','-profile:v','4','-pix_fmt','yuva444p10le',str(carrier)])
            comp.write_text(fusion_comp(wrapped,duration,kind,info['width'],info['height'],size),encoding='utf-8')
            bundle['layers'].append({'kind':kind,'track':4 if kind=='caption' else 3,'start':row['start'],'end':row['end'],'media':carrier.relative_to(path).as_posix(),'preview_media':movie.relative_to(path).as_posix(),'comp':comp.relative_to(path).as_posix(),'text':wrapped,'source_start':0})
            if kind=='caption':srt.append((row['start']/fps,row['end']/fps,text))
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    (path/'captions.srt').write_text('\n'.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}\n' for i,(a,b,text) in enumerate(srt,1)),encoding='utf-8')
    for file in folder.iterdir():bundle['files'][file.relative_to(path).as_posix()]=file_hash(file)
    bundle['files']['captions.srt']=file_hash(path/'captions.srt')
    (path/'visuals.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2),encoding='utf-8')
    return bundle


def render_preview(path, rows, bundle):
    import edit_board
    path=Path(path);fps=bundle['fps'];width,height=bundle['width'],bundle['height']
    expr='1'
    for row in reversed(cues(rows)):
        if row['zoom']!=1:expr=f"if(gte(on,{row['start']})*lt(on,{row['end']}),{row['zoom']},{expr})"
    args=['ffmpeg','-v','error','-y','-i',str(path/'cut.mp4')]
    graph=[f"[0:v]scale={width}:{height},setsar=1,zoompan=z='{expr}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={fps}[base]"]
    layers=sorted(bundle['layers'],key=lambda x:x['track']);last='base'
    for i,layer in enumerate(layers,1):
        args+=['-i',str(path/layer.get('preview_media',layer['media']))]
        shift=layer['start']/fps;a,b=layer['start']/fps,layer['end']/fps
        graph.append(f'[{i}:v]scale={width}:{height},setpts=PTS-STARTPTS+{shift}/TB[layer{i}]')
        graph.append(f"[{last}][layer{i}]overlay=0:0:eof_action=pass:repeatlast=0:enable='gte(t,{a})*lt(t,{b})'[v{i}]");last=f'v{i}'
    args+=['-filter_complex',';'.join(graph),'-map',f'[{last}]','-map','0:a?','-frames:v',str(bundle['duration']),'-c:v','libx264','-crf','18','-preset','veryfast','-pix_fmt','yuv420p','-c:a','copy','-movflags','+faststart',str(path/'visual-preview.mp4')]
    edit_board.run_renderer(args)
    (path/'visual-preview.mp4').replace(path/'cut.mp4')
