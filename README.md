
В этой директории лежит симулятор

[Установка](https://cyberbotics.com/doc/guide/installation-procedure) 

После установки нужно открыть файл [world.wbt](worlds/remote.wbt)

Ссылки:
 - https://github.com/TLe1289/Robobulls_Micromouse_2023/tree/main/WebotsMicroMouse
 - https://github.com/emstef/Micromouse

Таймер
===

Таймер запускается когда любая часть робота выходит за границы первой клетки.
Таймер останавливается когда робот полностью находится в границах 4 центральных клеток лабиринта


Troubleshooting
===

Для macOS, чтобы система позволи примонтировать dmg образ, нужно будет скачать webots через curl:
    
    curl -L -O https://github.com/cyberbotics/webots/releases/download/R2023b/webots-R2023b.dmg
