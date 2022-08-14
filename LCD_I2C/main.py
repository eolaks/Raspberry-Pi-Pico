#Import Libraries
from machine import Pin, I2C
from time import sleep
from lcd_api import LcdApi
from pico_i2c_lcd import I2cLcd
sda = Pin(0)
scl = Pin(1)
i2c = I2C(0, sda= sda, scl=scl, freq = 400000)
#print(i2c.scan()) # print i2c address
I2C_ADDR     = 39
I2C_ROWS = 2
I2C_COLS = 16
lcd = I2cLcd(i2c, I2C_ADDR, I2C_ROWS, I2C_COLS)
while True:
  lcd.move_to(0,0) # line 1
  lcd.putstr("** Hi Welcome **")
  sleep(0.01)
  lcd.move_to(0,1) # line 2
  lcd.putstr("** Main menu! **")
  sleep(0.01)



