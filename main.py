#!/usr/bin/env python3
import ast
import json
import socket
import subprocess
import time
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


class FppSettings:
    def __init__(self, fpp_mode, status=None, xbee_com='/dev/ttyAMA0', xbee_baud=9600):
        self.fpp_mode = fpp_mode
        self.status = status
        while self.status is None:
            print('Waiting for FPPD to start...')
            time.sleep(1)
            self.status = self.get_fppd_status()
            self.local_xbee = DigiMeshDevice(xbee_com, xbee_baud)
        while True:
            try:
                self.local_xbee.open()
                break
            except XBeeException:
                print('Check the device is connected!')
            except InvalidOperatingModeException:
                print('Something went wrong lets try again.')
                self.local_xbee.close()
        self.xbee_network = self.local_xbee.get_network()
        self.network_devices = self.get_devices()
        if self.fpp_mode == 'slave':
            self.playlist_updated = False

    hostname = "http://" + socket.gethostname()
    playlists = requests.get(hostname + '/api/playlists').json()
    number_of_playlist = {'number_of_playlist': len(playlists)}

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
        for value in playlist_json['mainPlaylist']:
            values_to_send.append({'sequenceName': value['sequenceName']})
        return values_to_send

    def send_playlists(self, address):
        if self.fpp_mode == 'slave':
            return
        number_of_playlist_sent = 0
        for item in self.playlists:
            values_to_send = self.define_playlist_values(self.get_playlist(item))
            if number_of_playlist_sent == 0:
                self.send_message_to(str(self.number_of_playlist), address)
            for value in values_to_send:
                if type(value) == int:
                    self.send_message_to(str(value), address)
                elif type(value) == dict:
                    key = list(value)[0]
                    value[key + '_' + str(number_of_playlist_sent)] = value.pop(key)
                    print(value)
                    self.send_message_to(str(value), address)
                else:
                    self.send_message_to(value, address)
            number_of_playlist_sent += 1
        self.send_message_to('{"end_transmit": 1}', address)

    def send_message_all(self, message):
        for device in self.network_devices:
            self.local_xbee.send_data_async_64(device.get_64bit_addr(), message)

    def send_message_to(self, message, address):
        self.local_xbee.send_data_async_64(address, message)

    def post_playlist(self):
        # {
        #     "name": "UploadTest",
        #     "mainPlaylist": [
        #         {
        #             "type": "pause",
        #             "enabled": 1,
        #             "playOnce": 0,
        #             "duration": 8
        #         }
        #     ],
        #     "playlistInfo": {
        #         "total_duration": 8,
        #         "total_items": 1
        #     }
        # }

    def update_playlist(self):
        init_time = time.time()
        timeout = 15
        xbee_messages = []
        if not self.playlist_updated:
            self.send_message_all('send_playlists')
            while not self.playlist_updated:
                xbee_message = self.local_xbee.read_data()
                if xbee_message:
                    xbee_message = xbee_message.data.decode()
                    xbee_messages.append(ast.literal_eval(xbee_message))
                    if any('end_transmit' in key for key in xbee_messages):
                        xbee_messages = dict(ChainMap(*xbee_messages))
                        for i in range(0, xbee_messages['number_of_playlist']):
                            print(xbee_messages['number_of_playlist'])


playlist_dict = {"name": "play",
                 "mainPlaylist": [
                     {
                         "type": "sequence",
                         "enabled": 1,
                         "playOnce": 0,
                         "sequenceName": "2.25.19notes2f-G1f--.fseq"
                     },
                 ],
                 "playlistInfo": {
                     "total_duration": 90,
                     "total_items": 3
                 }
                 }


def check_for_message(xbee_message):
    return xbee_message.data.decode()


@click.command()
@click.option('--fppmode', '-f', type=click.Choice(['master', 'slave']), required=True,
              help='FPP Mode master or slave?')
def main(fppmode):
    try:
        fpp = FppSettings(fppmode)
        if fpp.fpp_mode == 'slave':
            fpp.update_playlist()
        print(fpp.status)
        print('Waiting for data....')
        while True:
            xbee_message = fpp.local_xbee.read_data()
            if xbee_message:
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
