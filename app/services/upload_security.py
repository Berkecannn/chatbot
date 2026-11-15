"""Validate media while retaining original theme fields and font formats."""
import io
import re
import secrets
import struct
from pathlib import Path

from flask import abort, current_app
from PIL import Image, ImageSequence, UnidentifiedImageError
from werkzeug.utils import secure_filename

def validate_theme(theme):
    color = r'(?:#[0-9a-fA-F]{3,8}|transparent|(?:rgb|hsl)a?\([0-9.,%\s]+\))'
    for key, value in theme.items():
        if 'color' in key and not re.fullmatch(color, str(value)):
            abort(400, description='Geçersiz renk değeri.')
    size = str(theme.get('font_size', '14'))
    if not re.fullmatch(r'[0-9]{1,2}(?:px)?', size) or not 1 <= int(size.removesuffix('px')) <= 96:
        abort(400, description='Geçersiz yazı boyutu.')
    for key in ('font','custom_font_family'):
        value = theme.get(key)
        if value and (not isinstance(value,str) or len(value)>100 or
                      not all(c.isalnum() or c in ' _-,' for c in value)):
            abort(400, description='Geçersiz font ailesi adı.')

def save_media(file, folder, kind):
    raw=file.read(10*1024*1024+1)
    if not raw or len(raw)>10*1024*1024:
        abort(400, description='Dosya boş veya 10 MB sınırını aşıyor.')
    if kind=='image':
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format not in ('PNG','JPEG','WEBP','GIF') or image.width*image.height>16000000:
                    raise ValueError()
                count=getattr(image,'n_frames',1)
                if count>100 or image.width*image.height*count>32000000:
                    raise ValueError()
                output=io.BytesIO()
                if count>1:
                    durations=[];frames=[]
                    for frame in ImageSequence.Iterator(image):
                        durations.append(frame.info.get('duration',100))
                        frames.append(frame.convert('RGBA').copy())
                    frames[0].save(output,format='GIF',save_all=True,append_images=frames[1:],
                        duration=durations,loop=image.info.get('loop',0),disposal=2)
                    suffix='.gif'
                else:
                    image.load();image.convert('RGBA').save(output,format='PNG');suffix='.png'
                raw=output.getvalue()
        except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):
            abort(400, description='Geçerli bir görsel dosyası gereklidir.')
    else:
        suffix=Path(secure_filename(file.filename)).suffix.lower()
        if suffix not in ('.woff','.woff2','.ttf','.otf'):
            abort(400, description='WOFF, WOFF2, TTF veya OTF font gereklidir.')
        try:
            if suffix=='.woff2':
                signature,flavor,length,tables,reserved,total,compressed=struct.unpack('>4sIIHHII',raw[:24])
                if signature!=b'wOF2' or length!=len(raw) or not 1<=tables<=512 or reserved or not 12<=total<=32000000 or not 0<compressed<=len(raw)-48:
                    raise ValueError()
            else:
                from fontTools.ttLib import TTFont
                expected={'.woff':b'wOFF','.ttf':b'\x00\x01\x00\x00','.otf':b'OTTO'}[suffix]
                if not raw.startswith(expected):raise ValueError()
                font=TTFont(io.BytesIO(raw),lazy=False)
                font.close()
        except Exception:
            abort(400, description='Font dosyasının içeriği geçersiz.')
    name=secrets.token_hex(16)+suffix
    destination=Path(current_app.static_folder)/folder
    destination.mkdir(parents=True,exist_ok=True)
    (destination/name).write_bytes(raw)
    return folder+'/'+name
