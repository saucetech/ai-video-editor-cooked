"""Bounded portability adapter for saved visual analyses; never edits its source."""
import hashlib
import json
import math
import re
from pathlib import Path

TREATMENTS = ('panel', 'clean', 'editorial', 'spotlight')
MOTIONS = ('none', 'title', 'lower_third', 'hero', 'outline', 'prompt_result')
DEFAULT = dict(treatment='clean', font='Arial', weight='Bold', size_pct=4.4, y_pct=82,
               words_per_phrase=5, color='#FFFFFF', accent='#C3DECB', case='sentence',
               box=False, shadow=False, stroke=False, entrance_s=.3)


def number(value, low, high, fallback):
    return value if type(value) in (int,float) and math.isfinite(value) and low <= value <= high else fallback


def color(value, fallback):
    return value.upper() if isinstance(value,str) and re.fullmatch('#[0-9a-fA-F]{6}',value) else fallback


def normalize(data, name, digest):
    if not isinstance(data,dict):raise ValueError('The saved analysis must be an object.')
    caps=data.get('captions') or {};look=data.get('look') or {};graphics=data.get('graphics') or {}
    if not all(isinstance(x,dict) for x in (caps,look,graphics)):raise ValueError('Invalid saved style sections.')
    s=dict(DEFAULT);notes=[];transfer={}
    measured=caps.get('present') is True
    font=caps.get('font_match') if measured else look.get('closest_google_font')
    serif=look.get('font_class')=='serif' or any(x in str(font).lower() for x in ('serif','playfair','georgia','times'))
    s.update(treatment='editorial' if serif else 'clean',font='Georgia' if serif else 'Arial',weight='Regular' if serif else 'Bold')
    transfer['font']={'basis':'measured candidate' if measured else 'inferred visual estimate','requested':str(font or 'unknown')[:100],'applied':s['font']}
    if font!=s['font']:notes.append(f"Font approximation: {str(font or 'unknown source font')[:100]} → {s['font']} {s['weight']}; exact font not verified.")
    if not measured:notes.append('Caption detector reports absent or unknown. Visual notes are inferred; caption enablement remains your choice. Size and timing use declared defaults.')
    mapping={'size_pct':('size_pct',2,8),'y_pct':('y_pct',60,90),'words_per_phrase':('words_per_caption',1,8)}
    for key,(source,low,high) in mapping.items():
        raw=caps.get(source) if measured else None
        s[key]=number(raw,low,high,s[key]);transfer[key]={'basis':'measured' if raw==s[key] and raw is not None else 'default','applied':s[key]}
    s['words_per_phrase']=round(s['words_per_phrase'])
    s['color']=color(caps.get('color'),s['color']) if measured else s['color']
    s['case']=caps.get('case',look.get('caption_case','sentence'))
    if s['case'] not in ('sentence','lower','upper'):s['case']='sentence'
    for key in ('box','shadow','stroke'):s[key]=caps.get(key) is True if measured else False
    if s['shadow'] or s['stroke']:notes.append('Source shadow/stroke can use a contrast panel approximation; exact shading is unsupported. Board controls set the applied contrast.')
    palette=graphics.get('palette') or []
    if isinstance(palette,list):
        for entry in reversed(palette):
            candidate=entry.get('hex',entry.get('color')) if isinstance(entry,dict) else entry
            if color(candidate,'') and candidate.upper() not in ('#000000','#FFFFFF'):
                s['accent']=candidate.upper();break
    transfer['palette']={'basis':'sampled palette' if s['accent']!=DEFAULT['accent'] else 'default','applied':s['accent']}
    entrances=graphics.get('entrances') or []
    measured_entrances=[e for e in entrances if isinstance(e,dict) and number(e.get('duration_s'),.1,1,None) is not None] if isinstance(entrances,list) else []
    if measured_entrances:
        selected=max(measured_entrances,key=lambda e:number(e.get('n'),0,100000,0))
        s['entrance_s']=selected['duration_s']
        transfer['entrance_s']={'basis':'measured duration; approximated easing','applied':s['entrance_s']}
        notes.append(f"Measured entrance duration {s['entrance_s']:g}s is used with cubic-out easing; source easing {str(selected.get('ease','unknown'))[:80]} is approximated.")
    else:transfer['entrance_s']={'basis':'default','applied':s['entrance_s']}
    for key in ('color','case','box','shadow','stroke'):
        transfer[key]={'basis':'measured candidate' if measured and key in caps else 'inferred' if key=='case' and 'caption_case' in look else 'default','applied':s[key]}
    notes.append('Not transferred: source cut rhythm, graphic density/holds, media references, tracked layout, secondary motion and exact entrance/exit effects.')
    notes+=['Long-side size units are preserved; text is fitted into a two-line safe region.',
            'Original native recipes approximate source motion; source easing, glass refraction, tracked graphics and face placement are not reproduced.',
            'Word nodes remain editable in Fusion; changing their wording requires a board rebuild to reflow.']
    s.update(source={'name':str(name)[:160],'digest':str(digest)[:64]},transfer={**transfer,'notes':notes})
    return validate(s)


