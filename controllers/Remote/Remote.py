# You may need to import some classes of the controller module. Ex:
#  from controller import Robot, Motor, DistanceSensor
import time
from email.policy import default

from controller import Robot

import json
import typing
import math
import asyncio
import threading
import random
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

#######################################################
# Creates Robot
#######################################################
robot = Robot()


#######################################################
# Sets the time step of the current world
#######################################################
timestep = int(robot.getBasicTimeStep())

#######################################################
# Gets Robots Distance Sensors
# Documentation:
#  https://cyberbotics.com/doc/reference/distancesensor
#######################################################
frontDistanceSensor = robot.getDevice('ds_front')
leftDistanceSensor = robot.getDevice('ds_left')
rightDistanceSensor = robot.getDevice('ds_right')
rearDistanceSensor = robot.getDevice('ds_back')
L45DistanceSensor = robot.getDevice('ds_l45')
R45DistanceSensor = robot.getDevice('ds_r45')

#######################################################
# Gets Robots Motors
# Documentation:
#  https://cyberbotics.com/doc/reference/motor
#######################################################
leftMotors = [robot.getDevice('wheel1'), robot.getDevice('wheel2')]
rightMotors = [robot.getDevice('wheel3'), robot.getDevice('wheel4')]

for x in leftMotors + rightMotors:
    x.setPosition(float('inf'))
    x.setVelocity(0)

#######################################################
# Gets Robot's the position sensors
# Documentation:
#  https://cyberbotics.com/doc/reference/positionsensor
#######################################################
leftposition_sensor = robot.getDevice('left wheel sensor')
rightposition_sensor = robot.getDevice('right wheel sensor')
leftposition_sensor.enable(timestep)
leftsample_period = leftposition_sensor.getSamplingPeriod()
rightposition_sensor.enable(timestep)
rightsample_period = rightposition_sensor.getSamplingPeriod()

#######################################################
# Gets Robot's IMU sensors
# Documentation:
#  https://cyberbotics.com/doc/reference/inertialunit
#######################################################
imu = robot.getDevice('inertial unit')
imu.enable(timestep)

#######################################################

def q_val(d, key):
    if key in d:
        return d[key]
    return ''

def to_int(val: str, default: int) -> int:
    try:
        return int(val)
    except ValueError:
        return default

def to_velocity(v: int) -> float:
    v = max(-255, min(255, v))

    return v * 15 / 255

class ThreadSafeAsyncFuture(asyncio.Future):
    """ asyncio.Future is not thread-safe
    https://stackoverflow.com/questions/33000200/asyncio-wait-for-event-from-other-thread
    """
    def set_result(self, result):
        func = super().set_result
        call = lambda: func(result)
        self._loop.call_soon_threadsafe(call)  # Warning: self._loop is undocumented


class ReadSensors(typing.NamedTuple):
    type: str

class SetMotors(typing.NamedTuple):
    r_motor_velocity: float
    l_motor_velocity: float
    r_motor_time: int
    l_motor_time: int

class Move(typing.NamedTuple):
    direction: str
    len: int

commandQueue = asyncio.Queue()

async def _cmd(c):
    future = ThreadSafeAsyncFuture()
    await commandQueue.put((future, c))
    return await future

def cmd(c: typing.Union[ReadSensors, SetMotors, Move]):
    return asyncio.run(_cmd(c))

