#!/usr/bin/python
from lcd_module import LCDController
import smbus
import time
from data_fetch import getData, getAsyncData, RCP_OK, RCP_FAIL
from data_write import DataWriter
import gpsdData
from gpsdData import GpsPoller
import math
import threading
from timeit import default_timer as timer

bus = smbus.SMBus(1) # User SMBus(0) for version 1

# The address we setup in the Arduino Program
address = 0x25

LCDOK = 1
LCDFAIL = 0
GPSOK = 1
GPSFAIL = 0

def lcdplot(lcd_controller, data, ardu_status, gps_status):
  if ardu_status == RCP_OK:
    ardu_plot_status = "*"
  else:
    ardu_plot_status = "_"

  if gps_status == GPSOK:
    gps_plot_status = "*"
  else:
    gps_plot_status = "_"

  lcd_controller.plot(
    "Wsp: %02.2f  A%s" % (data[1],ardu_plot_status),
    "Wdr: %05d G%s" % (data[0],gps_plot_status)
  )

RADIUS = 70 # radius of anemometrus in mm

def convert_wind_speed(rounds, timedelta):
  """
    Compute the wind speed given the rounds per time interval
    rounds: (twice) number of rounds
    timedelta: time interval
  """
  rps = rounds / 2. /timedelta
  radial_speed = rps * RADIUS # in mm/s
  return radial_speed 
    
    

def compute_wind_speed(wind_apparent_speed, wind_apparent_dir, fix_speed):
  """
    wind_apparent_speed in mm/s 
    wind_apparent_dir in degrees wrt my direction
    fix_speed in m/s given by the gps
  """
  a = wind_apparent_speed * 0.00194
  b = fix_speed * 1.94
  th = wind_apparent_dir
  # law of cosine
  spd = math.sqrt(a * a + b * b - 2 * a * b * math.cos(math.pi * th / 180))
  return spd

if __name__ == "__main__":
  # Setup initial statuses
  gps_status = GPSFAIL
  lcd_status = LCDFAIL
  ardu_status = RCP_FAIL

  # Initialize controllers
  lcd = LCDController()
  datawriter = DataWriter(filename="/home/pi/testdata.csv")
  gpsp = GpsPoller()
  gpsd = gpsdData.gpsd
  gpsp.running = False
  # Check how these fail in case the gps module is not connected
  # see https://gist.github.com/wolfg1969/4653340
  # and https://learn.adafruit.com/adafruit-ultimate-gps-on-the-raspberry-pi/using-your-gps
  start_time = timer()

  while True:
    try:

      # get data from arduino
      res = [[0,0,0,RCP_FAIL] ]
      datathread = threading.Thread(target=getAsyncData, args=(res,))
      datathread.start()
      datathread.join(1)
      data = res[0]
      end_time = timer()
      ardu_status = data[3]

      # Start the gps watcher
      try:
        if not gpsp.running:
          gpsp.running = True
          gpsp.start()
          gps_status = GPSOK
      except:
        gpsp.running = False
        gps_status = GPSFAIL
        raise

      try:
        timedelta = end_time - start_time
        if timedelta >= .4:
          rps = convert_wind_speed(data[1],timedelta)
        else:
          rps = 10 # dummy value
        start_time = end_time
        adj_speed = compute_wind_speed(rps,data[0],gpsd.speed)
        data[1] = adj_speed
      except:
        pass

      # set up the lcd
      try:
        if lcd_status == LCDFAIL:
          lcd.initialize()
          lcd_status = LCDOK
        lcdplot(lcd, data, ardu_status, gps_status)
        #lcd.plot("Wind spd: %03d" % data[1],"Wind dir: %03d" % data[0])

      except IOError:
        lcd_status = LCDFAIL

      # Pass the data (formatted) to the datawriter
      if ardu_status == RCP_OK:
        datawriter.append("%d,%d,%d"%(data[0],data[1],data[2]))

      # Wait before next rount
      time.sleep(.5)

    except (KeyboardInterrupt, SystemExit):
      if lcd_status == LCDOK:
        lcd.plot("Quitting, bye!","")
      gpsp.running = False
      gpsp.join()
      raise

    except:
      raise
