"""离线校验局刷缓冲等价性 (不需要墨水屏硬件)。"""

from PIL import Image, ImageDraw, ImageOps

from eink_dashboard import EinkDashboard, PARTIAL_REFRESH_ENABLED


def _pack_like_getbuffer(img: Image.Image) -> bytes:
    return bytes(bytearray(img.convert("1").tobytes("raw")))


def _pack_like_getbuffer_part(img: Image.Image) -> bytes:
    buf = bytearray(img.convert("1").tobytes("raw"))
    for i in range(len(buf)):
        buf[i] ^= 0xFF
    return bytes(buf)


def test_mode1_direct_invert_is_broken():
    img = Image.new("1", (16, 2), 1)
    ImageDraw.Draw(img).point((0, 0), fill=0)
    broken = ImageOps.invert(img.convert("1"))
    ok = EinkDashboard._invert_1bit(img)
    assert broken.tobytes("raw") != ok.tobytes("raw")


def test_invert_part_equals_getbuffer():
    img = Image.new("1", (800, 48), 1)
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (799, 47)], fill=0)
    draw.text((10, 10), "12:34", fill=1)

    a = _pack_like_getbuffer(img)
    b = _pack_like_getbuffer_part(EinkDashboard._invert_1bit(img))
    assert a == b, "getbuffer(img) must equal getbuffer_Part(_invert_1bit(img))"


def test_full_frame_buffer_size():
    img = Image.new("1", (800, 480), 1)
    buf = _pack_like_getbuffer_part(EinkDashboard._invert_1bit(img))
    assert len(buf) == 800 * 480 // 8
    assert PARTIAL_REFRESH_ENABLED is True


if __name__ == "__main__":
    test_mode1_direct_invert_is_broken()
    test_invert_part_equals_getbuffer()
    test_full_frame_buffer_size()
    print("OK: partial buffer checks passed")
