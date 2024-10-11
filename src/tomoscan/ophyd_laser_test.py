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
    DeviceStatus
)
from ophyd.utils import doc_annotation_forwarder
from ophyd.areadetector import cam
from ophyd.areadetector.filestore_mixins import FileStoreHDF5IterativeWrite
from ophyd.areadetector.plugins import HDF5Plugin_V34

from functools import partial
from threading import Lock


class MyHDF5Plugin(FileStoreHDF5IterativeWrite, HDF5Plugin_V34): ...


class MyDetector(SingleTrigger, AreaDetector):
    cam = ADComponent(cam.AreaDetectorCam, "cam1:")
    hdf1 = ADComponent(
        MyHDF5Plugin,
        "HDF:",
        write_path_template="/home/sfd73252/out/%Y/%m/%d/",
        read_path_template="/home/sfd73252/adOut/%Y/%m/%d/",
    )


class MyLaser(Device):
    pulse_id = Component(EpicsSignalRO, "TA1:PULSE_ID", name="pulse_id", kind="hinted")

class EPACLaser(Device):
    """Interface to EPAC laser control and pulse ID systems

    This will provide various signals associated with the state of the laser,
    but its main use is recording pulse IDs and synchronising data acquisition
    with laser pulses.

    When `trigger()` is called, the status object returned will complete
    immediately after the next laser pulse. The `pulse_id` signal will then
    contain the ID of that pulse. Therefore, any scan using this device as a
    detector will wait for a single laser pulse whenever it attempts to record
    data and it will record the ID of that laser pulse. This can then be used to
    identify which data must be recorded from Kafka.

    Arguments:
     - `pulse_id_delay`: float (keyword-only) - the delay in seconds between the
       pulse ID PV updating and the laser pulse happening

    Keyword arguments for `ophyd.Device` are also accepted.
    """

    pulse_id = Component(
        # Question: how should we be handling the PV names here?
        # AIUI, EPAC has no global prefix. The PVs we'll need to access may be
        # all over the place, so have no common prefix. So it seems like we'll
        # have to use the full names here.
        #
        # However, that makes it difficult to work in an environment that
        # doesn't use exactly the right names. The alternative is more
        # constructor arguments and using ophyd.FormattedComponent
        EpicsSignalRO,
        "PULSE_ID",
        name="pulse_id",
        kind="hinted",
    )

    def __init__(self, *, pulse_id_delay: float = 0.0, prefix: str = "EPAC-DEV:PULSE:",  **kwargs):
        super().__init__(prefix, **kwargs)
        self.__pending_status_list: list[DeviceStatus] = []
        self.__pending_status_lock = Lock()
        self.pulse_id_delay = pulse_id_delay
        self.pulse_id.subscribe(self.__pulse_id_cb, run=False)

    def __pulse_id_cb(self, **kwargs) -> None:
        with self.__pending_status_lock:
            pending_status_list = self.__pending_status_list
            self.__pending_status_list = []
        for s in pending_status_list:
            s.set_finished()

    @doc_annotation_forwarder(Device)
    def trigger(self) -> DeviceStatus:
        status = DeviceStatus(self, timeout=2.0, settle_time=self.pulse_id_delay)
        with self.__pending_status_lock:
            self.__pending_status_list.append(status)

        return status


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


# Custom plan to move motor and then take multiple images
def multi_scan(detectors, motor, laser, start, stop, steps, repeats=1):
    step_size = (stop - start) / (steps - 1)

    for det in detectors:
        yield from bps.stage(det)

    yield from bps.open_run()
    for i in range(steps):
        yield from bps.checkpoint()  # allows pausing/rewinding
        yield from mv(motor, start + i * step_size)
        for j in range(repeats):
            yield from bps.trigger_and_read(list(detectors) + [laser] + [motor])
    yield from bps.close_run()

    for det in detectors:
        yield from bps.unstage(det)
        
def repeating_step(detectors, step, pos_cache, take_reading=None, repeats=1):
    """
    Customised version of the default one_nd_step function which repeats the reading a number of times
    """
    take_reading = bps.trigger_and_read if take_reading is None else take_reading
    motors = step.keys()
    yield from bps.move_per_step(step, pos_cache)
    for i in range(repeats):
        yield from take_reading(list(detectors) + list(motors))


# Custom plan to move motor based on detector status
# designed for when detector is being triggered continuously outside of bluesky
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


#prefix = "TA1:CT_CAM:"
prefix = "TA1:CAM2:"
det = MyDetector(prefix, name="det")
det.hdf1.create_directory.put(-5)

det.hdf1.kind = 3  # config | normal, required to include images in run documents

det.cam.stage_sigs["image_mode"] = "Multiple"
det.cam.stage_sigs["acquire_time"] = 0.01
det.cam.stage_sigs["num_images"] = 1

motor1 = EpicsMotor("TA1:SMC100:m1", name="motor1")

# laser1 = MyLaser("laser:", name="laser1")
#laser1 = MyLaser("", name="laser1")
laser1 = EPACLaser(prefix="TA1:" ,name="laser1")
laser1.wait_for_connection()

#adStatus = EpicsSignalRO("TA1:CT_CAM:cam1:DetectorState_RBV", name="adStatus")
pulse_ID = EpicsSignalRO("TA1:PULSE_ID", name="pulse_ID")

RE = RunEngine()

bec = BestEffortCallback()
catalog = databroker.catalog["mongo"]  # Connects to MongoDB database

# Send all metadata/data captured to the BestEffortCallback.
RE.subscribe(bec)
# Insert all metadata/data captured into the catalog.
RE.subscribe(catalog.v1.insert)


# Example of how to run a scan between 0 and 180 in 5 steps:
# RE(scan([det,laser1], motor1, 0, 180, 5))

# Take a look at the data from the run
# run = catalog.v2[uids[0]]
# ds = run.primary.read()
