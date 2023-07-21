#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import logging
import re
import time
from cmd import Cmd

import RPi.GPIO as GPIO
from apscheduler.schedulers.background import BackgroundScheduler
from prometheus_client import start_http_server, Gauge

# needed global Variables
T_a, T_v, T_r, T_r_soll, Brenner_Count, Brenner_Seconds = 0, 0, 0, 0, 0, 0
Heating, Pumping = False, False
Mode, Mode_action = 'AUTO', ''
Old_Date = datetime.date.min
Time_Start = datetime.datetime.min
sched = BackgroundScheduler()
gauge_T_a = Gauge('t_a', 'Außentemperatur')
gauge_T_v = Gauge('t_v', 'Vorlauftemperatur')
gauge_T_r = Gauge('t_r', 'Rücklauftemperatur')
gauge_T_r_soll = Gauge('t_r_soll', 'Rücklauf Solltemperatur')
gauge_heating = Gauge('heating','Status Brenner')
gauge_pumping = Gauge('pumping', 'Status Pumpe')
gauge_heater_starts = Gauge('heater_starts', 'Brennerstarts')
gauge_heater_runtime = Gauge('heater_runtime', 'Brennerlaufzeit')


class Prompt(Cmd):
    """Basic Class for console-based user interaction"""
    def do_status(self, args):
        """Gives you the actual status of the heater."""
        print('Pumpen: {0} | Brennen: {1} | Starts: {2} | Laufzeit: {3} Min'.format(Pumping, Heating, Brenner_Count, Brenner_Seconds / 60.0))

    def do_temps(self, args):
        """Gives you the actual temperatures read by the system."""
        print('Aussen: {0} C | Vorlauf: {1} C | Ruecklauf: {2} C | Ruecklauf Soll: {3} C'.format(T_a, T_v, T_r, T_r_soll))

    def do_mode(self, args):
        """Gives you the actual mode of the heater"""
        print(Mode)

    def do_setmode(self, args):
        """Setting the mode of the heater to AUTO or MAN"""
        global Mode, Mode_action
        if args == 'AUTO':
            Mode = 'AUTO'
            Mode_action = ''
        elif args == 'MAN':
            Mode = 'MAN'
        else:
            print('Mode "' + args + '" is not supported. Please use AUTO or MAN as mode!')

    def do_on(self, args):
        """If MAN mode is used the heater turns on."""
        global Mode_action
        if Mode == 'AUTO':
            print('Please activate the MAN mode before using ON!')
        elif Mode == 'MAN':
            Mode_action = 'ON'
            while not Pumping or not Heating:
                time.sleep(0.1)
            print('Heater turned on.')

    def do_off(self, args):
        """If MAN mode is used the heater turns off."""
        global Mode_action
        if Mode == 'AUTO':
            print('Please activate the MAN mode before using OFF!')
        elif Mode == 'MAN':
            Mode_action = 'OFF'
            while Pumping or Heating:
                time.sleep(0.1)
            print('Heater turned off.')

    def do_quit(self, args):
        """Quits the heater-controller."""
        raise KeyboardInterrupt


def read_sensor(path):
    value = 'U'
    try:
        f = open(path, 'r')
        line = f.readline()
        if re.match(r'([0-9a-f]{2} ){9}: crc=[0-9a-f]{2} YES', line):
            line = f.readline()
            m = re.match(r'([0-9a-f]{2} ){9}t=([+-]?[0-9]+)', line)
            if m:
                value = float(m.group(2)) / 1000.0
        f.close()
    except IOError as e:
        print(time.strftime('%x %X'), 'Error reading', path, ': ', e)
    return value


def get_temperature_outside():
    global T_a, gauge_T_a
    for i in range(0,3):
        reading = read_sensor('/sys/bus/w1/devices/10-000802dae530/w1_slave')
        if reading != 85.0 and reading != 'U':
            break
        else:
            time.sleep(1)
    else:
        logging.error('Reading outdoor sensor failed.')
        return
    T_a = round(reading, 1)
    gauge_T_a.set(T_a)


def get_temperature_heater():
    global T_v, T_r, gauge_T_v, gauge_T_r
    for i in range(0,3):
        reading = read_sensor('/sys/bus/w1/devices/10-000802dbd820/w1_slave')
        if reading != 85.0 and reading != 'U':
            break
        else:
            time.sleep(1)
    else:
        logging.error('Reading heater sensor (T_v) failed.')
        return
    T_v = round(reading, 1)
    gauge_T_v.set(T_v)

    time.sleep(0.5)

    for i in range(0,3):
        reading = read_sensor('/sys/bus/w1/devices/10-000802dab364/w1_slave')
        if reading != 85.0 and reading != 'U':
            break
        else:
            time.sleep(1)
    else:
        logging.error('Reading heater sensor (T_r) failed.')
        return
    T_r = round(reading, 1)
    gauge_T_r.set(T_r)


