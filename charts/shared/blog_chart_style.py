"""Shared blog chart appearance, calibrated against published 1AEO figures.

Font sizes are renderer points; targets refer to the resulting article pixels.
This module contains no post data, private identities or publishing behavior.
"""
from pathlib import Path
import html
import math
import re
from xml.parsers import expat

FONT_FAMILY = 'Arial'
SVG_FONT_STACK = "Arial, Helvetica, sans-serif"
PALETTE = {
    'background':'#191f20', 'text':'#e1e7e6', 'muted':'#bdc8c9',
    'grid':'#3e4b4d', 'axis':'#687171', 'missing':'#697373',
    'begin_dir':'#48d9ef', 'hs_get':'#f1d05d', 'hs_post':'#f2eced',
    'closed_wait':'#ff9873', 'written':'#55dda3', 'read':'#aabaff',
    'consensus':'#7b7ddb', 'mixed':'#8c9897',
    'relay_bm':'#62b5ff', 'relay_o':'#55dda3',
}
MAIN_WIDTH = 800
NARROW_WIDTH = 360
MAIN_BREAKPOINT = 768
# The 800px published compression chart is the reference desktop hierarchy.
DESKTOP_PX = {'title':24, 'subtitle':17, 'panel':16, 'axis':14,
              'tick':13, 'legend':14, 'annotation':14, 'source':13}
MOBILE_PX = {'title':20, 'subtitle':16, 'panel':16, 'axis':15,
             'tick':15, 'legend':15, 'annotation':15, 'source':14}
MOBILE_MIN_PX = {'title':15, 'subtitle':12, 'panel':12, 'axis':11.5,
                 'tick':11.5, 'legend':11.5, 'annotation':11.5, 'source':10.5}

def points(role, width_inches, narrow=False, display_width=None):
    """Choose points for the actual display cap. Narrow caps are 270–360px;
    the minimum covers a 270px image at a 320px viewport.
    """
    width_pt=_positive_size(width_inches,'Figure width')*72
    reference=_positive_size(display_width if display_width is not None else
                             NARROW_WIDTH if narrow else MAIN_WIDTH,'Display width')
    if narrow and not 270<=reference<=NARROW_WIDTH:
        raise ValueError('Narrow image display width must be between 270 and 360 pixels')
    value=(MOBILE_PX if narrow else DESKTOP_PX)[role]*width_pt/reference
    if narrow:value=max(value,MOBILE_MIN_PX[role]*width_pt/270)
    return round(value,3)

def displayed_pixels(font_pt, svg_width_pt, image_width_px):
    return (_positive_size(font_pt,'Font size')*_positive_size(image_width_px,'Image width')
            /_positive_size(svg_width_pt,'SVG width'))

def _positive_size(value,label):
    try:value=float(value)
    except (TypeError,ValueError,OverflowError) as error:
        raise ValueError(label+' must be positive and finite') from error
    if not math.isfinite(value) or value<=0:raise ValueError(label+' must be positive and finite')
    return value

def configure(matplotlib):
    matplotlib.rcParams.update({
        'font.family':'sans-serif','font.sans-serif':['Arial','Helvetica','DejaVu Sans'],
        'text.color':PALETTE['text'],'axes.labelcolor':PALETTE['text'],
        'xtick.color':PALETTE['muted'],'ytick.color':PALETTE['muted'],
        'axes.edgecolor':PALETTE['axis'],'axes.facecolor':PALETTE['background'],
        'figure.facecolor':PALETTE['background'],'grid.color':PALETTE['grid'],
        'svg.fonttype':'none','path.simplify':False,
    })

def style_axes(ax, narrow=False, display_width=None, legend=True):
    width=ax.figure.get_size_inches()[0]
    size=lambda role:points(role,width,narrow,display_width)
    ax.tick_params(labelsize=size('tick'))
    ax.xaxis.label.set_fontsize(size('axis'));ax.yaxis.label.set_fontsize(size('axis'))
    for title in [ax.title,ax._left_title,ax._right_title]:
        title.set_fontsize(size('panel'));title.set_fontweight('bold')
    if legend and ax.get_legend():
        for t in ax.get_legend().get_texts():t.set_fontsize(size('legend'));t.set_fontweight('normal')
    for line in ax.get_xgridlines()+ax.get_ygridlines():
        line.set_color(PALETTE['grid']);line.set_alpha(.55);line.set_linewidth(.65)
    return size