def validate(style):
    if not isinstance(style,dict):raise ValueError('Choose a valid caption style.')
    s=dict(style)
    if s.get('treatment') not in TREATMENTS or s.get('font') not in ('Arial','Georgia') or s.get('weight') not in ('Regular','Bold'):raise ValueError('Unsupported caption font or treatment.')
    for key,low,high in [('size_pct',2,8),('y_pct',60,90),('words_per_phrase',1,8),('entrance_s',.1,1)]:
        if number(s.get(key),low,high,None) is None:raise ValueError('Caption style values are out of bounds.')
    if type(s['words_per_phrase']) is not int:raise ValueError('Use an integer phrase length.')
    if s.get('case') not in ('sentence','lower','upper'):raise ValueError('Unsupported caption case.')
    for key in ('color','accent'):
        if not color(s.get(key),''):raise ValueError('Use a six-digit caption color.')
    if any(type(s.get(k)) is not bool for k in ('box','shadow','stroke')):raise ValueError('Invalid caption contrast setting.')
    if 'source' in s and (not isinstance(s['source'],dict) or any(not isinstance(s['source'].get(k),str) or len(s['source'][k])>160 for k in ('name','digest'))):raise ValueError('Invalid style source identity.')
    if 'transfer' in s and (not isinstance(s['transfer'],dict) or not isinstance(s['transfer'].get('notes'),list) or any(not isinstance(n,str) or len(n)>1000 for n in s['transfer']['notes'])):raise ValueError('Invalid style transfer notes.')
    if len(json.dumps(s,allow_nan=False))>12000:raise ValueError('Style snapshot is too large.')
    # Strip unknown keys before they can influence graph construction.
    return {k:s[k] for k in (*DEFAULT,'source','transfer') if k in s}


def style_path(root, ident):
    if not isinstance(ident,str) or not re.fullmatch(r'[\w-]{1,120}',ident):raise ValueError('Choose a saved style from the library.')
    root=Path(root).resolve();folder=(root/'creator-teardowns').resolve()
    if not folder.is_relative_to(root):raise ValueError('Style folder must stay inside the library.')
    path=(folder/ident/'style.json').resolve()
    if not path.is_relative_to(folder) or path.parent.name!=ident or not path.is_file():raise ValueError('Saved style is unavailable or outside the library.')
    return path


def load(root, ident):
    path=style_path(root,ident);raw=path.read_bytes()
    if len(raw)>2_000_000:raise ValueError('Saved style analysis is too large.')
    return normalize(json.loads(raw),ident,hashlib.sha256(raw).hexdigest())


def catalog(root):
    folder=Path(root).resolve()/'creator-teardowns';out=[]
    for path in sorted(folder.glob('*/style.json')):
        try:
            s=load(root,path.parent.name)
            out.append({'id':path.parent.name,'name':path.parent.name,'style':s})
        except (OSError,ValueError,TypeError):continue
        if len(out)>=100:break
    return out


def snapshot_words(raw):
    """Keep only alignment inputs; invalid timings remain explicit nulls, never invented."""
    if isinstance(raw,dict):raw=raw.get('words',[])
    if not isinstance(raw,list):return [{'invalid':True}]
    result=[]
    for word in raw:
        if not isinstance(word,dict):result.append({'invalid':True});continue
        text=word.get('word',word.get('text',''))
        result.append({'word':text if isinstance(text,str) else '',
                       **{key:number(word.get(key),0,1e10,None) for key in ('start','end')}})
    return result


def align_words(row, words, fps):
    """Exact normalized token alignment only; corrections never acquire invented times."""
    fallback='Word timing unavailable or caption correction differs from the transcript; static passage timing is used.'
    if isinstance(words,dict):words=words.get('words',[])
    if not isinstance(words,list):return None,fallback
    selected=[];previous=-1
    try:
        for w in words:
            a,b=w['start'],w['end']
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (a,b)) or a<0 or b<=a: return None,fallback
            if b<=row['start_frame']/fps or a>=row['end_frame']/fps:continue
            text=str(w.get('word',w.get('text',''))).strip()
            if len(text.split())!=1 or a<previous:return None,fallback
            previous=b
            selected.append({'text':text,'start':max(0,round(a*fps)-row['start_frame']),
                             'end':min(row['end_frame']-row['start_frame'],round(b*fps)-row['start_frame'])})
    except (TypeError,KeyError,ValueError):return None,fallback
    tokens=row['caption'].split()
    clean=lambda t:re.sub(r'[^\w]','',t).casefold()
    if not tokens or len(tokens)!=len(selected) or any(clean(t)!=clean(w['text']) or w['end']<=w['start'] for t,w in zip(tokens,selected)):return None,fallback
    for t,w in zip(tokens,selected):w['text']=t
    return selected,None
