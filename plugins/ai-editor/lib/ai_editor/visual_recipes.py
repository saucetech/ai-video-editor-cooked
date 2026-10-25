"""Original portable scenes. Pixel geometry and sampled curves drive both renderers."""
import json
import math
from pathlib import Path
import board_styles


def font(family, weight, size):
    from PIL import ImageFont
    suffix=' Bold' if weight=='Bold' else ''
    candidates=[Path('/System/Library/Fonts/Supplemental')/(family+suffix+'.ttf'),
                Path('C:/Windows/Fonts')/('georgiab.ttf' if family=='Georgia' and suffix else 'georgia.ttf' if family=='Georgia' else 'arialbd.ttf' if suffix else 'arial.ttf')]
    for p in candidates:
        if p.is_file():return ImageFont.truetype(str(p),max(1,round(size)))
    raise ValueError(f'{family} {weight} must be installed for portable captions. No silent font replacement is used.')


def ease(t):
    t=max(0,min(1,t));return 1-(1-t)**3


def fit(text, width, height, size, family, weight, max_lines=2):
    """Explicit newlines survive. Refuse illegible text instead of squeezing forever."""
    from PIL import Image,ImageDraw
    d=ImageDraw.Draw(Image.new('RGBA',(1,1)))
    floor=max(12,min(width,height)*.035)
    for px in range(max(round(size),round(floor)),round(floor)-1,-1):
        f=font(family,weight,px);lines=[]
        for para in text.split('\n'):
            line=''
            for word in para.split():
                candidate=(line+' '+word).strip()
                if d.textlength(candidate,font=f)>width*.82 and line:lines.append(line);line=word
                else:line=candidate
            lines.append(line)
        if len(lines)<=max_lines and all(d.textlength(line,font=f)<=width*.84 for line in lines):return lines,px
    raise ValueError('Text is too dense for two lines. Shorten the caption or split the source passage.')