def svg_font_fallback(path):
    """Normalize generated SVG font declarations without changing chart text.

    XML offsets preserve all other bytes, including metadata and geometry.
    Support UTF-8 SVG font-family attributes and CSS font-family/font declarations.
    """
    path=Path(path);svg=path.read_bytes();edits=[];style_starts=[]
    try:svg.decode('utf-8-sig')
    except UnicodeDecodeError as error:
        raise ValueError('SVG font normalization requires UTF-8 XML') from error
    if b'\x00' in svg:raise ValueError('SVG font normalization requires UTF-8 XML')
    parser=expat.ParserCreate()
    def declaration(version,encoding,standalone):
        if encoding is not None and encoding.lower() not in {'utf-8','utf8','ascii','us-ascii'}:
            raise ValueError('SVG font normalization requires UTF-8 XML')
    def start(name,attrs):
        offset=parser.CurrentByteIndex
        tag=re.match(rb'<(?:[^>\"\x27]|\"[^\"]*\"|\x27[^\x27]*\x27)*>',svg[offset:]).group()
        for match in re.finditer(rb'([^\s=<>/\"\x27]+)\s*=\s*([\"\x27])(.*?)\2',tag,re.S):
            if match[1] not in (b'style',b'font-family'):continue
            raw=match[3].decode()
            if match[1]==b'style':updated=_font_xml_css(raw,attribute=True)
            else:
                value=html.unescape(raw);family=_font_family(value)
                updated=html.escape(family,quote=True) if family!=value else raw
            if updated!=raw:
                edits.append((offset+match.start(3),offset+match.end(3),updated.encode()))
        if name.split(':')[-1]=='style':style_starts.append(offset+len(tag))
    def end(name):
        if name.split(':')[-1]=='style':
            begin=style_starts.pop();finish=parser.CurrentByteIndex
            value=svg[begin:finish].decode();updated=_font_xml_css(value)
            if updated!=value:edits.append((begin,finish,updated.encode()))
    parser.XmlDeclHandler=declaration
    parser.StartElementHandler=start;parser.EndElementHandler=end
    parser.Parse(svg,True)
    for begin,end,updated in sorted(edits,reverse=True):svg=svg[:begin]+updated+svg[end:]
    if edits:path.write_bytes(svg)

def _font_family(value):
    # A comma inside a quoted family belongs to that one name, not the stack.
    parts=[];begin=0;quote=None
    for i,char in enumerate(value):
        if char=='\\':return value  # Preserve escaped/custom family spellings.
        if quote:
            if char==quote:quote=None
        elif char in ('\"',"'"):quote=char
        elif char==',':parts.append(value[begin:i]);begin=i+1
    if quote:return value
    parts.append(value[begin:])
    families=[]
    for part in parts:
        family=part.strip()
        if len(family)>=2 and family[0] in ('\"',"'") and family[-1]==family[0]:
            family=family[1:-1]
        families.append(family)
    known={'Arial','Helvetica','DejaVu Sans','sans-serif'}
    return SVG_FONT_STACK if families and all(family in known for family in families) else value

def _font_css(css):
    for begin,end,updated in reversed(_font_css_edits(css)):
        css=css[:begin]+updated+css[end:]
    return css

def _font_css_edits(css):
    """Find declarations outside CSS strings, comments and function arguments."""
    edits=[]
    def declaration(begin,end):
        match=re.fullmatch(r'(?P<prefix>(?:\s|/\*.*?\*/)*)'
                           r'(?P<property>font-family|font)\s*:\s*(?P<value>.*)',
                           css[begin:end],re.S|re.I)
        if not match:return
        value=match['value'];important=''
        suffix=re.search(r'\s*!\s*important\s*$',value,re.I)
        if suffix:
            important=value[suffix.start():];value=value[:suffix.start()]
        if match['property'].lower()=='font-family':updated=_font_family(value)
        else:
            # Matplotlib font shorthand: optional weight/style, size, family.
            size=re.fullmatch(r'(.*?\b[\d.]+(?:px|pt)(?:\s*/\s*[\d.]+(?:px|pt|%)?)?\s+)(.+)',value,re.S)
            updated=size[1]+_font_family(size[2]) if size else value
        updated+=important
        if updated!=match['value']:edits.append((begin+match.start('value'),end,updated))
    begin=0;i=0;quote=None;depth=0
    while i<len(css):
        char=css[i]
        if char=='\\':i+=2;continue
        if quote:
            if char==quote:quote=None
        elif css.startswith('/*',i):
            end=css.find('*/',i+2)
            i=len(css) if end<0 else end+2
            continue
        elif char in ('\"',"'"):quote=char
        elif char in '([':depth+=1
        elif char in ')]':depth=max(0,depth-1)
        elif char in ';{}' and not depth:
            declaration(begin,i);begin=i+1
        i+=1
    if not quote and not depth:declaration(begin,len(css))
    return edits

def _font_xml_css(source, *, attribute=False):
    """Map decoded stylesheet edits back to XML without re-escaping its text."""
    decoded=[];positions=[];i=0;region=0;in_cdata=False
    def append(text,begin,end):
        for char in text:
            decoded.append(char);positions.append((begin,end,region,in_cdata))
    while i<len(source):
        if source.startswith('<![CDATA[',i):
            region+=1;in_cdata=True;end=source.index(']]>',i+9)
            for position in range(i+9,end):append(source[position],position,position+1)
            i=end+3;region+=1;in_cdata=False
        elif source.startswith('<!--',i):
            i=source.index('-->',i+4)+3;region+=1
        elif source[i]=='&':
            end=source.index(';',i)+1
            append(html.unescape(source[i:end]),i,end);i=end
        else:
            append(source[i],i,i+1);i+=1
    edits=[]
    for begin,end,updated in _font_css_edits(''.join(decoded)):
        # Preserve wrappers if a declaration crosses XML text/CDATA regions.
        if positions[begin][2]!=positions[end-1][2]:continue
        left,right=positions[begin][0],positions[end-1][1]
        # Normalized fonts contain no XML-special text; only the untouched
        # shorthand prefix could need escaping outside a CDATA section.
        if not positions[begin][3]:
            updated=html.escape(updated,quote=attribute)
        edits.append((left,right,updated))
    for begin,end,updated in reversed(edits):source=source[:begin]+updated+source[end:]
    return source
