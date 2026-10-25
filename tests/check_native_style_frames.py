"""Compare visible held-caption bounds from an actual native proof (manual QA, no vendor mock).
Usage: python tests/check_native_style_frames.py /absolute/path/to/report.json
Only first-passage held frames are used; neutral synthetic QA footage is required.
This geometry check is not a general video-quality or pixel-equivalence score.
"""
import json
import sys
from pathlib import Path
from PIL import Image


def bounds(path):
    image=Image.open(path).convert('RGB');w,h=image.size
    mask=image.crop((round(w*.05),round(h*.74),round(w*.95),round(h*.9))).point(lambda v:255 if v>=220 else 0)
    import PIL.ImageChops
    r,g,b=mask.split();box=PIL.ImageChops.multiply(PIL.ImageChops.multiply(r,g),b).getbbox()
    if not box:raise ValueError('Held caption pixels are missing from the expected QA region.')
    return (box[2]-box[0])/w,(box[3]-box[1])/h


def main():
    path=Path(sys.argv[1]);report=json.loads(path.read_text(encoding='utf-8'));results=[]
    for frame in report['frames']:
        if not .3<=frame['seconds']<=1.6:continue
        native=bounds(path.parent/frame['native']);preview=bounds(path.parent/frame['preview'])
        error=abs(native[0]/preview[0]-1)
        results.append({'frame':frame['frame'],'native_width':native[0],'preview_width':preview[0],'width_error':round(error,4)})
    print(json.dumps(results,indent=2))
    if not results or any(r['width_error']>.04 for r in results):raise SystemExit('Native caption width differs by more than 4%; calibrate before accepting this recipe.')

if __name__=='__main__':main()
