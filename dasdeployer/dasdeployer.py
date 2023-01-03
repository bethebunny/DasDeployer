#!/usr/bin/env python3

from gpiozero import LEDBoard, ButtonBoard, Button, CPUTemperature
from subprocess import check_call
from time import sleep, time
from lcd import LCD_HD44780_I2C
from rgb import Color, RGBButton
from pipelines import Pipelines, QueryResult


import socket

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/FISHMANPET/DasDeployer.git"

TITLE = ">>> Das Deployer <<<"

# Define controls
switchLight = LEDBoard(red=17, yellow=22, green=9, blue=11, pwm=True)
switch = ButtonBoard(red=18, yellow=23, green=25, blue=8, hold_time=5)
toggleLight = LEDBoard(dev=0, test=26, stage=6, prod=19)
toggle = ButtonBoard(dev=1, test=20, stage=12, prod=16, pull_up=False)
keys = ButtonBoard(one=14, two=15)
leds = LEDBoard(switchLight, toggleLight)
lcd = LCD_HD44780_I2C()
rgbmatrix = RGBButton()
big_button = Button(7)

key_one_time = 0.0
key_two_time = 0.0

pipes = Pipelines()
active_environment = None
last_result = QueryResult()
keys_enabled = True
enable_main = True


def turn_one():
    print("one turned")
    global key_one_time
    key_one_time = time()
    check_keys()


def turn_two():
    print("two turned")
    global key_two_time
    key_two_time = time()
    check_keys()


def check_keys():
    global key_two_time, key_one_time
    if key_one_time and key_two_time:
        time_diff = key_one_time - key_two_time
        if time_diff >= -1 and time_diff <= 1:
            print("matched")
            key_one_time = 0.0
            key_two_time = 0.0
            deploy_question2()
        else:
            key_one_time = 0.0
            key_two_time = 0.0
            print("timer reset")


# Nifty get_ip function from Jamieson Becker https://stackoverflow.com/a/28950776
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


def format_lcd_message(
    *args: str
) -> str:
    final_string = ""
    for line in args:
        if len(line) > 20:
            line = line[:17] + '...'
        final_string += (line + '\n')
    return final_string


def shutdown():
    lcd.message = "Switching off..."
    sleep(3)
    leds.off()
    check_call(['sudo', 'poweroff'])


def reboot():
    lcd.message = "Das rebooting..."
    leds.off()
    check_call(['sudo', 'reboot'])


def reload_pipes():
    lcd.message = "Reloading pipelines"
    global pipes
    pipes = Pipelines()
    sleep(3)
    cpu = CPUTemperature()
    lcd.message = format_lcd_message(
        TITLE,
        f"IP:  {get_ip()}",
        f"CPU: {str(round(cpu.temperature))}{chr(0xDF)}",
        "Off Reset Pipes Back"
    )


def dev_deploy():
    deploy_question("Dev")


def test_deploy():
    deploy_question("Test")


def stage_deploy():
    deploy_question("Stage")


def prod_deploy():
    deploy_question("Prod")


def deploy_question(environment):
    print("Toggle up")
    global active_environment
    active_environment = environment

    if keys_enabled:
        keys.one.when_pressed = turn_one
        keys.two.when_pressed = turn_two
        rgbmatrix.fillButton(Color.OFF)
        rgbmatrix.pulseRing(Color.YELLOW)
        rgbmatrix.chaseKey1(Color.YELLOW)
        rgbmatrix.chaseKey2(Color.YELLOW)
        lcd.message = format_lcd_message(
            TITLE,
            "Turn Keys",
            "to activate"
        )
    else:
        deploy_question2()


