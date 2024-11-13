from controller import Supervisor
from datetime import timedelta
from typing import Self
import math

TIME_STEP = 32

supervisor = Supervisor()  # create Supervisor instance

robot_node = supervisor.getFromDef("ROBOT")

def print_time(ms: int):
    s1, s2, s3 = str(timedelta(seconds=ms/1000)).split(':', 2)
    supervisor.setLabel(0, s2 + ':' + s3[:6], 0.0, 0, 0.2, 0xCCFF99)

class Vector(tuple):
    def rotate(self, angle_rad) -> Self:
        x = self[0]
        y = self[1]
        return Vector((
            x * math.cos(angle_rad) - y * math.sin(angle_rad),
            x * math.sin(angle_rad) + y * math.cos(angle_rad),
        ))

    def add(self, other: Self) -> Self:
        return Vector((self[0] + other[0], self[1] + other[1]))

    def add_xy(self, x, y) -> Self:
        return Vector((self[0] + x, self[1] + y))

def angle() -> float:
    ori = robot_node.getOrientation()
    d = ori[4]
    d = max(-1, min(1, d))

    d = math.acos(d)
    if ori[1] < 0:
        d = -d

    return d

def getCellBox(i, j) -> tuple:
    full = 2.886

    # pillar coordinates
    x = i * 0.180 + 0.006 - full / 2
    y = j * 0.180 + 0.006 - full / 2

    return (
        x - 0.180, y,
        x, y - 0.180
    )

firstCellBox = getCellBox(1, 1)
centerBox = getCellBox(8, 9)[:2] + getCellBox(9, 8)[2:4]

robot_box = [
    Vector((-0.04, -0.035)),
    Vector((0.04, -0.035)),
    Vector((-0.04, 0.035)),
    Vector((0.04, 0.035)),
]

def in_box(box, pos, angle) -> bool:
    x_min = min(box[0], box[2])
    x_max = max(box[0], box[2])
    y_min = min(box[1], box[3])
    y_max = max(box[1], box[3])

    for _, p in enumerate(robot_box):
        p = p.rotate(angle).add(pos)
        if not ((x_min <= p[0] <= x_max) and (y_min <= p[1] <= y_max)):
            return False

    return True

def robot_in_the_boxes() -> (bool, bool):
    pos = robot_node.getPosition()

    a = angle()

    return in_box(firstCellBox, pos, a), in_box(centerBox, pos, a)

def main():
    timer_started = False
    timer_finished = False
    timer_value = 0
    last_draw = 0
    print_time(0)

    while supervisor.step(TIME_STEP) != -1:
        in_start, in_center = robot_in_the_boxes()

        if timer_started and not timer_finished:
            timer_value += TIME_STEP
            if timer_value - last_draw > 66:
                last_draw = timer_value
                print_time(timer_value)


        if not timer_started and not in_start:
            timer_started = True
            print("Timer started")

        if in_center and not timer_finished:
            timer_finished = True
            print("Timer stopped")

main()