class HttpGetHandler(BaseHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.protocol_version = 'HTTP/1.1'
        super().__init__(request, client_address, server)

    def log_message(self, format, *args) -> None:
      pass # disable logs

    def _read_body(self):
        # refuse to receive non-json content
        if self.headers.get('Content-Type') != 'application/json':
            self.send_response(400)
            self.end_headers()
            return None

        # read the message and convert it into a python dictionary
        length = int(self.headers.get('Content-Length'))

        msg = json.loads(self.rfile.read(length))
        if q_val(msg, 'id') != 'token': # auth
          return self._respond(404, 'Wrong token')

        return msg

    def _respond(self, code, msg) -> None:
      self.send_response(code)
      data = (str(code) + ' ' + msg).encode()
      self.send_header("Content-type", "text/plain")
      self.send_header('Content-Length', str(len(data)))
      self.end_headers()
      self.wfile.write(data)

    def _respond_json(self, data) -> None:
        self.send_response(200)
        data = json.dumps(data).encode()
        self.send_header("Content-type", "application/json")
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


    def do_GET(self):
        return self._respond(404, 'Unknown path')

    def do_POST(self):
        query_url = urlparse(self.path)

        if query_url.path == '/sensor':
            self.handle_sensors()
        else:
            return self._respond(404, 'Unknown path')

    def do_PUT(self):
        query_url = urlparse(self.path)

        if query_url.path == '/motor':
            self.handle_motors()
        elif query_url.path == '/move':
            self.handle_move()
        else:
          return self._respond(404, 'Unknown path')

    def handle_move(self):
        msg = self._read_body()
        if msg is None:
          return

        try:
          move_len = int(msg['len'])
        except ValueError:
          return self._respond(400, 'Invalid len'
                               )
        direction = msg['direction']
        if direction == 'left' or direction == 'right':
          if move_len < 0 or move_len > 360:
            return self._respond(400, 'Invalid len (grad)')
        elif direction == 'forward' or direction == 'backward':
          if move_len < 0 or move_len > 10_000:
              return self._respond(400, 'Invalid len (mm)')
        else:
          return self._respond(400, 'Invalid direction')

        cmd(Move(direction, move_len))
        return self._respond(200, 'ok')

    def handle_motors(self):
        msg = self._read_body()
        if msg is None:
            return

        r_motor_velocity = to_velocity(to_int(q_val(msg, 'r'), 0))
        l_motor_velocity = to_velocity(to_int(q_val(msg, 'l'), 0))
        r_motor_time = to_int(q_val(msg, 'r_time'), 0)
        l_motor_time = to_int(q_val(msg, 'l_time'), 0)

        # todo (hack)
        if (r_motor_velocity > 0 and l_motor_velocity > 0) or (r_motor_velocity < 0 and l_motor_velocity < 0):
            r_motor_velocity = -r_motor_velocity
            l_motor_velocity = -l_motor_velocity

        cmd(SetMotors(r_motor_velocity, l_motor_velocity, r_motor_time, l_motor_time))

        self._respond_json({
            'status': 'ok'
        })

    def handle_sensors(self):
        msg = self._read_body()
        if msg is None:
            return

        self._respond_json(cmd(ReadSensors(msg['type'])))


class MyServer(threading.Thread):
    def run(self):
        self.server = ThreadingHTTPServer(('', 8000), HttpGetHandler)
        self.server.serve_forever()
    def stop(self):
        self.server.shutdown()

server = MyServer()
server.start()

def main():
    r_motor_velocity, r_motor_time, l_motor_velocity, l_motor_time = 0, 0, 0,0
    rollpitchyaw = []

    start_yaw = random.randint(0, 180)
    sensors = [
        rearDistanceSensor,
        leftDistanceSensor,
        R45DistanceSensor,
        frontDistanceSensor,
        rightDistanceSensor,
        L45DistanceSensor,
    ]

    sensors_values = [0 for _ in sensors]
    sensor_delay = 200
    sensor_index = 0
    for sensor in sensors:
        sensor.enable(30) # 30ms between updates

    while True:
        try:
            (future, cmd) = commandQueue.get_nowait()

            if isinstance(cmd, ReadSensors):
                response = {}
                if (cmd.type == 'all') or (cmd.type == 'laser'):
                    response['laser'] = {
                        str(k+1): round(v) for (k,v) in enumerate(sensors_values)
                    }

                if (cmd.type == 'all') or (cmd.type == 'imu'):
                    response['imu'] = {
                        'roll': round(math.degrees(rollpitchyaw[0])),  # 1
                        'pitch': round(math.degrees(rollpitchyaw[1])), # 1
                        'yaw': (start_yaw + 180 - round(math.degrees(rollpitchyaw[2]))) % 360,   # 282
                    }

                future.set_result(response)
            elif isinstance(cmd, SetMotors):
                r_motor_velocity = cmd.r_motor_velocity
                r_motor_time = cmd.r_motor_time
                l_motor_velocity = cmd.l_motor_velocity
                l_motor_time = cmd.l_motor_time
                future.set_result(None)
            elif isinstance(cmd, Move):
                if cmd.direction == 'left' or cmd.direction == 'right':
                    traveled = 0
                    prev_yaw = -1

                    if cmd.len > 30:
                        # random error
                        traveled = 0

                        v = to_velocity(255 if cmd.direction == 'right' else -255)
                        while True:
                            if robot.step(min(timestep, 8)) == -1:
                                break

                            current_yaw = 180 + round(math.degrees(imu.getRollPitchYaw()[2]))
                            if prev_yaw != -1:
                                traveled += abs(prev_yaw - current_yaw)
                            prev_yaw = current_yaw

                            if traveled >= cmd.len:
                                break

                            for motor in leftMotors: motor.setVelocity(v)
                            for motor in rightMotors: motor.setVelocity(-v)
                else: # backward/forward
                    v = to_velocity(-255 if cmd.direction == 'forward' else 255)
                    t = round(cmd.len * 869 / 170)
                    while t > 0:
                        for motor in leftMotors:
                            motor.setVelocity(v)
                        for motor in rightMotors:
                            motor.setVelocity(v)
                        if robot.step(min(t, timestep)) == -1:
                            break
                        t -= timestep

                for motor in leftMotors + rightMotors: motor.setVelocity(0)
                future.set_result(None)
            else:
                raise "Unknown command type"

            continue
        except asyncio.QueueEmpty:
            pass

        t = min([x for x in [timestep, r_motor_time, l_motor_time] if x > 0])

        if robot.step(t) == -1:
            return

        rollpitchyaw = imu.getRollPitchYaw()

        sensor_delay -= t
        if len(sensors_values) == 0:
            sensors_values = [x.getValue() for x in sensors]
        elif sensor_delay <= 0:
            sensors_values[sensor_index] = sensors[sensor_index].getValue()
            if sensors_values[sensor_index] <= 25:
                sensors_values[sensor_index] = random.randint(18,25)

            sensor_index = (sensor_index + 1) % len(sensors)


        r_motor_time = max(0, r_motor_time - t)
        l_motor_time = max(0, l_motor_time - t)

        if (r_motor_time <= 0) and (r_motor_velocity != 0):
            r_motor_velocity = 0
        if (l_motor_time <= 0) and (l_motor_velocity != 0):
            l_motor_velocity = 0

        for motor in leftMotors: motor.setVelocity(l_motor_velocity)
        for motor in rightMotors: motor.setVelocity(r_motor_velocity)

main()

# exiting
server.stop()
exit(0)