def deploy_question2():
    print("Toggle up2")
    if keys.one.when_pressed:
        keys.one.when_pressed = None
    if keys.two.when_pressed:
        keys.two.when_pressed = None
    if keys_enabled:
        rgbmatrix.pulseKey1(Color.GREEN)
        rgbmatrix.pulseKey2(Color.GREEN)
    global active_environment
    environment = active_environment
    active_environment = None

    if environment in ('Dev', 'Test', 'Stage'):
        line2 = "Deploy branch"
        if environment == 'Dev':
            line3 = last_result.branch_dev
        elif environment == 'Test':
            line3 = last_result.branch_tst
        elif environment == 'Stage':
            line3 = last_result.branch_stage
        line4 = f"to {environment}?"
        lcd.message = format_lcd_message(TITLE, line2, line3, line4)
    elif environment == 'Prod':
        line2 = "Deploy to Prod?"
        lcd.message = format_lcd_message(TITLE, line2)

    rgbmatrix.pulseButton(Color.RED, 1)
    rgbmatrix.unicornRing(25)
    big_button.when_pressed = deploy


def deploy():
    # Find what we should be deploying.
    deploy_env = None
    if (toggle.prod.value):
        deploy_env = "Prod"
    elif (toggle.test.value):
        deploy_env = "Test"
    elif (toggle.stage.value):
        deploy_env = "Stage"
    elif (toggle.dev.value):
        deploy_env = "Dev"
    else:
        return

    # Approve it.

    big_button.when_pressed = None
    rgbmatrix.fillButton(Color.WHITE)
    rgbmatrix.stopRing()
    rgbmatrix.stopKey1()
    rgbmatrix.stopKey2()

    lcd.message = format_lcd_message(TITLE, f"Deploying to {deploy_env}")

    build_result = pipes.approve(deploy_env)
    rgbmatrix.chaseRing(Color.BLUE, 1)
    if build_result is not None:
        lcd.message = format_lcd_message(
            TITLE,
            f"Build {build_result.build_number}",
            f"triggered to {deploy_env}"
        )


def toggle_release():
    print("Toggle down")
    global key_two_time, key_one_time
    key_one_time = 0.0
    key_two_time = 0.0
    rgbmatrix.stopKey1()
    rgbmatrix.stopKey2()
    if keys.one.when_pressed:
        keys.one.when_pressed = None
    if keys.two.when_pressed:
        keys.two.when_pressed = None

    if last_result is None:
        print("No last result available")
        return
    else:
        update_display(last_result)


def run_diagnostics():
    """ Diagnostic menu when Red button is held down """
    toggle_main_off()
    cpu = CPUTemperature()
    lcd.message = format_lcd_message(
        TITLE,
        f"IP:  {get_ip()}",
        f"CPU: {str(round(cpu.temperature))}{chr(0xDF)}",
        "Off Reset Pipes Back"
    )
    switchLight.red.on()
    switchLight.yellow.on()
    switchLight.green.on()
    switchLight.blue.on()

    switch.red.wait_for_release()

    switch.red.when_pressed = shutdown
    switch.yellow.when_pressed = reboot
    switch.green.when_pressed = reload_pipes

    switch.blue.wait_for_press()

    # Blue light pressed - reset and drop out of diagnostics mode
    toggle_main_on()
    update_display(last_result)


def key_toggle():
    """ Menu for toggling key requirement when green button is held down """
    toggle_main_off()
    lcd.message = format_lcd_message(
        TITLE,
        f"Keys enabled: {keys_enabled}",
        "",
        "Toggle          Back"
    )
    switchLight.red.on()
    switchLight.blue.on()

    switch.green.wait_for_release()

    switch.red.when_pressed = toggle_keys

    switch.blue.wait_for_press()

    # Blue light pressed - reset and drop out of diagnostics mode
    toggle_main_on()
    update_display(last_result)


def toggle_keys():
    global keys_enabled
    keys_enabled = not keys_enabled
    lcd.message = format_lcd_message(
        TITLE,
        f"Keys enabled: {keys_enabled}",
        "",
        "Toggle          Back"
    )


def get_build_color(build_result):
    if (build_result == "succeeded"):
        return Color.GREEN
    elif (build_result == "failed"):
        return Color.RED
    elif (build_result == "canceled"):
        return Color.WHITE
    elif (build_result == "partiallySucceeded"):
        return Color.YELLOW
    return Color.OFF


