import os
import sys
import logging
# import ConfigParser
# from util.server import get_absolute_path
import ast
# from sqlalchemy import create_engine, MetaData, Table

CONFIG_FILE = "config.ini"
wdir = os.getcwd()
# Config= ConfigParser.ConfigParser()
# Config.read("config.ini")

# set up logging to file - see previous section for more details
# log_level = eval('logging.'+Config.get('Logger', 'Level'))
logging.basicConfig(level='DEBUG',
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%y-%m-%d %H:%M',
                    filename='mashahir.log',
                    filemode='a')
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel('DEBUG')
# set a format which is simpler for console use
formatter = logging.Formatter('%(asctime)s %(name)-12s: %(levelname)-8s %(message)s')
# tell the handler to use this format
console.setFormatter(formatter)
# add the handler to the root logger
logging.getLogger('').addHandler(console)

class Property(object):
    pass

class MyWriter:
    def __init__(self, stdout, logger):
        self.stdout = stdout
        self.logger = logger

    def write(self, text):
        self.logger.debug(text)

    def close(self):
        self.stdout.close()

writer = MyWriter(sys.stdout, logging)
sys.stdout = writer
