import yaml
import argparse
import subprocess
import os


def getChipFromDeviceVersion(device_version:str) -> str:
    chip = "unknown"
    try:
        chip = device_version.split("_")[0]
    except Exception as e:
        print(e)

    return chip

def deviceToPlatform(device_version:str) -> str:
    known_devices = {
        "NRF52840": "nrf52840dk_nrf52840",
    }
    return known_devices.get(getChipFromDeviceVersion(device_version), "unknown")
    
def main(hardware_map_path):
    hardware_map = None
    with open(hardware_map_path) as hw_file:
            hardware_map = yaml.safe_load(hw_file)

    if len(hardware_map) == 0:
        os.remove(hardware_map_path)
        exit(0)

    for device in hardware_map:
        if (device["platform"] == "unknown"):
            out = subprocess.run(["nrfjprog", "--deviceversion", "--snr", int(device["id"])], capture_output=True)
            device_family = out.stdout.decode("utf-8")
            device["platform"] = deviceToPlatform(device_family)
    

    with open(hardware_map_path, "w") as hw_file:
        yaml.dump(hardware_map, hw_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")

    parser.add_argument("hardware_map_path", type=str, help="")
    args = parser.parse_args()

    main(args.hardware_map_path)


