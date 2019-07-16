################################################################################
#Python 3 package to control the TC-720 temperature controller from:
#TE Technology Inc. (https://tetech.com/)

#Date: 7 September 2018
#Author: Lars E. Borm
#E-mail: lars.borm@ki.se or larsborm@hotmail.com
#Python version: 3.5.4

#Based on TC-720 operating Manual; Appendix B - USB Communication
#https://tetech.com/product/tc-720/

#NOTE!
#Not all possible functions of the TC-720 are implemented in this code.
#Hopefully this code in combination with the manual provides enough support to
#implement the other functions. If you do please update the project to improve.

################################################################################

#Basic Operation:

#First, find the address of the temperature controller by using the:
#"find_address()" function. 

#Then initialize the connection with the controller:
#import Py_TC720
#my_device = Py_TC720.TC720(address, name='hotstuff', verbose=True)

#The temperature controller had different modes of operation which are set
#by changing the mode using the set_mode() function:
# 0: Normal Set Mode; This mode is used to hold one temperature (0), one output 
#   power(1) or an analogue output by another power source (2). Set one of
#   these 3 control types using the set_control_type() function.
# 1: Ramp/Soak Mode: This mode is used to program a specific temperature and
#   and time sequence.
# 2: Proportional+Dead Band mode; (limited to no support yet)

# The machine will default to the Normal set mode that hold one specific
# temperature. Default is 20C. The temperature can be set using: set_temp(X)

#If you want a more custom temperature cycle:
#Set the machine in Ramp/Soak mode using: set_mode(1)
#To program the temperature schedule:
#The controller has 8 'locations' that can hold information for a temperature
#cycle. For each location you need to specify the desired temperature, the 
#time it should hold that temperature (soak time), the time it should take to
#reach the desired temperature (ramp time), the number of times this location
#should be performed (repeats) and the next step/location that should be
#performed if the current location is fully executed (repeat location).
#These 8 steps are the same as the 8 slots in the graphical interface that is
#provided by TE Technologies INC.
#You can start the execution of the 8 location by calling "start_control()",
#and stop it by calling "set_idle()".
################################################################################

#_______________________________________________________________________________
#   IMPORTS
import serial
from serial.tools import list_ports
import time
import numpy as np
from collections import deque
import warnings

#_______________________________________________________________________________
#   FIND SERIAL PORT
def find_address(identifier = None):
    """
    Find the address of a serial device. It can either find the address using
    an identifier given by the user or by manually unplugging and plugging in 
    the device.
    Input:
    `identifier`(str): Any attribute of the connection. Usually USB to Serial
        converters use an FTDI chip. These chips store a number of attributes
        like: name, serial number or manufacturer. This can be used to 
        identify a serial connection as long as it is unique. See the pyserial
        list_ports.grep() function for more details.
    Returns:
    The function prints the address and serial number of the FTDI chip.
    `port`(obj): Returns a pyserial port object. port.device stores the 
        address.
    
    """
    found = False
    if identifier != None:
        port = [i for i in list(list_ports.grep(identifier))]
        
        if len(port) == 1:
            print('Device address: {}'.format(port[0].device))
            found = True
        elif len(port) == 0:
            print('''No devices found using identifier: {}
            \nContinue with manually finding USB address...\n'''.format(identifier))
        else:
            for p in connections:
                print('{:15}| {:15} |{:15} |{:15} |{:15}'.format('Device', 'Name', 'Serial number', 'Manufacturer', 'Description') )
                print('{:15}| {:15} |{:15} |{:15} |{:15}\n'.format(str(p.device), str(p.name), str(p.serial_number), str(p.manufacturer), str(p.description)))
            raise Exception("""The input returned multiple devices, see above.""")

    if found == False:
        print('Performing manual USB address search.')
        while True:
            input('    Unplug the USB. Press Enter if unplugged...')
            before = list_ports.comports()
            input('    Plug in the USB. Press Enter if USB has been plugged in...')
            after = list_ports.comports()
            port = [i for i in after if i not in before]
            if port != []:
                break
            print('    No port found. Try again.\n')
        print('Device address: {}'.format(port[0].device))
        try:
            print('Device serial_number: {}'.format(port[0].serial_number))
        except Exception:
            print('Could not find serial number of device.')
    
    return port[0]
    
#==============================================================================
#   TC-720 class
#==============================================================================

