"""Bound inline image payloads independently of original upload size."""
from io import BytesIO
from PIL import Image, ImageOps


def prepare_image(path, mime_type):
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        image.thumbnail((3200, 3200), Image.Resampling.LANCZOS)
        if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
            rgba = image.convert('RGBA')
            background = Image.new('RGB', rgba.size, 'white')
            background.paste(rgba, mask=rgba.getchannel('A'))
            image = background
        else:
            image = image.convert('RGB')
        for quality in (92, 85, 75, 65):
            buffer = BytesIO()
            image.save(buffer, 'JPEG', quality=quality, optimize=True)
            if buffer.tell() <= 1500 * 1024:
                return buffer.getvalue(), 'image/jpeg'
        raise ValueError('照片細節過多，請裁切成個別題目再上傳，避免壓縮造成文字不清楚')
