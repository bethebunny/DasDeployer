from time import sleep
from subprocess import check_call
from gpiozero import LEDBoard, ButtonBoard, Button, CPUTemperature, LED, PWMLED
from lcd import LCD_HD44780_I2C
from rgb import Color, RGBButton
from signal import pause
from threading import Event

import socket
import os

TITLE = ">>> Das Deployer <<<"

switchLight = LEDBoard(red=17, yellow=22, green=9, blue=11, pwm=True)
switch = ButtonBoard(red=18, yellow=23, green=25, blue=8, hold_time=5)
toggleLight = LEDBoard(dev=0, stage=6, prod=19)
toggle = ButtonBoard(dev=1, stage=12, prod=16, pull_up=False)
leds = LEDBoard(switchLight, toggleLight)
lcd = LCD_HD44780_I2C()
rgbmatrix = RGBButton()
bigButton = Button(7)
done = Event()


## Nifty get_ip function from Jamieson Becker https://stackoverflow.com/a/28950776
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def shutdown():
    lcd.message = "Switching off..."
    sleep(3)
    leds.off()
    check_call(['sudo', 'poweroff'])

def reboot():
    lcd.message = "Das rebooting..."
    leds.off()
    check_call(['sudo', 'reboot'])

def exit_demo():
    lcd.message = "Exiting Demo mode"
    leds.off()
    rgbmatrix.stopRing()
    rgbmatrix.fillButton(Color.OFF)
    done.set()



def run_diagnostics():
    """ Diagnostic menu when Red button is held down """
    cpu = CPUTemperature()
    lcd.message = TITLE + \
        "\nIP:  " + get_ip() + \
        "\nCPU: " + str(round(cpu.temperature)) + chr(0xDF) + \
        "\nOff  Reset      Back"
    switchLight.on()

    switch.red.wait_for_release()
    switch.red.when_held = None

    switch.red.when_pressed = shutdown
    switch.yellow.when_pressed = reboot

    switch.blue.wait_for_press()

    # Blue light pressed - reset and drop out of diagnostics mode
    switchLight.off()
    switch.yellow.when_pressed = None
    switch.red.when_pressed = None
    switch.red.when_held = run_diagnostics
    lcd.message = TITLE


def test_button(name: str, led):
    lcd.message = (
        TITLE +
        f"\n{name} button pressed"
    )
    led.toggle()


def main():
    # Attach diagnotic menu to red button when held down
    switch.red.when_held = run_diagnostics
    switch.blue.when_held = exit_demo

    # toggle.dev.when_pressed = dev_deploy
    # toggle.stage.when_pressed = stage_deploy
    # toggle.prod.when_pressed = prod_deploy

    # toggle.dev.when_released = toggle_release
    # toggle.stage.when_released = toggle_release
    # toggle.prod.when_released = toggle_release

    # Quick init sequence to show all is well
    lcd.message = TITLE + "\n\n\n" + get_ip()
    leds.blink(0.5,0.5,0,0,2,True)
    rgbmatrix.pulseButton(Color.RED, 1)
    rgbmatrix.unicornRing(25)
    lcd.message = TITLE

    # # Set up build polling.
    # # pipes = Pipelines()
    # global last_result
    # last_result = pipes.get_status()

    # # Display loop
    # while True:
    #     result = pipes.get_status()

    #     # Set the state of the approval toggle LED's
    #     toggleLight.dev.value = result.enable_dev
    #     toggleLight.stage.value = result.enable_stage
    #     toggleLight.prod.value = result.enable_prod

    #     if (result == last_result):
    #         # Nothing has changed - lets just wait a bit
    #         sleep(1)
    #     else:
    #         update_display(result)
    #         last_result = result
    # while True:
    #     sleep(1)
    done.wait()

if __name__ == '__main__':
    main()