class TC720():
    """
    Class to control the TC-720 temperature controller from TE Technology Inc. 
    
    """
    def __init__(self, address, name = 'TC-720', mode = 0, control_type = 0,
                 default_temp = 20, verbose = False):
        """
        Input:
        `address`(str): The address of TC-720. Use the "find_address()" function
            to find the address. It should have the format of 'ComX' on Windows
            and 'dev/ttyUSBX' in linux, where X is the address number.
        `name`(str): Custom name of the TC-720. Useful if there are multiple
            units connected. Default = TC-720.
        `mode`(int 0-2): The mode of operation:
            0: Normal Set Mode; maintain one value. This can be one temperature
            one output power or output by an external power source. See 
            control_type for options.
            1: Ramp/Soak Mode: This mode is used to program a specific 
            temperature and time sequence.
            2: Proportional+Dead Band mode; (limited to no support yet)
            Default = 0 (set one value)
        `control_type`(int 0-2): If mode is 0 the controller can maintain
            one temperature (0), one output power(1) or an analogue 
            output by another power source (2).
            Default = 0 (set one temperature
        `default_temp`(int): Default temperature in degree centigrade.
            Default = 20C
        `verbose`(bool): Option to print status messages.

        """
        self.address = address
        self.name = name
        self.mode = mode
        self.control_type = control_type
        self.default_temp = default_temp
        self.verbose = verbose
        self.verboseprint = print if self.verbose else lambda *a, **k: None

        #make connection with controller
        self.ser = serial.Serial(self.address, timeout= 2, baudrate=230400, stopbits=serial.STOPBITS_ONE, parity=serial.PARITY_NONE)
        self.verboseprint('Made connection with temperature controller: {}'.format(self.name))

        #Set the machine into temperature control
        self.set_temp(self.default_temp)
        self.set_mode(self.mode)
        self.set_control_type(self.control_type)
        self.verboseprint('Mode set to: {}, control type set to: {}, temperature set to: {}C'.format(self.mode, self.control_type, self.default_temp))

    #==========================================================================
    #    Functions for sending and reading messages
    #==========================================================================

    def int_to_hex(self, integer):
        """
        Formats integers to hexadecimal encoded string, to use in the 
        self.message_builder function. Max is 32768.
        Handles negative numbers
        
        """
        if abs(integer) > 32768:
            raise ValueError('Can not encode positive or negative integers larger than  32768 in length 4 hexadecimal number.')

        #Negative numbers
        if integer < 0:
            integer = int((0.5 * 2**16) - integer)
        
        return '{h:0>4}'.format(h = hex(integer)[2:])

    def response_to_int(self, response):
        """
        Returns the integer representation of the response of the 4 data bits.
        Handles negative numbers.
        
        """
        response = int(response[1:5], base=16)
        #Check if it is a negative number, if yes, invert it to the correct value.
        if response > 0.5 * (2**16): 
            response = -(2**16 - response)
        return response

    def make_checksum(self, message):
        """
        Make the 2 bit checksum for messages. It calculates the 8 bit, modulo 
        256 checksum in the format of 2 ASCII hex characters.
        Returns the checksum as a string.
        
        """
        if type(message) == list:
            message = ''.join(message)
            
        if type(message) == bytes:
            message = message.decode()
            
        checksum = hex(sum(message[1:7].encode('ascii')) % 256)[-2:]
        return checksum

    def check_checksum(self, response):
        """
        Checks if the checksum of the response is correct.
        Input:
        `response`(bytes): Response of the temperature control unit. 8 bits.
        Returns True or False
        
        """
        response = response.decode()
        #Get checksum send by the controller
        response_checksum = response[5:7]
        #Calculate the checksum of the received response.
        calculated_checksum = hex(sum(response[1:5].encode('ascii')) % 256)#[-2:]
        if len(calculated_checksum) == 3:
            calculated_checksum = '{c:0>2}'.format(c = calculated_checksum[-1])
        else:
            calculated_checksum = calculated_checksum[-2:]
                
        if response_checksum == calculated_checksum:
            return True
        else:
            return False

    def message_builder(self, command, value='0000'):
        """
        Constructs the message in the right format.
        Input:
        `command`(str): Command character with length 2, encoded in hexadecimal
            ASCII characters.
        `value`(str): Value characters with length 4, encoded in hexadecimal
            ASCII characters.
        Returns message as list of 10 individual bits.     
        
        Structure of message: (stx)CCDDDDSS(etx)
            (stx): Start text character = '*'
            CC: Command, 2 bits
            DDDD: Value, 4 bits
            SS: Checksum, 2 bits
            (etx): End of text character = '\r'    
        
        """
        message = ['*', '0', '0', '0', '0', '0', '0', '0', '0', '\r']
        
        #Command
        if type(command) != str:
            try:
                command = str(command)
            except Exception:
                raise ValueError('Invalid command input: "{}", Type:"{}". Input should be a string of length 2'.format(command, type(command)))
        if len(command) != 2:
            raise ValueError('Invalid command input: "{}", Type:"{}". Input should be a string of length 2'.format(command, type(command)))
        
        message[1:2] = command[0], command[1]
        
        #Make string message
        if type(value) != str:
            try:
                value = str(value)
            except Exception:
                raise ValueError('Invalid message input: "{}", Type:"{}". Input should be a string of length 4'.format(value, type(value)))
        if len(value) != 4:
            raise ValueError('Invalid message input: "{}", Type:"{}". Input should be a string of length 4'.format(value, type(value)))
        
        message[3:8] = value[0], value[1], value[2], value[3]
        
        #Checksum
        checksum = self.make_checksum(message)
        message[7:9] = checksum[0], checksum[1]
        
        return message

    def send_message(self, message, write=False):
        """
        Send message to the temperature control unit. Use the 
        self.message_builder()function to construct the message in the right 
        format.
        Input:
        `message`(list): Message with 10 bits as individual ASCII stings.
            Structure of message: (stx)CCDDDDSS(etx)
                (stx): Start text character = '*'
                CC: Command, 2 bits
                DDDD: Value, 4 bits
                SS: Checksum, 2 bits
                (etx): End of text character = '\r'
            Format: ['*', 'C', 'C', 'D', 'D', 'D', 'D', 'S', 'S', '\r']
        `write`(bool): Small trick to make sure a certain message is dealt with
            as a write command (opposed to a read command). The problem is that 
            if a zero is written to the controller the program thinks it is a
            read command because read commands sent the value '0000'.
        
        """
        #Make sure the reply buffer is empty
        self.ser.read_all()
        
        #There are 2 types of messages, read commands and write commands.
        #The read command is responded with the requested value.
        #The write command is responded with a repeat of the value to write.
        #These 2 messages are handled differently. For the read commands the 
        #command is just send and the "self.read_message()" function deals with
        #error handling. For write commands, this function checks if the 
        #message is properly received. 
        
        #Send read commands
        if ''.join(message[3:7]) == '0000' and write == False:
            for i in message:
                    self.ser.write(str.encode(i))
                    time.sleep(0.005)
             
        #Send write commands
        else:
            #Send the message
            for n in range(5):
                for i in message:
                    self.ser.write(str.encode(i))
                    time.sleep(0.005)

                #The controller acknowledges the send command by repeating the value.
                response = self.read_message(detect_error=False)
                if response[1:5].decode() == ''.join(message[3:7]):
                    break
                #Check if there is an error in the checksum.
                if response == b'*XXXX60^':
                    checksum_error = 'Checksum error'
                    print('    {} Error: Checksum error.'.format(self.name))
                #Unknown error
                else:
                    checksum_error = ''
                    self.verboseprint('    {} Error: Temperature controller did not correctly receive the command.'.format(self.name))
                time.sleep(0.05)
            else:
                raise Exception('Could not correctly send "{}" to temperature controller: {}. {}'.format(''.join(message[:-1]), self.name, checksum_error))
    
    def read_message(self, timeout=1, detect_error=True):
        """
        Read a message sent by the temperature control unit. 
        
        Input
        `timeout`(int): Time in seconds in which the program will check if 
            there are messages send by the controller. If it times out it will 
            throw a warning and return an empty byte-string (b''), which will 
            probably cause an error in the rest of the code. Default = 1 second.
        `detect_error`(bool): If True, it will check if the controller reports 
            an error in the checksum of the send messages. And it will check if
            the response by the controller has an error in the checksum. It 
            will raise an error if a checksum mistake as been made. 
            Default = True.
        Returns: 
        The response by the controller as byte-string.     
        
        """
        try:
            start_time = time.time()
            while True:
                #Check if there is a response waiting to be read.
                if self.ser.in_waiting >= 8:
                    response =  self.ser.read_all()
                    
                    if detect_error == True:
                        #Check if there is an error in the checksum of the send message.
                        if response == b'*XXXX60^':
                            raise Exception ('{} Error: Checksum error in the send message.'.format(self.name))
                        #Check if there is an error in the checksum of the received message.
                        if self.check_checksum(response) == False:
                            raise Exception ('{} Error: Checksum error in the received message.'.format(self.name))
                        
                    return response
                
                #Timeout check
                elif (time.time() - start_time) > timeout:
                    warnings.warn('Did not receive a response from temperature control unit "{}" within timout period.'.format(self.name))
                    return self.ser.read_all()
                    break
                
                else:
                    time.sleep(0.05)
        
        except Exception as e:
            print('{} Error: {}'.format(self.name, e))
            raise Exception ('Connection error with temperature control unit: {}. Error: {}'.format(self.name, e))

    #==========================================================================
    #    Read functions
    #==========================================================================

    def get_temp(self):
        """
        Read the current temperature on sensor 1.
        Returns temperature in degree Celsius with 2 decimals.
        
        """
        self.send_message(self.message_builder('01'))
        return self.response_to_int(self.read_message()) / 100

    def get_temp2(self):
        """
        Read the current temperature on sensor 2.
        Returns temperature in degree Celsius with 2 decimals.
        
        """
        self.send_message(self.message_builder('04'))
        return self.response_to_int(self.read_message()) / 100

    def get_mode(self):
        """
        Get the mode of the temperature control unit. 
        Returns mode:
            0 = Normal set
            1 = Ramp/Soak set mode
            2 = Proportional+Dead Band
        
        """
        #Ask for mode
        self.send_message(self.message_builder('71'))
        return self.response_to_int(self.read_message())

    def get_control_type(self):
        """
        Get the control mode of the temperature control unit.
        Relevant only if the mode is set to 0 (Normal set)
        Return control type:
            0 = PID, set a single fixed temperature.
            1 = Manual, set a fixed output power level.
            2 = Analog Out, Use with external variable voltage
            supply.

        """
        self.send_message(self.message_builder('73'))
        return self.response_to_int(self.read_message())

    def get_set_temp(self):
        """
        Get the current set temperature for the Normal set mode.
        Returns set temperature in degree Celsius

        """
        self.send_message(self.message_builder('50'))
        return self.response_to_int(self.read_message()) / 100

    def get_output(self):
        """
        Get the current output level.
        Returns the current output in the range -511 to 511
        for -100% and 100% output power.

        """
        self.send_message(self.message_builder('02'))
        return self.response_to_int(self.read_message())


    def get_set_output(self):
        """
        Get the set manual output.
        Returns the set output in the range -511 to 511
        for -100% and 100% output power.

        """
        self.send_message(self.message_builder('74'))
        return self.response_to_int(self.read_message())

    def get_ramp_soak_status(self):
        """
        Returns if the temperature control unit is running a temperature
        sequence. If it is running a sequence it returns the Ramp/Soak status.
        Returns:
        "No sequence running" or a list of currently running operations.   
        
        """
        #Ask for status
        self.send_message(self.message_builder('09'))
        response = self.read_message()
        
        #Convert to binary code where each bit marks an running operation.
        response_bit = bin(int(response[1:5], base=16))  
        status_response = '{0:03}'.format(int(response_bit[2:]))
        
        if status_response == '000':
            return 'No sequence running'
        else:
            status_list = ['Sequence Running', 'Soak stage', 'Ramp stage']
            return [status_list[n] for n,i in enumerate(status_response) if i == '1']
            
    def get_soak_temp(self, location):
        """
        Get the soak temperature (holding temperature) of the specified
        location.
        Input:
        `location`(int): locations 1-8
        Returns the set temperature in degree Centigrade
        
        """
        #Check input
        self.validate_data(location)
        
        #Get soak temperature
        location_code = 'a' + hex(location + 7)[-1]
        self.send_message(self.message_builder(location_code))
        return self.response_to_int(self.read_message()) / 100

    def get_ramp_time(self, location):
        """
        Get the ramp time of the specified location.
        Input:
        `location`(int): locations 1-8.
        Returns the ramp time in seconds. 
        
        """
        #Check input
        self.validate_data(location)
        
        #Get ramp time
        location_code = 'b' + hex(location + 7)[-1]
        self.send_message(self.message_builder(location_code))
        return self.response_to_int(self.read_message())

    def get_soak_time(self, location):
        """
        Get the soak time (holding time) of the specified location.
        Input:
        `location`(int): locations 1-8
        Returns the soak time in seconds.
        
        """
        #Check input
        self.validate_data(location)
        
        #Get soak time
        location_code = 'c' + hex(location + 7)[-1]
        self.send_message(self.message_builder(location_code))
        return self.response_to_int(self.read_message())

    def get_repeats(self, location):
        """
        Get the number of repeats that is assigned to the specified location.
        Input:
        `location`(int): locations 1-8
        Returns the number of repeats assigned to the location.
        
        """
        #Check input
        self.validate_data(location)
        
        #Get number of repeats
        location_code = 'd' + hex(location + 7)[-1]
        self.send_message(self.message_builder(location_code))
        return self.response_to_int(self.read_message())

    def get_repeat_location(self, location):
        """
        Get the next location to execute. There are 8 locations where
        temperature settings can be stored. When one is done it will execute 
        the next one. This function fetches the next location that will be 
        performed after the one in the specified location is done.
        Input:
        `location`(int): locations 1-8
        Returns the next location in the sequence. 
        
        """
        #Check input
        self.validate_data(location)
        
        #Get number of repeats
        location_code = 'e' + hex(location + 7)[-1]
        self.send_message(self.message_builder(location_code))
        return self.response_to_int(self.read_message())

    def validate_data(self, input):
        """
        Check if the input for a location is valid.

        """
        if type(input) != int or not 1 <= input <= 8:
            raise ValueError('Invalid location: "{}", type: "{}. Must be an integer in the range 1-8.'.format(input, type(input)))


    def check_mode(self, desired_mode):
        """
        Check if the machine is in the desired mode.
        Used to check if machine is in the corresponding mode to execute a 
        function.
        Input:
        `desired_mode`(int): Desired mode 0, 1 or 2.
        Returns True or False and gives a warning if False

        """
        if desired_mode not in [0, 1, 2]:
            raise ValueError('Invalid input: {}, should be integer 0, 1 or 2'.format(repr(desired_mode)))

        cur_mode = self.get_mode()
        if not  cur_mode == desired_mode:
            warnings.warn('TC720: {} is not set in the right mode to use this function. Current mode: {}, set the machine in the {} mode using set_mode({})'.format(self.name, cur_mode, desired_mode, desired_mode))
            return False
        else:
            return True
    #==========================================================================
    #    Set functions for the operation modes
    #==========================================================================

    def set_mode(self, mode):
        """
        Set the mode of the temperature control unit.
        Input:
        `mode`(int): Mode to set. 
            0 = Normal set. Set a single temperature, a single output power 
                level or Analog out with an external power source.
                Set one of these 3 with the set_control() function
            1 = Ramp/Soak. Use the 8 ramp/soak sequences to program a 
                temperature cycle.
            2 = Proportional+Dead Band
        
        """
        #Check input
        if mode not in [0, 1, 2]:
            raise ValueError('Invalid input: {}, should be integer 0, 1 or 2'.format(repr(mode)))
        
        #Set the mode
        self.send_message(self.message_builder('3d',  self.int_to_hex(mode)), write=True)
        self.verboseprint('Mode set to: {}'.format(mode))


    def set_control_type(self, control_type):
        """
        Set the control mode of the temperature control unit.
        Relevant only if the mode is set to 0 (Normal set)
        Input:
        `control_type`:
            0 = PID, set a single fixed temperature.
            1 = Manual, set a fixed output power level.
            2 = Analog Out, Use with external variable voltage
            supply.

        """
        #Check input
        if control_type not in [0, 1, 2]:
            raise ValueError('Invalid input: {}, should be integer 0, 1 or 2'.format(repr(control_type)))

        #Check mode
        self.check_mode(0)

        #Set the control type
        self.send_message(self.message_builder('3f',  self.int_to_hex(control_type)), write=True)
        self.verboseprint('Control type set to: {}'.format(control_type))

    #---------------------------------------------------------------------------
    #    Set functions for Normal set mode
    #    These functions are used to set and hold a single temperature
    #    or output level.
    #---------------------------------------------------------------------------

    def set_temp(self, temperature):
        """
        Set the temperature and hold that temperature.
        Input:
        `temperature`(int): Temperature in degree Celsius

        Only works in the Normal set mode: set_mode(0) and
        control type PID: set_control(0)
        """
        #Check mode
        self.check_mode(0)
        
        #Set the temperature
        temperature = int(temperature * 100)
        self.send_message(self.message_builder('1c',  self.int_to_hex(temperature)), write=True)
        self.verboseprint('Temperature set to: {}C'.format(temperature/100))

    def set_output(self, output):
        """
        Set the output to a specific value.
        Input:
        `output`(int): range -511 to 511 for -100% to 100% output.

        Only works in the Normal set mode: set_mode(0) and control
        type Manual: set_control(1)
        """
        #Check mode
        self.check_mode(0)

        self.send_message(self.message_builder('40',  self.int_to_hex(output)), write=True)
        self.verboseprint('Output set to: {}'.format(output))

    #---------------------------------------------------------------------------
    #    Set functions for ramp/soak mode
    #    Functions to set the ramp/soak sequence.
    #---------------------------------------------------------------------------

    def set_soak_temp(self, location, temperature):
        """
        Set the soak temperature (holding temperature) of the specified location.
        Input:
        `location`(int): locations 1-8
        `temperature`(float, max 2 decimals): Temperature in degree centigrade.
            Positive and negative values are possible.
        
        """
        if type(location) != int or (1< location > 8):
            raise ValueError('Invalid location: "{}", type: "{}. Must be a integer in the range 1-8.'.format(location, type(location)))
        #Check mode
        self.check_mode(1)
        
        location_code = 'a' + str(location-1)
        temperature = int(temperature * 100)
        #If the temperature is negative use the "two's complement"
        if temperature < 0:
            temperature = 2**16 + temperature
        
        #Set soak temperature
        self.send_message(self.message_builder(location_code, self.int_to_hex(temperature)), write=True)

    def set_ramp_time(self, location, time):
        """
        Set the ramp time to specified time. The temperature control unit will 
        ramp to the new temperature in the given time.
        Input:
        `location`(int): locations 1-8.
        `time`(int): Number of seconds that the ramp should take. 
        
        """
        #Check input
        self.validate_data(location)
        #Check mode
        self.check_mode(1)
        
        #Set ramp time
        location_code = 'b' + str(location-1)
        self.send_message(self.message_builder(location_code, self.int_to_hex(time)), write=True)

    def set_soak_time(self, location, time):
        """
        Set the soak time, number of seconds the temperature should be kept at
        the soak temperature. 
        Input:
        `location`(int): Locations 1-8.
        `time`(int): Seconds the soak temperature should be kept.
        
        """
        #Check input
        self.validate_data(location)
        if type(time) != int or (1< time > 32768): #half 2**16
            raise ValueError('Invalid time: "{}", type: "{}. Must be a integer in the range 1-32768.'.format(location, type(location)))
        #Check mode
        self.check_mode(1)
            
        #set soak time
        location_code = 'c' + str(location-1)
        self.send_message(self.message_builder(location_code, self.int_to_hex(time)), write=True)

    def set_repeats(self, location, repeats):
        """
        Set the number of repeats to a temperature location. The program will 
        cycle over all 8 locations in sequence and counts how many times a 
        location is performed.
        Warning: There is some strange behavior if one of the locations has 
        fewer repeats than the other locations, it will be executed as many
        times as the location with the most. 
        Input:
        `location`(int): locations 1-8
        `Repeats`(int): Number of times the temperature sequence should be 
            repeated. 
        
        """
        #Check input
        self.validate_data(location)
        #Check mode
        self.check_mode(1)
        
        location_code = 'd' + str(location-1)
        self.send_message(self.message_builder(location_code, self.int_to_hex(repeats)), write=True)

    def set_repeat_location(self, location, repeat_loc):
        """
        Set which location has to be performed after the specified location is
        done.
        Input:
        `location`(int): locations 1-8
        `repeat_loc`(int): locations 1-8
        
        """
        #Check input
        self.validate_data(location)
        self.validate_data(repeat_loc)
        #Check mode
        self.check_mode(1)
        
        location_code = 'e' + str(location-1)
        self.send_message(self.message_builder(location_code, self.int_to_hex(repeat_loc)), write=True)

    #--------------------------------------------------------------------------
    #    Start stop functions
    #--------------------------------------------------------------------------

    def start_soak(self):
        """
        Start the ramp/soak temperature control and execute all sequences
        in the locations.

        """
        #Check mode
        self.check_mode(1)
        #Start soak
        self.send_message(self.message_builder('08', '0001'))

    def idle_soak(self):
        """
        Stop the ramp/soak execution.        

        """
        #Check mode
        self.check_mode(1)
        #Set to idle
        self.send_message(self.message_builder('08', '0000'))

    def set_idle(self):
        """
        Set in to output control mode with 0 output.

        """
        self.set_mode(0)
        self.set_output(0)
        self.set_control_type(1)

    #==========================================================================
    #    Combined functions
    #    These are the most useful to the user
    #==========================================================================

    def get_sequence(self, location='all'):
        """
        Get the current sequence of the temperature control unit. There are 8 
        locations where the different parameters that define the ramp and soak
        are specified. This function repeats a single row or the full table. 
        Input:
        `location`(list, int or str): Specify one location as an integer (1-8).
            Or specify multiple locations as a list of integers. Or use the 
            keyword "all" to retrieve data of all locations (takes 4-5 seconds)
        Returns:
        Array of the data. The first row contains the headers of the table:
        ['Loc', 'Temp', 'Ramp time', 'Soak time', 'Repeats', 'Repeat loc']
        'Loc': Location the data is coming from.
        'Temp': The soak temperature, which is the target temperature.
        'Ramp time': The time the ramp takes to reach the soak temperature.
        'Soak time' : The time the soak temperature should be kept.
        'Repeats': The number of times the step (location) should be repeated.
        'Repeat loc': The next step in the sequence. 
        The subsequent rows contain the data of the different locations. 
        
        """
        #Initiate the array with the headers
        seq = np.array([['Loc', 'Temp', 'Ramp time', 'Soak time', 'Repeats', 'Repeat loc']])
        
        #Make the list of locations to retrieve
        if location == 'all':
            location = [1,2,3,4,5,6,7,8]
        elif type(location) != list:
            location = [location]
         
        #Add the data to the array
        for i in location:
            seq = np.append(seq, [[i, self.get_soak_temp(i), self.get_ramp_time(i), self.get_soak_time(i), self.get_repeats(i), self.get_repeat_location(i)]], axis=0)    
        
        return seq

    def set_single_sequence(self, location, temp=20, ramp_time=60, 
                            soak_time=30000, repeats=1, go_to=None):
        """
        Set the ramp and temperature settings of one location. 
        Input:
        `location`(int): Location to alter (1-8).
        `temp`(float, max 2 decimals): Target temperature in Celsius.
        `ramp_time`(int): Time it has to take to ramp up to the target 
            temperature.
        `soak_time`(int): Time the temperature has to be kept at the target
            temperature. In seconds, max = 30000 seconds. 
            Actually it should be 32767, which is 0.5 * 2**16, but higher
            values gives checksum errors sometimes.
        `repeats`(int): Number of times the location has to be repeated. The
            program will cycle over all 8 locations in sequence and counts how 
            many times a location is performed. 
            Warning: There is some strange behavior if one of the locations 
            has fewer repeats than the other locations, it will be executed 
            as many times as the location with the most. 
        `go_to`(int, None): If specified indicates the next location to
            execute. If set to "None" it will default to the next location. 
            If the location = 8, it will go to location 1. 
        
        """
        #Check input
        self.validate_data(location)

        self.set_soak_temp(location, temp)
        self.set_ramp_time(location, ramp_time)
        self.set_soak_time(location, soak_time)
        self.set_repeats(location, repeats)
        if go_to == None:
            l = [1,2,3,4,5,6,7,8]
            next_loc = l[((location)%8)]
        elif type(go_to) != int or (1< repeat_loc > 8):
            raise ValueError('Invalid go_to: "{}", type: "{}". Must be a integer in the range 1-8.'.format(go_to, type(go_to)))
        else:
            next_loc = location + 100
        self.set_repeat_location(location, next_loc)
     
    #==========================================================================
    #   Wait until desired temperature is reached
    #==========================================================================

    def waitTemp(self, target_temp, error=1, array_size=5, sd=0.01, 
                timeout = 5, set_idle = True):
        """
        Wait until the target temperature has been reached. This can also be
        done by waiting the ramp time, but use this function if you want to be
        sure it reached the temperature.
        Input:
        `tarselfget_temp`(float): Temperature to reach in Celsius.
        `error`(float): Degree Celsius error allowed between target and real 
            temperature.
        `array_size`(int): Size of array to check if stable temperature plateau 
            is reached. Default = 5
        `sd`(float): Standard deviation, if sd of temperature array drops below 
            threshold value, the temperature has been reached and is stable.
            Default = 0.01
        `timeout`(float): Number of minutes after which the program times-out.
            It will raise and exception if the temperature could not be 
            reached withing the timeout period if "set_idle" is "True", 
            otherwise it will only raise an Warning.
        `set_idle`(bool): If True it will set the controller to idle if the 
            target temperature could not be reached within the timeout period.
            Otherwise it will be able to continue provided that there are no
            errors on the controller.
            
        """
        bufferT = deque(maxlen=array_size)
        counter = 0

        while True:
            tic = time.time()

            cur_temp = self.get_temp()
            bufferT.append(cur_temp)
            
            self.verboseprint('Current temperature: ', cur_temp, ' Standard deviation: ', np.std(bufferT))

            # Check if temp is within the error range of the target_temp
            if (target_temp-error) < cur_temp < (target_temp+error):
                self.verboseprint('Within range of target temperature {}C with error {}C'.format( target_temp, error))
                if counter > array_size:
                    #Check if slope has plateaus by checking the standard deviation
                    if np.std(bufferT) < sd:
                        self.verboseprint('Temperature stable, slope minimal')
                        break
            if counter >= (timeout*60): #Raise and exception after the timeout period
                #Make sure there are no errors on the system
                self.check_error(set_idle=set_idle, raise_exception=True)
            
                if set_idle == True:
                    self.set_idle()
                    raise Exception('Temperature could not be reached in {} minutes, check {} system.'.format(timeout, self.name))
                else:
                    warnings.warn('Temperature could not be reached in {} minutes, check {} system.'.format(timeout, self.name))
                    break


            counter +=1        
            toc = time.time()
            execute_time = toc - tic
            if execute_time > 1:
                execute_time = 0.001
            # Check every second
            time.sleep(1-execute_time)


    #==========================================================================
    #    Check errors
    #==========================================================================

    def check_error(self, set_idle = True, raise_exception = True):
        """
        Check if there are errors on the system.  
        Input:
        `set_idle`(bool): If an error is detected the function will set the
            temperature controller to idle.
        `raise_exception`(bool): If and error is detected and "raise_exception"
            is set to "True", it will raise an exception and thereby 
            terminate the running program. If set to "False" it will throw a 
            warning only and the program can continue. Do this with caution!
            Useful if another program does the error handling.
        Returns:
        If there are no errors it will return a list with True and a message.
        If there is an error detected it will raise and exception or return a
        list with False and the error message if "rais_exception" is set to
        "False". This can then be interpreted by another program.
        
        """
        #Ask for error
        self.send_message(self.message_builder('03'))
        response = self.read_message()
        response = '{b:0>6}'.format(b = bin(int(response[1:5], 16))[2:])
          
        #No errors detected
        if response == '000000':
            self.verboseprint('No errors on temperature controller: {}'.format(self.name))
            return [True, 'No errors on temperature controller: {}'.format(self.name)]
        
        #Error detected
        else:
            reset='Device NOT set to idle'
            #Try to set the controller to idle
            if set_idle == True:
                self.set_idle()
                reset = 'Device is set to idle.'
                self.verboseprint(reset)
            
            #Report the error
            error_list = ['Over Current Detected', 'Key press to store value',
                          'Low Input Voltage', 'Open Input 2', 'Open Input 1', 
                          'Low Alarm 2', 'High Alarm 2', 'Low Alarm 1', 
                          'High Alarm 1',]
            current_errors = [error_list[n] for n,i in enumerate(response) if i == '1']
            #Check if it should raise an exception or give a warning.
            if raise_exception == True:
                raise Exception('Error(s) on {}: {}. {}'.format(self.name, current_errors, reset))
            else:
                warnings.warn('Error(s) on {}: {}. {}'.format(self.name, current_errors, reset))
                return [False, 'Error(s) on {}: {}. {}'.format(self.name, current_errors, reset)]

