"""Generate local secrets without changing the original web registration flow."""
import os
import re
import secrets
from pathlib import Path
from cryptography.fernet import Fernet
from dotenv import dotenv_values

def initialize(directory=None):
    root=Path(directory) if directory is not None else Path(__file__).resolve().parent
    target=root/'.env'
    content=target.read_text(encoding='utf-8-sig') if target.exists() else ''
    values=dotenv_values(target) if target.exists() else {}
    changed=False
    for name in ('FLASK_SECRET_KEY','JWT_SECRET_KEY'):
        if not values.get(name) or len(values[name])<32:
            line=name+'='+secrets.token_urlsafe(48)
            if re.search(r'^'+name+r'\s*=',content,re.M):
                content=re.sub(r'^'+name+r'\s*=.*$',line,content,flags=re.M)
            else:
                content=content.rstrip()+'\n'+line+'\n'
            changed=True
    encryption_key=values.get('ENCRYPTION_KEY')
    if encryption_key:
        Fernet(encryption_key.encode())  # Never replace the key for saved credentials.
    else:
        if (root/'data/settings.json').exists() and 'gAAAAA' in (root/'data/settings.json').read_text(encoding='utf-8-sig'):
            raise ValueError('Eski şifreli ayarlar bulundu. Önce orijinal ENCRYPTION_KEY değerini geri yükleyin.')
        content=content.rstrip()+'\nENCRYPTION_KEY='+Fernet.generate_key().decode()+'\n'
        changed=True
    if 'FLASK_DEBUG' not in values:
        content=content.rstrip()+'\nFLASK_DEBUG=False\n'
        changed=True
    if changed:
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as handle:handle.write(content)
    print('Yerel gizli ayarlar hazır. Yönetici hesabını orijinal Kayıt Ol ekranından oluşturabilirsiniz.')

if __name__=='__main__':initialize()
