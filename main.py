#!/usr/bin/env python3
import ast
import json
import socket
import subprocess
import time
from builtins import enumerate
from collections import ChainMap


import click
import requests
from digi.xbee.devices import DigiMeshDevice
from digi.xbee.exception import XBeeException, InvalidOperatingModeException
from led import Light
# from serial import SerialException


key_list = [
    'FPPD_Mode',
    'FPP_Status',
    'Volume',
    'Playlist_or_NextPlaylist',
    'file_type',
    'sequence_name',
    'sequence_position',
    'number_of_sequences',
    'time_elapsed',
    'time_remaining',
    'next_playlist',
    'schedule',
    'repeat',
]


class FppSettings(Light):
    def __init__(self, fpp_mode, status=None, xbee_com='/dev/ttyAMA0', xbee_baud=9600):
        Light.__init__(self, 15, 16, 18)
        # Define a mode so we know if we are the master or slave
        self.fpp_mode = fpp_mode
        self.status = status
        # Check if the fpp player is up and running so we don't issue commands before its ready that may cause a crash.
        while self.status is None:
            print('Waiting for FPPD to start...')
            self.states['loading'] = True
            time.sleep(1)
            self.status = self.get_fppd_status()
            self.local_xbee = DigiMeshDevice(xbee_com, xbee_baud)
        while True:
            """ Attempt to connect to an xbee device that is plugged in. 
            Currently this will loop infinitely if no device is connected. 
            Needs to be updated with a timeout feature.
            Should finish loading the script then try and connect to a xbee device periodically. 
            """
            try:
                self.states['loading'] = True
                self.local_xbee.open()
                break
            except XBeeException:
                self.states['loading'] = False
                self.states['error'] = True
                print('Check the device is connected!')
            except InvalidOperatingModeException:
                self.states['loading'] = False
                self.states['error'] = True
                print('Something went wrong lets try again.')
                self.local_xbee.close()
        self.xbee_network = self.local_xbee.get_network()
        # Save all the network devices in a list so we can find who to talk to.
        self.network_devices = self.get_devices()
        if self.fpp_mode == 'slave':
            self.playlist_updated = False
            self.master_device = self.get_master_device()

    hostname = "http://" + socket.gethostname()
    playlists = requests.get(hostname + '/api/playlists').json()
    number_of_playlist = {'number_of_playlist': len(playlists)}

    def get_master_device(self):
        for device in self.network_devices:
            if 'master' in device.get_node_id():
                print('Found the master')
                return device



    @staticmethod
    def convert_str_to_int(item):
        if item.isdigit():
            return int(item)
        else:
            return item

    @classmethod
    def get_fppd_status(cls):
        status = subprocess.run(['/opt/fpp/src/fpp', '-s'], stdout=subprocess.PIPE).stdout.decode(
            'utf-8').strip('\n')
        if 'false' in status:
            return None
        status_list = status.split(',')
        if '' in status_list:
            status_list.remove('')
        else:
            return None
        status_list = list(map(cls.convert_str_to_int, status_list))
        status_list = dict(zip(key_list, status_list))
        return status_list

    # Incoming message from another FPP device. Try to call the command from the class methods.
    def get_command(self, command, address):
        if hasattr(self, command):
            method = getattr(self, command, lambda: 'nothing')
            return method(address)
        elif command == 'quit':
            pass
        elif '{' in command and command.endswith('}'):
            print(json.loads(command.replace("'", '"')))
        else:
            print('Unhandled Command: ' + command)

    def get_devices(self):
        """" Method to discover all the xbees in the current network this method is blocking."""
        self.xbee_network.start_discovery_process()
        while self.xbee_network.is_discovery_running():
            time.sleep(0.5)
        return self.xbee_network.get_devices()

    def list_devices(self):
        for device in self.network_devices:
            print(device.get_64bit_addr())

    def get_playlist(self, playlist):
        # GET /playlist/:PlaylistName
        r = requests.get(self.hostname + '/api/playlist/' + playlist).json()
        return r

    @staticmethod
    def dump_json(json_data):
        stringify = json.dumps(json_data, indent=2)
        return stringify

    @staticmethod
    def define_playlist_values(playlist_json):
        """ Dictionary of only the values we need to transmit to slave players
            'playlistInfo': dict{
                total_duration: int*
                total_items: int*
            }

            'mainPlaylist': list of dicts [{
                sequenceName: str*
            }]
            'name': str
        """
        values_to_send = [{'total_duration': playlist_json['playlistInfo']['total_duration']},
                          {'total_items': playlist_json['playlistInfo']['total_items']}]
        for i, value in enumerate(playlist_json['mainPlaylist']):
            values_to_send.append({'sequenceName' + str(i): value['sequenceName']})

        return values_to_send

    def send_playlists(self, address):
        # Ignore playlist request if we are a slave controller.
        if self.fpp_mode == 'slave':
            return
        number_of_playlist_sent = 0
        for item in self.playlists:
            # Loop through the list of items in the playlists api.
            # Grab a json value from the specified playlist for sending
            values_to_send = self.define_playlist_values(self.get_playlist(item))
            # If we haven't send anything send out the total number of playlist.
            # So the reciever knows how many to expect.
            if number_of_playlist_sent == 0:
                self.send_message_to(str(self.number_of_playlist), address)
            # Send values and append which playlist number the belong too so we don't have repeating keys.
            for value in values_to_send:
                if type(value) == int:
                    self.send_message_to(str(value), address)
                elif type(value) == dict:
                    key = list(value)[0]
                    value[key + '_' + str(number_of_playlist_sent)] = value.pop(key)
                    self.send_message_to(str(value), address)
                else:
                    self.send_message_to(value, address)
            number_of_playlist_sent += 1
        # Let the receiver know the transmission has finished.
        self.send_message_to('{"end_transmit": 1}', address)

    def send_message_all(self, message):
        for device in self.network_devices:
            self.local_xbee.send_data_async_64(device.get_64bit_addr(), message)

    def send_message_to(self, message, address):
        self.local_xbee.send_data_async_64(address, message)

    # def post_playlist(self):
    #     pass
    #     # {
    #     #     "name": "UploadTest",
    #     #     "mainPlaylist": [
    #     #         {
    #     #             "type": "pause",
    #     #             "enabled": 1,
    #     #             "playOnce": 0,
    #     #             "duration": 8
    #     #         }
    #     #     ],
    #     #     "playlistInfo": {
    #     #         "total_duration": 8,
    #     #         "total_items": 1
    #     #     }
    #     # }

    def update_playlist(self):
        init_time = time.time()
        timeout = 15
        xbee_messages = []
        if not self.playlist_updated:
            self.send_message_to('send_playlists', self.master_device.get_64bit_addr())
            while not self.playlist_updated:
                xbee_message = self.local_xbee.read_data()
                if xbee_message:
                    xbee_message = xbee_message.data.decode()
                    xbee_messages.append(ast.literal_eval(xbee_message))
                    items = ['total_items', 'sequence_name']
                    if any('end_transmit' in key for key in xbee_messages):
                        xbee_messages = dict(ChainMap(*xbee_messages))
                        if self.post_playlist(xbee_messages):
                            break
                        # print(xbee_messages)
                        # for i in range(0, xbee_messages['number_of_playlist']):
                        #     xbee_message_key = '_' + str(i)
                        #     for j in range(0, xbee_messages['total_items' + xbee_message_key]):
                        #         print(xbee_messages['sequenceName' + str(j) + xbee_message_key])

    def post_playlist(self, playlist_data):
        playlist_name = 'play_'
        for i in range(playlist_data['number_of_playlist']):
            playlist_name += str(i)
            playlist_data_key = '_' + str(i)
            playlist_dict = {"name": playlist_name,
                             "mainPlaylist": [

                             ],
                             "playlistInfo": {
                                 "total_duration": playlist_data['total_duration' + playlist_data_key],
                                 "total_items": playlist_data['total_items' + playlist_data_key]
                                                },
                             }
            for j in range(0, playlist_data['total_items' + playlist_data_key]):
                sequence_dict = {
                    "type": "sequence",
                    "enabled": 1,
                    "playOnce": 0,
                    "sequenceName": playlist_data['sequenceName' + str(j) + playlist_data_key]
                }

                playlist_dict["mainPlaylist"].append(sequence_dict.copy())
            r = requests.post(self.hostname + '/api/playlist/' + playlist_dict["name"], json=playlist_dict)
            print(r.status_code)
        return True


def check_for_message(xbee_message):
    return xbee_message.data.decode()


@click.command()
@click.option('--fppmode', '-f', type=click.Choice(['master', 'slave']), required=True,
              help='FPP Mode master or slave?')
def main(fppmode):
    try:
        fpp = FppSettings(fppmode)
        if fpp.fpp_mode == 'slave':
            fpp.states['transmitting'] = True
            fpp.update_playlist()
        print('Waiting for data....')
        while True:
            fpp.change_state()
            xbee_message = fpp.local_xbee.read_data()
            fpp.states['loading'] = False
            fpp.states['error'] = False
            fpp.states['receiving'] = False
            fpp.states['transmitting'] = False
            if xbee_message:
                fpp.states['receiving'] = True
                new_message = xbee_message.data.decode()
                sender_address = xbee_message.remote_device.get_64bit_addr()
                fpp.get_command(new_message, sender_address)
                if new_message == 'quit':
                    print('Exiting.....')
                    break
    finally:
        if fpp.local_xbee is not None and fpp.local_xbee.is_open():
            fpp.local_xbee.close()


main()
