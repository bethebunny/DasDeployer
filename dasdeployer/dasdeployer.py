#!/usr/bin/env python3

from gpiozero import LEDBoard, ButtonBoard, Button, CPUTemperature
from subprocess import check_call
# from signal import pause
from time import sleep, time
from lcd import LCD_HD44780_I2C
from rgb import Color, RGBButton
# from datetime import datetime
# from pipelines import Pipelines, QueryResult, QueryResultStatus
from pipelines import Pipelines, QueryResult
# from pprint import pprint
from threading import Event


import socket

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/martinwoodward/DasDeployer.git"

TITLE = ">>> Das Deployer <<<"

# Define controls
switchLight = LEDBoard(red=17, yellow=22, green=9, blue=11, pwm=True)
switch = ButtonBoard(red=18, yellow=23, green=25, blue=8, hold_time=5)
toggleLight = LEDBoard(dev=0, test=26, stage=6, prod=19)
toggle = ButtonBoard(dev=1, test=20, stage=12, prod=16, pull_up=False)
# toggleLight = LEDBoard(dev=0, test=6, stage=26, prod=19)
# toggle = ButtonBoard(dev=1, test=12, stage=20, prod=16, pull_up=False)
leds = LEDBoard(switchLight, toggleLight)
lcd = LCD_HD44780_I2C()
rgbmatrix = RGBButton()
bigButton = Button(7)

key_one_time = 0.0
key_two_time = 0.0
keys_turned = Event()

# global pipes
# global buildNumber
# global activeEnvironment
# global last_result
pipes = Pipelines()
# buildNumber = ""
active_environment = None
last_result = QueryResult()
keys_enabled = True


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


def shutdown():
    lcd.message = "Switching off..."
    sleep(3)
    leds.off()
    check_call(['sudo', 'poweroff'])


def reboot():
    lcd.message = "Das rebooting..."
    leds.off()
    check_call(['sudo', 'reboot'])


# def demo_release_toggle():
#     lcd.message = "{}\nContosoAir {}\nBuild Successful.".format(TITLE, buildNumber)
#     rgbmatrix.fillButton(Color.GREEN)
#     rgbmatrix.stopRing()
#     bigButton.when_pressed = None

# def demo_dev_deploy():
#     demo_deploy_question("Dev")
# def demo_stage_deploy():
#     demo_deploy_question("Staging")
# def demo_prod_deploy():
#     demo_deploy_question("Prod")


def dev_deploy():
    print("Toggle up Dev")
    deploy_question("Dev")


def test_deploy():
    print("Toggle up Test")
    deploy_question("Test")


def stage_deploy():
    print("Toggle up Stage")
    deploy_question("Stage")


def prod_deploy():
    print("Toggle up Prod")
    deploy_question("Prod")


def deploy_question(environment):
    print("Toggle up")
    global active_environment
    active_environment = environment
    # if environment == 'Dev':
    #     branch = f"branch\n{last_result.branch_dev}\n"
    # elif environment == 'Test':
    #     branch = f"branch\n{last_result.branch_tst}\n"
    # elif environment == 'Stage':
    #     branch = f"branch\n{last_result.branch_stage}\n"
    # elif environment == 'Prod':
    #     branch = ""

    if keys_enabled:
        switch.yellow.when_pressed = turn_one
        switch.green.when_pressed = turn_two
        rgbmatrix.fillButton(Color.OFF)
        rgbmatrix.pulseRing(Color.YELLOW)
        lcd.message = (
            TITLE +
            "Turn Keys\nto activate"
        )
    else:
        deploy_question2()

    # lcd.message = "{}\nDeploy {}to {}?".format(TITLE, branch, environment)
    # rgbmatrix.pulseButton(Color.RED, 1)
    # rgbmatrix.unicornRing(25)
    # bigButton.when_pressed = deploy


def deploy_question2():
    print("Toggle up2")
    if switch.yellow.when_pressed:
        switch.yellow.when_pressed = None
    if switch.green.when_pressed:
        switch.green.when_pressed = None
    global active_environment
    environment = active_environment
    active_environment = None

    if environment == 'Dev':
        branch = f"branch\n{last_result.branch_dev}\n"
    elif environment == 'Test':
        branch = f"branch\n{last_result.branch_tst}\n"
    elif environment == 'Stage':
        branch = f"branch\n{last_result.branch_stage}\n"
    elif environment == 'Prod':
        branch = ""

    lcd.message = "{}\nDeploy {}to {}?".format(TITLE, branch, environment)
    rgbmatrix.pulseButton(Color.RED, 1)
    rgbmatrix.unicornRing(25)
    bigButton.when_pressed = deploy


