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


class MyHDF5Plugin(FileStoreHDF5IterativeWrite, HDF5Plugin_V34): ...


class MyDetector(SingleTrigger, AreaDetector):
    cam = ADComponent(cam.AreaDetectorCam, "cam1:")
    hdf1 = ADComponent(
        MyHDF5Plugin,
        "HDF:",
        write_path_template="/home/brw82791/out/%Y/%m/%d/",
        read_path_template="/home/brw82791/adOut/%Y/%m/%d/",
    )


class MyLaser(Device):
    pulse_id = Component(EpicsSignalRO, "TA1:PULSE_ID", name="pulse_id", kind="hinted")


prefix = "TA1:CT_CAM:"
det = MyDetector(prefix, name="det")
det.hdf1.create_directory.put(-5)

det.hdf1.kind = 3  # config | normal, required to include images in run documents

det.cam.stage_sigs["image_mode"] = "Multiple"
det.cam.stage_sigs["acquire_time"] = 0.005
det.cam.stage_sigs["num_images"] = 1

motor1 = EpicsMotor("TA1:SMC100:m1", name="motor1")

# laser1 = MyLaser("laser:", name="laser1")
laser1 = MyLaser("", name="laser1")
laser1.wait_for_connection()

adStatus = EpicsSignalRO("TA1:CT_CAM:cam1:DetectorState_RBV", name="adStatus")
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
