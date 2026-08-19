"""Patch epdconfig.py to replace gpiozero with RPi.GPIO."""
import sys

with open(sys.argv[1], 'r') as f:
    content = f.read()

# 1. Replace import gpiozero
content = content.replace(
    'import gpiozero',
    'import RPi.GPIO as GPIO\nGPIO.setmode(GPIO.BCM)'
)

# 2. Replace gpiozero.LED/Button with plain GPIO pin numbers
replacements = [
    ("self.GPIO_RST_PIN    = gpiozero.LED(self.RST_PIN)",
     "self.GPIO_RST_PIN    = self.RST_PIN"),
    ("self.GPIO_DC_PIN     = gpiozero.LED(self.DC_PIN)",
     "self.GPIO_DC_PIN     = self.DC_PIN"),
    ("self.GPIO_CS_PIN     = gpiozero.LED(self.CS_PIN)",
     "self.GPIO_CS_PIN     = self.CS_PIN"),
    ("self.GPIO_BUSY_PIN   = gpiozero.Button(self.BUSY_PIN, pull_up=False)",
     "self.GPIO_BUSY_PIN   = self.BUSY_PIN"),
    ("self.GPIO_PWR_PIN    = gpiozero.LED(self.PWR_PIN)",
     "self.GPIO_PWR_PIN    = self.PWR_PIN"),
]

for old, new in replacements:
    content = content.replace(old, new)

# 3. Insert GPIO setup after the pin assignments
setup_block = """
        for pin in [self.RST_PIN, self.DC_PIN, self.CS_PIN, self.PWR_PIN]:
            GPIO.setup(pin, GPIO.OUT)
        GPIO.setup(self.BUSY_PIN, GPIO.IN)
"""
# Insert after BUSY_PIN line
marker = "self.GPIO_BUSY_PIN   = self.BUSY_PIN"
if marker in content:
    content = content.replace(marker, marker + setup_block)

# 4. Fix digital_write to use GPIO.output
old_dw1 = "epdconfig.GPIO_RST_PIN.on()"
new_dw1 = "GPIO.output(epdconfig.GPIO_RST_PIN, 1)"
content = content.replace(old_dw1, new_dw1)

old_dw2 = "epdconfig.GPIO_RST_PIN.off()"
new_dw2 = "GPIO.output(epdconfig.GPIO_RST_PIN, 0)"
content = content.replace(old_dw2, new_dw2)

old_dw3 = "epdconfig.GPIO_DC_PIN.on()"
new_dw3 = "GPIO.output(epdconfig.GPIO_DC_PIN, 1)"
content = content.replace(old_dw3, new_dw3)

old_dw4 = "epdconfig.GPIO_DC_PIN.off()"
new_dw4 = "GPIO.output(epdconfig.GPIO_DC_PIN, 0)"
content = content.replace(old_dw4, new_dw4)

old_dw5 = "epdconfig.GPIO_CS_PIN.on()"
new_dw5 = "GPIO.output(epdconfig.GPIO_CS_PIN, 1)"
content = content.replace(old_dw5, new_dw5)

old_dw6 = "epdconfig.GPIO_CS_PIN.off()"
new_dw6 = "GPIO.output(epdconfig.GPIO_CS_PIN, 0)"
content = content.replace(old_dw6, new_dw6)

old_dw7 = "epdconfig.GPIO_PWR_PIN.on()"
new_dw7 = "GPIO.output(epdconfig.GPIO_PWR_PIN, 1)"
content = content.replace(old_dw7, new_dw7)

old_dw8 = "epdconfig.GPIO_PWR_PIN.off()"
new_dw8 = "GPIO.output(epdconfig.GPIO_PWR_PIN, 0)"
content = content.replace(old_dw8, new_dw8)

# 5. Fix digital_read
old_dr = "return epdconfig.GPIO_BUSY_PIN.value"
new_dr = "return GPIO.input(epdconfig.GPIO_BUSY_PIN)"
content = content.replace(old_dr, new_dr)

# 6. Fix module_exit
old_me = "epdconfig.GPIO_RST_PIN.off()\n    epdconfig.GPIO_DC_PIN.off()\n    epdconfig.GPIO_CS_PIN.off()\n    epdconfig.GPIO_PWR_PIN.off()"
new_me = "GPIO.output(epdconfig.GPIO_RST_PIN, 0)\n    GPIO.output(epdconfig.GPIO_DC_PIN, 0)\n    GPIO.output(epdconfig.GPIO_CS_PIN, 0)\n    GPIO.output(epdconfig.GPIO_PWR_PIN, 0)"
content = content.replace(old_me, new_me)

# 7. Remove gpiozero references from delay_ms
content = content.replace("gpiozero.LED", "GPIO")
content = content.replace("gpiozero.Button", "GPIO")

with open(sys.argv[1], 'w') as f:
    f.write(content)

print("Patched successfully!")
