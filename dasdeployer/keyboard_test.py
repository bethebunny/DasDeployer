import serial
import time
import json

ser = serial.Serial('/dev/ttyACM1', 9600, timeout=0)
# ser = serial.Serial('/dev/ttyAMA5', 9600, timeout=0)
time.sleep(1)
print("done sleeping")
# ser.write(b"start")
ser.write(json.dumps({
    "state": "enabled",
    "possible_chars": "abcdefghijklmnopqrstuvwxyz_",
    "display_name": "Built For"
}).encode())

time.sleep(1)
print("sending chars")
ser.write(b"abcde")

while True:
    result = ser.readline()
    if result:
        print(result.decode().strip())
        break
    # print(result)
    # print(ser.readline().decode().strip())
print("found result")
time.sleep(1)
ser.write(b"end")
