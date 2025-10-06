from machine import Pin, ADC, I2C, PWM
from ssd1306 import SSD1306_I2C
import time
import random

# === OLED Setup ===
WIDTH = 128
HEIGHT = 64
i2c = I2C(0, scl=Pin(1), sda=Pin(0))
oled = SSD1306_I2C(WIDTH, HEIGHT, i2c)

# === Joystick Setup ===
xJoy = ADC(Pin(26))
yJoy = ADC(Pin(27))
button = Pin(15, Pin.IN, Pin.PULL_UP)

# === Passive Buzzer Setup ===
buzzer = PWM(Pin(18))
buzzer.duty_u16(0)

# === Game Variables ===
player_x = WIDTH // 2
player_y = HEIGHT - 10
bullets = []
enemies = []
score = 0
lives = 3
game_over = False

# === Generate Fewer, Slower Enemies ===
for i in range(3):
    enemies.append([random.randint(0, WIDTH - 5), random.randint(0, HEIGHT // 3), random.uniform(0.2, 0.4)])  
    # [x, y, speed]

# === Helper Functions ===
def tone(freq, duration):
    buzzer.freq(freq)
    buzzer.duty_u16(30000)
    time.sleep(duration)
    buzzer.duty_u16(0)

def draw_player(x, y):
    oled.fill_rect(x - 3, y, 6, 3, 1)

def draw_bullets():
    for b in bullets:
        oled.pixel(int(b[0]), int(b[1]), 1)

def draw_enemies():
    for e in enemies:
        oled.fill_rect(int(e[0]), int(e[1]), 4, 4, 1)

def update_bullets():
    global bullets, enemies, score
    new_bullets = []
    for b in bullets:
        b[1] -= 2
        if b[1] > 0:
            new_bullets.append(b)
    bullets = new_bullets

    # Collision detection
    for b in bullets[:]:
        for e in enemies[:]:
            if e[0] < b[0] < e[0] + 4 and e[1] < b[1] < e[1] + 4:
                enemies.remove(e)
                bullets.remove(b)
                score += 1
                tone(1000, 0.05)
                # Respawn enemy
                enemies.append([random.randint(0, WIDTH - 5), random.randint(0, HEIGHT // 3), random.uniform(0.2, 0.4)])
                break

def update_enemies():
    global enemies, lives, game_over
    for e in enemies:
        e[1] += e[2]  # slower speed
        if e[1] > HEIGHT - 5:
            e[1] = random.randint(0, HEIGHT // 3)
            e[0] = random.randint(0, WIDTH - 5)
            e[2] = random.uniform(0.2, 0.4)
            lives -= 1
            if lives <= 0:
                game_over = True

def draw_status():
    oled.text("Score:{}".format(score), 0, 0)
    oled.text("Lives:{}".format(lives), 70, 0)

# === Main Game Loop ===
while True:
    if game_over:
        oled.fill(0)
        oled.text("GAME OVER", 25, 25)
        oled.text("Score: {}".format(score), 30, 40)
        oled.show()
        buzzer.duty_u16(0)
        break

    oled.fill(0)

    # Read joystick
    xVal = xJoy.read_u16()
    yVal = yJoy.read_u16()

    # Move player
    if xVal < 20000 and player_x > 5:
        player_x -= 2
    elif xVal > 45000 and player_x < WIDTH - 5:
        player_x += 2

    # Fire bullet
    if not button.value():
        bullets.append([player_x, player_y - 5])
        tone(2000, 0.03)
        time.sleep(0.2)

    # Update objects
    update_bullets()
    update_enemies()

    # Draw
    draw_player(player_x, player_y)
    draw_bullets()
    draw_enemies()
    draw_status()

    oled.show()
    time.sleep(0.05)

# Turn off buzzer
buzzer.deinit()
