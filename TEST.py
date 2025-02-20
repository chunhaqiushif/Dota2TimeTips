import pygetwindow as gw

title = "Dota 2"


window = gw.getWindowsWithTitle(title)[0]

x = window.left
window.moveTo(x,0)
window.resizeTo(int(2567), int(1447))