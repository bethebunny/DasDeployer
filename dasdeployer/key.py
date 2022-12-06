from gpiozero import ButtonBoard
from time import time
from threading import Event

key = ButtonBoard(one=23, two=25)

key_one_time = 0.0
key_two_time = 0.0
keys_turned = Event()


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
            keys_turned.set()
        else:
            key_one_time = 0.0
            key_two_time = 0.0
            print("timer reset")


key.one.when_pressed = turn_one
key.two.when_pressed = turn_two

keys_turned.wait()