def deploy():
    # Find what we should be deploying.
    # print(toggle.dev.value)
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

    bigButton.when_pressed = None
    rgbmatrix.fillButton(Color.WHITE)
    rgbmatrix.stopRing()
    lcd.message = "{}Deploying to {}".format(TITLE, deploy_env)

    build_result = pipes.approve(deploy_env)
    rgbmatrix.chaseRing(Color.BLUE, 1)
    if build_result is not None:
        lcd.message = "{}\nBuild {}\ntriggered to {}".format(TITLE, build_result.build_number, deploy_env)


def toggle_release():
    print("Toggle down")
    global key_two_time, key_one_time
    key_one_time = 0.0
    key_two_time = 0.0

    if last_result is None:
        print("No last result available")
        return
    else:
        update_display(last_result)


def run_diagnostics():
    """ Diagnostic menu when Red button is held down """
    cpu = CPUTemperature()
    lcd.message = TITLE + \
        "\nIP:  " + get_ip() + \
        "\nCPU: " + str(round(cpu.temperature)) + chr(0xDF) + \
        "\nOff  Reset      Back"
    switchLight.red.on()
    switchLight.yellow.on()
    switchLight.blue.on()

    switch.red.wait_for_release()
    switch.red.when_held = None
    switch.green.when_held = None

    switch.red.when_pressed = shutdown
    switch.yellow.when_pressed = reboot
    # switch.green.when_pressed = key_diag

    switch.blue.wait_for_press()

    # Blue light pressed - reset and drop out of diagnostics mode
    switchLight.off()
    # switch.green.when_pressed = None
    switch.yellow.when_pressed = None
    switch.red.when_pressed = None
    switch.red.when_held = run_diagnostics
    switch.green.when_held = key_diagnostics
    update_display(last_result)


def key_diagnostics():
    """ Diagnostic menu when Red button is held down """
    lcd.message = (
        TITLE +
        f"Keys enabled: {keys_enabled}\n\n" +
        "Toggle          Back"
    )
    switchLight.red.on()
    switchLight.blue.on()

    switch.green.wait_for_release()
    switch.red.when_held = None
    switch.green.when_held = None

    switch.red.when_pressed = toggle_keys
    # switch.yellow.when_pressed = reboot
    # switch.green.when_pressed = key_diag

    switch.blue.wait_for_press()

    # Blue light pressed - reset and drop out of diagnostics mode
    switchLight.off()
    # switch.green.when_pressed = None
    # switch.yellow.when_pressed = None
    switch.red.when_pressed = None
    switch.red.when_held = run_diagnostics
    switch.green.when_held = key_diagnostics
    update_display(last_result)


# def key_diag():
#     lcd.message = (
#         TITLE +
#         f"Keys enabled: {keys_enabled}\n\n" +
#         "Toggle          Back"
#     )
#     switch.red.when_pressed = toggle_keys
#     switch.yellow.when_pressed = None
#     switch.green.when_pressed = None
#     switch.blue.wait_for_press()
#     # run_diagnostics()


