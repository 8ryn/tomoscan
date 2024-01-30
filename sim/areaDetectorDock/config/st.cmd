cd "$(TOP)"

dbLoadDatabase "dbd/ioc.dbd"
ioc_registerRecordDeviceDriver(pdbbase)

# simDetectorConfig(portName, maxSizeX, maxSizeY, dataType, maxBuffers, maxMemory)
simDetectorConfig("SIM.CAM", 1024, 1024, 1, 1000, 0)

# NDFileHDF5Configure(portName, queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr)
NDFileHDF5Configure("SIM.hdf", 16, 0, "SIM.CAM", 0)

# NDPvaConfigure(portName, queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr, pvName, maxBuffers, maxMemory, priority, stackSize)
NDPvaConfigure("SIM.pva", 16, 0, "SIM.CAM", 0, ADT:USER1:Pva1:ARRAY, 0, 0, 0, 0)
startPVAServer

# instantiate Database records for Sim Detector
dbLoadRecords (simDetector.template, "P=ADT:USER1, R=:CAM:, PORT=SIM.CAM, TIMEOUT=1, ADDR=0")
dbLoadRecords (NDFileHDF5.template, "P=ADT:USER1, R=:HDF1:, PORT=SIM.hdf, ADDR=0, NDARRAY_PORT=SIM.CAM, TIMEOUT=1, NDARRAY_ADDR=0, ENABLED=1, SCANRATE=I/O Intr")
dbLoadRecords (NDPva.template, "P=ADT:USER1, R=:Pva1:, PORT=SIM.pva, ADDR=0, TIMEOUT=1, NDARRAY_PORT=SIM.CAM, NDARRAY_ADDR=0, ENABLED=1, SCANRATE=I/O Intr")

# also make Database records for DEVIOCSTATS
#dbLoadRecords(iocAdminSoft.db, "IOC=EXAMPLE")
#dbLoadRecords(iocAdminScanMon.db, "IOC=EXAMPLE")

# start IOC shell
iocInit

# Extra post-init IOC commands
dbpf "ADT:USER1:HDF1:FileTemplate", "%s/%s_%d.h5"

dbpf "ADT:USER1:CAM:AcquirePeriod", "0.2"

dbpf "ADT:USER1:CAM:ImageMode", "Single"

dbpf "ADT:USER1:CAM:Noise", "5"

dbpf "ADT:USER1:CAM:NDAttributesFile", "/epics/ioc/config/detAttributes.xml"