def calc_t_r_soll():
    global T_r_soll, gauge_T_r_soll
    m, n, r_soll = 0.65, 2.0, 21.8  # Winterstandard: 0.65 2.0, 21.8
    T_r_soll = round(1.1 * m * (r_soll ** (T_a / (320.0 - (4.0 * T_a)))) * (-T_a + 20.0) + r_soll + n, 1)
    gauge_T_r_soll.set(T_r_soll)


def turn_off_pumping():
    global Pumping, gauge_pumping
    GPIO.output(13, GPIO.LOW)
    GPIO.output(12, GPIO.LOW)
    Pumping = False
    gauge_pumping.set(Pumping)


def turn_off_heating():
    global Heating, gauge_heating
    GPIO.output(11, GPIO.LOW)
    Heating = False
    gauge_heating.set(Heating)


def turn_on_pumping():
    global Pumping, gauge_pumping
    GPIO.output(12, GPIO.HIGH)
    GPIO.output(13, GPIO.HIGH)
    Pumping = True
    gauge_pumping.set(Pumping)


def turn_on_heating():
    global Heating, gauge_heating
    GPIO.output(11, GPIO.HIGH)
    Heating = True
    gauge_heating.set(Heating)


def init():
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(11, GPIO.OUT)  # Heater
    GPIO.setup(12, GPIO.OUT)  # PEN
    GPIO.setup(13, GPIO.OUT)  # L
    get_temperature_outside()
    time.sleep(1)
    get_temperature_heater()
    calc_t_r_soll()
    logging.basicConfig(filename='heizung.log', level=logging.WARNING)


def check_status():
    global Brenner_Count, Brenner_Seconds, Old_Date, Time_Start, gauge_heater_starts, gauge_heater_runtime
    calc_t_r_soll()
    now = datetime.datetime.now()
    if Old_Date < now.date():
        logging.warning(str(Old_Date) + ': Starts: ' + str(Brenner_Count) + ' Laufzeit: ' + str(Brenner_Seconds))
        Old_Date = now.date()
        Brenner_Count = 0
        Brenner_Seconds = 0
    gauge_heater_starts.set(Brenner_Count)
    gauge_heater_runtime.set(Brenner_Seconds)
    if Mode == 'AUTO':
        if datetime.time(5, 0) <= now.time() <= datetime.time(20, 30) or Heating or Pumping:
            if T_r < (T_r_soll - 5) and not Heating and not Pumping:
                turn_on_pumping()
                logging.warning(str(now) + ': Heizung AN!')
            elif T_r < (T_r_soll - 5) and not Heating and Pumping:
                turn_on_heating()
                logging.warning(str(now) + ': Brenner AN!')
                Time_Start = datetime.datetime.now()
            elif T_r < (T_r_soll - 4.8) and not Heating and Pumping:
                pass
            elif T_r > (T_r_soll + 5) and Heating:
                turn_off_heating()
                logging.warning(str(now) + ': Brenner AUS!')
                time_delta = datetime.datetime.now() - Time_Start
                Brenner_Seconds += time_delta.seconds
                Brenner_Count += 1
            elif T_v <= (T_r + 0.9) and Pumping and not Heating:
                turn_off_pumping()
                logging.warning(str(now) + ': Heizung AUS!')
            elif T_v >= (T_r + 2) and not Pumping and not Heating:
                turn_on_pumping()
                logging.warning(str(now) + ': Heizung AN!')
    elif Mode == 'MAN' and Mode_action == 'ON':
        if Pumping:
            if not Heating:
                turn_on_heating()
                logging.warning(str(now) + ': Brenner AN (MANUELL)!')
                Time_Start = datetime.datetime.now()
        else:
            turn_on_pumping()
            logging.warning(str(now) + ': Heizung AN (MANUELL)!')
            time.sleep(10)
            turn_on_heating()
            logging.warning(str(now) + ': Brenner AN (MANUELL)!')
            Time_Start = datetime.datetime.now()
    elif Mode == 'MAN' and Mode_action == 'OFF':
        if Pumping:
            if Heating:
                turn_off_heating()
                logging.warning(str(now) + ': Brenner AUS (MANUELL)!')
                time_delta = datetime.datetime.now() - Time_Start
                Brenner_Seconds += time_delta.seconds
                Brenner_Count += 1
                time.sleep(10)
                turn_off_pumping()
                logging.warning(str(now) + ': Heizung AUS (MANUELL)!')
            else:
                turn_off_pumping()
                logging.warning(str(now) + ': Heizung AUS (MANUELL)!')


if __name__ == '__main__':
    try:
        print('Initializing Data and starting workers ...')
        init()
        sched.add_job(get_temperature_outside, 'interval', seconds=120)
        sched.add_job(get_temperature_heater, 'interval', seconds=17)
        sched.add_job(check_status, 'interval', seconds=30)
        sched.start()
        start_http_server(8000)
        prompt = Prompt()
        prompt.prompt = '>'
        prompt.cmdloop('Starting prompt ...')
    except KeyboardInterrupt:
        print('Quit by User.')
    finally:
        sched.shutdown()
        GPIO.output(11, GPIO.LOW)
        GPIO.output(13, GPIO.LOW)
        GPIO.output(12, GPIO.LOW)
        GPIO.cleanup()