def deploy_in_progress(build, environment):
    print("Deploy")
    rgbmatrix.fillButton(Color.WHITE)
    rgbmatrix.chaseRing(Color.BLUE, 1)
    lcd.message = format_lcd_message(
        TITLE,
        f"Build {build.build_number}",
        f"Deploying to {environment}"
    )


def deploy_finished(result, build, environment):
    print("Finished")
    rgbmatrix.fillButton(Color.WHITE)
    rgbmatrix.pulseRing(get_build_color(build.result))
    lcd.message = format_lcd_message(
        TITLE,
        f"Build {build.build_number}",
        f"Deployment to {environment}",
        f"Status: {build.result}"
    )


def update_display(result: QueryResult):
    if result is None:
        return

    elif (toggle.dev.value):
        # Dev switch is up
        if (result.deploying_dev):
            # Dev deployment in progress
            deploy_in_progress(result.build_dev, "Dev")
        else:
            # Dev deployment is finished
            deploy_finished(result, result.build_dev, "Dev")

    elif (toggle.test.value):
        # Test switch is up
        if (result.deploying_tst):
            # Test deployment in progress
            deploy_in_progress(result, "Test")
        else:
            deploy_finished(result, result.build_stage, "Test")

    elif (toggle.stage.value):
        # Stage switch is up
        if (result.deploying_stage):
            # Stage deployment in progress
            deploy_in_progress(result, "Staging")
        else:
            # Stage deployment is finished
            deploy_finished(result, result.build_stage, "Staging")

    elif (toggle.prod.value):
        # Prod switch is up
        if (result.deploying_prod):
            # Prod deployment in progress
            deploy_in_progress(result.build_prod, "Prod")
        else:
            # Prod deoployment is finished
            deploy_finished(result, result.build_prod, "Prod")

    else:
        rgbmatrix.fillButton(Color.GREEN)
        rgbmatrix.fillRing(Color.OFF)
        lcd.message = TITLE


def toggle_main_on():
    global enable_main
    enable_main = True
    # Attach diagnotic menu to red button when held down
    switch.red.when_held = run_diagnostics
    # Attach key toggle menu to green button when held down
    switch.green.when_held = key_toggle
    if switch.yellow.when_held:
        switch.yellow.when_held = None
    if switch.blue.when_held:
        switch.blue.when_held = None

    for button in switch:
        if button.when_pressed:
            button.when_pressed = None
    switchLight.off()

    toggle.dev.when_pressed = dev_deploy
    toggle.test.when_pressed = test_deploy
    toggle.stage.when_pressed = stage_deploy
    toggle.prod.when_pressed = prod_deploy

    toggle.dev.when_released = toggle_release
    toggle.test.when_released = toggle_release
    toggle.stage.when_released = toggle_release
    toggle.prod.when_released = toggle_release


def toggle_main_off():
    global enable_main
    enable_main = False
    for button in switch:
        if button.when_pressed:
            button.when_pressed = None
        if button.when_held:
            button.when_held = None
    switchLight.off()

    for tog in toggle:
        if tog.when_pressed:
            tog.when_pressed = None
        if tog.when_released:
            tog.when_released = None


def main():
    toggle_main_on()

    # Quick init sequence to show all is well
    lcd.message = TITLE + "\n\n\n" + get_ip()
    rgbmatrix.pulseButton(Color.RED, 1)
    rgbmatrix.unicornRing(25)
    leds.blink(0.5, 0.5, 0, 0, 2, False)
    switchLight.blink(1, 1, 0.5, 0.5, 2, False)
    lcd.message = TITLE

    # Set up build polling.
    # pipes = Pipelines()
    global last_result
    last_result = pipes.get_status()

    # Display loop
    while True:
        if enable_main:
            result = pipes.get_status()

            # Set the state of the approval toggle LED's
            toggleLight.dev.value = result.enable_dev
            toggleLight.test.value = result.enable_tst
            toggleLight.stage.value = result.enable_stage
            toggleLight.prod.value = result.enable_prod

            if (result == last_result):
                # Nothing has changed - lets just wait a bit
                sleep(1)
            else:
                # Something has changed, update the display
                update_display(result)
                last_result = result
        else:
            sleep(1)


main()
