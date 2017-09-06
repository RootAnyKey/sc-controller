#!/usr/bin/env python2
"""
SC Controller - Dualshock 4 Driver

Extends HID driver with DS4-specific options.
"""

from scc.drivers.hiddrv import HIDController, HIDDecoder, hiddrv_test, _lib
from scc.drivers.hiddrv import BUTTON_COUNT, ButtonData, AxisType, AxisData, AxisMode, AxisDataUnion, AxisModeData, HatswitchModeData
from scc.constants import SCButtons, ControllerFlags
from scc.constants import STICK_PAD_MIN, STICK_PAD_MAX
from scc.tools import init_logging, set_logging_level
from scc.drivers.usb import register_hotplug_device
from collections import namedtuple
import sys, struct, ctypes, logging
log = logging.getLogger("DS4")

VENDOR_ID = 0x054c
PRODUCT_ID = 0x09cc


def init(daemon):
	""" Registers hotplug callback for ds4 device """
	def cb(device, handle):
		return DS4Controller(device, daemon, handle, None)
	
	register_hotplug_device(cb, VENDOR_ID, PRODUCT_ID)


class DS4Controller(HIDController):
	# Most of axes are the same
	AXIS_DATA = AxisModeData(scale = 1.0, offset = -127.5, clamp_max = 257, deadzone = 10)
	AXIS_DATA_N = AxisModeData(scale = -1.0, offset = 127.5, clamp_max = 257, deadzone = 10)
	AXIS_DATA_GYRO = AxisModeData(scale = 1.0, offset = -32768, clamp_max = 1)
	TRIGGER_DATA = AxisModeData(scale = 1.0, clamp_max = 1, deadzone = 10)
	BUTTON_MAP = (
		SCButtons.X,
		SCButtons.A,
		SCButtons.B,
		SCButtons.Y,
		SCButtons.LB,
		SCButtons.RB,
		1 << 64,
		1 << 64,
		SCButtons.BACK,
		SCButtons.START,
		SCButtons.STICKPRESS,
		SCButtons.RPAD,
		SCButtons.C,
		SCButtons.CPAD,
	)
	
	
	def __init__(self, *a, **b):
		HIDController.__init__(self, *a, **b)
		self.flags |= ControllerFlags.HAS_GYROS

	
	def _load_hid_descriptor(self, config, max_size, vid, pid, test_mode):
		# Overrided and hardcoded
		self._decoder = HIDDecoder()
		self._decoder.axes[AxisType.AXIS_LPAD_X] = AxisData(
			mode = AxisMode.HATSWITCH, byte_offset = 5, size = 8,
			data = AxisDataUnion(hatswitch = HatswitchModeData(
				button = SCButtons.LPAD | SCButtons.LPADTOUCH,
				min = STICK_PAD_MIN, max = STICK_PAD_MAX
			))
		)
		self._decoder.axes[AxisType.AXIS_STICK_X] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 1, size = 8,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA)
		)
		self._decoder.axes[AxisType.AXIS_STICK_Y] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 2, size = 8,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_N)
		)
		self._decoder.axes[AxisType.AXIS_RPAD_X] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 3, size = 8,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA)
		)
		self._decoder.axes[AxisType.AXIS_RPAD_Y] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 4, size = 8,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_N)
		)
		self._decoder.axes[AxisType.AXIS_LTRIG] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 8, size = 8,
			data = AxisDataUnion(axis = DS4Controller.TRIGGER_DATA)
		)
		self._decoder.axes[AxisType.AXIS_RTRIG] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 9, size = 8,
			data = AxisDataUnion(axis = DS4Controller.TRIGGER_DATA)
		)
		self._decoder.axes[AxisType.AXIS_GPITCH] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 13, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.axes[AxisType.AXIS_GROLL] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 15, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.axes[AxisType.AXIS_GYAW] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 17, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.axes[AxisType.AXIS_Q1] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 19, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.axes[AxisType.AXIS_Q2] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 21, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.axes[AxisType.AXIS_Q3] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 23, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.axes[AxisType.AXIS_Q4] = AxisData(
			mode = AxisMode.AXIS, byte_offset = 24, size = 16,
			data = AxisDataUnion(axis = DS4Controller.AXIS_DATA_GYRO)
		)
		self._decoder.buttons = ButtonData(
			enabled = True, byte_offset=5, bit_offset=4, size=14,
			button_count = 14
		)
		
		if test_mode:
			for x in xrange(BUTTON_COUNT):
				self._decoder.buttons.button_map[x] = x
		else:
			for x in xrange(BUTTON_COUNT):
				self._decoder.buttons.button_map[x] = 64
			for x, sc in enumerate(DS4Controller.BUTTON_MAP):
				self._decoder.buttons.button_map[x] = self.button_to_bit(sc)
		
		self._packet_size = 64
	
	
	def test_input(self, endpoint, data):
		# print " ".join([ "%3s" % ord(x) for x in data[9:] ])
		_lib.decode(ctypes.byref(self._decoder), data)
		print self._decoder.state.q4
	
	
	def _generate_id(self):
		"""
		ID is generated as 'ds4' or 'ds4:X' where 'X' starts as 1 and increases
		as controllers with same ids are connected.
		"""
		magic_number = 1
		id = "ds4"
		while id in self.daemon.get_active_ids():
			id = "ds4:%s" % (magic_number, )
			magic_number += 1
		return id

if __name__ == "__main__":
	""" Called when executed as script """
	init_logging()
	set_logging_level(True, True)
	sys.exit(hiddrv_test(DS4Controller, [ "054c:09cc" ]))