def build(row, kind, width, height, fps, words):
    frames=row['end_frame']-row['start_frame']
    if frames>round(fps*60):raise ValueError('Split passages longer than 60 seconds before adding advanced visuals.')
    style=board_styles.validate(row['caption_style']) if row.get('caption_style') else dict(board_styles.DEFAULT)
    nodes=[];notes=list(style.get('transfer',{}).get('notes',[]));timing='passage'
    ones=[1.0]*frames
    def add(type, **kw):
        node=dict(id='GenMedia'+str(len(nodes)+1),type=type,alpha=list(ones),scale=list(ones),**kw);nodes.append(node);return node
    def label(text,x,y,size,family,weight,color,alpha=None,role=None):
        n=add('text',text=text,x=x,y=y,size=size,font=family,weight=weight,color=color,role=role)
        if alpha is not None:n['alpha']=list(alpha)
        return n
    if kind=='caption':
        treatment=row.get('caption_treatment','clean');family='Georgia' if treatment=='editorial' else style['font'];weight='Regular' if family=='Georgia' else style['weight']
        text=row['caption'];transform=str.lower if style['case']=='lower' else str.upper if style['case']=='upper' else lambda x:x
        aligned,note=board_styles.align_words(row,words,fps)
        if note:notes.append(note);timing='passage fallback'
        else:timing='word timestamps'
        groups=[aligned[i:i+style['words_per_phrase']] for i in range(0,len(aligned),style['words_per_phrase'])] if aligned else [[{'text':t,'start':0,'end':frames} for t in text.split()]]
        manual_breaks='\n' in text
        if aligned and manual_breaks:groups=[aligned]
        # Authored line breaks take precedence over automatic phrase grouping.
        for page,group in enumerate(groups):
            content=transform(' '.join(w['text'] for w in group) if aligned and not manual_breaks else text)
            lines,size=fit(content,width,height,min(max(width,height)*style['size_pct']/100,height*.09),family,weight)
            y=min(height*.87,max(height*.65,height*style['y_pct']/100));line_height=size*1.3
            a=group[0]['start'] if aligned else 0
            b=groups[page+1][0]['start'] if aligned and page+1<len(groups) else frames
            alpha=[float(a<=i<b) for i in range(frames)]
            if style['box'] or style['shadow'] or style['stroke']:
                brightness=sum(int(style['color'][i:i+2],16)*weight for i,weight in zip((1,3,5),(.2126,.7152,.0722)))/255
                panel_color='#080A0E' if brightness>.5 else '#F4F4F5'
                add('rect',x=width/2,y=y,w=min(width*.9,max(font(family,weight,size).getlength(line) for line in lines)+size*1.2),h=len(lines)*line_height+size*.5,color=panel_color,opacity=.8,radius=size*.25)['alpha']=alpha
            if treatment=='spotlight' and aligned:
                f=font(family,weight,size);from PIL import Image,ImageDraw
                draw=ImageDraw.Draw(Image.new('RGBA',(1,1)));offset=0
                for line_index,line in enumerate(lines):
                    tokens=line.split();lengths=[draw.textlength(t,font=f) for t in tokens];gap=draw.textlength(' ',font=f)
                    x=(width-sum(lengths)-gap*(len(tokens)-1))/2
                    for t,length in zip(tokens,lengths):
                        word=group[offset];offset+=1;cy=y+(line_index-(len(lines)-1)/2)*line_height
                        label(t,x+length/2,cy,size,family,weight,style['color'],alpha,'base')
                        accent=[float(a<=i<b and word['start']<=i<word['end']) for i in range(frames)]
                        label(t,x+length/2,cy,size,family,weight,style['accent'],accent,'accent');x+=length+gap
            else:
                for line_index,line in enumerate(lines):label(line,width/2,y+(line_index-(len(lines)-1)/2)*line_height,size,family,weight,style['color'],alpha,'base')
    else:
        minimum=max(1.1,len(row['motion_text'].split())*.25+2*style['entrance_s'])
        if kind=='prompt_result':minimum=max(minimum,1.8,(len(row['motion_result'].split())*.22+2*style['entrance_s'])/.58)
        if frames<math.ceil(fps*minimum):raise ValueError(f'This hook is too short for a readable hold. Keep at least {minimum:g} seconds or choose a simple fade title.')
        ramp=min(round(fps*style['entrance_s']),frames//5);ramp=max(2,ramp)
        envelope=[min(ease(i/ramp),ease((frames-1-i)/ramp)) for i in range(frames)]
        scale=[.95+.05*ease(i/ramp) for i in range(frames)]
        lines,size=fit(row['motion_text'],width,height,min(width*.075,height*.095),'Arial','Bold')
        y=height*.32
        for j,line in enumerate(lines):
            n=label(line,width/2,y+(j-(len(lines)-1)/2)*size*1.25,size,'Arial','Bold',style['color'],envelope)
            if kind=='hero':n['scale']=scale
        accent=style['accent']
        if kind=='hero':add('rect',x=width/2,y=y+size*(len(lines)*.7+.6),w=width*.12,h=max(2,height*.006),color=accent,opacity=1)['alpha']=envelope
        if kind=='outline':
            bw=width*.89;bh=size*(len(lines)*1.3+1);thick=max(2,height*.004)
            for cy in (y-bh/2,y+bh/2):
                n=add('rect',x=width/2,y=cy,w=bw,h=thick,color=accent,opacity=1);n['alpha']=envelope;n['scale']=[ease(i/ramp) for i in range(frames)]
            for x in ((width-bw)/2,(width+bw)/2):add('rect',x=x,y=y,w=thick,h=bh,color=accent,opacity=1)['alpha']=envelope
        if kind=='prompt_result':
            phase=round(frames*.42);reveal=[envelope[i]*ease((i-phase)/ramp) for i in range(frames)]
            result_lines,result_size=fit(row['motion_result'],width,height,size*.85,'Georgia','Regular')
            brightness=sum(int(accent[i:i+2],16)*weight for i,weight in zip((1,3,5),(.2126,.7152,.0722)))/255
            panel_color='#080A0E' if brightness>.5 else '#F4F4F5'
            add('rect',x=width/2,y=height*.54,w=min(width*.88,max(font('Georgia','Regular',result_size).getlength(line) for line in result_lines)+result_size*1.2),h=result_size*(len(result_lines)*1.2+.7),color=panel_color,opacity=.92,radius=result_size*.25)['alpha']=reveal
            for j,line in enumerate(result_lines):label(line,width/2,height*.54+(j-(len(result_lines)-1)/2)*result_size*1.2,result_size,'Georgia','Regular',accent,reveal)
            add('rect',x=width/2,y=height*.44,w=width*.08,h=max(2,height*.004),color=accent,opacity=1)['alpha']=reveal
    if len(nodes)>80:raise ValueError('Too many editable word nodes in one passage. Split it into shorter passages.')
    return dict(schema=1,kind=kind,width=width,height=height,frames=frames,fps=fps,nodes=nodes,notes=notes,timing=timing)


def render(scene, frame):
    from PIL import Image,ImageDraw,ImageColor
    image=Image.new('RGBA',(scene['width'],scene['height']))
    for n in scene['nodes']:
        a=n['alpha'][frame]
        if a<=0:continue
        rgba=ImageColor.getrgb(n['color'])+(round(a*n.get('opacity',1)*255),)
        layer=Image.new('RGBA',image.size);d=ImageDraw.Draw(layer)
        if n['type']=='text':d.text((n['x'],n['y']),n['text'],font=font(n['font'],n['weight'],n['size']*n['scale'][frame]),fill=rgba,anchor='mm')
        else:
            w=n['w']*n['scale'][frame];h=n['h']
            d.rounded_rectangle((n['x']-w/2,n['y']-h/2,n['x']+w/2,n['y']+h/2),radius=n.get('radius',0),fill=rgba)
        image=Image.alpha_composite(image,layer)
    return image


def fusion(scene,width,height):
    """All geometry originates in the preview scene, scaled into native normalized space."""
    w,h=scene['width'],scene['height'];tools=[];checks=[];frames=scene['frames'];j=json.dumps
    def inp(value):return 'Input { Value = '+(j(value,ensure_ascii=False) if isinstance(value,str) else str(value))+' }'
    def curve(name,values):
        # Retain plateau boundaries so linear interpolation never fades a stepped word.
        keys=[i for i in range(len(values)) if i in (0,len(values)-1) or values[i]!=values[i-1] or (i+1<len(values) and values[i]!=values[i+1])]
        tools.append(name+' = BezierSpline { KeyFrames = { '+', '.join(f'[{i}] = {{ {values[i]:.9g}, Flags = {{ Linear = true }} }}' for i in keys)+' } }')
        return 'Input { SourceOp = '+j(name)+', Source = "Value" }'
    tools.append(f'GenMediaClear = Background {{ Inputs = {{ Width = {inp(width)}, Height = {inp(height)}, UseFrameFormatSettings = {inp(1)}, TopLeftAlpha = {inp(0)} }} }}')
    last='GenMediaClear'
    sample_frames=sorted(set([0,min(frames-1,round(scene['fps'])),frames//2,frames-1]))
    for n in scene['nodes']:
        name=n['id'];x,y=n['x']/w,1-n['y']/h
        rgb=[int(n['color'][i:i+2],16)/255 for i in (1,3,5)]
        if n['type']=='text':
            # Resolve 21.1.1 native held-frame calibration against the same installed TTFs.
            # Text+ nominal size differs from Pillow em size: Georgia was 6.36% narrower.
            metric_scale=1.065 if n['font']=='Georgia' else 1.045
            size=n['size']/w*4/3*metric_scale
            scaled=[size*v for v in n['scale']]
            inputs={'StyledText':inp(n['text']),'Font':inp(n['font']),'Style':inp(n['weight']),
                    'Size':curve(name+'Size',scaled),'Center':f'Input {{ Value = {{ {x}, {y} }} }}','UseFrameFormatSettings':inp(1),
                    **{k:inp(v) for k,v in zip(('Red1','Green1','Blue1'),rgb)}}
            tools.append(name+' = TextPlus { Inputs = { '+', '.join(k+' = '+v for k,v in inputs.items())+' } }')
            for key,value in [('StyledText',n['text']),('Font',n['font']),('Style',n['weight']),*zip(('Red1','Green1','Blue1'),rgb)]:checks.append(dict(node=name,input=key,value=value,frame=None))
            for i in sorted(set([0,frames-1,frames//2])):checks.append(dict(node=name,input='Size',value=scaled[i],frame=i))
        else:
            mask=name+'Mask';widths=[n['w']/w*v for v in n['scale']]
            tools.append(mask+' = RectangleMask { Inputs = { Center = Input { Value = { '+f'{x}, {y}'+' } }, Width = '+curve(mask+'Width',widths)+', Height = '+inp(n['h']/h)+', CornerRadius = '+inp(n.get('radius',0)/n['h'])+' } }')
            tools.append(name+' = Background { Inputs = { '+', '.join(['Width = '+inp(width),'Height = '+inp(height),'UseFrameFormatSettings = '+inp(1),*['TopLeft'+k+' = '+inp(v) for k,v in zip(('Red','Green','Blue'),rgb)],'TopLeftAlpha = '+inp(n['opacity']),'EffectMask = Input { SourceOp = '+j(mask)+', Source = "Mask" }'])+' } }')
            for key,value in [*zip(('TopLeftRed','TopLeftGreen','TopLeftBlue'),rgb),('TopLeftAlpha',n['opacity'])]:checks.append(dict(node=name,input=key,value=value,frame=None))
            for i in (0,frames//2,frames-1):checks.append(dict(node=mask,input='Width',value=widths[i],frame=i))
        merge=name+'Merge';blend=curve(merge+'Alpha',n['alpha'])
        tools.append(merge+' = Merge { Inputs = { Background = Input { SourceOp = '+j(last)+', Source = "Output" }, Foreground = Input { SourceOp = '+j(name)+', Source = "Output" }, Blend = '+blend+' } }')
        # Include an active word sample and the frame immediately after it, beyond generic hold points.
        active=next((i for i,v in enumerate(n['alpha']) if v==1),None)
        samples=set(sample_frames)
        if active is not None:samples.add(active)
        inactive=next((i for i in range((active or 0)+1,frames) if n['alpha'][i]==0),None)
        if inactive is not None:samples.add(inactive)
        for i in sorted(samples):checks.append(dict(node=merge,input='Blend',frame=i,value=n['alpha'][i]))
        last=merge
    tools.append('MediaOut1 = MediaOut { Inputs = { Index = Input { Value = "0" }, Input = Input { SourceOp = '+j(last)+', Source = "Output" } } }')
    return '{ Tools = ordered() {\n'+',\n'.join(tools)+'\n} }',checks
