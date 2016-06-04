from __future__ import print_function # To support the splat operator in LightingMinion.debug()

import sys
import json
import time
import array
import select

from MeteorClient import MeteorClient
from ola import OlaClient

rate = 0.002

class MeteorTime:
    def __init__(self, meteor):
        self.meteor = meteor
        
        self.latency = 0
        self.last = 0
        self.last_time = 0
    
    def update(self):
        self.start = time.time()
        self.meteor.call('getTime', [], self.callback)
        
    def callback(self, error, server_now):
        now = time.time()
        self.latency = now - self.start
        self.last = (server_now * 0.001 - self.latency / 2)
        self.last_time = now
        
    def now(self):
        return self.last + (time.time() - self.last_time)

class Fade:
    def __init__(self, start, end, time, length, uni, channel, meteortime):
        self.start = start
        self.curr = start
        self.end = end
        self.time = time
        self.length = length
        self.uni = uni
        self.channel = channel
        self.meteortime = meteortime
        self.finished = False
        
    def tick(self):
        currtime = self.meteortime.now()
        if currtime < self.time: return
        
        elapsed = currtime - self.time
        
        if self.curr < self.end:
            try: self.curr = self.start + (self.end - self.start) / (self.length / elapsed)
            except ZeroDivisionError: self.curr = self.end
            if self.curr > self.end: self.curr = self.end

        elif self.curr > self.end:
            try: self.curr = self.end + (self.start - self.end) / (self.length / (self.length - elapsed))
            except ZeroDivisionError: self.curr = self.end
            if self.curr < self.end: self.curr = self.end

        self.uni[self.channel] = int(self.curr)
        
        if self.curr == self.end:
            self.finished = True        

class LightingMinion:
    def __init__(self, config):
        self.config = config
        self.universes = {}
        self.fades = {}
        
        self.last = 0
        self.ready = False
        
        self.meteor = MeteorClient(self.config['server'])
        self.meteor.on('connected', self.connect_cb)
        self.meteor.connect()
        
    def connect_cb(self):
        self.debug('Connection to Meteor established.')

        if not self.config.get('id'):
            self.debug('No id in settings, registering as new.')
            self.meteor.call('minionNew', [self.config['type']], self.register)
        
        else:
            self.register(None, self.config['id'])
    
    def register(self, err, id):
        self.config['id'] = id
        self.debug('Connecting with id ' + id)
        self.meteor.call('minionConnect', [id], self.prep)

    def prep(self, e, r):
        self.meteortime = MeteorTime(self.meteor)
        
        self.meteor.subscribe('lights')
        self.meteor.on('added', self.added)
        self.meteor.on('changed', self.changed)
        
        self.ola = OlaClient.OlaClient()
        self.olasock = self.ola.GetSocket()
        self.olasock.setblocking(False)
        self.selectargs = ([self.olasock], [], [], 0)
        
        self.ready = True
        
        print('Connected to server.')
        
    def debug(self, *args):
        if self.config.get('debug'):
            print(*args)
            
    def added(self, collection, id, fields):
        self.changed(collection, id, fields, None)
        
    def changed(self, collection, id, fields, cleared):
        light = self.meteor.find_one('lights', selector={'_id': id})
        settings = light.get('settings')
        if not settings: return
        
        if light['minion'] == self.config['id']:
            self.debug('light changed: ', light['title'], fields)

            for channel in light['channels']:
                uni_num = channel['universe']

                if not self.universes.get(uni_num):
                    self.universes[uni_num] = array.array('B', [0] * 512)
                    self.fades[uni_num] = {}
                
                uni = self.universes[uni_num]

                addr = channel['address'] - 1
                curr = uni[addr]

                try:
                    value = light['values'][light['channels'].index(channel)] * 255
                except IndexError:
                    continue

                if not value == curr:
                    self.fades[uni_num][addr] = Fade(uni[addr], value, settings['time'], settings['fade'], uni, addr, self.meteortime)

    def run(self):
        while True:
            start = time.time()

            if self.ready:
                r, w, e = select.select(*self.selectargs)
                if len(r) > 0: self.ola.SocketReady()

                if start - self.last >= 1:
                    self.meteortime.update()
                    self.last = time.time()
            
                for uni, fades in self.fades.items():
                    for addr, fade in tuple(fades.items()):
                        fade.tick()
                        if fade.finished: del self.fades[uni][addr]
            
                for num, uni in self.universes.items():
                    self.ola.SendDmx(num, uni, None)
            
            try: time.sleep(rate - (time.time() - start))
            except ValueError: continue
            except IOError: continue
                    
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: lightingminion.py <config file>')
        quit()
    
    conffile = open(sys.argv[1], 'r+')
    config = json.load(conffile)

    config['type'] = 'lighting'

    minion = LightingMinion(config)
    
    try:
        minion.run()
    except KeyboardInterrupt:
        print('Shutting down...')
        minion.meteor.close()

        conffile.seek(0)
        json.dump(minion.config, conffile, indent = 4)
        conffile.close()
        quit()
