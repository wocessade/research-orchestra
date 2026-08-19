"""WalnutPi 1B (Allwinner H616) 极简 GPIO 封装 — 内核 v1 ioctl 直操

需求面很小: 墨水屏 RST/DC/PWR 三路输出 + BUSY 一路输入 + 两颗状态 LED。
不用 gpiozero (native 后端只支持树莓派 BCM 寄存器映射, H616 不可用);
不用 libgpiod.so.1 (系统未装, 装包需 sudo)。/dev/gpiochip0 权限 660 pi:pi,
普通用户即可 open, 走内核 uapi 的 gpio v1 ioctl (与 libgpiod 1.x 同一协议,
Debian 12 内核 6.1 完全支持)。

线程安全: 仅进程内使用, 上层 (epdconfig/led_controller) 已持有自己的锁,
本模块不做额外加锁。
"""

import os
import fcntl
import struct

CHIP_PATH = "/dev/gpiochip0"
CONSUMER = b"usage-monitor"

# linux/gpio.h v1 ioctl 协议 (64 位: _IOC_DIRBITS=2, SIZEBITS=14)
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = 8
_IOC_SIZESHIFT = 16
_IOC_DIRSHIFT = 30
_IOC_WRITE = 1
_IOC_READ = 2


def _ioc(direction, number, size):
    return ((direction << _IOC_DIRSHIFT) | (0xB4 << _IOC_TYPESHIFT)
            | (number << _IOC_NRSHIFT) | (size << _IOC_SIZESHIFT))


# struct gpiohandle_request: lineoffsets[64]u32 + flags u32 + default_values[64]u8
#   + consumer_label[32] + lines u32 + fd i32 = 364 字节
# struct gpiohandle_data: values[16]u32 = 64 字节
#   注意: 主线内核 GPIOHANDLES_MAX=64 (256 字节), 但核桃派厂商内核
#   (Allwinner SDK, 6.1.31) 把它改成了 16 (64 字节)! ioctl 号里的 size
#   字段必须与内核编译时一致, 否则 switch 不匹配 → EINVAL。实测确认:
#   GET_LINEHANDLE(364) 成功, 而 256 字节的 values ioctl 报 EINVAL,
#   64 字节的 values ioctl 正常。
_GPIO_GET_LINEHANDLE_IOCTL = _ioc(_IOC_READ | _IOC_WRITE, 0x03, 364)
_GPIOHANDLE_GET_LINE_VALUES_IOCTL = _ioc(_IOC_READ | _IOC_WRITE, 0x08, 64)
_GPIOHANDLE_SET_LINE_VALUES_IOCTL = _ioc(_IOC_READ | _IOC_WRITE, 0x09, 64)

GPIOHANDLE_REQUEST_INPUT = 0x01
GPIOHANDLE_REQUEST_OUTPUT = 0x02

_HANDLE_SIZE = 364
_DATA_SIZE = 64


class GPIOException(RuntimeError):
    pass


_chip_fd = None
_fds = {}  # pin -> line handle fd


def _chip_handle():
    global _chip_fd
    if _chip_fd is None:
        _chip_fd = os.open(CHIP_PATH, os.O_RDONLY)
    return _chip_fd


def _request(pin, flags, initial=0):
    """请求 pin 为输入或输出, 返回 line handle fd (每个 pin 独立句柄)。"""
    buf = bytearray(_HANDLE_SIZE)
    struct.pack_into("<I", buf, 0, pin)             # lineoffsets[0]
    struct.pack_into("<I", buf, 256, flags)         # flags
    struct.pack_into("<B", buf, 260, initial)       # default_values[0]
    buf[324:356] = CONSUMER[:31].ljust(32, b"\x00")  # consumer_label
    struct.pack_into("<I", buf, 356, 1)             # lines = 1
    fcntl.ioctl(_chip_handle(), _GPIO_GET_LINEHANDLE_IOCTL, buf)
    fd = struct.unpack_from("<i", buf, 360)[0]
    if fd < 0:
        raise GPIOException("gpio request pin %d failed" % pin)
    return fd


def open_output(pin, initial=0):
    """请求 pin 为输出 (默认低电平)。同一 pin 重复请求会被替换。"""
    _release(pin)
    _fds[pin] = _request(pin, GPIOHANDLE_REQUEST_OUTPUT, 1 if initial else 0)


def open_input(pin):
    """请求 pin 为输入 (浮空, 不配上下拉 — 与树莓派版行为一致)。"""
    _release(pin)
    _fds[pin] = _request(pin, GPIOHANDLE_REQUEST_INPUT)


def write(pin, value):
    """输出 0/1; pin 未请求时抛 GPIOException。"""
    fd = _fds.get(pin)
    if fd is None:
        raise GPIOException("pin %d not requested" % pin)
    buf = bytearray(_DATA_SIZE)
    struct.pack_into("<I", buf, 0, 1 if value else 0)
    fcntl.ioctl(fd, _GPIOHANDLE_SET_LINE_VALUES_IOCTL, buf)


def read(pin):
    """读取输入电平, 返回 0/1。"""
    fd = _fds.get(pin)
    if fd is None:
        raise GPIOException("pin %d not requested" % pin)
    buf = bytearray(_DATA_SIZE)
    fcntl.ioctl(fd, _GPIOHANDLE_GET_LINE_VALUES_IOCTL, buf)
    return struct.unpack_from("<I", buf, 0)[0]


def _release(pin):
    fd = _fds.pop(pin, None)
    if fd is not None:
        os.close(fd)


def release(pin):
    _release(pin)


def release_all():
    for pin in list(_fds):
        _release(pin)
    global _chip_fd
    if _chip_fd is not None:
        os.close(_chip_fd)
        _chip_fd = None
