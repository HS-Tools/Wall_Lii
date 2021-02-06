import asyncio
import simpleobsws

# async def on_event(data):
#     print('New event! Type: {} | Raw Data: {}'.format(data['update-type'], data)) # Print the event data. Note that `update-type` is also provided in the data

# async def on_switchscenes(data):
#     print('Scene switched to "{}". It has these sources: {}'.format(data['scene-name'], data['sources']))

# async def make_request():
#     await ws.connect() # Make the connection to OBS-Websocket
#     await asyncio.sleep(1)
#     data = {'item':'Image', 'visible': True}
#     result = await ws.call('SetSceneItemProperties', data) # Make a request with the given data
#     print(result)
#     await ws.disconnect() # Clean things up by disconnecting. Only really required in a few specific situations, but good practice if you are done making requests or listening to events.

backgrounds = [
    'Couch',
    'Salami',
    'Jail',
    'Banana'
]

async def set_background_request(sourceName, ws):
    if sourceName in backgrounds:
        await ws.connect() # Make the connection to OBS-Websocket
        await asyncio.sleep(1)

        for background in backgrounds:
            data = {'item':background, 'visible': background == sourceName}
            result = await ws.call('SetSceneItemProperties', data) # Make a request with the given data
            print(result)
        await ws.disconnect() # Clean things up by disconnecting. Only really required in a few specific situations, but good practice if you are done making requests or listening to events.

def set_background(sourceName):
    loop = asyncio.get_event_loop()
    ws = simpleobsws.obsws(host='127.0.0.1', port=4444, password='ThisIsAPass', loop=loop) # Every possible argument has been passed, but none are required. See lib code for defaults.
    
    loop.run_until_complete(set_background_request(sourceName, ws))