def toggle_keys():
    global keys_enabled
    keys_enabled = not keys_enabled
    lcd.message = (
        TITLE +
        f"Keys enabled: {keys_enabled}\n\n" +
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
    # lcd.message = "{}\n{}\n{}\nDeploying to {}...".format(
    #     TITLE,
    #     result.latest_build.definition.name,
    #     result.dev_release.name,
    #     environment
    # )
    lcd.message = "{}\nBuild {}\nDeploying to {}...".format(
        TITLE,
        build.build_number,
        environment
    )


def deploy_finished(result, build, environment):
    print("Finished")
    rgbmatrix.fillButton(Color.WHITE)
    rgbmatrix.pulseRing(get_build_color(build.result))
    # lcd.message = "{}\n{}\n{}\nDeploying to {}...".format(
    #     TITLE,
    #     result.latest_build.definition.name,
    #     result.dev_release.name,
    #     environment
    # )
    lcd.message = "{}\nBuild {}...\nDeployment to {}\nStatus: {}".format(
        TITLE,
        build.build_number,
        environment,
        build.result
        # result.latest_build.definition.name,
        # result.dev_release.name,
        # environment,
        # status
    )


def update_display(result: QueryResult):
    # print(result)
    if result is None:
        return

    elif (toggle.dev.value):
        # print("Dev switch is up")
        # Dev switch is up
        if (result.deploying_dev):
            # Dev deployment in progress
            deploy_in_progress(result.build_dev, "Dev")
        else:
            deploy_finished(result, result.build_dev, "Dev")

    elif (toggle.stage.value):
        # Stage switch is up
        if (result.deploying_stage):
            # Stage deployment in progress
            deploy_in_progress(result, "Stage")
        else:
            deploy_finished(result, result.build_stage, "Stage")

    elif (toggle.test.value):
        # Test switch is up
        if (result.deploying_stage):
            # Test deployment in progress
            deploy_in_progress(result, "Test")
        else:
            deploy_finished(result, result.build_stage, "Test")

    elif (toggle.prod.value):
        # Prod switch is up
        if (result.deploying_prod):
            # Prod deployment in progress
            deploy_in_progress(result.build_prod, "Prod")
        else:
            deploy_finished(result, result.build_prod, "Prod")

    else:
        rgbmatrix.fillButton(Color.GREEN)
        rgbmatrix.fillRing(Color.OFF)
        lcd.message = TITLE

    # elif (result.status == QueryResultStatus.BUILD_COMPLETE):
    #     rgbmatrix.fillButton(get_build_color(result.last_build.result))
    #     rgbmatrix.fillRing(Color.OFF)
    #     lcd.message = "{}\n{}\nBuild {}\n{}.".format(TITLE,
    #         result.latest_build.definition.name,
    #         result.latest_build.build_number,
    #         result.latest_build.result)

    # elif (result.status == QueryResultStatus.BUILD_IN_PROGRESS):
    #     print("Build In Progress")
    #     rgbmatrix.pulseButton(get_build_color(result.last_build.result), 1)
    #     rgbmatrix.chaseRing(Color.BLUE, 1)
    #     lcd.message = "{}\n{}\nBuild {}\nin progress...".format(TITLE,
    #         result.latest_build.definition.name,
    #         result.latest_build.build_number)

    # print(result.enable_dev, result.enable_stage, result.enable_prod)


def main():
    # Attach diagnotic menu to red button when held down
    switch.red.when_held = run_diagnostics
    switch.green.when_held = key_diagnostics

    toggle.dev.when_pressed = dev_deploy
    toggle.test.when_pressed = test_deploy
    toggle.stage.when_pressed = stage_deploy
    toggle.prod.when_pressed = prod_deploy

    toggle.dev.when_released = toggle_release
    toggle.test.when_released = toggle_release
    toggle.stage.when_released = toggle_release
    toggle.prod.when_released = toggle_release

    # Quick init sequence to show all is well
    lcd.message = TITLE + "\n\n\n" + get_ip()
    leds.blink(0.5, 0.5, 0, 0, 2, True)
    rgbmatrix.pulseButton(Color.RED, 1)
    rgbmatrix.unicornRing(25)
    lcd.message = TITLE

    # Set up build polling.
    # pipes = Pipelines()
    global last_result
    last_result = pipes.get_status()

    # Display loop
    while True:
        result = pipes.get_status()

        # Set the state of the approval toggle LED's
        toggleLight.dev.value = result.enable_dev
        toggleLight.test.value = result.enable_tst
        toggleLight.stage.value = result.enable_stage
        toggleLight.prod.value = result.enable_prod

        if (result == last_result):
            # Nothing has changed - lets just wait a bit
            # print('same')
            sleep(1)
        else:
            update_display(result)
            last_result = result

        # if (
        #     last_result.enable_dev != result.enable_dev or
        #     last_result.enable_tst != result.enable_tst or
        #     last_result.enable_stage != result.enable_stage or
        #     last_result.enable_prod != result.enable_prod or
        #     last_result.deploying_dev != result.deploying_dev or
        #     last_result.deploying_tst != result.deploying_tst or
        #     last_result.deploying_stage != result.deploying_stage or
        #     last_result.deploying_prod != result.deploying_prod or
        #     last_result.dev_branch != result.dev_branch or
        #     last_result.tst_branch != result.tst_branch
        # ):
        #     update_display(result)
        #     last_result = result
        # else:
        #     # Nothing has changed - lets just wait a bit
        #     sleep(1)
        # update_display(result)
        # sleep(1)


main()
