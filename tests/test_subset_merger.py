from fontTools.designspaceLib import DesignSpaceDocument
from gftools import subsetmerger
from gftools.subsetmerger import DonorMasterDescriptor, InputDescriptor
from ufoLib2 import Font


def test_descriptor_compatibility():
    input_ds = DesignSpaceDocument()
    input_ds.addAxisDescriptor(
        name="Weight", tag="wght", minimum=100, maximum=300, default=200
    )
    master = input_ds.addSourceDescriptor(location={"Weight": 100})
    input_descriptor = InputDescriptor(input_ds, master, Font())

    donor_ds_incompat = DesignSpaceDocument()
    donor_ds_incompat.addAxisDescriptor(
        name="Weight", tag="wght", minimum=100, maximum=300, default=200
    )
    donor_ds_incompat.addAxisDescriptor(
        name="Width", tag="wdth", minimum=100, maximum=300, default=200
    )
    master = donor_ds_incompat.addSourceDescriptor(
        # Width is at non-default location
        location={"Weight": 100, "Width": 100}
    )

    assert not subsetmerger.is_compatible(
        DonorMasterDescriptor(donor_ds_incompat, master, Font()),
        input_descriptor,
    )

    # Width is now at default location
    master.location["Width"] = 200
    assert subsetmerger.is_compatible(
        DonorMasterDescriptor(donor_ds_incompat, master, Font()),
        input_descriptor,
    )
