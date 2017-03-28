import time
import logging
logging.basicConfig(format='%(asctime)s %(message)s', filename='/python-daemon/daemon.log', level=logging.DEBUG)

while True:
  print 'Daemon is running'
  logging.debug('Daemon is running')
  time.sleep(10)
