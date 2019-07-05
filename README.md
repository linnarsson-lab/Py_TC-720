# Py_TC-720
Python library for the control of the [TC-720 temperature controller](https://tetech.com/product/tc-720/).  
The TC-720 is a peltier based temperature control device made by [TE Technology Inc.](https://tetech.com/) which can control the temperature with high presision and speed. The company provides a graphic user interface to control and monitor the TC-720. This package was written to make it possible to incorporate the TC-720 in projects that require automatic control of the TC-720.
  
The TC-720 has a large range of functions and settings. Most have been included in this code but not all, as they were too advanced or not relevant for our use. However, with this code and [Appendix B of the operating manual](https://tetech.com/product/tc-720/) (see under Manuals) it should be possible to easily write the desired functions (please contribute). 

# Getting started
* Install the dependencies: `pip install pyserial`
* Download or clone the code.
* Import the library: `import Py_TC720`
* Find the device address: `Py_TC720.find_address()`  
  This will give you the port address of the device.  
  On windows the address looks like: 'COMX' and on unix it looks like 'dev/ttyUSBX', where X is the address number.  
  It will also give you the device's serial number, which you can use to find the port of this machine in the future, by using: `Py_TC720.find_address(identifier='<device-serial-number>')`.  
* Use the address to instantiate the controller:  
  `my_device = Py_TC720.TC720(address)`  
* You are now ready to use the TC-720.
* For example: Use the `my_device.set_temp()` function to set the controller to a desired temperature. 

# Operation modes:
There are 3 operational modes which you can find below. Set them using the `my_device.set_mode()` function and give 0, 1 or 2 as input.

## Mode: 0, One value
Set the controller to maintain one value. There are 3 options for values that can be set by using the `my_device.set_control_type()` function. Control type: 0, for controlling a single temperature. Control type: 1, for controlling a specific output level. And, Control type: 2, for use with an external power source (Not yet supported).  
  
The easiest option is to set one temperature:
- set the mode to 0: `my_device.set_mode(0)`
- set the control type to 0: `my_device.set_control_type(0)` this type controls the temperature.
- set the desired temperature, for instance 37C: `my_device.set_temp(37)`
  
The device will default to this mode and set the temperature to 20C when initiated.
To set the device to idle use the `my_device.set_idle()` function. This will set the controller into mode 0, control type 1 to control the output, and then set the output to zero. To resume operation you might need to change the mode and control type to the desired settings.

## Mode: 1, Programming a temperature cycle
This is used for setting a specific temperature cycle.  
The controller has 8 'locations' that can hold information for a temperature cycle. You can program these using the `my_device.set_single_sequence()` function. For each location you need to specify the desired temperature (soak temp), the time it should take to reach the desired temperature (ramp time), the time it should hold that temperature (soak time), the number of times this location should be performed (repeats) and the next step/location that should be performed if the current location is fully excecuted (repeat location). These 8 steps are the same as the 8 slots in the graphical interface that is provided by TE Technology Inc.  
You can start the execution of the locations by calling `my_device.start_control()`. The controller will start with executing location 1, and then move to the next location as indicated by the repeat location value.  
To stop the operation use: `my_device.idle_soak()`.  
You can get the settings of each location by using: `my_device.get_sequence(location='all')`.

## Mode: 2, Proportional + Dead bead mode
Not yet supported

# Programming your own functions
Using the manual more functions can be implemented. 
The device has a number of locations which store information. To these location you can either write new information or read it.  

To read information use:  
- Request the information: `my_device.send_message( my_device.message_builder(<location>), write=True )`
- Read the information: `my_device.read_message()`

To set new information use:
- Write a number to a location: `my_device.send_message( <location>, my_device.int_to_hex(<number>), write=True )`
