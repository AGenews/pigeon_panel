# -*- coding: utf-8 -*-
"""
@author: Andreas Genewsky
"""

import numpy as np
import os
from tkinter import Tk, messagebox
from serial import Serial
from serial.tools.list_ports import comports
from TLC5955 import SCPIProtocol, SCPIException, TLC5955
from time import sleep

## Set PORTNAME = None to auto-detect
PORTNAME = None

# Setting reset_config to True will save default settings into panel_config.npz
#  otherwise we'll load panel_config.npz and use the stored settings
reset_config = True

# Setting save_config to True will save the configuration settings to the
#  display panel in addition to panel_config.npz
save_config = False

config_path = 'board 2 data/0'

config_file = os.path.join(config_path,'panel_config.npz')

if not os.path.exists(config_file): reset_config = True
if reset_config:
    ## Settings to use when resetting the config ##
    serial = '4'
    mode = {'dsprpt':True, 'espwm':True} #don't change these
    ## N.B. The product of maxcurrent and brightness must be greater than 1
    maxcurrent = np.array([8, 8, 3.2, 8]) #each must be one of (3.2,8,11.2,15.9,19.1,23.9,27.1,31.9) V/UV was 15.9 -- too bright
    brightness = np.array([0.42, 0.58, 0.5, 0.5]) # 0.1 to 1.0
    dotcorrect = np.ones((8,12,5))
    spif = 3000000
    os.makedirs(config_path,exist_ok=True)
    np.savez(config_file,serial=serial,mode=mode,maxcurrent=maxcurrent,brightness=brightness,dotcorrect=dotcorrect,spif=spif)
else:
    with np.load(config_file,allow_pickle=True) as cfg:
        mode = cfg['mode'][()]
        maxcurrent = cfg['maxcurrent']
        brightness = cfg['brightness']
        dotcorrect = cfg['dotcorrect']
        spif = cfg['spif']

if PORTNAME is None:
    print('Detecting Serial ports... ',end='',flush=True)
    target_hwid = 'VID:PID=16C0:0483'
    for port in comports():
        if port.hwid.find(target_hwid) > 0:
            PORTNAME = port.device
            print(f'Found Teensy on {PORTNAME}')
            break
if PORTNAME is None:
    print('Could not find Teensy USB!')
    exit(1)

#dead pixels have dotcorrect == nan
dead_pixels = np.where(np.any(np.isnan(dotcorrect),-1).flat)[0]
mode = TLC5955.mode_code(**mode)
maxcurrent = [TLC5955.maxcurrent_code(mc) for mc in maxcurrent]
brightness = [int(TLC5955.brightness_code(bc)) for bc in brightness]
dotcorrect = TLC5955.dotcorrect_code(dotcorrect)

img = np.zeros((8,12,5))
img1 = np.zeros((8,12,5))
img2 = np.zeros((8,12,5))
img3 = np.zeros((8,12,5))
img4 = np.zeros((8,12,5))
img5 = np.zeros((8,12,5))

def img_bytes(img):
    return scpi.format_bytes(TLC5955.pwm_code(img).tobytes())

# Connect to panel and set the settings
with Serial(PORTNAME) as port:
    with SCPIProtocol(port) as scpi:
        #first thing, turn off echo because it's annoying
        try:
            resp = scpi.command(b'syst:comm:echo off', True, timeout=1)
        except SCPIException:
            pass
        #TODO: scpi.command(f'syst:serial?') to check that serial # matches
        scpi.command('disp:spif {}'.format(spif),True)
        scpi.command('disp:mode {}'.format(mode))
        scpi.command('disp:maxc {}'.format(','.join('{}'.format(mc) for mc in maxcurrent)))
        scpi.command('disp:bri {}'.format(','.join('{}'.format(bc) for bc in brightness)))
        scpi.command(b'disp:dotc:all ' + scpi.format_bytes(dotcorrect.tobytes()))
        
        if save_config:
            scpi.command('disp:save')
        

        
        on_time = 0.2
        off_time = 0.2

        bf = 1.0 # brightness factor
        # (8,12,5)
        while 1:
            img[:] = 0  # set all values to 0
            img1[[2],[5],[0]] = bf
            img2[[3,3],[4,6],[0,0]] = bf
            img3[[3],[5],[0] = bf
            img4[[4,4],[4,6],[0,0]] = bf
            img5[[4],[5],[0]] = bf
            
            img = img1+img2+img3+img4+img5
            
            scpi.command(b'disp:pwm:all ' + img_bytes(img))
            scpi.command(b'disp on')
            sleep(on_time)
            scpi.command(b'disp off')
            sleep(off_time)
    
