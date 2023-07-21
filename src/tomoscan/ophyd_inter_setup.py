# Designed to be used with iocs and simulators all running in docker compose

import time as ttime

import bluesky.plan_stubs as bps
import databroker
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
    SingleTrigger,
)
from ophyd.areadetector import cam
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from ophyd.areadetector.plugins import HDF5Plugin_V34


class MyHDF5Plugin(FileStoreHDF5IterativeWrite, HDF5Plugin_V34):
    ...


class MyDetector(SingleTrigger, AreaDetector):
    cam = ADComponent(cam.AreaDetectorCam, "CAM:")
    hdf1 = ADComponent(
        MyHDF5Plugin,
        "HDF1:",
        write_path_template="/out/%Y/%m/%d/",
        read_path_template="/data/%Y/%m/%d/",  # Ensure this is the path from bluesky/docker container to output
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


RE = RunEngine()

bec = BestEffortCallback()
# db = Broker.named("temp")  # This creates a temporary database
# db = Broker.named("mongo")  # Connects to MongoDB database
catalog = databroker.catalog["mongo"]

# Send all metadata/data captured to the BestEffortCallback.
RE.subscribe(bec)
# Insert all metadata/data captured into the catalog.
RE.subscribe(catalog.v1.insert)


prefix = "ADT:USER1:"
det = MyDetector(prefix, name="det")
det.hdf1.create_directory.put(-5)
det.hdf1.warmup()

det.cam.stage_sigs["image_mode"] = "Single"
det.cam.stage_sigs["acquire_time"] = 0.05

motor1 = EpicsMotor("motorS:axis1", name="motor1")

# laser1 = MyLaser("laser:", name="laser1")
laser1 = MyLaser("", name="laser1")
laser1.wait_for_connection()

adStatus = EpicsSignalRO("ADT:USER1:CAM:DetectorState_RBV", name="adStatus")
pulse_ID = EpicsSignalRO("EPAC-DEV:PULSE:PULSE_ID", name="pulse_ID")


# Examples of how to run both scans:
# RE(pulse_sync([det], motor1, laser1, -10, 10, 11))
# RE(passive_scan([det], motor1, -10, 10, 11, adStatus , pulse_ID))
