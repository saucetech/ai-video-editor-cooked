"""Create original, explicitly synthetic footage/timings for manual native style acceptance.
Usage: installed-python tests/make_native_style_demo.py LIBRARY NEW_EDIT_NAME [--portrait] [--style SAVED_ID]
Requires existing FFmpeg/Pillow installation. Refuses to overwrite an existing edit.
"""
import argparse
import subprocess
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/ai-editor/lib/ai_editor'))
import edit_board as board
import board_styles


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library',type=Path);parser.add_argument('name');parser.add_argument('--portrait',action='store_true');parser.add_argument('--style')
    args=parser.parse_args();root=args.library.expanduser().resolve();path=root/'edits'/args.name
    if path.resolve().parent!=root/'edits' or path.exists():raise ValueError('Choose a new edit name inside the library; existing edits are never overwritten.')
    style=board_styles.load(root,args.style) if args.style else board_styles.normalize({},'Original synthetic default','synthetic')
    path.mkdir(parents=True);w,h=(360,640) if args.portrait else (1280,720)
    image=Image.new('RGB',(w,h),'#101216');draw=ImageDraw.Draw(image)
    scale=min(w,h)/360
    font=lambda px,bold=False:ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial'+(' Bold' if bold else '')+'.ttf',round(px*scale))
    draw.rounded_rectangle((w*.045,h*.03,w*.955,h*.97),radius=22*scale,fill='#171A20',outline='#30343E')
    draw.text((w*.09,h*.06),'GenMedia',font=font(16,True),fill='#F3F4F5')
    draw.text((w*.09,h*.10),'SYNTHETIC STUDIO',font=font(9),fill='#9DA6B2')
    draw.rounded_rectangle((w*.083,h*.16,w*.917,h*.65),radius=12*scale,fill='#202630')
    draw.text((w*.135,h*.45),'Shape the story.',font=font(14),fill='#B4BEC8')
    draw.text((w*.135,h*.49),'Give each idea room to land.',font=font(12),fill='#B4BEC8')
    for x,width,color in [(.135,.135,'#758D82'),(.285,.25,'#4F6B82'),(.55,.21,'#978878')]:draw.rounded_rectangle((w*x,h*.55,w*(x+width),h*.60),radius=4*scale,fill=color)
    draw.line((w*.445,h*.53,w*.445,h*.62),fill='#E8EBED',width=round(2*scale))
    draw.text((w*.09,h*.93),'Original demo / authored timing',font=font(10),fill='#929AA5')
    image.save(path/'studio.png')
    subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(path/'studio.png'),'-f','lavfi','-i','sine=frequency=220:sample_rate=48000','-t','12','-r','30','-c:v','libx264','-pix_fmt','yuv420p','-af','volume=.03','-c:a','aac',str(path/'source.mp4')],check=True)
    board.write(path/'report.json',{'source':str(path/'source.mp4'),'fps':30,'frames':[[0,120],[120,240],[240,360]]})
    board.write(path/'decisions.json',[{'start':i,'end':i+4} for i in (0,4,8)])
    texts=['Make every frame count.','Keep the story moving.','Your next edit starts here.']
    words=[{'word':word,'start':i*4+.2+j*.48,'end':i*4+.58+j*.48} for i,text in enumerate(texts) for j,word in enumerate(text.split())]
    board.write(path/'words.raw.json',words)
    state=board.load(path)
    for row,text,kind,treatment in zip(state['rows'],texts,['hero','outline','prompt_result'],['editorial','clean','spotlight']):
        row.update(caption_enabled=True,caption=text,caption_treatment=treatment,caption_style=style,motion=kind,
                   motion_text={'hero':'Make every frame count.','outline':'Keep the story moving.','prompt_result':'Start with a thought.'}[kind],motion_result='Finish with a story.' if kind=='prompt_result' else '')
    state=board.save(path,state['version'],state['rows'],[root])
    print(path);print(board.preview(path,state['version'])['revision']['id'])

if __name__=='__main__':main()
