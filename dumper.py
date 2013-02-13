#!/usr/bin/python
#Parts of this are based off of https://gist.github.com/4678643

import subprocess
import sys
import os
import json
from pprint import pprint

#Get symbols
functions = subprocess.check_output(['./arm-eabi-nm', '-DCnS', sys.argv[1]]).splitlines()
#Get the start and end address from nm to only dump one function
def get_functions(function):
    function_list = []
    for functions_line in functions:
        if function in functions_line:
            functions_line_split = functions_line.split(' ')
            stop_address = hex(int(functions_line_split[0], 16)  + int(functions_line_split[1], 16))
            function_dump =  subprocess.check_output(['./arm-eabi-objdump',
                '-CD',
                '--start-address=0x' + functions_line_split[0],
                '--stop-address=' + stop_address,
                sys.argv[1]]).splitlines()[6:]
            function_list.append(function_dump)
    return function_list

def filter_instructions(function, filters):
    filtered = []
    filtered.append(function[0])
    function = function[1:]
    for function_line in function:
        if not function_line.strip():
            continue
        function_line_split = function_line.split('\t')
        instruction = function_line_split[2]
        if instruction in filters:
            filtered.append(function_line)
    return filtered

output = {}
output['classes'] = {
            "biome.superclass": "NA",
            "block.superclass": "NA",
            "entity.list": "EntityFactory::CreateEntity",
            "item.superclass": "NA",
            "nethandler.client": "NA",
            "nethandler.server": "NA",
            "packet.superclass": "MinecraftPackets::createPacket",
            "recipe.superclass": "NA"
        }
#if "MobFactory::CreateMob" in functions_line:
##Packets

#Get packet side
side = {}
for function in functions:
    if "ServerSideNetworkHandler::handle" in function:
        packet_side_name = function.split(' ')[5][:-2]
        try:
            side[packet_side_name]['server'] = True
        except KeyError:
            side[packet_side_name] = {}
            side[packet_side_name]['server'] = True

    elif "ClientSideNetworkHandler::handle" in function:
        packet_side_name = function.split(' ')[5][:-2]
        try:
            side[packet_side_name]['client'] = True
        except KeyError:
            side[packet_side_name] = {}
            side[packet_side_name]['client'] = True

packet_functions = get_functions("Packet::write")
output['packets'] = {}
output['packets']['packet'] = {}
for packet_function in packet_functions:
    packet_id = None
    packet_name = packet_function[0].split(' ', 1)[1]
    packet_function = packet_function[1:]

    for function_line in packet_function:
        if not function_line.strip():
            continue
        function_line_split = function_line.split('\t')
        instruction = function_line_split[2]
        if instruction == 'movs' and packet_id == None:
            packet_id_int = int(function_line.split('#')[1])
            output['packets']['packet'][packet_id_int] = {}
            packet = output['packets']['packet'][packet_id_int]
            packet['class'] = packet_name.split('::')[0][1:]
            packet['from_client'] = False
            packet['from_server'] = False

            try:
                packet['from_client'] = side[packet['class']]['client']
            except KeyError:
                pass
            try:
                packet['from_server'] = side[packet['class']]['server']
            except KeyError:
                pass
            packet['id'] = packet_id_int
            packet['size'] = 0
            packet['instructions'] = []

        elif instruction == "bl" and not "<operator new(unsigned int)>" in function_line:
            packet_call = function_line_split[3].split(' ', 1)[1]
            packet_field = packet_call.split('(')[0].split('::')[-1]

            #More need to be implemented
            if packet_field == "Write<short>":
                packet_field_type = "short"
            elif packet_field == "Write<int>":
                packet_field_type = "int"
            elif packet_field == "Write<float>":
                packet_field_type = "float"
            elif packet_field == "Write<long>":
                packet_field_type = "long"
            elif packet_field == "Write<char>" or packet_field == "Write<signed char>":
                packet_field_type = "byte"
            else:
                packet_field_type = None
            if packet_field_type:
                packet['instructions'].append({
                    "field": "",
                    "operation": "write",
                    "type": packet_field_type
                })


output['packets']['info'] = {}
output['packets']['info']['count'] = len(output['packets']['packet'])

##Entitys

output['entities'] = {}
output['entities']['entity'] = {}

entity_function = get_functions("EntityFactory::CreateEntity")[0]
entity_function = filter_instructions(entity_function, ['bl'])[1:]
for function_line in entity_function:
    function_line_split = function_line.split('\t')
    if not "operator" in function_line and not "Throwable" in function_line:
        entity_call = function_line_split[3].split(' ', 1)[1][1:-1]
        #Entity Name
        entity_name = entity_call.split('::')[0]
        #Entity ID
        id_function = get_functions(entity_name + "::getEntityTypeId")[0]
        id_function = filter_instructions(id_function, ['movs'])[1:]
        for id_function_line in id_function:
            entity_id_int = int(id_function_line.split('#')[1])
            break
        output['entities']['entity'][entity_id_int] = {}
        entity = output['entities']['entity'][entity_id_int]
        #Entity Name
        entity['name'] = entity_name
        entity['class'] = entity_call
        entity['id'] = entity_id_int
        #Entity type
        type_function = get_functions(entity_call)[0]
        type_function = filter_instructions(type_function, ['bl'])[1:]
        for type_function_line in type_function:
            type_function_split = type_function_line.split('\t')[-1].split(' ')[-1][1:-1]

output['source'] = {
            "classes": len(functions),
            "file": os.path.basename(sys.argv[1]),
            #Other is number of files
            "other": 1,
            "size": os.path.getsize(sys.argv[1])
        }
print json.dumps([output], sort_keys=True, indent=4)
