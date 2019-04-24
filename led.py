import wiringpi
from time import sleep, time


class Light:
    # Take in the pins we attached to the raspberry and assign wiring function to methods of the class to make prettier.
    def __init__(self, r_pin, g_pin, b_pin):
        self.R_PIN = r_pin
        self.G_PIN = g_pin
        self.B_PIN = b_pin
        self.LED_PINS = [self.R_PIN, self.G_PIN, self.B_PIN]

        self.states = {'loading': False, 'error': False, 'transmitting': False, 'receiving': False}
        self.last_value = False

        self.setup = wiringpi.wiringPiSetupPhys()
        self.pinMode = wiringpi.pinMode

        self.delay_time = .4
        self.current_time = time()
        self.last_time = time()


    def digital_write(self, pin, output):
        wiringpi.digitalWrite(pin, output)

    def setup_pins(self):
        for PIN in self.LED_PINS:
            self.pinMode(PIN, 1)

    def tear_down_pins(self):
        for PIN in self.LED_PINS:
            self.digital_write(PIN, 0)
            self.pinMode(PIN, 0)

    def light_off(self):
        for pin in self.LED_PINS:
            self.digital_write(pin, 0)

    def change_state(self):
        self.current_time = time()
        if self.current_time - self.delay_time > self.last_time:
            self.last_time = self.current_time
            for state, value in self.states.items():
                if state == 'loading' and value:
                    self.digital_write(self.G_PIN, self.last_value)
                    self.last_value = not self.last_value
                elif state == 'loading' and not value:
                    self.digital_write(self.G_PIN, value)
                elif state == 'error' and value:
                    self.digital_write(self.G_PIN, self.last_value)
                    self.last_value = not self.last_value
                elif state == 'error' and not value:
                    self.digital_write(self.G_PIN, value)
                elif state == 'transmitting' and value:
                    self.digital_write(self.G_PIN, self.last_value)
                    self.last_value = not self.last_value
                elif state == 'transmitting' and not value:


