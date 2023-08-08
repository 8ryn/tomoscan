# Designed to be used with iocs and simulators all running in docker compose
# Useful info in https://bcda-aps.github.io/apstools/latest/examples/de_0_adsim_hdf5_basic.html

import time as ttime

import bluesky.plan_stubs as bps
import databroker
import hdf5plugin  # noqa F401
from apstools.devices import CamMixin_V34, SingleTrigger_V34, ensure_AD_plugin_primed
from bluesky import RunEngine
from bluesky.callbacks.best_effort import BestEffortCallback
from bluesky.plan_stubs import mv
from bluesky.plans import count, scan  # noqa F401
from ophyd import (
    ADComponent,
    AreaDetector,
    Component,
    Device,
    EpicsMotor,
    EpicsSignal,
    EpicsSignalRO,
)
from ophyd.areadetector import SimDetectorCam
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from ophyd.areadetector.plugins import HDF5Plugin_V34


class SimDetectorCam_V34(CamMixin_V34, SimDetectorCam):
    ...


class MyHDF5Plugin(FileStoreHDF5IterativeWrite, HDF5Plugin_V34):
    def stage(self):
        self.stage_sigs.move_to_end("capture", last=True)
        super().stage()


class MyDetector(SingleTrigger_V34, AreaDetector):
    cam = ADComponent(SimDetectorCam_V34, "CAM:")
    hdf1 = ADComponent(
        MyHDF5Plugin,
        "HDF1:",
        write_path_template="/out/%Y/%m/%d/",
        # read_path_template="/data/%Y/%m/%d/",  # Where bluesky container mount data
        read_path_template="/home/bar/Projects/tomoscan/data/%Y/%m/%d/",  # Temporary path for local testing
    )


class MyLaser(Device):
    power = Component(EpicsSignalRO, "laser:power")
    pulse_id = Component(EpicsSignalRO, "EPAC-DEV:PULSE:PULSE_ID", name="pulse_id")


#   Legacy laser variables for when laser is not set by pulse-id-gen
#    pulse_id = Component(EpicsSignalRO, "pulse_id")
#    freq = Component(EpicsSignalRO, "freq", kind="config")


# Heavily influenced by _wait_for_value function in epics_pvs.py, does block
def wait_for_value(signal: EpicsSignal, value, poll_time=0.01, timeout=10):
    expiration_time = ttime.time() + timeout
    current_value = signal.get()
    while current_value != value:
        # ttime.sleep(poll_time)
        yield from bps.sleep(poll_time)
        if ttime.time() > expiration_time:
            raise TimeoutError(
                "Timed out waiting for %r to take value %r after %r seconds"
                % (signal, value, timeout)
            )
        current_value = signal.get()


# Custom plan to move motor and then wait for laser pulse to take reading
def pulse_sync(detectors, motor, laser, start, stop, steps):
    step_size = (stop - start) / (steps - 1)

    for det in detectors:
        yield from bps.stage(det)

    yield from bps.open_run()
    for i in range(steps):
        yield from bps.checkpoint()  # allows pausing/rewinding
        yield from mv(motor, start + i * step_size)
        yield from wait_for_value(
            laser.power, 0, poll_time=0.01, timeout=10
        )  # Want to be at 0 initially such that image taken on pulse
        yield from wait_for_value(laser.power, 1, poll_time=0.001, timeout=10)
        yield from bps.trigger_and_read(list(detectors) + [motor] + [laser])
    yield from bps.close_run()

    for det in detectors:
        yield from bps.unstage(det)


# Custom plan to move motor based on detector status
# designed for when detector is being triggered outside of bluesky
def passive_scan(detectors, motor, start, stop, steps, adStatus, pulse_ID):
    step_size = (stop - start) / (steps - 1)

    yield from mv(motor, start)  # Move motor to starting position since may take time

    yield from bps.open_run()

    for det in detectors:
        yield from bps.stage(det)

    for i in range(steps):
        yield from mv(motor, start + i * step_size)
        yield from bps.checkpoint()
        yield from wait_for_value(adStatus, 2, poll_time=0.001, timeout=10)
        yield from bps.trigger_and_read([motor] + [pulse_ID])
        yield from wait_for_value(adStatus, 0, poll_time=0.001, timeout=10)

    for det in detectors:
        yield from bps.unstage(det)

    yield from bps.close_run()


prefix = "ADT:USER1:"
det = MyDetector(prefix, name="det")
det.hdf1.kind = 3  # config | normal
det.hdf1.create_directory.put(-5)

# override default setting from ophyd
det.hdf1.stage_sigs["blocking_callbacks"] = "No"
det.cam.stage_sigs["wait_for_plugins"] = "Yes"

det.hdf1.warmup()

det.cam.stage_sigs["image_mode"] = "Multiple"
det.cam.stage_sigs["acquire_time"] = 0.05
det.cam.stage_sigs["num_images"] = 1
# det.hdf1.stage_sigs["num_capture"] = 0  # capture ALL frames received
# det.hdf1.stage_sigs["compression"] = "LZ4"

# ensure_AD_plugin_primed(det.hdf1, True)


motor1 = EpicsMotor("motorS:axis1", name="motor1")

# laser1 = MyLaser("laser:", name="laser1")
laser1 = MyLaser("", name="laser1")
laser1.wait_for_connection()

adStatus = EpicsSignalRO("ADT:USER1:CAM:DetectorState_RBV", name="adStatus")
pulse_ID = EpicsSignalRO("EPAC-DEV:PULSE:PULSE_ID", name="pulse_ID")

RE = RunEngine()

bec = BestEffortCallback()
# db = Broker.named("temp")  # This creates a temporary database
# db = Broker.named("mongo")  # Connects to MongoDB database
catalog = databroker.catalog["mongo"]
# catalog = databroker.temp().v2

# Send all metadata/data captured to the BestEffortCallback.
RE.subscribe(bec)
# Insert all metadata/data captured into the catalog.
RE.subscribe(catalog.v1.insert)


# Examples of how to run both scans:
# uids = RE(pulse_sync([det], motor1, laser1, -10, 10, 11))
# uids = RE(passive_scan([det], motor1, -10, 10, 11, adStatus , pulse_ID))

# Take a look at the data from the run
# run = catalog.v2[uids[0]]
# ds = run.primary.read()
