import sys
import json
import array
import asyncio
import ddp_asyncio

from ola.ClientWrapper import ClientWrapper

class LightingMinion:
    def __init__(self, config):
        self.config = config
        self.universes = {}
        self.wrapper = ClientWrapper()

        asyncio.async(self.update())
        
    def debug(self, *args):
        if self.config.get('debug'):
            print(*args)

    @asyncio.coroutine
    def connect(self):
        self.ddp = ddp_asyncio.DDPClient(self.config['server'])
        yield from self.ddp.connect()

        if not self.config.get('id'):
            self.config['id'] = yield from self.ddp.call('minionNew', self.config['type'])

        self.lightssub = yield from self.ddp.subscribe('lights', self.config['id'], ready_cb = self.ready, changed_cb = self.changed)
        self.lights = self.lightssub.data
        
        yield from self.ddp.call('minionConnect', self.config['id'])
        self.debug('connected to server')
        
    @asyncio.coroutine
    def ready(self, sub):
        for lightid, light in self.lights.items():
            yield from self.changed(self.lightssub, lightid, light)
        
    @asyncio.coroutine
    def changed(self, lightssub, lightid, data):
        light = self.lights[lightid]
        self.debug('light changed: ', data)
        
        for channel in light['channels']:
            if not self.universes.get(channel['universe']):
                self.universes[channel['universe']] = array.array('B', [0] * 512)
            
            uni = self.universes[channel['universe']]
            
            uni[channel['address']] = int(light['values'].get(channel['type']) or 0) * 255
    
    @asyncio.coroutine
    def update(self):
        while True:
            for num, uni in self.universes.items():
                self.wrapper.Client().SendDmx(num, uni, None)
                
            yield from asyncio.sleep(0.02)
        
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: lightingminion.py <config file>')
        quit()
        
    loop = asyncio.get_event_loop()
    
    conffile = open(sys.argv[1], 'r+')
    config = json.load(conffile)

    config['type'] = 'lighting'

    minion = LightingMinion(config)
    loop.run_until_complete(minion.connect())
    
    conffile.seek(0)
    json.dump(minion.config, conffile, indent = 4)
    conffile.close()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        quit()
