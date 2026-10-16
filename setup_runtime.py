import urllib.request, zipfile, tarfile, io, hashlib, ssl, certifi
from pathlib import Path
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
root=Path(__file__).resolve().parent
runtime=root/'.runtime'/'php'
runtime.mkdir(parents=True,exist_ok=True)
url='https://downloads.php.net/~windows/releases/archives/php-8.5.11-nts-Win32-vs17-x64.zip'
data=urllib.request.urlopen(url,timeout=90).read()
assert hashlib.sha256(data).hexdigest()=='0ea96e0d2b9b737a6036f05cf4e95c49313faa6d0f27bd97edb2742503f0c043', 'PHP archive checksum mismatch'
with zipfile.ZipFile(io.BytesIO(data)) as z:
    for info in z.infolist():
        dest=(runtime/info.filename).resolve()
        if runtime.resolve() not in dest.parents: continue
        if not info.is_dir(): dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(info))
(runtime/'php.ini').write_text('extension_dir="'+str(runtime/'ext').replace('\\','/')+'"\nextension=curl\npost_max_size=32M\nupload_max_filesize=8M\nmax_file_uploads=8\nexpose_php=Off\n',encoding='utf-8')
vendor=root/'app'/'static'/'vendor';vendor.mkdir(parents=True,exist_ok=True)
packages=[('katex','0.16.9'),('marked','15.0.12'),('dompurify','3.2.6')]
for name,version in packages:
    data=urllib.request.urlopen('https://registry.npmjs.org/'+name+'/-/'+name+'-'+version+'.tgz',timeout=60).read()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        for member in archive.getmembers():
            suffix=None
            if name=='katex' and member.name.startswith('package/dist/'):
                rel=member.name[len('package/dist/'):]
                if rel in ['katex.min.js','katex.min.css'] or rel.startswith('fonts/') or rel=='contrib/auto-render.min.js': suffix='katex/'+('auto-render.min.js' if rel=='contrib/auto-render.min.js' else rel)
            if name=='marked' and member.name=='package/lib/marked.umd.js':suffix='marked.min.js'
            if name=='dompurify' and member.name=='package/dist/purify.min.js':suffix='purify.min.js'
            if suffix and member.isfile():
                dest=(vendor/suffix).resolve()
                if vendor.resolve() not in dest.parents:raise ValueError('Invalid archive path')
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.extractfile(member).read())
print('PHP runtime and local rendering assets ready')

