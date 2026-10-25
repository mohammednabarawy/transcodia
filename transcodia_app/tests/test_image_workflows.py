from dataclasses import asdict
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageOps

from transcodia_app.handlers.image_handler import ImageConfig, ImageConverter


@pytest.mark.parametrize("extension,expected", [("webp", "WEBP"), ("jpg", "JPEG"), ("png", "PNG"), ("ico", "ICO"), ("bmp", "BMP"), ("gif", "GIF"), ("tiff", "TIFF"), ("tga", "TGA")])
def test_every_picture_format_can_be_reopened(sample_image, tmp_path, extension, expected):
    target = tmp_path / "nested" / f"converted.{extension}"
    assert ImageConverter.convert_image(sample_image, str(target))
    with Image.open(target) as image:
        image.load()
        assert image.format == expected
        assert image.width > 0 and image.height > 0


@pytest.mark.parametrize("angle,flip_h,flip_v", [(90, False, False), (180, False, False), (270, False, False), (0, True, False), (0, False, True), (90, True, True)])
def test_transform_changes_actual_pixels(sample_image, tmp_path, angle, flip_h, flip_v):
    target = str(tmp_path / "result.png")
    config = ImageConfig(rotate_angle=angle, flip_h=flip_h, flip_v=flip_v)
    assert ImageConverter.convert_image(sample_image, target, config)
    with Image.open(sample_image) as source, Image.open(target) as actual:
        expected = source.copy().rotate(-angle, expand=True)
        if flip_h:
            expected = ImageOps.mirror(expected)
        if flip_v:
            expected = ImageOps.flip(expected)
        assert actual.size == expected.size
        assert actual.tobytes() == expected.tobytes()


@pytest.mark.parametrize("keep,expected", [(True, (20, 10)), (False, (20, 20))])
def test_resize_checks_dimensions(sample_image, tmp_path, keep, expected):
    target = str(tmp_path / "resized.png")
    assert ImageConverter.convert_image(sample_image, target, ImageConfig(width=20, height=20, keep_aspect_ratio=keep))
    with Image.open(target) as image:
        assert image.size == expected


def test_jpeg_transparency_uses_white_background(sample_image, tmp_path):
    with Image.open(sample_image) as source:
        source.paste((0, 0, 0, 0), (0, 0, 16, 16))
        source.save(sample_image)
    target = str(tmp_path / "white.jpg")
    ImageConverter.convert_image(sample_image, target, ImageConfig(quality=100))
    with Image.open(target) as image:
        assert min(image.getpixel((4, 4))) > 240


def test_icon_conversion_does_not_change_reused_settings(sample_image, tmp_path):
    config = ImageConfig()
    before = asdict(config)
    ImageConverter.convert_image(sample_image, str(tmp_path / "icon.ico"), config)
    assert asdict(config) == before


def test_phone_photo_orientation_is_applied(tmp_path):
    source = tmp_path / "phone.jpg"
    image = Image.new("RGB", (40, 20), "red")
    exif = image.getexif()
    exif[274] = 6
    image.save(source, exif=exif)
    target = str(tmp_path / "upright.png")
    ImageConverter.convert_image(str(source), target)
    with Image.open(target) as result:
        assert result.size == (20, 40)
